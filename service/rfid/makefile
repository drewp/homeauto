SERVICE=rfid

build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile ../../lib/*.py *.py *.txt *.html MFRC522-python tmp_ctx
	docker build --network=host -t bang6:5000/$(SERVICE)_x86:latest tmp_ctx
	docker push bang6:5000/$(SERVICE)_x86:latest
	rm -rf tmp_ctx


build_image_pi:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.pi ../../lib/*.py *.py *.txt *.html MFRC522-python tmp_ctx
	docker build --file Dockerfile.pi --network=host -t bang6:5000/$(SERVICE)_pi:latest tmp_ctx
	docker push bang6:5000/$(SERVICE)_pi:latest
	rm -rf tmp_ctx

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/$(SERVICE)_x86:latest  /bin/sh

local_run:
	docker run --rm -it --net=host bang6:5000/$(SERVICE)_x86:latest
