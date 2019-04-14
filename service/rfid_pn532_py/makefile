SERVICE=rfid_pn532_py
JOB=rfid
PORT=10012
RUNHOST=frontdoor

pyfreefare-build-x86/nfc.py: Dockerfile.pyfreefare.x86 pyfreefare/nfc.h pyfreefare/freefare.h build_ctypes_modules.sh
	docker build --file Dockerfile.pyfreefare.x86 -t pyfreefare_build_x86:latest .
	docker run --rm --net=host \
          -v `pwd`/pyfreefare:/opt/pyfreefare \
          -v `pwd`/pyfreefare-build-x86:/opt/pyfreefare-build \
          --name pyfreefare_build pyfreefare_build_x86:latest

pyfreefare-build-pi/nfc.py: Dockerfile.pyfreefare.pi pyfreefare/nfc.h pyfreefare/freefare.h build_ctypes_modules.sh
	docker build --file Dockerfile.pyfreefare.pi -t pyfreefare_build_pi:latest .
	docker run --rm --net=host \
          -v `pwd`/pyfreefare:/opt/pyfreefare \
          -v `pwd`/pyfreefare-build-pi:/opt/pyfreefare-build \
          --name pyfreefare_build pyfreefare_build_pi:latest

#pyfreefare/nfc.py pyfreefare/freefare.py
test_tags: tags.py tags_test.py 
	PYTHONPATH=pyfreefare-build-x86 nose2-3 tags_test


build_image_x86: pyfreefare-build-x86/nfc.py pyfreefare-build-x86/freefare.py Dockerfile.x86
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.x86 ../../lib/*.py *.py *.txt *.html pyfreefare-build-x86 tmp_ctx
	docker build --network=host --file Dockerfile.x86 -t bang6:5000/$(SERVICE)_x86:latest tmp_ctx
	docker push bang6:5000/$(SERVICE)_x86:latest

build_image_pi: pyfreefare-build-pi/nfc.py pyfreefare-build-pi/freefare.py Dockerfile.pi
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile.pi ../../lib/*.py *.py *.txt *.html pyfreefare-build-pi tmp_ctx
	docker build --network=host --file Dockerfile.pi -t bang6:5000/$(SERVICE)_pi:latest tmp_ctx
	docker push bang6:5000/$(SERVICE)_pi:latest

run_local_x86: build_image_x86
	docker run -it --rm --privileged --net=host --hostname=testhost --cap-add=SYS_PTRACE --name $(JOB)_run bang6:5000/$(SERVICE)_x86:latest python3 rfid.py -v


# test on pi:
# docker pull bang6:5000/rfid_pn532_py_pi:latest && docker run -it --rm --privileged --name rfid_shell bang6:5000/rfid_pn532_py_pi:latest nose2-3 tags_test

fresh_sudo:
	sudo -v
redeploy: fresh_sudo build_image_pi
	sudo /my/proj/ansible/playbook -l $(RUNHOST) -t rfid
	supervisorctl -s http://$(RUNHOST):9001/ restart $(JOB)_$(PORT)

nginx_local:
	nginx -c `pwd`/local.conf

