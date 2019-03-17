JOB=store
PORT=10014

TAG=bang6:5000/${JOB}_x86:latest

push_x86:
	docker push ${TAG}

build_x86:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py *.txt *.html tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	rm -rf tmp_ctx

build_image: build_x86 push_x86

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host $(TAG) /bin/sh

local_run: build_x86
	docker run --rm -it --net=host -v `pwd`/index.html:/opt/index.html -v `pwd`:/opt/homeauto_store bang6:5000/store_x86:latest python ./store.py -v
