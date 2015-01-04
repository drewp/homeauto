BOARD_TAG    = diecimila
USER_LIB_PATH := $(realpath LiquidCrystal_V1.2.1/)
ARDUINO_LIBS = LiquidCrystal Wire
MONITOR_PORT = /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A4001lVK-if00-port0

include /usr/share/arduino/Arduino.mk

setup:
	ln -sf LiquidCrystal_V1.2.1/LiquidCrystal/LiquidCrystal.cpp LiquidCrystal.cpp
