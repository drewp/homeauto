FROM bang6:5000/base_x86

WORKDIR /opt


        apt install libsdl-mixer-dev
        apt install libsdl-mixer1.2-dev
wget https://www.pygame.org/ftp/pygame-1.9.6.tar.gz
   34  tar xvzf pygame-1.9.6.tar.gz
        35  cd pygame-1.9.6
        python3 setup.py  install
python3 -c 'import pygame; print(pygame.__version__, pygame.__file__); pygame.mixer.init()'


RUN touch need-new-update
RUN apt-get update
RUN apt-get install --yes libopenal1 libogg0 pulseaudio-utils festival sox python-pygame
COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

ENV SDL_AUDIODRIVER pulse
ENV PULSE_SERVER /tmp/pulseaudio
COPY pulse-client.conf /etc/pulse/client.conf
COPY *.py req* *.jade ./

EXPOSE 9049

CMD [ "python3", "./playSound.py" ]
