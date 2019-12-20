from invoke import task, Collection

import sys
sys.path.append('/my/proj/release')
from serv_tasks import serv_tasks

ns = Collection()
serv_tasks(ns, 'serv.n3', 'speechmusic_dash')


'''
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
	  --mount type=tmpfs,destination=/tmp,tmpfs-size=52428800 \
          -v /tmp/pulseaudio:/tmp/pulseaudio \
          ${TAG} \
          python playSound.py -v
'''
