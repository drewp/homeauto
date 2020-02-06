#!/bin/sh
set -x
proc=`uname --processor`
if [ "$proc" = "armv7l" ]; then
    ARCH=arm-linux-gnueabihf
    TARGET=armv7l
else
    ARCH=x86_64-linux-gnu
    TARGET=x86_64-Linux
fi
CARGS="-I/usr/include/${ARCH} -I/usr/lib/llvm-5.0/lib/clang/5.0.1/include -I/usr/lib/llvm-5.0/lib/"
clang2py -o /opt/pyfreefare-build/nfc.py --target ${TARGET} --clang-args="${CARGS}" -l /usr/lib/${ARCH}/libnfc.so --comments /opt/pyfreefare/nfc.h

PYTHONPATH=/opt/pyfreefare-build clang2py -o /opt/pyfreefare-build/freefare.py --target ${TARGET} --clang-args="${CARGS}" -l /usr/lib/${ARCH}/libfreefare.so --comments --module nfc /opt/pyfreefare/freefare.h
