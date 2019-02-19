# make rfid && make build_image_pi
# docker pull bang6:5000/rfid_pn532_pi && docker run --rm -it --name rfid --net=host --privileged bang6:5000/rfid_pn532_pi

import nfc-nim/freefare
import strformat
import strutils
import graphserver
import tags

var nn = newNfcDevice()

while true:
  echo "loop"

  nn.forAllTags proc (tag: NfcTag) = 
    if tag.tagType() == freefare.MIFARE_CLASSIC_1K:
      echo &"found mifare 1k"
    else:
      echo &" unknown tag type {freefare.freefare_get_tag_friendly_name(tag.tag)}"
      return

    echo &"  uid {tag.uid()}"

    tag.connect()
    try:
      echo &" block1: {tag.readBlock(1).escape}"
      #tag.writeBlock(1, toBlock("helloworld"))
    finally:
      tag.disconnect()

    if false:
      var data: freefare.MifareClassicBlock
      data[0] = cast[cuchar](5)
      data[1] = cast[cuchar](6)
      data[2] = cast[cuchar](7)
      tag.writeBlock(1, data)

nn.destroy()

let server = newGraphServer(port = 10012)
server.run()
