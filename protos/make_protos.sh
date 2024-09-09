#!/bin/sh
python -m grpc_tools.protoc -I. --python_out=../src --grpc_python_out=../src bloomberg.proto
python -m grpc_tools.protoc -I. --python_out=../src/simple --grpc_python_out=../src/simple simple.proto
