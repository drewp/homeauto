FROM bang6:5000/base_nim_x86

WORKDIR /opt

RUN apt-get install -y libnfc5 libfreefare0 libnfc-dev libfreefare-dev && \
  ln -sf libnfc.so.5 /usr/lib/x86_64-linux-gnu/libnfc.so && \
  ln -sf libfreefare.so.0 /usr/lib/x86_64-linux-gnu/libfreefare.so

COPY *.nim *.cfg ./
COPY nfc-nim/ nfc-nim/

RUN nim c -d:nimDebugDlOpen rfid.nim

ENV LIBNFC_DEFAULT_DEVICE="pn532_i2c:/dev/i2c-1"

EXPOSE 10012

CMD ["./rfid"]
