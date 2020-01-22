from standardservice.logsetup import log
import w1thermsensor

def hello():
    log.info('hi devices')

    log.info(w1thermsensor.W1ThermSensor.get_available_sensors())
