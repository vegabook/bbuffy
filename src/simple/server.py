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
from simple_pb2 import HelloReply
from simple_pb2 import HelloRequest
from simple_pb2 import SumRequest
from simple_pb2 import SumResponse 

from simple_pb2_grpc import simpleServiceServicer 
from simple_pb2_grpc import add_simpleServiceServicer_to_server

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--grpchost', default='localhost')
parser.add_argument('--grpcport', default='50051')
# add insecure argument
parser.add_argument('--insecure', action='store_true', default=False)
args = parser.parse_args()

from pathlib import Path

from colorama import Fore, Back, Style, init as colinit
colinit()


import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NUMBER_OF_REPLY = 10
CERT_LOCATION_RELATIVE = '../../certs/out/'



class Greeter(simpleServiceServicer):

    def __init__(self):
        self.my_number = 0
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



async def serve() -> None:

    keyfile = CERT_LOCATION_RELATIVE + 'server.key'
    with open(keyfile, 'rb') as f:
        print(f"keyfile: {keyfile}")
        server_key = f.read()

    certfile = CERT_LOCATION_RELATIVE + 'server.crt'
    with open(certfile, 'rb') as f:
        print(f"certfile: {certfile}")
        server_cert = f.read()

    CAfile = CERT_LOCATION_RELATIVE + 'zombieCA.crt'
    with open(CAfile, 'rb') as f:
        print(f"CAfile: {CAfile}")
        ca_cert = f.read()

    server = grpc.aio.server()
    add_simpleServiceServicer_to_server(Greeter(), server)
    listen_addr = f"{args.grpchost}:{args.grpcport}"

    if args.insecure:
        server_credentials = grpc.ssl_server_credentials(((server_key, server_cert),))
        server.add_insecure_port(listen_addr) 
    else:
        server_credentials = grpc.ssl_server_credentials(((server_key, server_cert),), 
                                                         root_certificates=ca_cert, 
                                                         require_client_auth=True)
        server.add_secure_port(listen_addr, server_credentials) 

    logging.info("Starting server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
