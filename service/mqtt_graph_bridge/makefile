JOB=mqtt_graph_bridge
PORT=10008

TAG=bang6:5000/${JOB}_x86:latest

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py *.txt tmp_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -rf tmp_ctx


shell: build_image
	docker run --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/mqtt_graph_bridge_x86:latest  /bin/sh

local_run: build_image
	docker run --rm -it --net=host bang6:5000/mqtt_graph_bridge_x86:latest
