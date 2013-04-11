#!/usr/bin/python3
"""
read button and knob on rpi, send back to thermostat program
"""
from RPi.GPIO import setmode, PUD_UP, setup, BCM, IN, input as pinInput
import time, json
# using a copy of urllib/request.py from py3.3 which supports 'method'
from request import urlopen, Request

requestedTemperature = 'http://bang.bigasterisk.com:10001/requestedTemperature'
requestOpts = dict(headers={'user-agent': 'rpi buttons'})

def getRequestedTemp():
    return (json.loads(urlopen(
        Request(requestedTemperature, **requestOpts)).read().decode('utf-8'))
    )['tempF']

def setRequestedTemp(f):
    urlopen(Request(url=requestedTemperature,
            method='PUT',
            data=json.dumps({'tempF' : f}).encode('utf-8'),
            **requestOpts))

PIN_KNOB_A = 1
PIN_KNOB_B = 4
PIN_BUTTON = 0

setmode(BCM)
setup(PIN_KNOB_A, IN, PUD_UP)
setup(PIN_KNOB_B, IN, PUD_UP)
setup(PIN_BUTTON, IN, PUD_UP)

print("reading knob and button, writing to %s" % requestedTemperature)
prev = None
prevButton = 0
buttonHold = 0
step = .02
while True:
    a, b = pinInput(PIN_KNOB_A), pinInput(PIN_KNOB_B)
    button = not pinInput(PIN_BUTTON)
    pos = (b * 2) + (a ^ b)

    if prev is None:
        prev = pos
    dpos = (pos - prev) % 4

    if dpos == 1:
        print ("up")
        setRequestedTemp(getRequestedTemp() + 1)
    elif dpos == -1 % 4:
        print ("down")
        setRequestedTemp(getRequestedTemp() - 1)
    else:
        pass # 0 or unknown
    prev = pos
    
    if button:
        buttonHold += 1
        if buttonHold == int(.1 / step):
            print ("button to", button)
    else:
        buttonHold = 0

    time.sleep(step)
