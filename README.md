# gBLP

![background](images/finvids.gif#gh-dark-mode-only)
![background](images/finvids.gif#gh-light-mode-only)

gRPC for the Bloomberg API V3

$${\color{red}LEGAL NOTICE
\color{orange} \newline
This \space software \space is \space provided \space "as \space is," \space without \space warranty \space of \space any \space kind, \space\newline express \space or \space implied. \space 
The \space developer \space of \space this \space software \space assumes \space no \space responsibility \space or \space liability \space\newline for \space any \space use \space of \space the \space software \space by \space any \space party. \space 
It \space is \space the \space sole \space responsibility \space of \space the \space user \space to \space ensure \space that \space their \space\newline use \space of \space this \space software \space complies \space with \space all \space applicable \space laws, \space regulations, \space and \space the \space terms \space and \space conditions \space of \space the \space Bloomberg \space API. \space 
By \space using \space this \space software, \space you \space acknowledge \space and \space agree \space that \space the \space developer \space\newline shall \space not \space be \space held \space liable \space for \space any \space consequences \space arising \space from \space the \space use \space of \space this \space software, \space including \space but \space not \space limited \space to, \space any \space violations \space of \space the \space Bloomberg \space API \space terms.}
$$


$${\color{red}Welcome \space \color{lightblue}To \space \color{orange}Stackoverflow}$$

## Status
_This is an alpha work in progress_

## Installation
_todo_
`pip install gBLP` or
`nix develop`

## Aims 
To allow users of any gRPC programming language to use the Bloomberg V3 API. 
Supports:
* Historica APIs (`//refdata`).
* Streaming APIs (`//subdata`).
* Full control over session options. 
* Protocol buffer `.proto` files usable by any programming language that has a gRPC implementation.

## FAQ
#### Why not REST?
Rest is not typed, Rest doesn't do streaming, BLPAPI's "correlationID" concept maps easily to function calls. 
#### Is this legal?
For Terminal users: yes long as you use both gRPC server (this software), and client, on the same machine. 

## Dependencies
This is a python package and depends on Python 3.10+

## Clients
_todo_
* Elixir
* Swift
* Javascript
* Roll your own
    * Use the proto files with the protocul buffers compile `protoc` (see [here](https://grpc.io/docs/protoc-installation/)) to generate function stubs for your programming language.
    * Note that you will likely have to install a `protoc` plugin. Here fore example is the [plugin for Elixir](https://github.com/brexhq/protobuf-elixir). Here is Elixir's [gRPC library](https://github.com/elixir-grpc/grpc)
 

