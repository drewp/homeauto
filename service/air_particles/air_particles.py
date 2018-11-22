from __future__ import print_function
import sys
import logging
import serial
import time
from influxdb import InfluxDBClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

location, = sys.argv[1:]
min_period = 5

ser_port = "/dev/ttyUSB0"
ser = serial.Serial(ser_port, baudrate=9600, stopbits=1, parity="N",  timeout=2)

influx = InfluxDBClient('bang6', 9060, 'root', 'root', 'main')

last_write = 0
while True:     
    ser.flushInput()
    s = map(ord, ser.read(32))
    if s[:2] != [0x42, 0x4d]:
        log.warn('unknown packet header: %s' % s)
        continue
        
    cs = (s[30] * 256 + s[31])   # check sum
    check = 0
    for i in range(30):
        check += s[i]
    if check != cs:
        log.warn('checksum mismatch: %s' % s)
        continue

    sample = {
        # PM1, PM2.5 and PM10 values for standard particle in ug/m^3
        'pm1_0_std': s[4] * 256 + s[5],
        'pm2_5_std': s[6] * 256 + s[7],
        'pm10_0_std': s[8] * 256 + s[9],

        # PM1, PM2.5 and PM10 values for atmospheric conditions in ug/m^3
        'pm1_0_atm': s[10] * 256 + s[11],
        'pm2_5_atm': s[12] * 256 + s[13],
        'pm10_0_atm': s[14] * 256 + s[15],

        # Number of particles bigger than 0.3 um, 0.5 um, etc. in #/cm^3
        'part_0_3': s[16] * 256 + s[17],
        'part_0_5': s[18] * 256 + s[19],
        'part_1_0': s[20] * 256 + s[21],
        'part_2_5': s[22] * 256 + s[23],
        'part_5_0': s[24] * 256 + s[25],
        'part_10_0': s[26] * 256 + s[27],
    }

    now = int(time.time())
    if now < last_write + min_period:
        continue
    if last_write == 0:
        log.info('sending first sample: %s', sample)
    last_write = now
    influx.write_points([{'measurement': 'air_particles',
                          "fields": sample,
                          "time": now,
                          }],
                          tags=dict(location=location),
                        time_precision='s')
