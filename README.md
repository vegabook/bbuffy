# gBLP - Bloomberg V3 API gRPC Server

![background](images/finvids.gif#gh-dark-mode-only)
![background](images/finvids.gif#gh-light-mode-only)


$$\textcolor{JungleGreen}{\rule{120cm}{0.5mm}}$$
### Legal Notice
This software is provided "as is," without warranty of any kind, express or implied. The developer of this software assumes no responsibility or liability for any use of the software by any party. It is the sole responsibility of the user to ensure that their use of this software complies with all applicable laws, regulations, and the terms and conditions of the Bloomberg API. By using this software, you acknowledge and agree that the developer shall not be held liable for any consequences arising from the use of this software, including but not limited to, any violations of the Bloomberg API terms.

$$\textcolor{JungleGreen}{\rule{120cm}{0.5mm}}$$


## Description
Bloomberg provides native APIs for Python, Java, C#, and C++. This project aims to provide a Python-based gRPC server that can be used by any gRPC-capable programming language to access the Bloomberg V3 API. 
Supports:
* Historica APIs (`//refdata`).
* Streaming APIs (`//mktdata`). Subscribe to data, Excel-style, with push updates.  
* Full control over session options. 
* Protocol buffer `.proto` files usable by any programming language that has a gRPC implementation.

## Status
_This is an alpha work in progress_

## Installation
_todo_
`pip install gBLP` or
`nix develop`


## FAQ
#### Why not REST?
Rest is not typed, Rest doesn't do streaming, BLPAPI's "correlationID" concept used in the Bloomberg API maps naturally to function calls. 
#### Why not Websockets?
Websockets are asynchronous and are not a natural fit for request <-> response patterns, and do not map well to the "correlationID" concepts used in the Bloomberg API.
#### Can I use this if I don't have a Bloomberg terminal?
[No](https://stackoverflow.com/a/74503768/122792).



## Dependencies
This is the server component of the gRPC client <-> server pairing. It is a python package and depends on Python 3.10+

## Clients
_todo_
* Elixir
* Swift
* Javascript
* Roll your own
    * Use the proto files with the protocul buffers compile `protoc` (see [here](https://grpc.io/docs/protoc-installation/)) to generate function stubs for your programming language.
    * Note that you will likely have to install a `protoc` plugin. Here fore example is the [plugin for Elixir](https://github.com/brexhq/protobuf-elixir). Here is Elixir's [gRPC library](https://github.com/elixir-grpc/grpc)

## Licence
GNU AGPL

Please also see the [licence](https://github.com/vegabook/gBLP/blob/main/src/bbg_copyright.txt) for the Bloomberg API code contained in this package. 

 

