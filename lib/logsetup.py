# todo: graylog, twisted web route to some channel

import logging
logging.basicConfig(format="%(created)f %(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger('restkit.client').setLevel(logging.WARN)
log = logging.getLogger()
log.setLevel(logging.INFO)
