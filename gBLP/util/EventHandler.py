# colorscheme greenvision dark

import blpapi

RESP_INFO = "info"
RESP_REF = "refdata"
RESP_SUB = "subdata"
RESP_BAR = "bardata"
RESP_STATUS = "status"
RESP_ERROR = "error"
RESP_ACK = "ack"

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EventHandler(object):

    def __init__(self, parent):
        self.parent = parent

    def getTimeStamp(self):
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def processResponseEvent(self, event, partial):
        for msg in event:
            cid = msg.correlationId().value()
            logger.info((f"Received response to request {msg.getRequestId()} "
                        f"partial {partial}"))
            sendmsg = (RESP_REF, {"cid": cid, "partial": partial, "data": msg.toPy()})
            # now put message into correct queue
            self.parent.correlators[cid]["queue"].put(sendmsg)

    def processSubscriptionStatus(self, event):
        timeStamp = self.getTimeStamp()
        for msg in event:
            pymsg = msg.toPy()
            cid = msg.correlationId().value()
            if msg.messageType() == blpapi.Names.SUBSCRIPTION_FAILURE:
                sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
            elif msg.messageType() == blpapi.Names.SUBSCRIPTION_TERMINATED:
                stopevent.set() # DEBUG
                sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
            elif msg.messageType() == blpapi.Names.SUBSCRIPTION_STARTED:
                correl = msg.correlationId().value()
                sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
            else:
                sendmsg = (RESP_STATUS, (str(msg.messageType()), topic, pymsg))
            #self.parent.correlators[cid]["queue"].put(sendmsg)

    def searchMsg(self, msg, fields):
        return [{"field": field, "value": msg[field]} 
                for field in fields if msg.hasElement(field)]

    def makeBarMessage(self, msg, msgtype, topic, interval):
        msgdict = {"msgtype": msgtype, "topic": topic, "interval": interval}
        for f, m in {"open": "OPEN", 
                     "high": "HIGH", 
                     "low": "LOW", 
                     "close": "CLOSE", 
                     "volume": "VOLUME", 
                     "numticks": "NUMBER_OF_TICKS",
                     "timestamp": "DATE_TIME"}.items():
            if msg.hasElement(m):
                msgdict[f] = msg[m]
            else:
                msgdict[f] = None

        return msgdict

    def processSubscriptionDataEvent(self, event):
        """ 
        process subsription data message and put on queue
        """
        timestamp = self.getTimeStamp()
        timestampdt = dt.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        for msg in event:
            fulltopic = msg.correlationId().value()
            topic = fulltopic.split("/")[-1] # just ticker
            msgtype = msg.messageType()
            # bars --->
            if msgtype in (blpapi.Name("MarketBarUpdate"),
                           blpapi.Name("MarketBarStart"),
                           blpapi.Name("MarketBarEnd"),
                           blpapi.Name("MarketBarIntervalEnd")):
                sendmsg = (RESP_BAR, self.makeBarMessage(msg, str(msgtype), 
                                                          topic, interval = 1))
                #self.parent.correlators[cid]["queue"].put(sendmsg)

            # subscription --->
            elif msgtype == blpapi.Name("MarketDataEvents"):
                # mktdata event type
                sendmsg = (RESP_SUB, 
                       {"timestamp": timestampdt, 
                       "topic": topic,
                       "prices": self.searchMsg(msg, DEFAULT_FIELDS)})
                #self.parent.correlators[cid]["queue"].put(sendmsg)

            # something else --->
            else:
                logger.warning(f"Unknown message type {msgtype}")
                breakpoint()

    def processMiscEvents(self, event):
        for msg in event:
            sendmsg = (RESP_STATUS, str(msg.messageType()))
            #self.parent.correlators[cid]["queue"].put(sendmsg)


    def processEvent(self, event, _session):
        """ event processing selector """
        try:
            match event.eventType():
                case blpapi.Event.PARTIAL_RESPONSE:
                    self.processResponseEvent(event, True)
                case blpapi.Event.RESPONSE:
                    self.processResponseEvent(event, False)
                case blpapi.Event.REQUEST_STATUS:
                    for msg in event:
                        if msg.messageType == blpapi.Names.REQUEST_FAILURE:
                            reason=msg.getElement("reason")
                            print(f"Request failed: {reason}")
                            done = True
                        done = True
                case blpapi.Event.SUBSCRIPTION_DATA:
                    self.processSubscriptionDataEvent(event)
                case blpapi.Event.SUBSCRIPTION_STATUS:
                    self.processSubscriptionStatus(event)
                case _:
                    self.processMiscEvents(event)
        except blpapi.Exception as e:
            print(f"Failed to process event {event}: {e}")
        return False
