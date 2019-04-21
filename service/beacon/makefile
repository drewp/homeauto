build_image_x86:
	docker build --network=host -t bang6:5000/beacon_x86:latest .
	docker push bang6:5000/beacon_x86:latest

build_image_pi:
	docker build --file Dockerfile.pi --network=host -t bang6:5000/beacon_pi:latest .
	docker push bang6:5000/beacon_pi:latest

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host bang6:5000/beacon_x86:latest  /bin/sh

local_run:
	docker run --rm -it -p 10004:10004 --net=host bang6:5000/beacon_x86:latest

fresh_sudo:
	sudo -v
redeploy_x86: fresh_sudo build_image_x86
	sudo /my/proj/ansible/playbook -l dash,bang  -t rfid
	supervisorctl -s http://$(RUNHOST):9001/ restart $(JOB)_$(PORT)
