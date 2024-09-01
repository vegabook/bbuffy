# colorscheme aiseered dark

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

import blpapi

import grpc
from bloomberg_pb2 import HelloReply
from bloomberg_pb2 import HelloRequest
from bloomberg_pb2 import SumRequest
from bloomberg_pb2 import SumResponse 
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

    options = parser.parse_args()
    options.options.append(f"interval=1")
    return options

globalOptions = parseCmdLine()

class SessionOptions:
    def __init__(self, 
                 name: str, 
                 interval: int,
                 maxEventQueueSize: int):
        self.name = name
        self.interval = 0
        self.maxEventQueueSize = 0

# -------------------- session and event handlers ----------------------

class EventHandler(object):

    def __init__(self): 
        pass

    def getTimeStamp(self):
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def processResponseEvent(self, event, partial):
        for msg in event:
            cid = msg.correlationId().value()
            logger.info((f"Received response to request {msg.getRequestId()} "
                        f"partial {partial}"))
            sendmsg = (RESP_REF, {"cid": cid, "partial": partial, "data": msg.toPy()})
            dataq.put(sendmsg)

    def processSubscriptionStatus(self, event):
        timeStamp = self.getTimeStamp()
        for msg in event:
            pymsg = msg.toPy()
            topic = msg.correlationId().value()
            match msg.messageType():
                case blpapi.Names.SUBSCRIPTION_DATA:
                    sendmsg = (RESP_SUB, {"timestamp": timeStamp, "topic": topic, "prices": self.searchMsg(msg, DEFAULT_FIELDS)})
                case blpapi.Names.SUBSCRIPTION_FAILURE:
                    sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
                case blpapi.Names.SUBSCRIPTION_TERMINATED:
                    correl = msg.correlationId().value()
                    subs.remove(correl)
                    print(f"!!!!!!! sub terminated for {correl}")
                    stopevent.set()
                    sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
                case blpapi.Names.SUBSCRIPTION_STARTED:
                    correl = msg.correlationId().value()
                    subs.add(correl)
                    sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
                case blpapi.Names.SUBSCRIPTION_FAILURE:
                    sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
                case _:
                    sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))

            dataq.put(sendmsg)

    def searchMsg(self, msg, fields):
        return [{"field": field, "value": msg[field]} 
                for field in fields if msg.hasElement(field)]

    def makeBarMessage(self, msg, msgtype, topic, interval):
        msgdict = {"msgtype": msgtype, "topic": topic, "interval": interval}
        for f, m in {"open": "OPEN", 
                     "high": "HIGH", 
                     "low": "LOW", 
                     "close": "CLOSE", 
                     "volume": "VOLUME", 
                     "numticks": "NUMBER_OF_TICKS",
                     "timestamp": "DATE_TIME"}.items():
            if msg.hasElement(m):
                msgdict[f] = msg[m]
            else:
                msgdict[f] = None

        return msgdict

    def processSubscriptionDataEvent(self, event):
        """ 
        process subsription data message and put on data queue 
        """
        timestamp = self.getTimeStamp()
        timestampdt = dt.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        for msg in event:
            fulltopic = msg.correlationId().value()
            topic = fulltopic.split("/")[-1] # just ticker
            msgtype = msg.messageType()
            # bars --->
            if msgtype in (blpapi.Name("MarketBarUpdate"),
                           blpapi.Name("MarketBarStart"),
                           blpapi.Name("MarketBarEnd"),
                           blpapi.Name("MarketBarIntervalEnd")):
                sendmsg = (RESP_BAR, self.makeBarMessage(msg, str(msgtype), 
                                                          topic, interval = 1))
                dataq.put(sendmsg)

            # subscription --->
            elif msgtype == blpapi.Name("MarketDataEvents"):
                # mktdata event type
                sendmsg = (RESP_SUB, 
                       {"timestamp": timestampdt, 
                       "topic": topic,
                       "prices": self.searchMsg(msg, DEFAULT_FIELDS)})
                dataq.put(sendmsg)

            # something else --->
            else:
                logger.warning(f"Unknown message type {msgtype}")
                breakpoint()

    def processMiscEvents(self, event):
        for msg in event:
            sendmsg = (RESP_STATUS, str(msg.messageType()))
            dataq.put(sendmsg) 

    def processEvent(self, event, _session):
        """ event processing selector """
        try:
            match event.eventType():
                case blpapi.Event.PARTIAL_RESPONSE:
                    self.processResponseEvent(event, True)
                case blpapi.Event.RESPONSE:
                    self.processResponseEvent(event, False)     
                case blpapi.Event.REQUEST_STATUS:
                    for msg in event:
                        if msg.messageType == blpapi.Names.REQUEST_FAILURE:
                            reason=msg.getElement("reason")
                            print(f"Request failed: {reason}")
                            done = True
                        done = True
                case blpapi.Event.SUBSCRIPTION_DATA:
                    self.processSubscriptionDataEvent(event)
                case blpapi.Event.SUBSCRIPTION_STATUS:
                    self.processSubscriptionStatus(event)
                case _:
                    self.processMiscEvents(event)
        except blpapi.Exception as e:
            print(f"Failed to process event {event}: {e}")
        return False


class Session(object):
    def __init__(self, options: SessionOptions):
        self.name = options.name
        self.interval = options.interval
        self.maxEventQueueSize = options.maxEventQueueSize
        self.servicesOpen = dict()
        self.subscriptionList = dict()
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

        sessionOptions = createSessionOptions(globalOptions) 
        sessionOptions.setMaxEventQueueSize(self.maxEventQueueSize)
        handler = EventHandler()
        self.eventDispatcher = blpapi.EventDispatcher(numDispatcherThreads=3) 
        self.eventDdispatcher.start()
        self.session = blpapi.Session(sessionOptions, 
                                      eventHandler=handler.processEvent,
                                      eventDispatcher=self.eventDispatcher)

    async def servicesAvail(self):
        """ return available services """
        return {**self.subServicesAvail, **self.refservicesAvail}

    async def openService(self, servString: str):
        """ open a service from the sub and ref services available """
        if not servString in self.servicesAvail.values():
            logger.error(f"Service {servString} not available")
            return
        if not self.refservices["session"].openService(servString):
            logger.error(f"Failed to open service {servString}")
            return False
        else:
            self.servicesOpen[servString] = True
            return True

        

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
        self, request: HelloRequest, context: grpc.aio.ServicerContext
    ) -> HelloReply:
        logging.info("Serving sayHello request %s", request)
        for i in range(self.my_number, self.my_number + NUMBER_OF_REPLY):
            yield HelloReply(message=f"Hello number {i}, {request.name}!")
        self.my_number += NUMBER_OF_REPLY

    async def sum(self, request: SumRequest, context: grpc.aio.ServicerContext) -> SumResponse:
        logging.info("Serving sum request %s", request)
        return SumResponse(result=request.num1 + request.num2)

    async def openSession(self, request: SessionOptions, context: grpc.aio.ServicerContext) -> Session:
        logging.info("Serving openSession request %s", request)
        options = SessionOptions(name=request.name, 
                                 interval=request.interval, 
                                 maxEventQueueSize=request.maxEventQueueSize)
        if not request.name in self.sessions:
            self.sessions[request.name] = Session(options=options)
        return self.sessions[request.name]



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
    breakpoint()
    listen_addr = f"{globalOptions.grpchost}:{globalOptions.grpcport}"
    server.add_secure_port(listen_addr, server_credentials) # secure uses the cert
    #server.add_insecure_port(listen_addr) # insecure
    logging.info("Starting server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
