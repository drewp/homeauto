JOB=tiny_screen
PORT=10013

TAG=bang6:5000/${JOB}_x86:latest
TAG_PI=bang6:5000/${JOB}_pi:latest

push:
	docker push ${TAG}

build_x86:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py *.txt *.html anim font tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	rm -rf tmp_ctx

build_image: build_x86 push

build_pi:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.pi ../../lib/*.py *.py *.txt *.html anim font tmp_ctx
	docker build -f Dockerfile.pi --network=host -t ${TAG_PI} tmp_ctx
	rm -rf tmp_ctx

build_image_pi: build_pi push

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host $(TAG) /bin/sh

local_run: build_x86
	docker run --rm -it --net=host -e DISPLAY=$(DISPLAY) -e HOME=$(HOME) -v $(HOME):$(HOME) -v /tmp/.X11-unix:/tmp/.X11-unix -v `pwd`/index.html:/opt/index.html bang6:5000/tiny_screen_x86:latest python ./tiny_screen.py -v -x
