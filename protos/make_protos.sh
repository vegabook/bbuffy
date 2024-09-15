#!/bin/sh
python -m grpc_tools.protoc -I. --python_out=../gBLP --grpc_python_out=../gBLP bloomberg.proto
