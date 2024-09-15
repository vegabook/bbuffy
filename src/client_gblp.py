# colorscheme iceberg dark

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
parser.add_argument('--grpchost', default='localhost')
parser.add_argument('--grpcport', default='50051')
parser.add_argument('--grpckeyport', default='50052')
from pathlib import Path
import datetime as dt
import time
from google.protobuf.timestamp_pb2 import Timestamp as protoTimestamp
from util.certMaker import get_conf_dir

args = parser.parse_args()


async def run() -> None:

    ichannel = grpc.aio.insecure_channel(f"{args.grpchost}:{args.grpckeyport}") # insecure for keys
    # now look for keys
    if not ((get_conf_dir() / "client_certificate.pem").exists() and \
            (get_conf_dir() / "client_private_key.pem").exists() and \
            (get_conf_dir() / "ca_certificate.pem").exists()):
        yn = input("Keys not found. Ask server? y/n <enter>: ")
        if yn.lower() == "y":


            
    channel = grpc.aio.insecure_channel(f"{args.grpchost}:{args.grpcport}") # insecure for keys
    with open(get_conf_dir() / "client_certificate.pem", "rb") as f:
        client_cert = f.read()
    with open(get_conf_dir() / "client_private_key.pem", "rb") as f:
        client_key = f.read()
    # Load CA certificate to verify the server
    with open(get_conf_dir() / "ca_certificate.pem", "rb") as f:
        ca_cert = f.read()
    # Create SSL credentials for the client
    client_credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert,
        private_key=client_key,
        certificate_chain=client_cert,
    )
    channel = grpc.aio.secure_channel(hostandport, client_credentials)

    hostandport = f"{args.grpchost}:{args.grpcport}"

    #async with grpc.aio.insecure_channel(hostandport) as channel:

    async with channel as chan:
        stub = bloomberg_pb2_grpc.SessionManagerStub(chan)

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
            name="session1", interval=1, maxEventQueueSize=100000
        )
        print(f"Opening session: {sessionOptions}")
        session = await stub.openSession(sessionOptions)
        print(f"Opened session: {session}")
        sst = protoTimestamp()
        sst.FromDatetime(dt.datetime(2019, 1, 1))
        est = protoTimestamp()
        est.FromDatetime(dt.datetime(2024, 1, 2))
        hreq = bloomberg_pb2.HistoricalDataRequest(
            session=session,
            topics=["AAPL US Equity", "IBM US Equity"],
            fields=["PX_LAST", "PX_BID", "PX_ASK"],
            start=sst,
            end=est
        )
        print(f"Requesting historical data: {hreq}")
        hdata = await stub.historicalDataRequest(hreq)
        print(hdata)
        time.sleep(30)
        closedSession = await stub.closeSession(session)
        print(f"Closed session: {closedSession}")


if __name__ == "__main__":
    logging.basicConfig()
    asyncio.run(run())
