# make rfid && make build_image_pi
# docker pull bang6:5000/rfid_pn532_pi && docker run --rm -it --name rfid --net=host --privileged bang6:5000/rfid_pn532_pi

# i2c keeps dropping. kernel from 1.20180313 to 1.201811112.1

import nfc-nim/freefare
import strformat
import strutils
import graphserver
import tags
import threadpool
import sets

type CardEvent = object of RootObj
  uid: cstring
  body: cstring
  appeared: bool
type CardEventChannel = Channel[CardEvent]


var events: CardEventChannel

type TagWatcher = object of RootObj
  dev: NfcDevice
  nearbyUids: var HashSet[cstring]

proc initTagWatcher(): var TagWatcher =
  result.nearbyUids.init()
  
proc oneScan(self: TagWatcher) =
  var nearThisPass = initSet[cstring]()

  self.dev.forAllTags proc (tag: NfcTag) = 
    if tag.tagType() == freefare.MIFARE_CLASSIC_1K:
      echo &"found mifare 1k"
    else:
      echo &" unknown tag type {freefare.freefare_get_tag_friendly_name(tag.tag)}"
      return

    echo &"  uid {tag.uid()}"

    nearThisPass.incl(tag.uid())

    if tag.uid() in self.nearbyUids:
      return

    tag.connect()
    try:
      echo &" block1: {tag.readBlock(1).escape}"
      events.send(CardEvent(uid: tag.uid(), body: tag.readBlock(1),
                            appeared: true))
      #tag.writeBlock(1, toBlock("helloworld"))
    finally:
      tag.disconnect()

  for uid in self.nearbyUids.difference(nearThisPass):
    events.send(CardEvent(uid: uid, appeared: false))

  self.nearbyUids = nearThisPass


proc scanTags(self: TagWatcher) =
  self.dev = newNfcDevice()
  try:
    while true:
      self.oneScan()
  finally:
    self.dev.destroy()

  
proc watchForever*(self: TagWatcher) {.thread.} =
  while true:
    try:
      self.scanTags()
    except IOError:
      echo "IOError: restarting nfc now"
  

proc tagsToGraph() {.thread.} =
  while true:
    echo "wait for event"
    echo &"ev {events.recv()}"
  

proc main() =
  events.open()

  var tw = initTagWatcher()
  var thr: Thread[void]
  thr.createThread(tw.watchForever)

  var t2: Thread[void]
  t2.createThread(tagsToGraph)
  

  let server = newGraphServer(port = 10012)
  server.run()

main()
