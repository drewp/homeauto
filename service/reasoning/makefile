JOB=reasoning
PORT=9071

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py ../../lib/twisted_sse_demo *.py *.n3 *.html input req* tmp_ctx
	rsync -a input tmp_ctx/
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -r tmp_ctx

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host ${TAG}  /bin/bash

local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          ${TAG} \
          python /mnt/${JOB}.py -iro

redeploy: build_image
	supervisorctl restart $(JOB)_$(PORT)

