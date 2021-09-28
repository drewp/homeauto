#!camtest/bin/python3
import binascii
import logging
import time
import io
import os
import json
from docopt import docopt
from standardservice.logsetup import log, verboseLogging

logging.basicConfig(level=logging.INFO)
from aiohttp import web
from aiohttp.web import Response
from aiohttp_sse import sse_response

import asyncio

from aioesphomeapi import APIClient
from aioesphomeapi.model import CameraState
import apriltag
import cv2
import numpy

class CameraReceiver:
    def __init__(self, loop, host):
        self.lastFrameTime = None
        self.loop = loop
        self.host = host
        self.lastFrame = b"", ''
        self.recent = []

    async def start(self):
        try:
            self.c = c = APIClient(self.loop, 
            self.host,
            6053, 'MyPassword')
            await c.connect(login=True)
            await c.subscribe_states(on_state=self.on_state)
        except OSError:
            loop.stop()
            return
        self.loop.create_task(self.start_requesting_image_stream_forever())

    async def start_requesting_image_stream_forever(self):
        while True:
            try:
                await self.c.request_image_stream()
            except AttributeError:
                self.loop.stop()
                return
            # https://github.com/esphome/esphome/blob/dev/esphome/components/esp32_camera/esp32_camera.cpp#L265 says a 'stream' is 5 sec long
            await asyncio.sleep(4)

    def on_state(self, s):
        if isinstance(s, CameraState):
            jpg = s.image
            if len(self.recent) > 10:
                self.recent = self.recent[-10:]

            self.recent.append(jpg)
            #print('recent lens: %s' % (','.join(str(len(x))
            #                                    for x in self.recent)))
        else:
            print('other on_state', s)

    def analyze(self, jpg):
        img = cv2.imdecode(numpy.asarray(bytearray(jpg)),
                           cv2.IMREAD_GRAYSCALE)
        result = detector.detect(img)
        msg = {}
        if result:
            center = result[0].center
            msg['center'] = [round(center[0], 2), round(center[1], 2)]
        return msg

    async def frames(self):
        while True:
            if self.recent:
                if self.lastFrameTime and time.time() - self.lastFrameTime > 15:
                    print('no recent frames')
                    os.abort()

                jpg = self.recent.pop(0)
                msg = self.analyze(jpg)
                yield jpg, msg
                self.lastFrame = jpg, msg
                self.lastFrameTime = time.time()
            else:
                await asyncio.sleep(.05)


def imageUri(jpg):
    return 'data:image/jpeg;base64,' + binascii.b2a_base64(jpg).decode('ascii')

async def stream(request):
    async with sse_response(request) as resp:
        await resp.send(imageUri(recv.lastFrame[0]))
        await resp.send(json.dumps(recv.lastFrame[1]))
        async for frame, msg in recv.frames():
            await resp.send(json.dumps(msg))
            await resp.send(imageUri(frame))
    return resp

async def index(request):
    d = r"""
        <html>
        <body>
    <style>
    #center {
    position: absolute;
    font-size: 35px;
    color: orange;
    text-shadow: black 0 1px 1px;
    margin-left: -14px;
    margin-top: -23px;
    }
    </style>
            <script>
                var evtSource = new EventSource("/stream");
                evtSource.onmessage = function(e) {
                    if (e.data[0] == '{') {
                      const msg = JSON.parse(e.data);
                      const st = document.querySelector('#center').style;
                      if (msg.center) {
                        st.left = msg.center[0];
                        st.top = msg.center[1];
                      } else {
                        st.left = -999;
                      }
                    } else {
                      document.getElementById('response').src = e.data;
                    }
                }
            </script>
            <h1>Response from server:</h1>
            <div style="position: relative">
              <img id="response"></img>
              <span id="center" style="position: absolute">&#x25ce;</span>
           </div>
        </body>
    </html>
    """
    return Response(text=d, content_type='text/html')

arguments = docopt('''
this

Usage:
  this [-v] [--cam host] [--port to_serve]

Options:
  -v --verbose       more log
  --port n           http server [default: 10020]
  --cam host         hostname of esphome server
''')

verboseLogging(arguments['--verbose'])
logging.getLogger('aioesphomeapi.connection').setLevel(logging.INFO)

loop = asyncio.get_event_loop()

recv = CameraReceiver(loop, arguments['--cam'])
detector = apriltag.Detector()

f = recv.start()
loop.create_task(f)

start_time = time.time()
app = web.Application()
app.router.add_route('GET', '/stream', stream)
app.router.add_route('GET', '/', index)
try:
    web.run_app(app, host='0.0.0.0', port=int(arguments['--port']))
except RuntimeError as e:
    log.error(e)
log.info(f'run_app stopped after {time.time() - start_time} sec')