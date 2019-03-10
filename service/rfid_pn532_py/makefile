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


rfid_build_image_pi: pyfreefare-build-pi/nfc.py pyfreefare-build-pi/freefare.py
	docker build --file Dockerfile.pi -t bang6:5000/rfid_pn532_py_pi:latest .
	docker push bang6:5000/rfid_pn532_py_pi:latest

# test on pi:
# docker pull bang6:5000/rfid_pn532_py_pi:latest && docker run -it --rm --privileged --name rfid_shell bang6:5000/rfid_pn532_py_pi:latest nose2-3 tags_test
