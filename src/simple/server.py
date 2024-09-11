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
parser.add_argument('--grpchost', default='signaliser.com')
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
SERVER_CERT_LOCATION_RELATIVE = '../../certs/out/server'
CLIENT_CERT_LOCATION_RELATIVE = '../../certs/out/client'

# full grpc instructions that actually work: https://chatgpt.com/share/e/a92ad120-9ffc-49e8-b77d-cac7fe0df943


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
        if not args.insecure:
            client_key = context.auth_context()["x509_pem_cert"]
            print(f"{Fore.WHITE}{Style.BRIGHT}Client certificate: {Fore.BLUE}{client_key}{Style.RESET_ALL}")
        for i in range(self.my_number, self.my_number + NUMBER_OF_REPLY):
            yield HelloReply(message=f"Hello number {i}, {request.name}!")
        self.my_number += NUMBER_OF_REPLY


    async def sum(self, request: SumRequest, context: grpc.aio.ServicerContext) -> SumResponse:
        logging.info("Serving sum request %s", request)
        return SumResponse(result=request.num1 + request.num2)


async def serve() -> None:

    # Load server certificate, private key, and client's CA certificate
    with open(f"{SERVER_CERT_LOCATION_RELATIVE}/fullchain.pem", 'rb') as f:
        server_certificate = f.read()

    with open(f"{SERVER_CERT_LOCATION_RELATIVE}/privkey.pem", 'rb') as f:
        server_private_key = f.read()

    # Load the client's CA certificate (custom or trusted CA)
    with open(f"{CLIENT_CERT_LOCATION_RELATIVE}/ca.pem", 'rb') as f:
        client_ca_certificate = f.read()

    # Create SSL credentials for the server (with client certificate verification)
    server_credentials = grpc.ssl_server_credentials(
        [(server_private_key, server_certificate)],
        root_certificates=client_ca_certificate,
        require_client_auth=True
    )


    server = grpc.aio.server()
    add_simpleServiceServicer_to_server(Greeter(), server)
    listen_addr = f"{args.grpchost}:{args.grpcport}"

    if args.insecure:
        server_credentials = grpc.ssl_server_credentials(((server_private_key, server_certificate),))
        server.add_insecure_port(listen_addr) 
    else:
        server_credentials = grpc.ssl_server_credentials(
            [(server_private_key, server_certificate)],
            root_certificates=client_ca_certificate,
            require_client_auth=True
        )
        server.add_secure_port(listen_addr, server_credentials) 

    logging.info("Starting server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
