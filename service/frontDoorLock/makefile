JOB=front_door_lock
PORT=10011

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py *.txt *.html tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -rf tmp_ctx


shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/$(JOB)_x86:latest  /bin/sh

local_run:
	docker run --rm -it --net=host -v `pwd`/index.html:/opt/index.html bang6:5000/$(JOB)_x86:latest python ./front_door_lock.py 
