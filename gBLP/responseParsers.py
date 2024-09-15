from bloomberg_pb2 import (
    HistoricalDataResponse,
    HistoricalDataResponseItem,
    SecurityData,
    FieldData
)

from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.struct_pb2 import Value
from google.protobuf.struct_pb2 import Struct
import datetime


def buildHistoricalDataResponse(data):
    response = HistoricalDataResponse()
    for item in data:
        securityDataDict = item['securityData']
        
        # Create SecurityData message
        securityDataMsg = SecurityData()
        securityDataMsg.security = securityDataDict['security']
        securityDataMsg.sequence_number = securityDataDict['sequenceNumber']
        
        # Handle fieldData
        for fieldDataItem in securityDataDict['fieldData']:
            fieldDataMsg = FieldData()
            
            # Convert date to Timestamp
            dateValue = fieldDataItem['date']
            datetimeObj = datetime.datetime.combine(dateValue, datetime.time.min)
            timestamp = Timestamp()
            timestamp.FromDatetime(datetimeObj)
            fieldDataMsg.date.CopyFrom(timestamp)
            
            # Add arbitrary fields
            for key, value in fieldDataItem.items():
                if key == 'date':
                    continue  # Skip the date field
                # Create a Value object based on the type of value
                if isinstance(value, (int, float)):
                    fieldDataMsg.fields[key].number_value = value
                elif isinstance(value, str):
                    fieldDataMsg.fields[key].string_value = value
                elif isinstance(value, bool):
                    fieldDataMsg.fields[key].bool_value = value
                else:
                    # Handle other types or raise an error
                    raise ValueError(f"Unsupported type for field '{key}': {type(value)}")
            
            # Append to fieldData
            securityDataMsg.field_data.append(fieldDataMsg)
        
        # Create HistoricalDataResponseItem
        responseItem = HistoricalDataResponseItem()
        responseItem.security_data.CopyFrom(securityDataMsg)
        
        # Append to items
        response.items.append(responseItem)
    
    return response

