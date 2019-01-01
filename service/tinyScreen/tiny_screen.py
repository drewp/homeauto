from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import ssd1331


class Screen(object):
    def __init__(self, spiDevice=1, rotation=0):
    self._dev = ssd1331(spi(device=spiDevice, port=0), rotation=rotation)
    with canvas(self._dev) as draw:
          draw.rectangle(d.bounding_box, outline="white", fill="red")

