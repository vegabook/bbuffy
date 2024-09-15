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

import queue
import blpapi

import grpc
from bloomberg_pb2 import HelloReply
from bloomberg_pb2 import HelloRequest
from bloomberg_pb2 import SumRequest
from bloomberg_pb2 import SumResponse 
from bloomberg_pb2 import Session
from bloomberg_pb2 import SessionOptions
from bloomberg_pb2 import HistoricalDataRequest 
from bloomberg_pb2 import HistoricalDataResponse
from bloomberg_pb2 import KeyResponse

from bloomberg_pb2_grpc import SessionManagerServicer, KeyManagerServicer
from bloomberg_pb2_grpc import add_SessionManagerServicer_to_server, add_KeyManagerServicer_to_server

from google.protobuf import struct_pb2

from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path

from util.SubscriptionOptions import \
    addSubscriptionOptions, \
    setSubscriptionSessionOptions
from util.ConnectionAndAuthOptions import \
    addConnectionAndAuthOptions, \
    createSessionOptions
from util.EventHandler import EventHandler, RESP_INFO, RESP_REF, RESP_SUB, \
    RESP_BAR, RESP_STATUS, RESP_ERROR, RESP_ACK
from util.certMaker import get_conf_dir, make_client_certs


from colorama import Fore, Back, Style, init as colinit
colinit()


import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NUMBER_OF_REPLY = 10

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
        type=str,
        default="localhost")
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
        "--make-cert",
        dest="make_cert",
        help="Generate a self-signed certificate",
        action="store_true",
        default=False)
    parser.add_argument(
        "--insecure", 
        action="store_true", 
        default=False)
    options = parser.parse_args()
    options.options.append(f"interval=1")
    return options

globalOptions = parseCmdLine()


# -------------------- session handler ----------------------

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
        self.subscriptionList = blpapi.SubscriptionList()
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


    def _getService(self, serviceReq: str) -> bool:
        """ open a service from the sub and ref services available """
        if not self.session:
            error = "Session not open"
            logger.error(error)
            return HistoricalDataResponse(error=error)
        if not self.servicesOpen.get(serviceReq):
            if not self.session.openService(self.servicesAvail[serviceReq]):
                error = "Failed to open service HistoricalDataRequest"
                logger.error(error)
                return HistoricalDataResponse(error=error)
            else:
                self.servicesOpen[serviceReq] = self.servicesAvail[serviceReq]
                logger.info("Opened service HistoricalDataRequest")
        logger.info(f"Service {serviceReq} is open via {self.servicesOpen[serviceReq]}")
        return self.servicesOpen[serviceReq]


    def _createEmptyRequest(self, serviceReq: str) -> blpapi.Request:
        service = self._getService(serviceReq)
        request = self.session.getService(service).createRequest(serviceReq)
        return request


    def grpcRepresentation(self) -> Session:
        """ return the session representation in gRPC terms """
        return Session(name=self.name, 
                       services=self.servicesAvail.keys(), 
                       alive=self.alive)
                       # dummy subscription list TODO this should be real

    async def open(self):
        """ open the session and associated services """
        # setup the correct options
        sessionOptions = createSessionOptions(globalOptions) 
        sessionOptions.setMaxEventQueueSize(self.maxEventQueueSize)
        sessionOptions.setSessionName(self.name)
        # mulithreaded dispather. not strictly needed
        self.eventDispatcher = blpapi.EventDispatcher(numDispatcherThreads=3) # threaded dispatcher
        self.eventDispatcher.start()
        # queue for our event handler to return messages back to this class
        handler = EventHandler(parent = self)
        # now actually open the session
        self.session = blpapi.Session(sessionOptions, 
                                      eventHandler=handler.processEvent,
                                      eventDispatcher=self.eventDispatcher)
        if not self.session.start():
            logger.error("Failed to start session.")
            self.alive = False
        else:
            logger.info("Session started.")
            self.alive = True
        # return all the details over gRPC
        return self.grpcRepresentation()

    async def close(self):
        """ close the session """
        self.session.stop()
        self.eventDispatcher.stop()
        self.alive = False
        return self.grpcRepresentation()

    async def historicalDataRequest(self, request: HistoricalDataRequest) -> HistoricalDataResponse:
        """ request historical data """
        logger.info(f"Requesting historical data {request}")
        bbgRequest = self._createEmptyRequest("HistoricalDataRequest")
        #self._sendInfo("HistoricalDataRequest", bbgRequest)
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
        #future = asyncio.get_event_loop().create_future()
        # queue for this request
        q = queue.Queue()
        self.correlators[corrString] = {"request": request, "queue": q}
        self.session.sendRequest(bbgRequest, correlationId=correlationId)
        # now wait for all the messages from our request to be received.
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

    async def _sendInfo(self, command, bbgRequest):
        """ sends back structure information about the request """
        desc = bbgRequest.asElement().elementDefinition()
        strdesc = desc.toString()
        sendmsg = (RESP_INFO, {"request_type": command, "structure": strdesc})
        await dataq.put(sendmsg)




class SessionManager(SessionManagerServicer):
    # implements all the gRPC methods for the session manager
    # and communicates with the SessionRunner(s)

    def __init__(self):
        self.my_number = 0
        self.sessions = dict()
        asyncio.create_task(self.do_stuff_regularly())

    async def do_stuff_regularly(self):
        while True:
            await asyncio.sleep(1)
            self.my_number -= 1
            print(f"my_number: {self.my_number}")

    async def sayHello(
        self, request: HelloRequest, context: grpc.aio.ServicerContext) -> HelloReply:
        logging.info("Serving sayHello request %s", request)
        for i in range(self.my_number, self.my_number + NUMBER_OF_REPLY):
            yield HelloReply(message=f"Hello number {i}, {request.name}!")
        self.my_number += NUMBER_OF_REPLY

    async def sum(self, request: SumRequest, context: grpc.aio.ServicerContext) -> SumResponse:
        logging.info("Serving sum request %s", request)
        return SumResponse(result=request.num1 + request.num2)

    async def openSession(self, options: SessionOptions, context: grpc.aio.ServicerContext) -> Session:
        print("opening session")
        auth_context = context.auth_context()
        print(f"auth_context: {auth_context}")
        breakpoint()
        if not options.name in self.sessions:
            logging.info("Serving openSession options %s", options)
            session = SessionRunner(options=options)
            grpcRepresentation = await session.open()
            self.sessions[options.name] = session
            return grpcRepresentation
        else:
            logging.error(f"Session {options.name} already exists")
            context.set_code(grpc.StatusCode.ALREADY_EXISTS)
            return self.sessions[options.name].grpcRepresentation()

    async def closeSession(self, session: Session, context: grpc.aio.ServicerContext) -> Session:
        logging.info("Serving closeSession session %s", session)
        if session.name in self.sessions:
            grpcRepresentation = await self.sessions[session.name].close()
            del self.sessions[session.name]
            return grpcRepresentation
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return session

    async def historicalDataRequest(self, 
                                    request: HistoricalDataRequest, 
                                    context: grpc.aio.ServicerContext) -> HistoricalDataResponse:
        session = self.sessions.get(request.session.name)
        if session:
            data = await session.historicalDataRequest(request)
            breakpoint()
            json_data = struct_pb2.Struct()
            json_data.update({"data": data})
            return HistoricalDataResponse(name = "", json_data = json_data)
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return HistoricalDataResponse(error="Session not found")


class KeyManager(KeyManagerServicer):
    # responds on an insecure port with client certificates
    # but only if authorised.  

    def __init__(self):
        pass

    async def keyRequest(self, request, context: grpc.aio.ServicerContext) -> KeyResponse:
        # TODO here you gotta ask if you want to grant the request
        logging.info("Serving keyRequest request %s", request)
        key, cert = make_client_certs(globalOptions.grpchost, get_conf_dir())
        return KeyResponse(key=key, cert=cert)


async def serveSession() -> None:

    listenAddr = f"{globalOptions.grpchost}:{globalOptions.grpcport}"
    sessionServer = grpc.aio.server()
    add_SessionManagerServicer_to_server(SessionManager(), sessionServer)

    # Load server's certificate and private key
    with open(get_conf_dir() / "server_certificate.pem", "rb") as f:
        serverCert = f.read()
    with open(get_conf_dir() / "server_private_key.pem", "rb") as f:
        serverKey = f.read()
    # Load CA certificate to verify clients
    with open(get_conf_dir() / "ca_certificate.pem", "rb") as f:
        CAcert = f.read()

    serverCredentials = grpc.ssl_server_credentials(
        [(serverKey, serverCert)],
        root_certificates=CAcert,
        require_client_auth=True,  # Require clients to provide valid certificates
    )
    sessionServer.add_secure_port(listenAddr, serverCredentials) 
    logging.info(f"Starting session server on {listenAddr}")
    await sessionServer.start()
    await sessionServer.wait_for_termination()


async def keySession() -> None:

    keyListenAddr = f"{globalOptions.grpchost}:{globalOptions.grpckeyport}"
    keyServer = grpc.aio.server()
    add_KeyManagerServicer_to_server(KeyManager(), keyServer)
    keyServer.add_insecure_port(keyListenAddr) # this listens without credentials
    logging.info(f"Starting key server on {keyListenAddr}")
    await keyServer.start()
    await keyServer.wait_for_termination()

async def main():
    await asyncio.gather(serveSession(), keySession())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if globalOptions.make_cert:
        print("not implemented")
    else:
        asyncio.run(main())
