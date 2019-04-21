# based on http://freshfoo.com/blog/pulseaudio_monitoring
#
# https://github.com/swharden/Python-GUI-examples/blob/master/2016-07-37_qt_audio_monitor/SWHear.py is similar
from __future__ import division
import socket, time, logging, os, subprocess
from Queue import Queue
from ctypes import c_void_p, c_ulong, string_at
from docopt import docopt
from influxdb import InfluxDBClient
import numpy

from pulseaudio import lib_pulseaudio as P

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


class PeakMonitor(object):

    def __init__(self, source_name, rate):
        self.source_name = source_name
        self.rate = rate

        self.bufs = []
        self.buf_samples = 0
        
        # Wrap callback methods in appropriate ctypefunc instances so
        # that the Pulseaudio C API can call them
        self._context_notify_cb = P.pa_context_notify_cb_t(self.context_notify_cb)
        self._source_info_cb = P.pa_source_info_cb_t(self.source_info_cb)
        self._stream_read_cb = P.pa_stream_request_cb_t(self.stream_read_cb)

        # stream_read_cb() puts peak samples into this Queue instance
        self._samples = Queue()

        # Create the mainloop thread and set our context_notify_cb
        # method to be called when there's updates relating to the
        # connection to Pulseaudio
        _mainloop = P.pa_threaded_mainloop_new()
        _mainloop_api = P.pa_threaded_mainloop_get_api(_mainloop)
        context = P.pa_context_new(_mainloop_api, 'peak_demo')
        P.pa_context_set_state_callback(context, self._context_notify_cb, None)
        P.pa_context_connect(context, None, 0, None)
        P.pa_threaded_mainloop_start(_mainloop)

    def __iter__(self):
        while True:
            yield self._samples.get()

    def context_notify_cb(self, context, _):
        state = P.pa_context_get_state(context)

        if state == P.PA_CONTEXT_READY:
            log.info("Pulseaudio connection ready...")
            # Connected to Pulseaudio. Now request that source_info_cb
            # be called with information about the available sources.
            o = P.pa_context_get_source_info_list(context, self._source_info_cb, None)
            P.pa_operation_unref(o)

        elif state == P.PA_CONTEXT_FAILED :
            log.error("Connection failed")
            os.abort()

        elif state == P.PA_CONTEXT_TERMINATED:
            log.error("Connection terminated")
            os.abort()

        else:
            log.info('context_notify_cb state=%r', state)

    def source_info_cb(self, context, source_info_p, _, __):
        if not source_info_p:
            return

        source_info = source_info_p.contents

        if source_info.name == self.source_name:
            # Found the source we want to monitor for peak levels.
            # Tell PA to call stream_read_cb with peak samples.
            log.info('setting up peak recording using %s', source_info.name)
            log.info('description: %r', source_info.description)
            
            samplespec = P.pa_sample_spec()
            samplespec.channels = 1
            samplespec.format = P.PA_SAMPLE_S32LE
            samplespec.rate = self.rate
            pa_stream = P.pa_stream_new(context, "audioInputLevels", samplespec, None)
            
            P.pa_stream_set_read_callback(pa_stream,
                                          self._stream_read_cb,
                                          source_info.index)
            P.pa_stream_connect_record(pa_stream,
                                       source_info.name,
                                       None,
                                       P.PA_STREAM_PEAK_DETECT)

    def stream_read_cb(self, stream, length, index_incr):
        data = c_void_p()
        P.pa_stream_peek(stream, data, c_ulong(length))
        try:
            buf = string_at(data, length)
            arr = numpy.fromstring(buf, dtype=numpy.dtype('<i4'))
            self.bufs.append(arr)
            self.buf_samples += arr.shape[0]

            if self.buf_samples > self.rate * 1.0:
                self.onChunk(numpy.concatenate(self.bufs))
                self.bufs = []
                self.buf_samples = 0
        finally:
            P.pa_stream_drop(stream)

    def fft(self, arr):
        t1 = time.time()
        # if this is slow, try
        # https://hgomersall.github.io/pyFFTW/sphinx/tutorial.html#the-workhorse-pyfftw-fftw-class
        # . But, it seems to take 1-10ms per second of audio, so who
        # cares.
        mags = numpy.abs(numpy.fft.fft(arr))
        ft = time.time() - t1
        return mags, ft

    def timeSinceLastChunk(self):
        now = time.time()
        if hasattr(self, 'lastRead'):
            dt = now - self.lastRead
        else:
            dt = 1
        self.lastRead = now
        return dt
        
    def onChunk(self, arr):
        dt = self.timeSinceLastChunk()
        
        n = 8192

        mags, ft = self.fft(arr[:n])
        freqs = numpy.fft.fftfreq(n, d=1.0/self.rate)

        def freq_range(lo, hi):
            mask = (lo < freqs) & (freqs < hi)
            return numpy.sum(mags * mask) / numpy.count_nonzero(mask)

        scl = 1000000000
        bands = {'hi': freq_range(500, 8192) / scl,
                 'mid': freq_range(300, 500) / scl,
                 'lo': freq_range(90, 300) / scl,
                 'value': freq_range(90, 8192) / scl,
                 }
        log.debug('%r', bands)
        #import ipdb;ipdb.set_trace()
        
        if log.isEnabledFor(logging.DEBUG):
            self.dumpFreqs(n, dt, ft, scl, arr, freqs, mags)
        self._samples.put(bands)

    def dumpFreqs(self, n, dt, ft, scl, arr, freqs, mags):
        log.debug(
            'new chunk of %s samples, dt ~%.4f; ~%.1f hz; max %.1f; fft took %.2fms',
            n, dt, n / dt, arr.max() / scl, ft * 1000,
        )
        rows = zip(freqs, mags)
        for fr,v in rows[1:8] + rows[8:n//8:30]:
            log.debug('%6.1f %6.3f %s',
                      fr, v / scl, '*' * int(min(80, 80 * int(v) / scl)))
        

def main():
    arg = docopt("""
    Usage: audioInputLevelsPulse.py [-v] --source=<name>

    --source=<name>   pulseaudio source name (use `pactl list sources | grep Name`)
    -v                Verbose
    """)

    log.setLevel(logging.DEBUG if arg['-v'] else logging.INFO)

    # todo move this into the PeakMonitor part
    subprocess.check_output(['pactl',
                             'set-source-volume', arg['--source'], '94900'])
    
    influx = InfluxDBClient('bang.vpn-home.bigasterisk.com', 9060, 'root', 'root', 'main')

    hostname = socket.gethostname()
    METER_RATE = 8192
    monitor = PeakMonitor(arg['--source'], METER_RATE)
    for sample in monitor:
        log.debug(' %6.3f %s', sample['value'], '>' * int(min(80, sample['value'] * 80)))
        influx.write_points([{'measurement': 'audioLevel',
                              "fields": sample,
                              "time": int(time.time())}],
                            tags=dict(location=hostname),
                            time_precision='s')
        
if __name__ == '__main__':
    main()
