JOB=speech_music
PORT=9049

TAG=bang6:5000/${JOB}_x86:latest
TAG_PI=bang6:5000/${JOB}_pi:latest

prep_ctx:
	rm -rf tmp_ctx
	mkdir -p tmp_ctx
	cp -a Dockerfile* ../../lib/*.py *.py *.jade req* *.conf /my/proj/csigen/generator.py tmp_ctx
	mkdir -p tmp_ctx/sound/
	cp '/my/music/entrance/leave.wav' tmp_ctx/sound/
	cp '/my/music/snd/Oxygen/KDE-Im-Highlight-Msg-44100.wav' tmp_ctx/sound/
	cp '/my/music/snd/angel_ogg/angel_question.wav' tmp_ctx/sound/
	cp '/my/music/snd/sampleswap/MELODIC SAMPLES and LOOPS/Acid Jazz Trumpet Lines/acid-jazz-trumpet-11.wav' tmp_ctx/sound/
	cp '/my/music/snd/troy_and_abed_in_the_morning.wav' tmp_ctx/sound/
	cp '/my/music/snd/bxfr/beep1.wav' tmp_ctx/sound/
	cp '/my/music/snd/bxfr/beep2.wav' tmp_ctx/sound/

build_image: prep_ctx
	docker build --network=host -t ${TAG} tmp_ctx
	docker push ${TAG}
	rm -rf tmp_ctx

build_image_pi: prep_ctx
	docker build --network=host --file=tmp_ctx/Dockerfile.pi -t ${TAG_PI} tmp_ctx
	docker push ${TAG_PI}
	rm -rf tmp_ctx

shell:
	docker run --rm -it --cap-add SYS_PTRACE --net=host -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} /bin/bash

pactl_test:
	docker run --rm -it --cap-add SYS_PTRACE --net=host -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} pactl stat

paplay_test_that_is_loud:
	docker run --rm -it --cap-add SYS_PTRACE --net=host -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} paplay /usr/local/lib/python2.7/dist-packages/pygame/examples/data/whiff.wav

pygame_test:
	docker run --rm -it --cap-add SYS_PTRACE --net=host -e SDL_AUDIOSERVER=pulseaudio -v /tmp/pulseaudio:/tmp/pulseaudio ${TAG} python -c  'import os; print os.environ; import pygame.mixer; pygame.mixer.init()'


local_run:
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
          -v /tmp/pulseaudio:/tmp/pulseaudio \
          ${TAG} \
          python /mnt/speechMusic.py -v

local_run_strace:
	docker run --rm -it -p ${PORT}:${PORT} \
          -v `pwd`:/mnt \
          --net=host \
-v /tmp/pulseaudio:/tmp/pulseaudio \
          --cap-add SYS_PTRACE \
-e SDL_AUDIOSERVER=pulse \
          ${TAG} \
          strace -f -tts 200 python /mnt/speechMusic.py -v
