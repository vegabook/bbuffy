# colorscheme blueshift light

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

from bloomberg_pb2_grpc import SessionManagerServicer
from bloomberg_pb2_grpc import add_SessionManagerServicer_to_server
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

from colorama import Fore, Back, Style, init as colinit
colinit()


import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NUMBER_OF_REPLY = 10
CERT_LOCATION_RELATIVE = '../certs/out/'


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
        help="Port that this gRPC will respond to.",
        default="50051")
    # add a boolean make-cert argument
    parser.add_argument(
        "--make-cert",
        dest="make_cert",
        help="Generate a self-signed certificate",
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
        self.dataq = queue.Queue()
        handler = EventHandler(self.dataq)
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
        # start the runner process that listens for data messages
        loop = asyncio.get_event_loop()
        loop.create_task(self.runner())
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
        # create a future so that once all the data for the correlation id is received,
        # by the event handler, the future will be set
        future = asyncio.get_event_loop().create_future()
        self.correlators[corrString] = {"future": future, "request": request}
        self.session.sendRequest(bbgRequest, correlationId=correlationId)

        return HistoricalDataResponse(name = correlationId.value())

    async def _sendInfo(self, command, bbgRequest):
        """ sends back structure information about the request """
        desc = bbgRequest.asElement().elementDefinition()
        strdesc = desc.toString()
        sendmsg = (RESP_INFO, {"request_type": command, "structure": strdesc})
        await dataq.put(sendmsg)


    async def runner(self):
        """ runs continously in session to handle messages from the message queue """
        loop = asyncio.get_event_loop()
        while self.alive:
            # await messages from the dataq in async way
            msg = await loop.run_in_executor(None, self.dataq.get)
            # process the message
            if msg[0] == RESP_REF:
                # whether partial or not, accumulate
                self.partialAccumulator[msg[1]["cid"]].append(msg[1]["data"])
                if not msg[1]["partial"]:
                    # collate data because this is the last message
                    print(self.partialAccumulator[msg[1]["cid"]])
                    self.correlators[msg[1]["cid"]]["future"].set_result(self.partialAccumulator[msg[1]["cid"]])
                    del self.correlators[msg[1]["cid"]]
                    del self.partialAccumulator[msg[1]["cid"]]
        logger.info(f"Session {self.name} is dead so runner is stopping.")


class SessionManager(SessionManagerServicer):

    def __init__(self):
        self.my_number = 0
        self.sessions = dict()
        asyncio.create_task(self.do_stuff_regularly())

    async def do_stuff_regularly(self):
        while True:
            await asyncio.sleep(10)
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
            print(f"{Fore.CYAN}{data}{Style.RESET_ALL}")
            print("---------------------------------------")
            breakpoint()
            json_data = json.dumps(data)
            return HistoricalDataResponse(name="response", json_data=json_data)
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return HistoricalDataResponse(error="Session not found")


async def serve() -> None:

    keyfile = CERT_LOCATION_RELATIVE + 'zombie.key'
    with open(keyfile, 'rb') as f:
        print(f"keyfile: {keyfile}")
        private_key = f.read()

    certfile = CERT_LOCATION_RELATIVE + 'zombie.crt'
    with open(certfile, 'rb') as f:
        print(f"certfile: {certfile}")
        certificate_chain = f.read()

    # Create server credentials
    server_credentials = grpc.ssl_server_credentials(((private_key, certificate_chain),))

    server = grpc.aio.server()
    add_SessionManagerServicer_to_server(SessionManager(), server)
    listen_addr = f"{globalOptions.grpchost}:{globalOptions.grpcport}"
    server.add_secure_port(listen_addr, server_credentials) # secure uses the cert
    #server.add_insecure_port(listen_addr) # insecure
    logging.info("Starting server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if globalOptions.make_cert:
        print("not implemented")
    else:
        asyncio.run(serve())
