#!/bin/sh
python -m grpc_tools.protoc -I. --python_out=../src --grpc_python_out=../src gBLP.proto
