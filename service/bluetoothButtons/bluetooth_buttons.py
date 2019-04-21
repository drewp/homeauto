import hidraw
import os
import requests
import json

fileno = os.open('/dev/hidraw0', os.O_RDWR)
h = hidraw.HIDRaw(fileno)

keys = {
    b'\x02\xb6\x00': 'left',
    b'\x02\xe9\x00': 'top',
    b'\x02\xb5\x00': 'right',
    b'\x02\xcd\x00': 'middle',
}

while True:
    buf = os.read(fileno, 16)
    print('got %r' % buf)
    addr = h.getPhysicalAddress().decode('ascii')

    if buf in keys:
        msg = {'addr': addr, 'key': keys[buf]}
        print(msg)
        requests.post('http://bang6:10011/bluetoothButton',
                      data=json.dumps(msg))
# to use port 10014
