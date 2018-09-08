JOB=tradfri
PORT=10009

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py req* pytradfri libcoap tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -rf tmp_ctx

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host ${TAG} /bin/bash

local_run:
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          ${TAG} \
          python /mnt/${JOB}.py -v

local_run_strace:
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          strace -f -tts 200 python /mnt/${JOB}.py -v
