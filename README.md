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
* Bloomberg Terminal API.
* Historica APIs (`//refdata`) for ticks, bars, and daily closes. 
* Streaming APIs (`//mktdata`, `//mktbar` services). Subscribe to data, Excel-style, with push updates.  
* Most common session options. 
* Protocol buffer `.proto` files usable by any programming language that has a gRPC implementation.
Does not currently support:
* Bloomberg's Bpipe product, which requires the authentication subsystem to be implemented.


## Status
_This is an alpha work in progress_


## Installation
_todo_
`pip install gBLP` or
`nix develop`


## FAQ
* Why not REST?
    * The Bloomberg API uses the concept of "correlationIDs" to link requests with responses, which are a natural fit for gRPC function calls. 
    * REST doesn't do streaming. 
    * gRPC will marshall types across languages. 
    * Automatic binary serialization and deserialization. 
    * Faster.
* Why not Websockets?
    * Websockets are not a natural fit for request <-> response patterns. 
    * Avoids having to write a custom protocol.
    * Types, serialization as per REST.
* Can I use this if I don't have a Bloomberg terminal?
    * [No](https://stackoverflow.com/a/74503768/122792), unless you have a subscription to Bloomberg's Bpipe product. 
* Why not use FFI to C++
    * FFI with C++ is a pain in many languages, and would be Windows only. Now you can WSL. 
* I don't like Windows / WSL.
    * Bloomberg Terminal is Windows only, and does not permit data to be moved off the Windows instance it is running on.
    * Bloomberg has a number of (expensive) products which will allow data to move -- consult your Bloomberg representative about this. 
 


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

 

