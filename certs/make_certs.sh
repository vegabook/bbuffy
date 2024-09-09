#!/bin/sh
default_host="localhost"
host=${1:-$default_host}
rm -f ./out/*
echo "creating certificate authority..."
certstrap init --common-name "zombieCA"

echo "done. creating server certificate...$host"
echo $host
certstrap request-cert --common-name "server" -domain $host
echo "done. signing server certificate..."
certstrap sign server --CA "zombieCA" 

echo "done. creating client certificate..."
echo $host
certstrap request-cert --common-name "client" 
echo "done. signing client certificate..."
certstrap sign client --CA "zombieCA" 


