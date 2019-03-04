import unittest
import tags

class TestNfc(unittest.TestCase):
    def test_open_close(self):
        n = tags.NfcDevice()
        del n
        
