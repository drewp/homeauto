FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get update
RUN apt-get install --yes libopenal1 libogg0 pulseaudio-utils python-pygame festival sox
COPY requirements.txt ./
RUN pip install -r requirements.txt

ENV SDL_AUDIODRIVER pulse
ENV PULSE_SERVER /tmp/pulseaudio
COPY pulse-client.conf /etc/pulse/client.conf
COPY *.py req* *.jade ./
RUN mkdir /sounds

EXPOSE 9049

CMD [ "python", "./speechMusic.py" ]
