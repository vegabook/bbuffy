# colorscheme blue dark

# Copyright 2021 gRPC authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import string
import random
from collections import defaultdict
import json
import datetime as dt
import sys # for hard exit
import threading
import signal
from functools import partial
import queue
import blpapi

import grpc
from bloomberg_pb2 import Session
from bloomberg_pb2 import SessionOptions
from bloomberg_pb2 import HistoricalDataRequest 
from bloomberg_pb2 import KeyRequestId, KeyResponse
from bloomberg_pb2 import HistoricalDataResponse
from bloomberg_pb2 import SubscriptionList
from bloomberg_pb2 import SubscriptionDataResponse
from bloomberg_pb2 import Topic

from bloomberg_pb2_grpc import SessionsManagerServicer, KeyManagerServicer
from bloomberg_pb2_grpc import add_SessionsManagerServicer_to_server, \
    add_KeyManagerServicer_to_server

from responseParsers import (
    buildHistoricalDataResponse, 
    buildSubscriptionDataResponse
)

from google.protobuf.struct_pb2 import Struct

from argparse import ArgumentParser, RawTextHelpFormatter

from pathlib import Path

from util.SubscriptionOptions import \
    addSubscriptionOptions, \
    setSubscriptionSessionOptions
from util.ConnectionAndAuthOptions import \
    addConnectionAndAuthOptions, \
    createSessionOptions

from util.EventHandler import EventHandler

from constants import (RESP_INFO, RESP_REF, RESP_SUB, RESP_BAR,
        RESP_STATUS, RESP_ERROR, RESP_ACK, DEFAULT_FIELDS)

from util.certMaker import get_conf_dir, make_client_certs, make_all_certs
from cryptography.hazmat.primitives import serialization, hashes

from rich.console import Console; console = Console()
from rich.traceback import install; install()


done = asyncio.Event() # signal to stop the subscription stream loop

# logging

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NUMBER_OF_REPLY = 10

# ----------------- thread creation tracking ----------------------
def trace_function(frame, event, arg):
    """Trace function that will be called for every line of code in every thread."""
    if event == 'call':
        console.print(f"[bold blue]Calling function: {frame.f_code.co_name} in {threading.current_thread().name}")
    elif event == 'line':
        console.print(f"[bold green]Line {frame.f_lineno} in {frame.f_code.co_name} in {threading.current_thread().name}")
    elif event == 'return':
        console.print(f"[bold red]Returning from {frame.f_code.co_name} in {threading.current_thread().name}")
    return trace_function  # Return itself to continue tracing

# Set this trace function to be used for all new threads
threading.settrace(trace_function)
# ----------------- util functions ----------------------

def serialize_datetime(obj): 
    if isinstance(obj, dt.datetime) or isinstance(obj, dt.date):
        return obj.isoformat() 
    raise TypeError("Type not serializable") 

# ----------------- parse the command line and session options ---------------

def parseCmdLine():
    """Parse command line arguments"""
    parser=ArgumentParser(formatter_class=RawTextHelpFormatter,
                            description="Asynchronous subscription with event handler")
    addConnectionAndAuthOptions(parser)
    addSubscriptionOptions(parser)
    parser.add_argument(
        "--grpchost",
        dest="grpchost",
        help="Hostname that this gRPC will respond to.",
        type=str)
    parser.add_argument(
        "--grpcport",
        dest="grpcport",
        type=str,
        help="Bloomberg session grpc port",
        default="50051")
    parser.add_argument(
        "--grpckeyport",
        dest="grpckeyport",
        type=str,
        help="Key request grpc port (for client certificates)",
        default="50052")
    # add a boolean make-cert argument
    parser.add_argument(
        "--gencerts",
        dest="gencerts",
        help="Generate a self-signed certificate",
        action="store_true",
        default=False)
    parser.add_argument(
        "--delcerts",
        dest="delcerts",
        help="Delete all certificates",
        action="store_true",
        default=False)
    options = parser.parse_args()
    options.options.append(f"interval=1")
    return options

globalOptions = parseCmdLine()


# ----------------- keys manager for mTLS ----------------------

class KeyManager(KeyManagerServicer):
    # responds on an insecure port with client certificates
    # but only if authorised by the server. 

    def __init__(self):
        pass

    async def input_timeout(self, prompt, timeout):
        # Run the blocking input() function in a separate thread
        try:
            return await asyncio.wait_for(asyncio.to_thread(input, prompt), 
                                          timeout=timeout)
        except asyncio.TimeoutError:
            return None 

    async def requestKey(self, 
                         request: KeyRequestId, 
                         context: grpc.aio.ServicerContext) -> KeyResponse:
        logging.info("Serving keyRequest request %s", request)
        accept = await self.input_timeout((f"Received request from {context.peer()}"
                        f" with id {request.id}. Accept? (y/n) "), 5)
        if accept is None:
            context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "Request timed out")
        if accept.lower() == "y":
            key, cert, cacert = make_client_certs(globalOptions.grpchost, get_conf_dir())
            bcacert = cacert.public_bytes(serialization.Encoding.PEM)
            logger.info(f"Key request granted for {request.id} and {context.peer()}")
            return KeyResponse(key=key, cert=cert, cacert=bcacert)
        else:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Request denied")


async def serveSessions(grpcServer) -> None:

    listenAddr = f"{globalOptions.grpchost}:{globalOptions.grpcport}"
    sessionsManager = SessionsManager()
    add_SessionsManagerServicer_to_server(sessionsManager, grpcServer)

    # first check if the certs are there
    confdir = get_conf_dir()
    if not ((confdir / "server_certificate.pem").exists() and \
            (confdir / "server_private_key.pem").exists() and \
            (confdir / "ca_certificate.pem").exists()):
        yn = input("Certificates not found. Make them? (y/n) ")
        if yn.lower() == "y":
            make_all_certs(str(globalOptions.grpchost), confdir)
        else:
            print("Exiting.")


    # Load server's certificate and private key
    with open(confdir / "server_certificate.pem", "rb") as f:
        serverCert = f.read()
    with open(confdir / "server_private_key.pem", "rb") as f:
        serverKey = f.read()
    # Load CA certificate to verify clients
    with open(confdir / "ca_certificate.pem", "rb") as f:
        CAcert = f.read()


    serverCredentials = grpc.ssl_server_credentials(
        [(serverKey, serverCert)],
        root_certificates=CAcert,
        require_client_auth=True,  # Require clients to provide valid certificates
    )
    grpcServer.add_secure_port(listenAddr, serverCredentials) 

    await grpcServer.start()
    logging.info(f"Starting session server on {listenAddr}")
    await grpcServer.wait_for_termination()
    await sessionsManager.closeAllSessions()
    logging.info("Sessions server stopped.")
    #raise # propagate


async def keySession(keyServer) -> None:

    keyListenAddr = f"{globalOptions.grpchost}:{globalOptions.grpckeyport}"
    add_KeyManagerServicer_to_server(KeyManager(), keyServer)
    keyServer.add_insecure_port(keyListenAddr) # this listens without credentials

    await keyServer.start()
    logging.info(f"Starting key server on {keyListenAddr}")
    await keyServer.wait_for_termination()
    logging.info("Key server stopped.")



# -------------------- individual session handler ----------------------

class SessionRunner(object):
    def __init__(self, options: SessionOptions):
        self.name = options.name
        self.interval = options.interval # subscription interval
        self.maxEventQueueSize = options.maxEventQueueSize
        self.servicesOpen = dict()
        self.correlators = dict()
        self.partialAccumulator = defaultdict(list)
        self.alive = False
        self.session = None # must SessionRunner.open() one first
        self.subscriptionList = SubscriptionList() # grpc subscription list not bloomberg
        self.servicesAvail = {"Subscribe": "//blp/mktdata",
                              "UnSubscribe": "//blp/mktdata",
                              "BarSubscribe": "//blp/mktbar",
                              "BarUnSubscribe": "//blp/mktbar",
                              "TaSubscribe": "//blp/tasvc",
                              "HistoricalDataRequest": "//blp/refdata",
                              "IntradayBarRequest": "//blp/refdata",
                              "IntradayTickRequest": "//blp/refdata",
                              "ReferenceDataRequest": "//blp/refdata",
                              "instrumentListRequest": "//blp/instruments", # terminal SECF
                              "curveListRequest": "//blp/instruments",      # terminal CRVF
                              "govtListRequest": "//blp/instruments",
                              "FieldListRequest": "//blp/apiflds",
                              "FieldSearchRequest": "//blp/apiflds",
                              "FieldInfoRequest": "//blp/apiflds",
                              "CategorizedFieldSearchRequest": "//blp/apiflds",
                              "studyRequest": "//blp/tasvc",
                              "SnapshotRequest": "//blp/mktlist"}
        self.subq = queue.Queue()
        self.numDispatcherThreads = 1 # if > 1 then threaded dispatchers will be created



    def _getService(self, serviceReq: str) -> bool:
        """ open a service from the sub and ref services available """
        if not self.session:
            error = "Session not open"
            logger.error(error)
            return (False, error)
        if not self.servicesOpen.get(serviceReq):
            if not self.session.openService(self.servicesAvail[serviceReq]):
                error = "Failed to open service HistoricalDataRequest"
                logger.error(error)
                return(False, error)
            else:
                self.servicesOpen[serviceReq] = self.servicesAvail[serviceReq]
                logger.info("Opened service HistoricalDataRequest")
        logger.info(f"Service {serviceReq} is open via {self.servicesOpen[serviceReq]}")
        return (True, self.servicesOpen[serviceReq])


    def _createEmptyRequest(self, serviceReq: str) -> blpapi.Request:
        success, service = self._getService(serviceReq)
        if not success:
            return (False, service)
        request = self.session.getService(service).createRequest(serviceReq)
        return (True, request)


    def grpcRepresentation(self) -> Session:
        """ return the session representation in gRPC terms """
        return Session(name=self.name, 
                       services=self.servicesAvail.keys(), 
                       alive=self.alive, 
                       subscriptionList=self.subscriptionList)

    async def open(self):
        """ open the session and associated services """
        # setup the correct options
        sessionOptions = createSessionOptions(globalOptions) 
        sessionOptions.setMaxEventQueueSize(self.maxEventQueueSize)
        sessionOptions.setSessionName(self.name)
        handler = EventHandler(parent = self)
        if self.numDispatcherThreads > 1:
            self.eventDispatcher = blpapi.EventDispatcher(numDispatcherThreads=self.numDispatcherThreads) 
            self.eventDispatcher.start()
            self.session = blpapi.Session(sessionOptions, 
                                          eventHandler=handler.processEvent,
                                          eventDispatcher=self.eventDispatcher)
        else:
            self.session = blpapi.Session(sessionOptions, 
                                          eventHandler=handler.processEvent)
        if not self.session.start():
            logger.error("Failed to start session.")
            self.alive = False
        else:
            logger.info("Session started.")
            self.alive = True
        # return all the details over gRPC
        grpcrep = self.grpcRepresentation()
        logger.debug(f"Session opened {grpcrep}")
        return grpcrep

    async def close(self):
        """ close the session """
        self.session.stop()
        if self.numDispatcherThreads > 1:
            self.eventDispatcher.stop()
        self.alive = False
        logger.info(f"Session {self.name} closed")
        return self.grpcRepresentation()

    async def historicalDataRequest(self, request: HistoricalDataRequest) -> list:
        """ request historical data """
        logger.info(f"Requesting historical data {request}")
        success, bbgRequest = self._createEmptyRequest("HistoricalDataRequest")
        if not success:
            return None
        logger.info(f"setting securities {request.topics}")
        dtstart = request.start.ToDatetime().strftime("%Y%m%d")
        dtend = request.end.ToDatetime().strftime("%Y%m%d")
        requestDict = {"securities": request.topics,
                       "fields": request.fields,
                       "startDate": dtstart,
                       "endDate": dtend}
        bbgRequest.fromPy(requestDict)
        # create a random 32-character string as the correlationId
        corrString = ''.join(random.choices(string.ascii_uppercase + string.digits, k=32))
        correlationId = blpapi.CorrelationId(corrString)
        # queue for this request, with correlator so event handler can match it
        q = queue.Queue()
        self.correlators[corrString] = {"request": request, "queue": q}
        self.session.sendRequest(bbgRequest, correlationId=correlationId)
        # TODO what happens if bad request?
        loop = asyncio.get_event_loop()
        messageList = []
        while True:
            msg = await loop.run_in_executor(None, q.get)
            messageList.append(msg[1]["data"])
            if not msg[1]["partial"]:
                break
        # remove self correlators
        del self.correlators[corrString]
        return messageList

    # ------------ subscriptions -------------------

    async def subscribe(self, gsession: Session):
        """ subscribe to a list of topics """
        
        # make sure the service is open
        success, service = self._getService("Subscribe")
        if not success:
            return self.grpcRepresentation()
        # create the subscription list
        ntl = [x.name for x in gsession.subscriptionList.topics] # existing topics
        etl= [x.name for x in self.subscriptionList.topics] # new topics
        # find the difference
        difftl = list(set(ntl) - set(etl)) # new topics to subscribe to
        if not difftl:
            logger.info("No new topics to subscribe to")
            return self.grpcRepresentation()
        logger.info(f"Subscribing to {difftl}")
        bbgsublist = blpapi.SubscriptionList()
        for topic in gsession.subscriptionList.topics:
            if topic.name in difftl:
                topicTypeName = Topic.topicType.Name(topic.type) # SEDOL1/TICKER/CUSIP etc
                substring = f"{service}/{topicTypeName}/{topic.name}"
                if topic.fields == []:
                    fields = ["LAST_PRICE"]
                if topic.interval is None:
                    intervalstr = "interval=2"
                else:
                    intervalstr = f"interval={int(topic.interval)}"
                cid = blpapi.CorrelationId(topic.name)
                bbgsublist.add(substring, topic.fields, intervalstr, cid)
                self.subscriptionList.topics.append(topic)
        # extend the subscription list
        self.session.subscribe(bbgsublist)
        return self.grpcRepresentation()


    async def unsubscribe(self, gsession: Session):
        print(f"unsubcribing TODO {gsession}")


    async def _sendInfo(self, command, bbgRequest):
        """ sends back structure information about the request TODO THIS IS JUST COPY PASTE FROM BLXX"""
        desc = bbgRequest.asElement().elementDefinition()
        strdesc = desc.toString()
        sendmsg = (RESP_INFO, {"request_type": command, "structure": strdesc})
        await dataq.put(sendmsg)


# ----------------- multiple sessions are managed here ----------------------


class SessionsManager(SessionsManagerServicer):
    # implements all the gRPC methods for the session manager
    # and communicates with the SessionRunner(s)

    def __init__(self):
        self.sessions = dict() # the sessions
        self.maxSessions = 7

    async def openSession(self, options: SessionOptions, 
                          context: grpc.aio.ServicerContext) -> Session:
        if len(self.sessions) >= self.maxSessions:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Too many sessions")
        print("opening session")
        auth_context = context.auth_context()
        print(f"auth_context: {auth_context}")
        if not options.name in self.sessions:
            logging.info("Serving openSession options %s", options)
            session = SessionRunner(options=options)
            grpcRepresentation = await session.open()
            self.sessions[options.name] = session
            return grpcRepresentation
        else:
            logging.warning(f"Session {options.name} already exists")
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "Session already exists")

    async def closeSession(self, gsession: Session, context: grpc.aio.ServicerContext) -> Session:
        logging.info("Serving closeSession session %s", gsession)
        session = self.sessions.get(gsession.name)
        if session:
            grpcRepresentation = await self.sessions[gsession.name].close()
            del self.sessions[gsession.name]
            return grpcRepresentation
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")

    async def historicalDataRequest(self, 
                                    request: HistoricalDataRequest, 
                                    context: grpc.aio.ServicerContext) -> HistoricalDataResponse:
        session = self.sessions.get(request.session.name)
        if session:
            data = await session.historicalDataRequest(request)
            if data:    
                result = buildHistoricalDataResponse(data)
                return result 
            else:
                context.abort(grpc.StatusCode.NOT_FOUND, "Data not found")
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")


    async def subscribe(self, gsession: Session, context: grpc.aio.ServicerContext) -> Session:
        session = self.sessions.get(gsession.name)
        if session:
            if not session.alive:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not open")
            await session.subscribe(gsession)
            return session.grpcRepresentation()
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")


    async def unsubscribe(self, gsession: Session, context: grpc.aio.ServicerContext) -> Session:
        session = self.sessions.get(gsession.name)
        if session:
            if not session.alive:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not open")
            await session.unsubscribe(gsession)
            return session.grpcRepresentation()
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")


    async def subscriptionStream(self, gsession: Session, context: grpc.aio.ServicerContext): 
        session = self.sessions.get(gsession.name)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")
        if not session.alive:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session not open")

        loop = asyncio.get_event_loop()
        while not done.is_set():
            # Get messages from the session's queue
            # async get from the queue
            try:
                msg = await loop.run_in_executor(None, session.subq.get)  
            except asyncio.TimeoutError:
                logger.error("Timeout while waiting for message from the queue")
                continue  # Handle timeout by continuing or breaking, depending on your logic
            response = buildSubscriptionDataResponse(msg)
            yield response
        logger.info("Subscription stream closed")


    async def sessionInfo(self, gsession, context):
        session = self.sessions.get(gsession.name)
        if not session:
            context.abort(grpc.StatusCode.NOT_FOUND, "Session not found")
        else:
            return session.grpcRepresentation()

    async def closeAllSessions(self):
        snames = list(self.sessions.keys())
        for sname in snames:
            session = self.sessions[sname]
            logging.info(f"Asking server {sname} to close")
            await session.close()
            del self.sessions[sname]


async def main():
    grpcServer = grpc.aio.server()
    keyServer = grpc.aio.server()
    session_task = asyncio.create_task(serveSessions(grpcServer))
    key_task = asyncio.create_task(keySession(keyServer))
    await asyncio.sleep(10)
    logger.info("Done is being set")
    done.set()
    logger.info("Waiting for done...")
    try:
        await done.wait()
        logger.info("done waitined for. Stopping gRPC servers...")
        await grpcServer.stop(grace=3)
        logger.info("gRPC server stopped.") 
        await keyServer.stop(grace=3)
        logger.info("Key server stopped.")
        logger.info("Gathering asyncio gRPC task wrappers...")
        await asyncio.gather(session_task, key_task)
        logger.info("All tasks stopped. Exiting.")
    except Exception as e:
        logger.info(f"Exception in main: {e}")
    finally:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        print("tasks", tasks)
        for task in tasks:
            logger.info(f"Force cancelling task {task}")
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    # now print all running threads
    for th in threading.enumerate():
        console.print(f"[bold magenta]Thread {th.name} is still running[/bold magenta]")





if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if globalOptions.gencerts:
        confdir = get_conf_dir()
        make_all_certs(str(globalOptions.grpchost), confdir)
    elif globalOptions.delcerts:
        confdir = get_conf_dir()
        for f in confdir.glob("*.pem"):
            f.unlink()
        print("Deleted all certificates. Run --gencerts to make new ones.")
    else:
        asyncio.run(main())
