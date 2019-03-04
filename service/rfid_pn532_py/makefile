 
pyfreefare_build_image_x86: Dockerfile.pyfreefare.x86
	docker build --file Dockerfile.pyfreefare.x86 -t pyfreefare_build_x86:latest .

pyfreefare_build_image_pi: Dockerfile.pyfreefare.pi
	docker build --file Dockerfile.pyfreefare.pi -t pyfreefare_build_pi:latest .

pyfreefare-build-x86/nfc.py: pyfreefare_build_image_x86 pyfreefare/nfc.h pyfreefare/freefare.h
	docker run --rm --net=host \
          -v `pwd`/pyfreefare:/opt/pyfreefare \
          -v `pwd`/pyfreefare-build-x86:/opt/pyfreefare-build \
          --name pyfreefare_build pyfreefare_build_x86:latest

#pyfreefare/nfc.py pyfreefare/freefare.py
test_tags: tags.py tags_test.py 
	PYTHONPATH=pyfreefare nose2-3 tags_test
