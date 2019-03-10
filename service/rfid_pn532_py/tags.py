import time
from ctypes import pointer, byref
import nfc, freefare
import logging
log = logging.getLogger('tags')

    
class NfcDevice(object):
    def __init__(self):
        self.context = pointer(nfc.nfc_context())
        nfc.nfc_init(byref(self.context))
        self.dev = None

        conn_strings = (nfc.nfc_connstring * 10)()
        t0, _, t2 = nfc.nfc_list_devices.argtypes
        nfc.nfc_list_devices.argtypes = [t0, type(conn_strings), t2]
        devices_found = nfc.nfc_list_devices(self.context, conn_strings, 10)
        print(f'{devices_found} connection strings')
        for i in range(devices_found):
            print(f'  dev {i}: {conn_strings[i]}')
        if devices_found < 1:
            raise IOError("no devices")
            
        print("open dev")
        self.dev = nfc.nfc_open(self.context, conn_strings[0])
        if nfc.nfc_device_get_last_error(self.dev):
            raise IOError(f'nfc.open failed on {conn_strings[0]}')

    def __del__(self):
        if self.dev:
            nfc.nfc_close(self.dev)
        nfc.nfc_exit(self.context)

    def getTags(self):
        log.info("getting tags")
        t0 = time.time()
        ret = freefare.freefare_get_tags(self.dev)
        if not ret:
            raise IOError("freefare_get_tags returned null")
        try:
            log.info(f"found tags in {time.time() - t0}")
            for t in ret:
                yield NfcTag(t)
        finally:
            freefare.freefare_free_tags(ret)

pubkey = ['\xff', '\xff', '\xff', '\xff', '\xff', '\xff']

def check(ret, msg):
    if ret != 0:
        raise IOError(msg)

class NfcTag(object):
    def __init__(self, tag): #FreefareTag
        self.tag = tag

    def tagType(self) -> freefare.freefare_tag_type:
        return freefare.freefare_get_tag_type(self.tag)

    def uid(self):
        return freefare.freefare_get_tag_uid(self.tag)

    def connect(self):
        check(freefare.mifare_classic_connect(self.tag), "connect")

    def disconnect(self):
        check(freefare.mifare_classic_disconnect(self.tag), "disconnect")

    def readBlock(self, blockNumber: int) -> str:
      blockNum = freefare.MifareClassicBlockNumber(blockNumber)
      check(freefare.mifare_classic_authenticate(
        self.tag, blockNum, pubkey, freefare.MFC_KEY_A),
            "mifare_classic_authenticate() failed")

      data = freefare.MifareClassicBlock()

      check(freefare.mifare_classic_read(self.tag, blockNum, pointer(data)),
            "classic_read() failed")
      return data

    def writeBlock(self,
                    blockNumber: int,
                    data: freefare.MifareClassicBlock):
      blocknum = freefare.MifareClassicBlockNumber(blockNumber)
      check(freefare.mifare_classic_authenticate(
        self.tag, blocknum, pubkey, freefare.MFC_KEY_A),
            "mifare_classic_authenticate() failed")

      check(freefare.mifare_classic_write(self.tag, blocknum, data),
            "classic_write() failed")
      log.info("  wrote block {blocknum}: {data}")
