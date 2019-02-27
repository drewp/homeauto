import nfc, freefare
import logging
log = logging.getLogger('tags')

class NfcDevice(object):
    def __init__(self):
        context = ptr nfc.nfc_context
        nfc.nfc_init(context)

        '''
          var connstrings: array[10, nfc.connstring]
          var n = nfc.list_devices(result.context,
                                   cast[ptr nfc.connstring](addr connstrings),
                                   len(connstrings))
          info(&"{n} connection strings")
          for i in 0 ..< n:
            info(&"  dev {i}: {join(connstrings[i])}")

          info("open dev")
          result.dev = nfc.open(result.context, connstrings[0])
          let dev = result.dev
          check(device_get_last_error(dev),
                &"nfc.open failed on {join(connstrings[0])}")
        '''

    def __del__(self):
        nfc.close(self.dev)
        nfc.exit(self.context)

    def getTags(self):
        log.info("getting tags")
        t0 = time.time()
        ret = freefare.freefare_get_tags(self.dev)
        if not ret: raise IOError("freefare_get_tags returned null")
        log.info(f"found tags in {time.time() - t0}")
        return ret

    # freefare lib wants to free all the tag memory, so process them in a
    # callback and don't keep them outside that.
    def forAllTags(self, onTag: (NfcTag) -> None):
        ret = self.getTags()
        for tagp in ret:
          if isNil(tagp):
            break
          if cast[int](tagp) < 10:
            # pointer value looks wrong
            break
  
          let tag: FreefareTag = tagp[]
          if isNil(tag):
            break
          onTag(NfcTag(tag: tag))
        freefare.freefare_free_tags(ret)

def blockFromString(s: str):
    result = MifareClassicBlock()
    for i in 0..result.high:
      if i < s.len:
        result[i] = s[i]
      else:
        result[i] = '\x00'
    return result
  
proc stringFromBlock(b: MifareClassicBlock) -> string
  return ''.join(b)#cast[array[16,char]](b).join
  
type TagArray {.unchecked.} = array[999, ptr FreefareTag]

pubkey = ['\xff', '\xff', '\xff', '\xff', '\xff', '\xff']

def check(ret, msg):
    if ret != 0:
        raise IOError(msg)

class NfcTag(object):
    def __init__(self, tag): #FreefareTag
        self.tag = tag

    def tagType(self): freefare.freefare_tag_type =
        return freefare.freefare_get_tag_type(self.tag)

    def uid(self):
        return freefare.freefare_get_tag_uid(self.tag)

    def connect(self):
        check(freefare.mifare_classic_connect(self.tag), "connect")

    def disconnect(self):
        check(freefare.mifare_classic_disconnect(self.tag), "disconnect")

    def readBlock(self, blockNumber: int) -> string:
      blockNum = cast[freefare.MifareClassicBlockNumber](blockNumber)
      check(freefare.mifare_classic_authenticate(
        self.tag, blockNum, pubkey, freefare.MFC_KEY_A),
            &"mifare_classic_authenticate() failed")

      var data: freefare.MifareClassicBlock

      check(mifare_classic_read(self.tag, blockNum, addr data),
            "classic_read() failed")
      return toString(data)

    def writeBlock(self,
                    blockNumber: int,
                    data: freefare.MifareClassicBlock) =
      var blocknum = cast[freefare.MifareClassicBlockNumber](blockNumber)
      check(freefare.mifare_classic_authenticate(
        self.tag, blocknum, pubkey, freefare.MFC_KEY_A),
            &"mifare_classic_authenticate() failed")

      check(mifare_classic_write(self.tag, blocknum, data),
            "classic_write() failed")
      log.info(&"  wrote block {blocknum}: {data}")
