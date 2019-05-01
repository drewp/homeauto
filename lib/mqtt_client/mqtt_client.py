import logging
from mqtt.client.factory import MQTTFactory
from rx import Observable
from rx.concurrency import TwistedScheduler
from twisted.application.internet import ClientService, backoffPolicy
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.endpoints import clientFromString

log = logging.getLogger('mqtt_client')

class MQTTService(ClientService):

    def __init__(self, endpoint, factory):
        self.endpoint = endpoint
        ClientService.__init__(self, endpoint, factory, retryPolicy=backoffPolicy())

    def startService(self):
        self.whenConnected().addCallback(self.connectToBroker)
        ClientService.startService(self)

    @inlineCallbacks
    def connectToBroker(self, protocol):
        self.protocol = protocol
        self.protocol.onDisconnection = self.onDisconnection
        # We are issuing 3 publish in a row
        # if order matters, then set window size to 1
        # Publish requests beyond window size are enqueued
        self.protocol.setWindowSize(1)

        try:
            yield self.protocol.connect("TwistedMQTT-pub", keepalive=60)
        except Exception as e:
            log.error("Connecting to {broker} raised {excp!s}",
                      broker=self.endpoint, excp=e)
        else:
            log.info("Connected to {broker}".format(broker=self.endpoint))
        if getattr(self, 'onMqttConnectionMade', False):
            self.onMqttConnectionMade()

    def onDisconnection(self, reason):
        log.warn("Connection to broker lost: %r", reason)
        self.whenConnected().addCallback(self.connectToBroker)

    def publish(self, topic, msg):
        def _logFailure(failure):
            log.warn("publish failed: %s", failure.getErrorMessage())
            return failure

        return self.protocol.publish(topic=topic, qos=0, message=msg).addErrback(_logFailure)


class MqttClient(object):
    def __init__(self, brokerHost='bang', brokerPort=1883):

        #scheduler = TwistedScheduler(reactor)
        
        factory = MQTTFactory(profile=MQTTFactory.PUBLISHER | MQTTFactory.SUBSCRIBER)
        myEndpoint = clientFromString(reactor, 'tcp:%s:%s' % (brokerHost, brokerPort))
        myEndpoint.__class__.__repr__ = lambda self: repr('%s:%s' % (self._host, self._port))
        self.serv = MQTTService(myEndpoint, factory)
        self.serv.startService()
        
    def publish(self, topic, msg):
        return self.serv.publish(topic, msg)

    def subscribe(self, topic):
        """returns rx.Observable of payload strings"""
        # This is surely broken for multiple topics and subscriptions. Might not even
        # work over a reconnect.
        
        ret = Observable.create(self._observe_msgs)

        self.serv.onMqttConnectionMade = lambda: self._resubscribe(topic)
        if (hasattr(self.serv, 'protocol') and
            self.serv.protocol.state ==self.serv.protocol.CONNECTED):
            self._resubscribe(topic)
        return ret

    def _resubscribe(self, topic):
        log.info('subscribing %r', topic)
        self.serv.protocol.onPublish = self._onPublish
        return self.serv.protocol.subscribe(topic, 2)
        
    def _observe_msgs(self, observer):
        self.obs = observer

    def _onPublish(self, topic, payload, qos, dup, retain, msgId):
        log.debug('received payload %r', payload)
        self.obs.on_next(payload)
