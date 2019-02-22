# make rfid && make build_image_pi
# docker pull bang6:5000/rfid_pn532_pi && docker run --rm -it --name rfid --net=host --privileged bang6:5000/rfid_pn532_pi

# i2c keeps dropping. kernel from 1.20180313 to 1.201811112.1

import nfc-nim/freefare
import strformat
import strutils
import graphserver
import tags
import threadpool
import os
import sets

type CardEvent = object of RootObj
  uid: cstring
  body: cstring
  appeared: bool
type CardEventChannel = Channel[CardEvent]


type FakeTagWatcher = ref object of RootObj
  events: ptr CardEventChannel
  
proc initFakeTagWatcher(events: ptr CardEventChannel): FakeTagWatcher =
  new result
  result.events = events

proc watchForever*(self: FakeTagWatcher) {.thread.} =
  while true:
    sleep(2000)
    self.events[].send(CardEvent(uid: "abcdef", body: "helloworld", appeared: true))
    sleep(2000)
    self.events[].send(CardEvent(uid: "abcdef", appeared: false))

   
type TagWatcher = ref object of RootObj
  dev: NfcDevice
  nearbyUids: HashSet[cstring]
  events: ptr CardEventChannel

proc initTagWatcher(events: ptr CardEventChannel): TagWatcher =
  new(result)
  result.nearbyUids.init()
  result.events = events

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
      self.events[].send(CardEvent(uid: tag.uid(), body: tag.readBlock(1),
                            appeared: true))
      #tag.writeBlock(1, toBlock("helloworld"))
    finally:
      tag.disconnect()

  for uid in self.nearbyUids.difference(nearThisPass):
    self.events[].send(CardEvent(uid: uid, appeared: false))

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

      
type TtgArgs = tuple[events: ptr CardEventChannel, server: GraphServer]
proc tagsToGraph(args: TtgArgs) {.thread.} =
  while true:
    echo "wait for event"
    let ev = args.events[].recv()
    if ev.appeared:
      args.server.setGraph()
    else:
      args.server.setGraph()

proc main() =

  var events: CardEventChannel
  events.open()

  var tw = initTagWatcher(addr events)
  var thr: Thread[tw.type]
  thr.createThread(watchForever, tw)

  let server = newGraphServer(port = 10012)

  var t2: Thread[TtgArgs]
  t2.createThread(tagsToGraph, (addr events, server))
  
  server.run()

main()
