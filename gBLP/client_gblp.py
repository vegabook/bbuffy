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
import threading
import grpc
import bloomberg_pb2
import bloomberg_pb2_grpc
import random
from pathlib import Path
import datetime as dt
import time
from google.protobuf.timestamp_pb2 import Timestamp as protoTimestamp
from util.certMaker import get_conf_dir
import getpass
import logging
from colorama import Fore, Back, Style, init as colinit; colinit()
from collections import deque, defaultdict
import IPython
from queue import Queue

from constants import (RESP_INFO, RESP_REF, RESP_SUB, RESP_BAR,
        RESP_STATUS, RESP_ERROR, RESP_ACK, DEFAULT_FIELDS)

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--message', default='hello!')
parser.add_argument('--grpchost', default='localhost')
parser.add_argument('--grpcport', default='50051')
parser.add_argument('--grpckeyport', default='50052')
parser.add_argument('--delcerts', action='store_true', default=False)
args = parser.parse_args()
username = getpass.getuser()

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class Cession:
    def __init__(self,
                 name=None,
                 handler = None,
                 grpchost="localhost",
                 grpcport=50051,
                 grpckeyport=50052,
                 defaultInterval=5,   # seconds
                 serverEventQueueSize=100000,
                 maxdDequeSize = 10000):       # max size of deques each holding one topic
        if name is None:
            self.name = self.makeName(6, 3)
        else:
            self.name = name
        self.grpchost = grpchost
        self.grpcport = grpcport
        self.grpckeyport = grpckeyport
        self.defaultInterval = defaultInterval
        self.serverEventQueueSize = serverEventQueueSize
        self.alive = False
        self.handler = handler
        if self.handler is None:   # create a deque
            self.subsdata = defaultdict(lambda: deque(maxlen = maxdDequeSize))
            self.statusLog = []


    def makeName(self, alphaLength, digitLength):
        """Make a dummy name if none provided."""
        consonants = "bcdfghjklmnpqrstvwxyz"
        vowels = "aeiou"
        digits = "0123456789"
        word = ''.join(random.choice(consonants if i % 2 == 0 else vowels) 
                       for i in range(alphaLength)) + \
                       ''.join(random.choice(digits) for i in range(digitLength))
        return word

    def open(self):
        # Start the event loop in a new thread
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, args=(self.loop,), daemon=False)
        self.thread.start()
        # Run asynchronous initialization in the event loop
        self.run_async(self.async_init())
        self.run_async_nowait(self.subscriptionsStream())
        logger.info("Subscription stream started.")
        self.alive = True

    def start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def run_async(self, coro):
        """Schedules a coroutine to be run on the event loop."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()  # Waits until the coroutine is done and returns the result

    async def async_init(self):
        await self.connect()
        await self.openSession()

    def run_async_nowait(self, coro):
        """Schedules a coroutine to be run on the event loop without waiting."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def makeCerts(self):
        """Make certificates if they do not exist."""
        confdir = get_conf_dir()
        ihostandport = f"{self.grpchost}:{self.grpckeyport}"
        ichannel = grpc.aio.insecure_channel(ihostandport)  # Insecure for keys
        idkey = input("Certificates not found. Input ID key: ")
        logger.info("Waiting for response from server...")
        async with ichannel as chan:
            istub = bloomberg_pb2_grpc.KeyManagerStub(chan)
            try:
                iresponse = await istub.requestKey(
                    bloomberg_pb2.KeyRequestId(id=str(idkey) + "@" + username)
                )
            except grpc.aio.AioRpcError as e:
                logger.info(f"Error: {e}")
                return
            # Make the confdir if it does not exist already
            confdir.mkdir(parents=True, exist_ok=True)
            with open(confdir / "client_certificate.pem", "wb") as f:
                f.write(iresponse.cert)
            with open(confdir / "client_private_key.pem", "wb") as f:
                f.write(iresponse.key)
            with open(confdir / "ca_certificate.pem", "wb") as f:
                f.write(iresponse.cacert)
        logger.info("Certificates written.")

    def delCerts(self):
        """Delete certificates."""
        confdir = get_conf_dir()
        for f in ["client_certificate.pem", "client_private_key.pem", "ca_certificate.pem"]:
            if (confdir / f).exists():
                (confdir / f).unlink()
        logger.info("Certificates deleted.")

    async def connect(self):
        """Connect to the gRPC server."""
        confdir = get_conf_dir()
        # Now look for keys, request them and write them if not found
        if not ((confdir / "client_certificate.pem").exists() and
                (confdir / "client_private_key.pem").exists() and
                (confdir / "ca_certificate.pem").exists()):
            await self.makeCerts()

        # Load client certificate and private key
        with open(confdir / "client_certificate.pem", "rb") as f:
            cert = f.read()
        with open(confdir / "client_private_key.pem", "rb") as f:
            key = f.read()
        # Load CA certificate to verify the server
        with open(confdir / "ca_certificate.pem", "rb") as f:
            cacert = f.read()

        # Create SSL credentials for the client
        client_credentials = grpc.ssl_channel_credentials(
            root_certificates=cacert,
            private_key=key,
            certificate_chain=cert,
        )
        hostandport = f"{self.grpchost}:{self.grpcport}"
        logger.info(f"Connecting to {hostandport}...")
        self.channel = grpc.aio.secure_channel(hostandport, client_credentials)

    async def openSession(self):
        stub = bloomberg_pb2_grpc.SessionsManagerStub(self.channel)
        sessionOptions = bloomberg_pb2.SessionOptions(
            name=self.name,
            interval=self.defaultInterval,
            maxEventQueueSize=self.serverEventQueueSize
        )
        gsession = await stub.openSession(sessionOptions)
        logger.info(f"Opened {self.name} session: {gsession}")
        self.stub = stub  # Stub for all the gRPC calls
        gsession.subscriptionList.CopyFrom(bloomberg_pb2.SubscriptionList())
        self.gsession = gsession

    async def closeSession(self):
        closedSession = await self.stub.closeSession(self.gsession)
        logger.info(f"Closed session: {closedSession}")
        await self.channel.close()

    def close(self):
        self.run_async(self.closeSession())
        # Stop the event loop and thread
        self.loop.call_soon_threadsafe(self.loop.stop())
        self.thread.join()

    def historicalDataRequest(self, 
                              topics, 
                              fields = ["LAST_PRICE"], 
                              start = dt.datetime.today() - dt.timedelta(days=365),
                              end = dt.datetime.today()):
        return self.run_async(self.async_historicalDataRequest(topics, fields, start, end))

    async def async_historicalDataRequest(self, topics, fields, start, end):
        sst = protoTimestamp()
        sst.FromDatetime(start)
        est = protoTimestamp()
        est.FromDatetime(end)
        hreq = bloomberg_pb2.HistoricalDataRequest(
            session=self.gsession,
            topics=topics,
            fields=fields,
            start=sst,
            end=est
        )
        logger.info(f"Requesting historical data: {hreq}")
        data = await self.stub.historicalDataRequest(hreq)
        return data


    def subscribe(self, topics, 
                  fields=["LAST_PRICE"],
                  type="TICKER",
                  interval=2):
        """ synchronous subscribe method """
        return self.run_async(
            self.async_subscribe(topics, fields, type, interval)
        )

    async def async_subscribe(self, topics, 
                              fields=["LAST_PRICE"],
                              type="TICKER",
                              interval=2):
        sub = bloomberg_pb2.SubscriptionList(
            topics=[
                bloomberg_pb2.Topic(
                    name=x, 
                    fields=fields, 
                    type=type, 
                    interval=interval
                ) for x in topics
            ]
        )
        self.gsession.subscriptionList.CopyFrom(sub)
        # Perform the asynchronous subscribe call
        self.gsession = await self.stub.subscribe(self.gsession)
        logger.info(f"Subscribed to topics: {topics}")


    def unsubscribe(self, topics):
        pass

    async def subscriptionsStream(self, handler = None):
        async for response in self.stub.subscriptionStream(self.gsession):
            try:
                if self.handler:
                    self.run_async(self.handler.handle(response))
                else:
                    if response.msgtype in (RESP_SUB, RESP_BAR):
                        self.subsdata[response.topic].append(response)
                    elif response.msgtype in (RESP_STATUS, RESP_ERROR):
                        self.statusLog.append(response)
                    else:
                        pass
            except Exception as e:
                print(f"Error: {e}")


    async def async_sessionInfo(self):
        info = await self.stub.sessionInfo(self.gsession)
        logger.info(f"Session info: {info}")
        return info
    
    def sessionInfo(self):
        return self.run_async(self.async_sessionInfo()) 




class Handler():
    """ Optional handler class to handle subscription responses """

    def __init__(self, follow_handler = None):
        # this will store by topic 
        self.follow_handler = follow_handler # can chain more handlers here
    
    async def handle(self, response):
        # this function must be present in any handler
        try:
            if response.msgtype in (RESP_SUB, RESP_BAR):
                print(Fore.GREEN, f"Received: {response}", Style.RESET_ALL)
            else:
                print(Fore.MAGENTA, Style.BRIGHT, f"Received: {response}", Style.RESET_ALL)
            if self.follow_handler:
                self.follow_handler.handle(response)
        except Exception as e:
            print(f"Error: {e}")


def syncmain():

    print_handler = Handler()

    cess = Cession(
        grpchost=args.grpchost,
        grpcport=args.grpcport,
        grpckeyport=args.grpckeyport
    )
    #handler=print_handler # TODO NOT WORKING
    cess.open()

    # Request historical data
    hist = cess.historicalDataRequest(
        ["RNO FP Equity", "MSFT US Equity"],
        ["PX_LAST", "CUR_MKT_CAP"],
        dt.datetime(2023, 11, 28),
        dt.datetime(2023, 11, 30)
    )
    print(hist)

    hist = cess.historicalDataRequest(
        ["AAPL US Equity", "GOOg US Equity"],
        ["PX_BID"],
        dt.datetime(2023, 11, 28),
        dt.datetime(2023, 11, 30)
    )
    print(hist)

    hist = cess.historicalDataRequest(
        ["R186 Govt"],
        ["PX_ASK"],
        dt.datetime(2023, 11, 28),
        dt.datetime(2023, 11, 30)
    )
    print(hist)

    # Enter IPython shell
    IPython.embed()

    # After exiting IPython, close the session
    cess.close()

if __name__ == "__main__":
    # TODO move certs into another class
    if args.delcerts:
        mycess = Cession()
        mycess.delCerts()
    else:
        syncmain()



