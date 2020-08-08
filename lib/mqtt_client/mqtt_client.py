import logging
from mqtt.client.factory import MQTTFactory
import rx.subject
from twisted.application.internet import ClientService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import clientFromString

log = logging.getLogger('mqtt_client')
AT_MOST_ONCE, AT_LEAST_ONCE, EXACTLY_ONCE = 0, 1, 2

class MQTTService(ClientService):

    def __init__(self, endpoint, factory, observersByTopic, clientId):
        self.endpoint = endpoint
        self.observersByTopic = observersByTopic
        self.clientId = clientId
        ClientService.__init__(self, endpoint, factory, retryPolicy=lambda _: 5)

    def startService(self):
        self.whenConnected().addCallback(self.connectToBroker)
        ClientService.startService(self)

    def ensureSubscribed(self, topic: bytes):
        self.whenConnected().addCallback(self._subscribeToLatestTopic, topic)

    def _subscribeToLatestTopic(self, protocol, topic: bytes):
        if protocol.state == protocol.CONNECTED:
            self.protocol.subscribe(topics=[(topic.decode('utf8'), AT_LEAST_ONCE)])
        # else it'll get done in the next connectToBroker.

    def _subscribeAll(self):
        topics = list(self.observersByTopic)
        if not topics:
            return
        log.info('subscribing %r', topics)
        self.protocol.subscribe(topics=[(topic.decode('utf8'), AT_LEAST_ONCE) for topic in topics])


    @inlineCallbacks
    def connectToBroker(self, protocol):
        self.protocol = protocol
        self.protocol.onDisconnection = self._onProtocolDisconnection

        # Publish requests beyond window size are enqueued
        self.protocol.setWindowSize(1)

        try:
            yield self.protocol.connect(self.clientId, keepalive=60)
        except Exception as e:
            log.error(f"Connecting to {self.endpoint} raised {e!s}")
            return

        log.info(f"Connected to {self.endpoint}")

        self.protocol.onPublish = self._onProtocolMessage
        self._subscribeAll()

    def _onProtocolMessage(self, topic, payload, qos, dup, retain, msgId):
        topic = topic.encode('ascii')
        observers = self.observersByTopic.get(topic, [])
        log.debug(f'received {topic} payload {payload} ({len(observers)} obs)')
        for obs in observers:
            obs.on_next(payload)

    def _onProtocolDisconnection(self, reason):
        log.warn("Connection to broker lost: %r", reason)
        self.whenConnected().addCallback(self.connectToBroker)

    def publish(self, topic: bytes, msg: bytes):
        def _logFailure(failure):
            log.warn("publish failed: %s", failure.getErrorMessage())
            return failure

        return self.protocol.publish(topic=topic.decode('utf-8'), qos=0,
                                     message=bytearray(msg)).addErrback(_logFailure)


class MqttClient(object):
    def __init__(self, clientId, brokerHost='bang', brokerPort=1883):

        self.observersByTopic = {} # bytes: Set(observer)

        factory = MQTTFactory(profile=MQTTFactory.PUBLISHER | MQTTFactory.SUBSCRIBER)
        myEndpoint = clientFromString(reactor, 'tcp:%s:%s' % (brokerHost, brokerPort))
        myEndpoint.__class__.__repr__ = lambda self: repr('%s:%s' % (self._host, self._port))
        self.serv = MQTTService(myEndpoint, factory, self.observersByTopic,
                                clientId)
        self.serv.startService()

    def publish(self, topic: bytes, msg: bytes):
        return self.serv.publish(topic, msg)

    def subscribe(self, topic: bytes):
        """returns rx.Observable of payload strings"""
        ret = rx.subject.Subject()
        self.observersByTopic.setdefault(topic, set()).add(ret)
        self.serv.ensureSubscribed(topic)
        return ret
