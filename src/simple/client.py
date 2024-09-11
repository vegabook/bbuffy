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
parser.add_argument('--certstrap', action='store_true', default=False)
from pathlib import Path
import datetime as dt
import time
from google.protobuf.timestamp_pb2 import Timestamp as protoTimestamp

args = parser.parse_args()

CLIENT_CERT_LOCATION_RELATIVE = '../../certs/out/client'

async def run() -> None:
    if args.certstrap:
        CLIENT_CERTS = '../../certs/out'
        # Load certifi"s CA bundle to verify the server"s certificate
        with open(f"{CLIENT_CERTS}/zombieCA.crt", "rb") as f:
            ca_certificate = f.read()
    else:
        CLIENT_CERTS = CLIENT_CERT_LOCATION_RELATIVE
        with open(certifi.where(), "rb") as f:
            ca_certificate = f.read()

    with open(f"{CLIENT_CERTS}/client.crt", "rb") as f:
        client_certificate = f.read()
    with open(f"{CLIENT_CERTS}/client.key", "rb") as f:
        client_private_key = f.read()

    # Create client credentials
    client_credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_certificate,
        private_key=client_private_key,
        certificate_chain=client_certificate
    )

    hostandport = f"{args.grpchost}:{args.grpcport}"

    if args.insecure:
        async with grpc.aio.insecure_channel(hostandport) as channel:
            stub = simple_pb2_grpc.simpleServiceStub(channel)
            # Read from an async generator
            async for response in stub.sayHello(
                simple_pb2.HelloRequest(name=args.message)
            ):
                print(
                    "Greeter client received from async generator: "
                    + response.message
                )

            # Direct read from the stub
            hello_stream = stub.sayHello(
                simple_pb2.HelloRequest(name=str(args.message))
            )
            while True:
                response = await hello_stream.read()
                if response == grpc.aio.EOF:
                    break
                print(
                    "Greeter client received from direct read: " + response.message
                    )
    else:
        print("Secure connection")
        async with grpc.aio.secure_channel(hostandport, client_credentials) as channel:
            stub = simple_pb2_grpc.simpleServiceStub(channel)
            # Read from an async generator
            async for response in stub.sayHello(
                simple_pb2.HelloRequest(name=args.message)
            ):
                print(
                    "Greeter client received from async generator: "
                    + response.message
                )

            # Direct read from the stub
            hello_stream = stub.sayHello(
                simple_pb2.HelloRequest(name=str(args.message))
            )
            while True:
                response = await hello_stream.read()
                if response == grpc.aio.EOF:
                    break
                print(
                    "Greeter client received from direct read: " + response.message
                    )



if __name__ == "__main__":
    logging.basicConfig()
    asyncio.run(run())
