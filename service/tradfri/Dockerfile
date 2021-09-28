FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install -y autoconf automake libtool
## this is https://github.com/ggravlingen/pytradfri/blob/master/script/install-coap-client.sh
#RUN \
#git clone --depth 1 --recursive -b dtls https://github.com/home-assistant/libcoap.git \
#&& cd libcoap \
#&& ./autogen.sh \
#&& ./configure --disable-documentation --disable-shared --without-debug CFLAGS="-D COAP_DEBUG_FD=stderr" \
#&& make \
#&& make install


COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -U 'https://github.com/drewp/cyclone/archive/python3.zip?v2'


COPY *.py req* ./

EXPOSE 10009

CMD [ "python3", "./tradfri.py" ]
