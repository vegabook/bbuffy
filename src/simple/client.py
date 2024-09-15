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
import certifi

import grpc

import simple_pb2
import simple_pb2_grpc

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--message', default='hello!')
parser.add_argument('--grpchost', default='signaliser.com')
parser.add_argument('--grpcport', default='50051')
parser.add_argument('--insecure', action='store_true', default=False)
from pathlib import Path
import datetime as dt
import time
from google.protobuf.timestamp_pb2 import Timestamp as protoTimestamp

args = parser.parse_args()

CERT_LOCATION_RELATIVE = "../../certs/out/pycerts/"

async def run() -> None:

    hostandport = f"{args.grpchost}:{args.grpcport}"

    if args.insecure:
        channel = grpc.aio.insecure_channel(hostandport)
    else:
        with open(CERT_LOCATION_RELATIVE+"client_certificate.pem", "rb") as f:
            client_cert = f.read()
        with open(CERT_LOCATION_RELATIVE+"client_private_key.pem", "rb") as f:
            client_key = f.read()
        # Load CA certificate to verify the server
        with open(CERT_LOCATION_RELATIVE+"ca_certificate.pem", "rb") as f:
            ca_cert = f.read()
        # Create SSL credentials for the client
        client_credentials = grpc.ssl_channel_credentials(
            root_certificates=ca_cert,
            private_key=client_key,
            certificate_chain=client_cert,
        )
        channel = grpc.aio.secure_channel(hostandport, client_credentials)
        breakpoint()

    async with channel as chan:
        stub = simple_pb2_grpc.simpleServiceStub(chan)
        # Read from an async generator
        async for response in stub.sayHello( simple_pb2.HelloRequest(name=args.message)):
            print("Greeter client received from async generator: " + response.message)
        # Direct read from the stub
        hello_stream = stub.sayHello(
            simple_pb2.HelloRequest(name=str(args.message))
        )
        while True:
            response = await hello_stream.read()
            if response == grpc.aio.EOF:
                break
            print("Greeter client received from direct read: " + response.message)


if __name__ == "__main__":
    logging.basicConfig()
    asyncio.run(run())
