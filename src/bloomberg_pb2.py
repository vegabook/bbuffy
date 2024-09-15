# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: bloomberg.proto
# Protobuf Python Version: 5.26.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
from google.protobuf import struct_pb2 as google_dot_protobuf_dot_struct__pb2
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0f\x62loomberg.proto\x12\tbloomberg\x1a\x1fgoogle/protobuf/timestamp.proto\x1a\x1cgoogle/protobuf/struct.proto\x1a\x1bgoogle/protobuf/empty.proto\"Z\n\x0eSessionOptions\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x10\n\x08interval\x18\x02 \x01(\x05\x12\x19\n\x11maxEventQueueSize\x18\x03 \x01(\x05\x12\r\n\x05\x65rror\x18\x04 \x01(\t\"\xcc\x01\n\x07Session\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x10\n\x08services\x18\x02 \x03(\t\x12=\n\x10subscriptionList\x18\x03 \x01(\x0b\x32#.bloomberg.Session.SubscriptionList\x12\r\n\x05\x61live\x18\x04 \x01(\x08\x12\r\n\x05\x65rror\x18\x05 \x01(\t\x1a\x44\n\x10SubscriptionList\x12\x0e\n\x06topics\x18\x01 \x03(\t\x12\x0e\n\x06\x66ields\x18\x02 \x03(\t\x12\x10\n\x08interval\x18\x03 \x01(\x05\"\xa0\x02\n\x15HistoricalDataRequest\x12#\n\x07session\x18\x01 \x01(\x0b\x32\x12.bloomberg.Session\x12\x0e\n\x06topics\x18\x02 \x03(\t\x12\x0e\n\x06\x66ields\x18\x03 \x03(\t\x12)\n\x05start\x18\x04 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\'\n\x03\x65nd\x18\x05 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12>\n\x07options\x18\x06 \x03(\x0b\x32-.bloomberg.HistoricalDataRequest.OptionsEntry\x1a.\n\x0cOptionsEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\"a\n\x16HistoricalDataResponse\x12\x0c\n\x04name\x18\x01 \x01(\t\x12*\n\tjson_data\x18\x02 \x01(\x0b\x32\x17.google.protobuf.Struct\x12\r\n\x05\x65rror\x18\x03 \x01(\t\"8\n\x0bKeyResponse\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\x0c\n\x04\x63\x65rt\x18\x02 \x01(\t\x12\x0e\n\x06\x63\x61\x63\x65rt\x18\x03 \x01(\t\"3\n\x0cHelloRequest\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x15\n\rnum_greetings\x18\x02 \x01(\t\"\x1d\n\nHelloReply\x12\x0f\n\x07message\x18\x01 \x01(\t\"(\n\nSumRequest\x12\x0c\n\x04num1\x18\x01 \x01(\x05\x12\x0c\n\x04num2\x18\x02 \x01(\x05\"\x1d\n\x0bSumResponse\x12\x0e\n\x06result\x18\x01 \x01(\x05\x32\xc4\x01\n\nKeyManager\x12>\n\nkeyRequest\x12\x16.google.protobuf.Empty\x1a\x16.bloomberg.KeyResponse\"\x00\x12>\n\x08sayHello\x12\x17.bloomberg.HelloRequest\x1a\x15.bloomberg.HelloReply\"\x00\x30\x01\x12\x36\n\x03sum\x12\x15.bloomberg.SumRequest\x1a\x16.bloomberg.SumResponse\"\x00\x32\xd5\x04\n\x0eSessionManager\x12>\n\x08sayHello\x12\x17.bloomberg.HelloRequest\x1a\x15.bloomberg.HelloReply\"\x00\x30\x01\x12\x36\n\x03sum\x12\x15.bloomberg.SumRequest\x1a\x16.bloomberg.SumResponse\"\x00\x12H\n\x11getDefaultOptions\x12\x16.google.protobuf.Empty\x1a\x19.bloomberg.SessionOptions\"\x00\x12>\n\x0bopenSession\x12\x19.bloomberg.SessionOptions\x1a\x12.bloomberg.Session\"\x00\x12\x35\n\tsubscribe\x12\x12.bloomberg.Session\x1a\x12.bloomberg.Session\"\x00\x12\x37\n\x0bsessionInfo\x12\x12.bloomberg.Session\x1a\x12.bloomberg.Session\"\x00\x12\x37\n\x0bunsubscribe\x12\x12.bloomberg.Session\x1a\x12.bloomberg.Session\"\x00\x12\x38\n\x0c\x63loseSession\x12\x12.bloomberg.Session\x1a\x12.bloomberg.Session\"\x00\x12^\n\x15historicalDataRequest\x12 .bloomberg.HistoricalDataRequest\x1a!.bloomberg.HistoricalDataResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'bloomberg_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_HISTORICALDATAREQUEST_OPTIONSENTRY']._loaded_options = None
  _globals['_HISTORICALDATAREQUEST_OPTIONSENTRY']._serialized_options = b'8\001'
  _globals['_SESSIONOPTIONS']._serialized_start=122
  _globals['_SESSIONOPTIONS']._serialized_end=212
  _globals['_SESSION']._serialized_start=215
  _globals['_SESSION']._serialized_end=419
  _globals['_SESSION_SUBSCRIPTIONLIST']._serialized_start=351
  _globals['_SESSION_SUBSCRIPTIONLIST']._serialized_end=419
  _globals['_HISTORICALDATAREQUEST']._serialized_start=422
  _globals['_HISTORICALDATAREQUEST']._serialized_end=710
  _globals['_HISTORICALDATAREQUEST_OPTIONSENTRY']._serialized_start=664
  _globals['_HISTORICALDATAREQUEST_OPTIONSENTRY']._serialized_end=710
  _globals['_HISTORICALDATARESPONSE']._serialized_start=712
  _globals['_HISTORICALDATARESPONSE']._serialized_end=809
  _globals['_KEYRESPONSE']._serialized_start=811
  _globals['_KEYRESPONSE']._serialized_end=867
  _globals['_HELLOREQUEST']._serialized_start=869
  _globals['_HELLOREQUEST']._serialized_end=920
  _globals['_HELLOREPLY']._serialized_start=922
  _globals['_HELLOREPLY']._serialized_end=951
  _globals['_SUMREQUEST']._serialized_start=953
  _globals['_SUMREQUEST']._serialized_end=993
  _globals['_SUMRESPONSE']._serialized_start=995
  _globals['_SUMRESPONSE']._serialized_end=1024
  _globals['_KEYMANAGER']._serialized_start=1027
  _globals['_KEYMANAGER']._serialized_end=1223
  _globals['_SESSIONMANAGER']._serialized_start=1226
  _globals['_SESSIONMANAGER']._serialized_end=1823
# @@protoc_insertion_point(module_scope)
