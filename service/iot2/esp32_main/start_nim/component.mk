#
# "main" pseudo-component makefile.
#
# (Uses default behaviour of compiling all source files in directory, adding 'include' to include path.)

COMPONENT_SRCDIRS := . ../../build/nimcache
COMPONENT_OBJS := @miot2_esp32.nim.o
COMPONENT_OWNBUILDTARGET=build

build:
	echo espbuild

clean:
	echo espclean
