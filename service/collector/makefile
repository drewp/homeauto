JOB=collector
PORT=9072

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py ../../lib/twisted_sse_demo *.py req* tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -r tmp_ctx

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host ${TAG} /bin/bash

local_run:
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          ${TAG} \
          python /mnt/sse_collector.py -v
