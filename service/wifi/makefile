JOB=wifi
PORT=9070

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py *.n3 *.html req* tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -r tmp_ctx

shell: build_image
	docker run --rm -it --cap-add SYS_PTRACE --net=host ${TAG} /bin/bash

local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} --net=host ${TAG} python3 wifi.py -v

local_run_strace: build_image
	docker run --rm -it -p ${PORT}:${PORT} --cap-add=SYS_PTRACE --net=host ${TAG} strace -f -s 200 python3 wifi.py -v

redeploy: build_image
	supervisorctl restart $(JOB)_$(PORT)
