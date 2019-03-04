#!/bin/sh
TARGET=x86_64-Linux
CARGS="-I/usr/include/x86_64-linux-gnu  -I/usr/lib/llvm-5.0/lib/clang/5.0.1/include -I/usr/lib/llvm-5.0/lib/"

clang2py -o /opt/pyfreefare-build/nfc.py --target ${TARGET} --clang-args="${CARGS}" -l /usr/lib/x86_64-linux-gnu/libnfc.so -c /opt/pyfreefare/nfc.h

clang2py -o /opt/pyfreefare-build/freefare.py --target ${TARGET} --clang-args="${CARGS}" -l /usr/lib/x86_64-linux-gnu/libfreefare.so -c /opt/pyfreefare/freefare.h
