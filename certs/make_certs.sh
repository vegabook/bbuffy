#!/bin/sh
default_host="localhost"
host=${1:-$default_host}
rm -f ./out/*
echo "creating certificate authority..."
certstrap init --common-name "zombieCA"
echo "done. creating certificate...$host"
certstrap request-cert --common-name "zombie" -domain "$host"
echo "done. signing certificate..."
certstrap sign zombie --CA "zombieCA"


