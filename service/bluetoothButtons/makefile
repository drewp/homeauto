build_image:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --network=host -t bang6:5000/bluetooth_buttons_x86:latest .
	docker push bang6:5000/bluetooth_buttons_x86:latest

build_image_pi:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --file Dockerfile.pi --network=host -t bang6:5000/bluetooth_buttons_pi:latest .
	docker push bang6:5000/bluetooth_buttons_pi:latest

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/bluetooth_buttons_x86:latest  /bin/bash

local_run:
	sudo docker run --rm -it --net=host --privileged -v /dev:/dev bang6:5000/bluetooth_buttons_x86:latest 
