import unittest
import tags
import time
import os
os.environ['LIBNFC_DEFAULT_DEVICE'] = "pn532_i2c:/dev/i2c-1"
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

class TestNfc(unittest.TestCase):
    def test_open_close(self):
        n = tags.NfcDevice()
        del n
        
    def test_update_tag(self): # writes to the current tag!
        n = tags.NfcDevice()
        for t in n.getTags():
            print('tag', t)
            print('  tagType', t.tagType())
            print('  uid %r' % t.uid())
            t.connect()
            try:
                print('  block 1', t.readBlock(1))
                print('write')
                t.writeBlock(1, 'hello %s' % int(time.time()))
                print('  block 1', t.readBlock(1))
            finally:
                t.disconnect()
