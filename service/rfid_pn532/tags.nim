import logging
import sequtils
import strformat
import strutils
import sugar
import times

import nfc-nim/nfc, nfc-nim/freefare

var L = newConsoleLogger()
addHandler(L)

proc check(succeed: bool, msg: string) =
  if not succeed:
    let e = new(IOError)
    e.msg = msg
    raise e

proc check(p: ptr, msg: string) =
  check(not isNil(p), msg)
    
proc check(ret: int, msg: string) =
  check(ret == 0, &"{msg} ({ret})")

type NfcDevice = ref object of RootObj
  context: ptr nfc.context
  dev*: ptr nfc.device
  
type NfcTag* {.byref.} = object 
  tag*: FreefareTag

proc toBlock*(s: string): MifareClassicBlock =
  for i in 0..result.high:
    if i < s.len:
      result[i] = s[i]
    else:
      result[i] = '\x00'

proc toString*(b: MifareClassicBlock): string =
  cast[array[16,char]](b).join
  
proc newNfcDevice*(): NfcDevice =
  new result
  nfc.init(addr result.context)

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

type TagArray {.unchecked.} = array[999, ptr FreefareTag]

proc getTags(dev: ptr nfc.device): ptr FreefareTag =
  info("getting tags")
  let t0 = epochTime()
  var ret: ptr FreefareTag = freefare.freefare_get_tags(dev)
  check(ret, "freefare_get_tags returned null")
  info(&"found tags in {epochTime() - t0}")
  return ret

# freefare lib wants to free all the tag memory, so process them in a
# callback and don't keep them outside that.
proc forAllTags*(self: var NfcDevice, onTag: (NfcTag) -> void) =
  var ret = getTags(self.dev)
  var tagList = cast[TagArray](ret)
  for tagp in tagList:
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

proc tagType*(self: NfcTag): freefare.freefare_tag_type =
  freefare.freefare_get_tag_type(self.tag)

proc uid*(self: NfcTag): cstring =
  freefare.freefare_get_tag_uid(self.tag)

proc connect*(self: NfcTag) =
  check(freefare.mifare_classic_connect(self.tag), "connect")
     
proc disconnect*(self: NfcTag) =
  check(freefare.mifare_classic_disconnect(self.tag), "disconnect")
  
proc destroy*(self: var NfcDevice) =
  nfc.close(self.dev)
  nfc.exit(self.context)

var pubkey: MifareClassicKey = [cast[cuchar](0xff),
                                cast[cuchar](0xff),
                                cast[cuchar](0xff),
                                cast[cuchar](0xff),
                                cast[cuchar](0xff),
                                cast[cuchar](0xff)]
    
proc readBlock*(self: NfcTag, blockNumber: int): string =
  var blockNum = cast[freefare.MifareClassicBlockNumber](blockNumber)
  check(freefare.mifare_classic_authenticate(
    self.tag, blockNum, pubkey, freefare.MFC_KEY_A),
        &"mifare_classic_authenticate() failed")

  var data: freefare.MifareClassicBlock

  check(mifare_classic_read(self.tag, blockNum, addr data),
        "classic_read() failed")
  return toString(data)

proc writeBlock*(self: NfcTag,
                blockNumber: int,
                data: freefare.MifareClassicBlock) =
  var blocknum = cast[freefare.MifareClassicBlockNumber](blockNumber)
  check(freefare.mifare_classic_authenticate(
    self.tag, blocknum, pubkey, freefare.MFC_KEY_A),
        &"mifare_classic_authenticate() failed")

  check(mifare_classic_write(self.tag, blocknum, data),
        "classic_write() failed")
  info(&"  wrote block {blocknum}: {data}")
