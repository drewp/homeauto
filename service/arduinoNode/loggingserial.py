# forked from /my/proj/house/frontdoor/loggingserial.py

import serial, logging

log = logging.getLogger('serial')

class LoggingSerial(object):
    """like serial.Serial, but logs all data"""
    
    def __init__(self, port=None, ports=None, baudrate=9600, timeout=10):
        if ports is None:
            ports = [port]
            
        for port in ports:
            try:
                log.info("trying port: %s" % port)
                self.ser = serial.Serial(port=port, baudrate=baudrate,
                                         timeout=timeout,
                                         xonxoff=0, rtscts=0)
            except serial.SerialException:
                pass
        if not hasattr(self, 'ser'):
            raise IOError("no port found")
        
    def flush(self):
        self.ser.flush()

    def close(self):
        self.ser.close()
              
    def write(self, s):
        log.info("Serial write: %r" % s)
        self.ser.write(s)

    def read(self, n, errorOnTimeout=True):
        buf = self.ser.read(n)
        log.info("Serial read: %r" % buf)
        if errorOnTimeout and n > 0 and len(buf) == 0:
            raise ValueError("timed out")
        return buf
