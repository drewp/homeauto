build_image:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --network=host -t bang6:5000/bluetooth_buttons_x86:latest .
	docker push bang6:5000/bluetooth_buttons_x86:latest

build_image_pi:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --file Dockerfile.pi --network=host -t bang6:5000/bluetooth_buttons_pi:latest .
	docker push bang6:5000/bluetooth_buttons_pi:latest

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/bluetooth_buttons_x86:latest  /bin/sh

local_run:
	docker run --rm -it -p 9107:9107 --net=host bang6:5000/bluetooth_buttons_x86:latest python ./bluetooth_buttons.py -v
