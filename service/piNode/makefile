build_image: gather_image_files
	docker build --network host -t bang6:5000/pi_node_pi:latest .
	docker push bang6:5000/pi_node_pi:latest

gather_image_files:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	(cd /my/proj/homeauto/service/arduinoNode; tar czf /my/site/projects/rdfdb/more2.tgz static)

shell:
	docker run -it bang6:5000/pi_node_pi:latest  /bin/bash

local_run:
	docker run -it -p 9059:9059 bang6:5000/pi_node_pi:latest python ./piNode.py -v


push_config:
	docker run -it --net=host -v `pwd`/config:/opt/config bang6:5000/arduino_node python pushConfig.py pi/

redeploy: build_image
	sudo /my/proj/ansible/playbook -l pi -t raspi_io_node
