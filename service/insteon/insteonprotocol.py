from twisted.internet.defer import Deferred
from twisted.protocols.stateful import StatefulProtocol, StringIO
from twisted.protocols.policies import TimeoutMixin


class InsteonProtocol(StatefulProtocol, TimeoutMixin):
    def getInitialState(self):
        return (self.surprise, 1)

    def surprise(self, bytes):
        print "received %r" % bytes



    def getImInfo(self):
        msg = map(ord, self._send("\x60", 6))
        def imInfoBack(
        self._sful_data = (imInfoBack, , StringIO(), 0

        
        d = Deferred()
        return d
        return {'id' : "%02X%02X%02X" % (msg[0], msg[1], msg[2]),
                'deviceCategory' : msg[3],
                'deviceSubcategory' : msg[4],
                'firmwareRevision': msg[5]}
