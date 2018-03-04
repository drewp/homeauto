# based on http://freshfoo.com/blog/pulseaudio_monitoring
from __future__ import division
import socket, argparse, time, logging, os
from Queue import Queue
from ctypes import POINTER, c_ubyte, c_void_p, c_ulong, cast
from influxdb import InfluxDBClient

# From https://github.com/Valodim/python-pulseaudio
from pulseaudio import lib_pulseaudio as P

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

METER_RATE = 1

class PeakMonitor(object):

    def __init__(self, source_name, rate):
        self.source_name = source_name
        self.rate = rate

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
            samplespec.format = P.PA_SAMPLE_U8
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
        data = cast(data, POINTER(c_ubyte))
        try:
            for i in xrange(length):
                # When PA_SAMPLE_U8 is used, samples values range from 128
                # to 255 because the underlying audio data is signed but
                # it doesn't make sense to return signed peaks.
                self._samples.put(data[i] - 128)
        except ValueError:
            # "data will be NULL and nbytes will contain the length of the hole"
            log.info("skipping hole of length %s" % length)
            # This seems to happen at startup for a while.
        P.pa_stream_drop(stream)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--source', required=True,
        help='pulseaudio source name (use `pactl list sources | grep Name`)')

    args = parser.parse_args()

    influx = InfluxDBClient('bang6', 9060, 'root', 'root', 'main')

    hostname = socket.gethostname()
    monitor = PeakMonitor(args.source, METER_RATE)
    for sample in monitor:
        log.debug(' %3d %s', sample, '>' * sample)
        influx.write_points([{'measurement': 'audioLevel',
                              "tags": dict(stat='max', location=hostname),
                              "fields": {"value": sample / 128},
                              "time": int(time.time())}], time_precision='s')
        
if __name__ == '__main__':
    main()
