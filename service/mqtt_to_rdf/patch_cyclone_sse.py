def patchCycloneSse():
    import cyclone.sse
    from cyclone import escape

    def sendEvent(self, message, event=None, eid=None, retry=None):
        if isinstance(message, dict):
            message = escape.json_encode(message)
        if isinstance(message, str):
            message = message.encode("utf-8")
        assert isinstance(message, bytes)

        if eid:
            self.transport.write(b"id: %s\n" % eid)
        if event:
            self.transport.write(b"event: %s\n" % event)
        if retry:
            self.transport.write(b"retry: %s\n" % retry)

        self.transport.write(b"data: %s\n\n" % message)

    cyclone.sse.SSEHandler.sendEvent = sendEvent
