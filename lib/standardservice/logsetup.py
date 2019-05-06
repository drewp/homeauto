# todo: graylog, twisted web route to some channel

import logging
from twisted.internet import defer

logging.basicConfig(format="%(created)f %(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger('restkit.client').setLevel(logging.WARN)
log = logging.getLogger()
log.setLevel(logging.INFO)

def enableTwistedLog():
    from twisted.python import log as twlog
    import sys
    twlog.startLogging(sys.stdout)

def verboseLogging(yes):
    if yes:
        enableTwistedLog()
        log.setLevel(logging.DEBUG)
        defer.setDebugging(True)
    else:
        log.setLevel(logging.WARN)
    

