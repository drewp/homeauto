JOB=environment
PORT=9075

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py ../../lib/twisted_sse_demo *.n3 *.html *.py req* tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -r tmp_ctx

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host ${TAG} /bin/bash

local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
	  -v /my/proj/rdfdb/rdfdb:/usr/local/lib/python2.7/dist-packages/rdfdb \
          --net=host \
          ${TAG} \
          python environment.py -v

local_run_strace: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          strace -f -tts 200 python environment.py -v

local_run_pyspy: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          --cap-add SYS_PTRACE \
          ${TAG} \
          py-spy -- python environment.py


redeploy: build_image
	supervisorctl restart $(JOB)_$(PORT)

