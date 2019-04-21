JOB=tradfri
PORT=10009

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py req* ../arduinoNode/static tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -rf tmp_ctx

shell: build_image
	docker run --rm --name tradfri_shell -it --cap-add SYS_PTRACE --net=host ${TAG} /bin/bash

local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          ${TAG} \
          python /mnt/${JOB}.py -v

local_run_strace: build_strace
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          strace -f -tts 200 python /mnt/${JOB}.py -v

local_run_trad_mqtt:
	docker volume create tradfri-mqtt-data
	docker run -d \
	  --name tradfri-mqtt -c 'local bridge to tradfri' \
	  --volume tradfri-mqtt-data:/data \
	  --env TRADFRI_GATEWAY=tradfri \
	  --env TRADFRI_PSK=`python -c 'from private import *; print hubKey'` \
	  --env MQTT_ADDRESS=tcp://127.0.0.1:1883 \
	  bonan/tradfri-mqtt
