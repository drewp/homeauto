build_image:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --network=host -t bang6:5000/arduino_node .
	docker push bang6:5000/arduino_node

shell: build_image
	docker run -it --net=host -v `pwd`/config:/opt/config bang6:5000/arduino_node  /bin/bash

local_run: build_image
	docker run -it -p 9059:9059 --device=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A900cepU-if00-port0 --net=host bang6:5000/arduino_node python ./arduinoNode.py -v

push_config:
	docker run -it --net=host -v `pwd`/config:/opt/config bang6:5000/arduino_node python pushConfig.py arduino/

lightsout:
	curl http://bang:9059/output\?s\=http://projects.bigasterisk.com/room/speakersStrips\&p\=http://projects.bigasterisk.com/room/x -XPUT -d 199

redeploy: build_image
	ctl restart arduinoNodeBang_9059
