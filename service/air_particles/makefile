build_image:
	docker build --network=host -t bang6:5000/air_particles_x86:latest .
	docker push bang6:5000/air_particles_x86:latest

build_image_pi:
	docker build --file Dockerfile.pi --network=host -t bang6:5000/air_particles_pi:latest .
	docker push bang6:5000/air_particles_pi:latest


shell:
	docker run --rm -it --cap-add SYS_PTRACE --device=/dev/ttyUSB0 --net=host bang6:5000/air_particles_x86:latest  /bin/sh

local_run:
	docker run --rm -it --cap-add SYS_PTRACE --device=/dev/ttyUSB0 --net=host bang6:5000/air_particles_x86:latest python air_particles.py local
