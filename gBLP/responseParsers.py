from bloomberg_pb2 import (
    HistoricalDataResponse,
    HistoricalDataResponseItem,
    SecurityData,
    FieldData
)

from bloomberg_pb2 import (
    SubscriptionDataResponse,
    SubFieldData
)



from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.struct_pb2 import Value
from google.protobuf.struct_pb2 import Struct
import datetime

import logging
logger = logging.getLogger(__name__)


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



def buildSubscriptionDataResponse(data):
    #('subdata', {'timestamp': datetime.datetime(2024, 9, 21, 23, 15, 7), 
    #'topic': 'XBTUSD Curncy', 
    #'prices': [{'field': 'LAST_PRICE', 'value': 63126.18}, {'field': 'BID', 'value': 63122.35}, {'field': 'ASK', 'value': 63130.0}]})
    response = SubscriptionDataResponse()
    subdata = data[1]
    response.timestamp.FromDatetime(subdata['timestamp'])
    response.topic = subdata['topic']
    if subdata.get("validated"):
        response.validated = subdata["validated"]
    if subdata.get("terminated"):
        response.terminated = subdata["terminated"]
    for price in subdata['prices']:
        success = True
        fieldDataMsg = SubFieldData()
        fieldDataMsg.field = price['field']
        if isinstance(price['value'], (int, float)):
            fieldDataMsg.value.number_value = price['value']
        elif isinstance(price['value'], str):
            fieldDataMsg.value.string_value = price['value']
        elif isinstance(price['value'], bool):
            fieldDataMsg.value.bool_value = price['value']
        elif isinstance(price['value'], datetime.datetime):
            fieldDataMsg.value.number_value = price['value'].timestamp()
        else:
            logger.warning(f"Unsupported type for field '{price['field']}': {type(price['value'])}")
            success = False
        if success:
            response.fields.append(fieldDataMsg)
    return response



