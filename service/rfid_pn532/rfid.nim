# make rfid && make build_image_pi
# docker pull bang6:5000/rfid_pn532_pi && docker run --rm -it --name rfid --net=host --privileged bang6:5000/rfid_pn532_pi

#import asyncdispatch
import os
import parseutils
import sets
import strformat
import strutils
import threadpool
import httpclient

import nfc-nim/freefare

#import graphserver
import rdf
import rdf_nodes
import tags

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

proc uidUri(card_id: cstring): Uri =
  let id10 = align($card_id, 10, '0')
  initUri(&"http://bigasterisk.com/rfidCard/{id10}")
     
proc graphChanged(newGraph: openArray[Quad]) =
  let client = newHttpClient()
  let response = client.request("http://localhost:10012/currentGraph", 
                                httpMethod = HttpPut, body = toSet(newGraph).toJsonLd())
  if response.status != "200 OK":
    raise new IOError

proc sendOneshot(graph: openArray[Quad]) =
  let client = newHttpClient()
  let response = client.request("http://10.2.0.1:9071/oneShot", 
                                httpMethod = HttpPost, 
                                body = graph.toNtriples(),
                                headers=newHttpHeaders({
                                "Content-Type":"text/n3"}))
  if response.status != "200 OK":
    raise new IOError


type TtgArgs = tuple[events: ptr CardEventChannel,]
proc tagsToGraph(args: TtgArgs) {.thread.} =
  let ROOM = initNamespace("http://projects.bigasterisk.com/room/")
  let sensor = ROOM["frontDoorWindowRfid"]
  let ctx = ROOM["frontDoorWindowRfidCtx"]

  while true:
    let ev = args.events[].recv()
    if ev.appeared:
      let cardUri = uidUri(ev.uid)
      graphChanged([
          Quad((sensor, ROOM["reading"], cardUri, ctx)),
          Quad((cardUri, ROOM["cardText"], initLiteral(ev.body), ctx)),
      ])
      sendOneshot([
        Quad((sensor, ROOM["startReading"], cardUri, ctx)),
        Quad((cardUri, ROOM["cardText"], initLiteral(ev.body), ctx))
        ])
    else:
      graphChanged([])

proc main() =
  var events: CardEventChannel
  events.open()

  var tw = initTagWatcher(addr events)
  var thr: Thread[tw.type]
  thr.createThread(watchForever, tw)

  var t2: Thread[TtgArgs]
  t2.createThread(tagsToGraph, (addr events,))
  
  joinThread(thr)
  joinThread(t2)

main()
