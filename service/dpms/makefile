build_image:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --network=host -t bang6:5000/dpms_x86:latest .
	docker push bang6:5000/dpms_x86:latest

build_image_pi:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	docker build --file Dockerfile.pi --network=host -t bang6:5000/dpms_pi:latest .
	docker push bang6:5000/dpms_pi:latest


shell:
	docker run --rm -it --cap-add SYS_PTRACE -v /tmp/.X11-unix/:/tmp/.X11-unix/ -v /home/drewp/.Xauthority:/root/.Xauthority --net=host bang6:5000/dpms_x86:latest  /bin/sh

local_run:
	docker run --rm -it -v /tmp/.X11-unix/:/tmp/.X11-unix/ -v /home/drewp/.Xauthority:/root/.Xauthority -p 9095:9095 --net=host bang6:5000/dpms python ./dpms_service.py 
