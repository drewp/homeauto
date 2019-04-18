JOB=collector
PORT=9072

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py ../../lib/twisted_sse_demo *.py req* tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host ${TAG} /bin/bash

local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          --net=host \
          ${TAG} \
          python sse_collector.py -v

local_run_strace: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          strace -f -tts 200 python /mnt/sse_collector.py -v

local_run_pyspy: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          py-spy -- python /mnt/sse_collector.py


redeploy: build_image
	supervisorctl restart sse_collector_9072

