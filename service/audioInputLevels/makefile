build_image:
	docker build --network=host -t bang6:5000/audio_input_levels_x86:latest .
	docker push bang6:5000/audio_input_levels_x86:latest

build_image_pi:
	docker build --file Dockerfile.pi --network=host -t bang6:5000/audio_input_levels_pi:latest .
	docker push bang6:5000/audio_input_levels_pi:latest


shell:
	docker run --rm -it --cap-add SYS_PTRACE -v /tmp/.X11-unix/:/tmp/.X11-unix/ -v /home/drewp/.Xauthority:/root/.Xauthority --net=host bang6:5000/audio_input_levels_x86:latest  /bin/sh

local_run:
	docker run --rm -it --cap-add SYS_PTRACE \
          -v /etc/pulse:/etc/pulse \
          -v /tmp/pulseaudio:/tmp/pulseaudio \
          -v `pwd`:/mnt \
          --net=host \
          bang6:5000/audio_input_levels_x86:latest \
          python /mnt/audioInputLevelsPulse.py --source alsa_input.pci-0000_00_1f.3.analog-stereo -v

local_run_pi:
	docker run --rm -it  -v /etc/pulse:/etc/pulse  -v /tmp/pulseaudio:/tmp/pulseaudio --net=host  bang6:5000/audio_input_levels_pi:latest python ./audioInputLevelsPulse.py --source alsa_input.usb-C-Media_Electronics_Inc._USB_PnP_Sound_Device-00.analog-mono -v
