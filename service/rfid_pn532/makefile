SERVICE=rfid_pn532

nfc-nim/nfc.nim: nfc-nim/nfc.h
	c2nim/c2nim  nfc-nim/nfc.h

nfc-nim/freefare.nim: nfc-nim/freefare.h
	c2nim/c2nim  nfc-nim/freefare.h

freefare_demo: freefare_demo.nim nfc-nim/nfc.nim nfc-nim/freefare.nim
	nim-0.19.4/bin/nim c -d:nimDebugDlOpen freefare_demo.nim

freefare_demo_run: freefare_demo
	./freefare_demo

rfid: rfid.nim graphserver.nim nfc-nim/nfc.nim nfc-nim/freefare.nim rdf.nim rdf_nodes.nim
	nim-0.19.4/bin/nim c -d:nimDebugDlOpen rfid.nim

rfid_local_run: rfid
	./rfid

test_rdf:
	nim-0.19.4/bin/nim c -r  rdf_test.nim


build_image:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile *.nim *.cfg nfc-nim tmp_ctx
	docker build --network=host -t bang6:5000/$(SERVICE)_x86:latest tmp_ctx
	docker push bang6:5000/$(SERVICE)_x86:latest
	rm -rf tmp_ctx


build_image_pi:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.pi *.nim *.cfg nfc-nim tmp_ctx
	docker build --file Dockerfile.pi --network=host -t bang6:5000/$(SERVICE)_pi:latest tmp_ctx
	docker push bang6:5000/$(SERVICE)_pi:latest
	rm -rf tmp_ctx

shell: build_image
	docker run --name rfid_shell --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/$(SERVICE)_x86:latest  /bin/bash

local_run: build_image
	docker run --name rfid_local --rm -it --net=host bang6:5000/$(SERVICE)_x86:latest



build_graphserver:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.graphserver *.py *.html require* ../../lib/*.py tmp_ctx
	docker build --file Dockerfile.graphserver --network=host -t bang6:5000/rfid_graphserver_x86:latest tmp_ctx
	docker push bang6:5000/rfid_graphserver_x86:latest
	rm -rf tmp_ctx

build_graphserver_pi:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.graphserver.pi *.py *.html require* ../../lib/*.py tmp_ctx
	docker build --file Dockerfile.graphserver.pi --network=host -t bang6:5000/rfid_graphserver_pi:latest tmp_ctx
	docker push bang6:5000/rfid_graphserver_pi:latest
	rm -rf tmp_ctx

local_run_graphserver: build_graphserver
	docker run --name rfid_local_graphserver --rm -it --net=host bang6:5000/rfid_graphserver_x86:latest
