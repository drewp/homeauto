from twisted.internet import reactor
from twisted.internet.serialport import SerialPort


from insteonprotocol import InsteonProtocol



s = SerialPort(
    InsteonProtocol(),
    "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900ex7S-if00-port0",
    reactor,
    baudrate=19200)

reactor.run()
