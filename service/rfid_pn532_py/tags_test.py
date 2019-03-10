import unittest
import tags
import os
os.environ['LIBNFC_DEFAULT_DEVICE'] = "pn532_i2c:/dev/i2c-1"

class TestNfc(unittest.TestCase):
    def test_open_close(self):
        n = tags.NfcDevice()
        del n
        
    def test_get_tags(self):
        n = tags.NfcDevice()
        print(n.getTags())
