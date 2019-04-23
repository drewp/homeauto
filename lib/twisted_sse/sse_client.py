from twisted.protocols.basic import LineReceiver


class EventSourceProtocol(LineReceiver):
    def __init__(self, onConnectionLost):
        self.onConnectionLost = onConnectionLost
        self.delimiter = b'\n'
        self.MAX_LENGTH = 1 << 20
        self.callbacks = {}
        self.finished = None
        # Initialize the event and data buffers
        self.event = b'message'
        self.data = b''

    def lineLengthExceeded(self, line):
        raise NotImplementedError('line too long')

    def setFinishedDeferred(self, d):
        self.finished = d

    def addCallback(self, event, func):
        self.callbacks[event] = func

    def lineReceived(self, line):
        if line == b'':
            # Dispatch event
            self.dispatchEvent()
        else:
            try:
                field, value = line.split(b':', 1)
                # If value starts with a space, strip it.
                value = lstrip(value)
            except ValueError:
                # We got a line with no colon, treat it as a field(ignore)
                return

            if field == b'':
                # This is a comment; ignore
                pass
            elif field == b'data':
                self.data += value + b'\n'
            elif field == b'event':
                self.event = value
            elif field == b'id':
                # Not implemented
                pass
            elif field == b'retry':
                # Not implemented
                pass

    def connectionLost(self, reason):
        self.onConnectionLost(reason)

    def dispatchEvent(self):
        """
        Dispatch the event
        """
        # If last character is LF, strip it.
        if self.data.endswith(b'\n'):
            self.data = self.data[:-1]
        if self.event in self.callbacks:
            self.callbacks[self.event](self.data)
        self.data = b''
        self.event = b'message'

def lstrip(value):
    return value[1:] if value.startswith(b' ') else value
