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
from pathlib import Path
import datetime as dt
import time
from google.protobuf.timestamp_pb2 import Timestamp as protoTimestamp

args = parser.parse_args()

CERT_LOCATION_RELATIVE = Path('../certs/out').resolve()
print(CERT_LOCATION_RELATIVE)

async def run() -> None:
    certfile = Path(CERT_LOCATION_RELATIVE, 'zombie.crt')
    with open(certfile, 'rb') as f:
        trusted_certs = f.read()

    # Create client credentials
    credentials = grpc.ssl_channel_credentials(root_certificates=trusted_certs)

    hostport = f"{args.grpchost}:{args.grpcport}"

    async with grpc.aio.secure_channel(hostport, credentials) as channel:
        stub = bloomberg_pb2_grpc.SessionManagerStub(channel)

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
