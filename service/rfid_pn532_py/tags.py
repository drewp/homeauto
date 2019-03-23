import time
from ctypes import pointer, byref, c_ubyte, cast, c_char_p
import nfc, freefare
import logging
log = logging.getLogger('tags')

class FakeNfc(object):
    def getTags(self):
        return []

    
class NfcDevice(object):
    def __init__(self):
        self.context = pointer(nfc.nfc_context())
        nfc.nfc_init(byref(self.context))
        self.dev = None

        conn_strings = (nfc.nfc_connstring * 10)()
        t0, _, t2 = nfc.nfc_list_devices.argtypes
        nfc.nfc_list_devices.argtypes = [t0, type(conn_strings), t2]
        devices_found = nfc.nfc_list_devices(self.context, conn_strings, 10)
        log.info(f'{devices_found} connection strings')
        for i in range(devices_found):
            log.info(f'  dev {i}: {cast(conn_strings[i], c_char_p).value}')
        if devices_found < 1:
            raise IOError("no devices")
            
        log.debug("open dev")
        self.dev = nfc.nfc_open(self.context, conn_strings[0])
        if not self.dev or nfc.nfc_device_get_last_error(self.dev):
            raise IOError(f'nfc.open failed on {cast(conn_strings[0], c_char_p).value}')

    def __del__(self):
        if self.dev:
            nfc.nfc_close(self.dev)
        nfc.nfc_exit(self.context)

    def getTags(self):
        log.debug("getting tags")
        t0 = time.time()
        ret = freefare.freefare_get_tags(self.dev)
        if not ret:
            raise IOError("freefare_get_tags returned null")
        try:
            log.debug(f"found tags in {time.time() - t0}")
            for t in ret:
                if not t:
                    break
                yield NfcTag(t)
        finally:
            freefare.freefare_free_tags(ret)

pubkey = b'\xff\xff\xff\xff\xff\xff'

class NfcTag(object):
    def __init__(self, tag): #FreefareTag
        self.tag = tag

    def _check(self, ret: int):
        if ret == 0:
            return

        raise IOError(cast(freefare.freefare_strerror(self.tag), c_char_p).value)
        
    def tagType(self) -> str:
        typeNum = freefare.freefare_get_tag_type(self.tag)
        return freefare.freefare_tag_type__enumvalues[typeNum]

    def uid(self) -> str:
        return cast(freefare.freefare_get_tag_uid(self.tag),
                    c_char_p).value.decode('ascii')

    def connect(self):
        self._check(freefare.mifare_classic_connect(self.tag))

    def disconnect(self):
        self._check(freefare.mifare_classic_disconnect(self.tag))

    def readBlock(self, blockNumber: int) -> bytes:
        blockNum = freefare.MifareClassicBlockNumber(blockNumber)
        self._check(freefare.mifare_classic_authenticate(
            self.tag, blockNum, (c_ubyte*6)(*pubkey), freefare.MFC_KEY_A))
  
        data = freefare.MifareClassicBlock()
        self._check(freefare.mifare_classic_read(self.tag, blockNum, pointer(data)))
        return ''.join(map(chr, data)) # with trailing nulls

    def writeBlock(self, blockNumber: int, data: str):
        blocknum = freefare.MifareClassicBlockNumber(blockNumber)
        self._check(freefare.mifare_classic_authenticate(
          self.tag, blocknum, (c_ubyte*6)(*pubkey), freefare.MFC_KEY_A))
  
        dataBytes = data.encode('utf8')
        if len(dataBytes) > 16:
            raise ValueError('too long')
        dataBlock = (c_ubyte*16)(*dataBytes)
        
        self._check(freefare.mifare_classic_write(self.tag, blocknum, dataBlock))
        log.info(f"  wrote block {blocknum}: {dataBlock}")
