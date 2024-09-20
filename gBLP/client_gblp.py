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

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--message', default='hello!')
parser.add_argument('--grpchost', default='signaliser.com')
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
                 grpchost="localhost",
                 grpcport=50051,
                 grpckeyport=50052,
                 defaultInterval=5,   # seconds
                 serverEventQueueSize=100000):
        if name is None:
            self.name = self.makeName()
        else:
            self.name = name
        self.grpchost = grpchost
        self.grpcport = grpcport
        self.grpckeyport = grpckeyport
        self.defaultInterval = defaultInterval
        self.serverEventQueueSize = serverEventQueueSize
        self.sessgen = None

    def open(self):
        # Start the event loop in a new thread
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, args=(self.loop,), daemon=True)
        self.thread.start()
        # Run asynchronous initialization in the event loop
        self.run_async(self.async_init())

    def start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def run_async(self, coro):
        """Schedules a coroutine to be run on the event loop."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()  # Waits until the coroutine is done and returns the result

    def makeName(self, length=6):
        """Make a dummy name if none provided."""
        consonants = "bcdfghjklmnpqrstvwxyz"
        vowels = "aeiou"
        word = ''.join(random.choice(consonants if i % 2 == 0 else vowels) 
                       for i in range(length))
        return word

    async def async_init(self):
        await self.connect()
        await self.openSession()

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
        session = await stub.openSession(sessionOptions)
        logger.info(f"Opened {self.name} session: {session}")
        self.stub = stub  # Stub for all the gRPC calls
        self.session = session

    async def closeSession(self):
        closedSession = await self.stub.closeSession(self.session)
        logger.info(f"Closed session: {closedSession}")
        await self.channel.close()

    def close(self):
        self.run_async(self.closeSession())
        print(1)
        # Stop the event loop and thread
        self.loop.call_soon_threadsafe(self.loop.stop())
        print(2)
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
            session=self.session,
            topics=topics,
            fields=fields,
            start=sst,
            end=est
        )
        logger.info(f"Requesting historical data: {hreq}")
        data = await self.stub.historicalDataRequest(hreq)
        return data

    async def sub_session_generator(self):
        session = None
        while True:
            received = yield session  # Wait for the next value to be sent in

    # The subscribe method that uses the async generator
    def subscribe(self, topics, fields, interval):
        if self.sessgen is None:
            self.sessgen = self.sub_session_generator()
            try:
                session = next(self.sessgen)  # start iterator
            except StopIteration:
                pass

        t = [bloomberg_pb2.Topic(name=t, fields=fields, type="TICKER", interval=interval) 
             for t in topics]
        sub = bloomberg_pb2.SubscriptionList(topics=t)
        asyncio.create_task(self.sessgen.asend(sub))  
        return self.run_async(self.async_subscribe(topics))  


    async def async_subscribe(self, topics):
        async for response in self.stub.subscribe(self.sessgen):
            print(f"Received: {response}")




if __name__ == "__main__":
    import IPython
    mycess = Cession(grpchost=args.grpchost,
                     grpcport=args.grpcport,
                     grpckeyport=args.grpckeyport)
    mycess.open()
    hist = mycess.historicalDataRequest(["AAPL US Equity", "IBM US Equity"],
                                        ["PX_LAST", "PX_BID", "PX_ASK", "CUR_MKT_CAP"],
                                        dt.datetime(2014, 1, 1),
                                        dt.datetime(2023, 11, 30))
    print(hist)
    IPython.embed()
    mycess.close()



    #sub = bloomberg_pb2.SubscriptionList(
    #    topics = [bloomberg_pb2.Topic(name="EURUSD Curncy", fields=["LAST_PRICE", "BID", "ASK"],
    #                                  type = "TICKER", interval = 2),
    #              bloomberg_pb2.Topic(name="USDZAR Curncy", fields=["LAST_PRICE", "LAST_TRADE_ACTUAL"],
    #                                  type = "TICKER", interval = 4)])
#
#    print(f"Subscribing to topics: {sub}")
#    #session.subscriptionList.CopyFrom(sub)
#
#    breakpoint()
#
#    async def session_generator(session):
#        while True:
#            yield session  # Send the session object to the server
#
#    stream = stub.subscribe(session_generator(session))
#    async for response in stream:
#        print(f"Received: {response}")
#
