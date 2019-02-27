
pyfreefare_build_image: Dockerfile.pyfreefare
	docker build --file Dockerfile.pyfreefare -t pyfreefare_build:latest .

pyfreefare/nfc.py: pyfreefare_build_image pyfreefare/nfc.h
	docker run --rm --net=host -v /my/proj/homeauto/service/rfid_pn532_py/pyfreefare:/opt/pyfreefare --name pyfreefare_build pyfreefare_build:latest \
          clang2py -o /opt/pyfreefare/nfc.py \
              --target x86_64-Linux \
              --clang-args="-I=/usr/include/x86_64-linux-gnu  -I/usr/lib/llvm-6.0/lib/clang/6.0.0/include -I/usr/lib/llvm-6.0/lib/ -v -xc" \
              /opt/pyfreefare/nfc.h

pyfreefare/freefare.py: pyfreefare_build_image pyfreefare/freefare.py
	docker run --rm --net=host -v /my/proj/homeauto/service/rfid_pn532_py/pyfreefare:/opt/pyfreefare --name pyfreefare_build pyfreefare_build:latest \
          clang2py -o /opt/pyfreefare/freefare.py \
              --target x86_64-Linux \
              --clang-args="-I=/usr/include/x86_64-linux-gnu  -I/usr/lib/llvm-6.0/lib/clang/6.0.0/include -I/usr/lib/llvm-6.0/lib/ -v -xc"  \
              /opt/pyfreefare/freefare.h

#pyfreefare/nfc.py pyfreefare/freefare.py
test_tags: tags.py tags_test.py 
	PYTHONPATH=pyfreefare nose2-3 tags_test
