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

import grpc
import bloomberg_pb2
import bloomberg_pb2_grpc

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--message', default='hello!')
parser.add_argument('--grpchost', default='signaliser.com')
parser.add_argument('--grpcport', default='50051')
parser.add_argument('--grpckeyport', default='50052')
parser.add_argument('--delcerts', action='store_true', default=False)
from pathlib import Path
import datetime as dt
import time
from google.protobuf.timestamp_pb2 import Timestamp as protoTimestamp
from util.certMaker import get_conf_dir
import getpass

args = parser.parse_args()
username = getpass.getuser()


async def run() -> None:
    
    confdir = get_conf_dir()
    ihostandport = f"{args.grpchost}:{args.grpckeyport}"
    ichannel = grpc.aio.insecure_channel(ihostandport) # insecure for keys
    # now look for keys, request them and write them if not found
    if not ((confdir / "client_certificate.pem").exists() and \
            (confdir / "client_private_key.pem").exists() and \
            (confdir / "ca_certificate.pem").exists()):
        idkey = input("Certificates not found. Input ID key: ")
        print("waiting for response from server...")
        async with ichannel as chan:
            istub = bloomberg_pb2_grpc.KeyManagerStub(chan)
            try:
                iresponse = await istub.\
                        requestKey(bloomberg_pb2\
                        .KeyRequestId(id=str(idkey) +"@" + username))
            except grpc.aio.AioRpcError as e:
                print(f"Error: {e}")
                return
            # make the confdir if it does not exist already
            confdir.mkdir(parents=True, exist_ok=True)
            with open(confdir / "client_certificate.pem", "wb") as f:
                f.write(iresponse.cert)
            with open(confdir / "client_private_key.pem", "wb") as f:
                f.write(iresponse.key)
            with open(confdir / "ca_certificate.pem", "wb") as f:
                f.write(iresponse.cacert)
        print("Certificates written.")

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
    hostandport = f"{args.grpchost}:{args.grpcport}"
    channel = grpc.aio.secure_channel(hostandport, client_credentials)

    async with channel as chan:
        stub = bloomberg_pb2_grpc.SessionsManagerStub(chan)

        # Read from an async generator
        async for response in stub.sayHello(
            bloomberg_pb2.HelloRequest(name=args.message)
        ):
            print(
                "Greeter client received from async generator: "
                + response.message
            )

        # Direct read from the stub
        hello_stream = stub.sayHello(
            bloomberg_pb2.HelloRequest(name=str(args.message))
        )
        while True:
            response = await hello_stream.read()
            if response == grpc.aio.EOF:
                break
            print(
                "Greeter client received from direct read: " + response.message
            )

        sessionOptions = bloomberg_pb2.SessionOptions(
            name=username, interval=1, maxEventQueueSize=100000
        )
        print(f"Opening session: {sessionOptions}")
        session = await stub.openSession(sessionOptions)
        print(f"Opened session: {session}")
        sst = protoTimestamp()
        sst.FromDatetime(dt.datetime(2014, 1, 1))
        est = protoTimestamp()
        est.FromDatetime(dt.datetime(2023, 11, 30))
        hreq = bloomberg_pb2.HistoricalDataRequest(
            session=session,
            topics=["AAPL US Equity", "IBM US Equity"],
            fields=["PX_LAST", "PX_BID", "PX_ASK", "CUR_MKT_CAP"],
            start=sst,
            end=est
        )
        print(f"Requesting historical data: {hreq}")
        hdata = await stub.historicalDataRequest(hreq)
        print(hdata)

        sub = bloomberg_pb2.SubscriptionList(
            topics = [bloomberg_pb2.Topic(name="EURUSD Curncy", fields=["LAST_PRICE", "BID", "ASK"],
                                          type = "TICKER", interval = 2),
                      bloomberg_pb2.Topic(name="USDZAR Curncy", fields=["LAST_PRICE", "LAST_TRADE_ACTUAL"],
                                          type = "TICKER", interval = 4)])

        print(f"Subscribing to topics: {sub}")
        session.subscriptionList.CopyFrom(sub)

        async def session_generator(session):
            yield session  # Send the session object to the server

        stream = stub.subscribe(session_generator(session))
        async for response in stream:
            print(f"Received: {response}")




        closedSession = await stub.closeSession(session)
        print(f"Closed session: {closedSession}")


if __name__ == "__main__":
    logging.basicConfig()
    if args.delcerts:
        confdir = get_conf_dir()
        for f in confdir.glob("*.pem"):
            f.unlink()
        print("Deleted certs.")
    else:
        asyncio.run(run())

