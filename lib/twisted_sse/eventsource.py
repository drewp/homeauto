from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from .sse_client import EventSourceProtocol


class EventSource(object):
    """
    The main EventSource class
    """
    def __init__(self, url, userAgent):
        # type: (str, bytes)
        self.url = url
        self.userAgent = userAgent
        self.protocol = EventSourceProtocol(self.onConnectionLost)
        self.errorHandler = None
        self.stashedError = None
        self.connect()

    def connect(self):
        """
        Connect to the event source URL
        """
        agent = Agent(reactor, connectTimeout=5)
        self.agent = agent
        d = agent.request(
            b'GET',
            self.url,
            Headers({
                b'User-Agent': [self.userAgent],
                b'Cache-Control': [b'no-cache'],
                b'Accept': [b'text/event-stream; charset=utf-8'],
            }),
            None)
        d.addCallbacks(self.cbRequest, self.connectError)

    def cbRequest(self, response):
        if response is None:
            # seems out of spec, according to https://twistedmatrix.com/documents/current/api/twisted.web.iweb.IAgent.html
            raise ValueError('no response for url %r' % self.url)
        elif response.code != 200:
            self.callErrorHandler("non 200 response received: %d" %
                                  response.code)
        else:
            response.deliverBody(self.protocol)

    def connectError(self, ignored):
        self.callErrorHandler("error connecting to endpoint: %s" % self.url)

    def onConnectionLost(self, reason):
        # overridden
        reason.printDetailedTraceback()
        
    def callErrorHandler(self, msg):
        if self.errorHandler:
            func, callInThread = self.errorHandler
            if callInThread:
                reactor.callInThread(func, msg)
            else:
                func(msg)
        else:
            self.stashedError = msg

    def onerror(self, func, callInThread=False):
        self.errorHandler = func, callInThread
        if self.stashedError:
            self.callErrorHandler(self.stashedError)

    def onmessage(self, func, callInThread=False):
        self.addEventListener('message', func, callInThread)

    def addEventListener(self, event, func, callInThread=False):
        assert isinstance(event, bytes), event
        callback = func
        if callInThread:
            callback = lambda data: reactor.callInThread(func, data)
        self.protocol.addCallback(event, callback)
