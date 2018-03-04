build_image:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --network=host -t bang6:5000/arduino_node .
	docker push bang6:5000/arduino_node

shell:
	docker run -it --net=host bang6:5000/arduino_node  /bin/sh

local_run:
	docker run -it -p 9059:9059 --device=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900cepU-if00-port0 --net=host bang6:5000/arduino_node python ./arduinoNode.py -v
