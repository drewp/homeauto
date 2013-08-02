from __future__ import division
import argparse, alsaaudio, time, numpy, galena, socket

def sendRecentAudio(accum, galenaOut, prefix):
    samples = numpy.concatenate(accum)
    samples = abs(samples / (1<<15))

    galenaOut.send(prefix + '.avg', numpy.average(samples))
    galenaOut.send(prefix + '.max', numpy.amax(samples))
    
def sendForever(card, prefix, periodSec, galenaOut):
    inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, card)
    inp.setchannels(1)
    inp.setrate(44100)
    inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    inp.setperiodsize(64)

    readSleepSec = .05
    lastSendTime = 0
    accum = []
    while True:

        # I was getting machine hangs on an eeePC and I tried anything
        # to make it not crash. I think this helped.
        time.sleep(readSleepSec)

        now = time.time()
        if now - lastSendTime > periodSec * 2:
            print "late: %s sec since last send and we have %s samples" % (
                now - lastSendTime, sum(len(x) for x in accum))
                
        nframes, data = inp.read()
        if nframes <= 0:
            #print 'nframes', nframes, len(data)
            continue # i get -32 a lot, don't know why
        samples = numpy.fromstring(data, dtype=numpy.int16) 
        accum.append(samples)

        # -readSleepSec is in here to make sure we send a little too
        # often (harmless) instead of missing a period sometimes,
        # which makes a gap in the graph
        if now > lastSendTime + periodSec - readSleepSec:
            sendRecentAudio(accum, galenaOut, prefix)
            lastSendTime = time.time()            

            accum[:] = []

parser = argparse.ArgumentParser()
parser.add_argument(
    '--card', required=True,
    help='alsa card name (see list of unindented lines from `arecord -L`)')

args = parser.parse_args()
sendForever(
    prefix='system.house.audio.%s' % socket.gethostname(),
    periodSec=2,
    card=args.card,
    galenaOut=galena.Galena(host='bang'),
)
