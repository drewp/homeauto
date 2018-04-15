build_image:
	(cd /my/proj/homeauto/lib; tar czf /my/site/projects/rdfdb/more.tgz *.py)
	(cd /my/proj/homeauto/service/arduinoNode; tar czf /my/site/projects/rdfdb/more2.tgz static)
	ssh pi@garage6 mkdir -p /tmp/piNode/
	rsync -av --exclude=lib --exclude=pi_base --delete ./ pi@garage6:/tmp/piNode/
	ssh pi@garage6 docker build -t bang6:5000/pi_node /tmp/piNode/
	ssh pi@garage6 docker push bang6:5000/pi_node

shell:
	docker run -it bang6:5000/pi_node  /bin/sh

local_run:
	docker run -it -p 9059:9059 bang6:5000/pi_node python ./piNode.py -v


push_config:
	bin/python ../arduinoNode/pushConfig.py pi/
