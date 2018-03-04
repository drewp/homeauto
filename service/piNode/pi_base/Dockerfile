FROM resin/rpi-raspbian:jessie

# built static per
# https://resin.io/blog/building-arm-containers-on-any-x86-machine-even-dockerhub/
COPY qemu-arm /usr/bin/qemu-arm

# then do this on build host:
# echo ':arm:M::\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x28\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-arm:' > /proc/sys/fs/binfmt_misc/register

WORKDIR /opt
RUN apt-get update
RUN apt-get install git build-essential python-pip python-numpy python-pillow python-cryptography
RUN apt-get install python-dev zlib1g-dev
