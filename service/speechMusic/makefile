JOB=speech_music
PORT=9049

TAG=bang6:5000/${JOB}_x86:latest
TAG_PI=bang6:5000/${JOB}_pi:latest

prep_ctx:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile* ../../lib/*.py *.py *.jade req* *.conf /my/proj/csigen/generator.py tmp_ctx

build_image: prep_ctx
	docker build --network=host -t ${TAG} tmp_ctx

push_image: build_image
	docker push ${TAG}


build_image_pi: prep_ctx
	docker build --network=host --file=tmp_ctx/Dockerfile.pi -t ${TAG_PI} tmp_ctx

push_image_pi: build_image_pi
	docker push ${TAG_PI}

shell: build_image
	docker run --rm -it \
	  --cap-add SYS_PTRACE \
	  --name=$(JOB)_shell \
	  --mount type=tmpfs,destination=/tmp,tmpfs-size=52428800 \
	   --net=host \
	  -v /tmp/pulseaudio:/tmp/pulseaudio \
	  ${TAG} \
	  /bin/bash

pactl_test: build_image
	docker run --rm -it --cap-add SYS_PTRACE --net=host -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} pactl stat

paplay_test_that_is_loud: build_image
	docker run --rm -it --cap-add SYS_PTRACE --net=host -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} paplay /usr/local/lib/python2.7/dist-packages/pygame/examples/data/whiff.wav

pygame_test: build_image
	docker run --rm -it --cap-add SYS_PTRACE --net=host -e SDL_AUDIOSERVER=pulseaudio -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} python -c  'import os; print os.environ; import pygame.mixer; pygame.mixer.init()'


local_run: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          --name=$(JOB)_local \
          --net=host \
	  --mount type=tmpfs,destination=/sounds,tmpfs-size=52428800 \
          -v /tmp/pulseaudio:/tmp/pulseaudio \
          ${TAG} \
          python speechMusic.py -v

local_run_strace: build_image
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --name=$(JOB)_local \
          --net=host \
	  -v /tmp/pulseaudio:/tmp/pulseaudio \
	  --mount type=tmpfs,destination=/sounds,tmpfs-size=52428800 \
          --cap-add SYS_PTRACE \
          ${TAG} \
          strace -f -tts 200 python /mnt/speechMusic.py -v

fresh_sudo:
	sudo -v

redeploy: fresh_sudo push_image push_image_pi
	sudo /my/proj/ansible/playbook -l with_speakers -t $(JOB)
	supervisorctl -s http://dash:9001/ restart $(JOB)_$(PORT)
	supervisorctl -s http://slash:9001/ restart $(JOB)_$(PORT)
	supervisorctl -s http://bed:9001/ restart $(JOB)_$(PORT)
	supervisorctl -s http://living:9001/ restart $(JOB)_$(PORT)
	supervisorctl -s http://kitchen:9001/ restart $(JOB)_$(PORT)

