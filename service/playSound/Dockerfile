FROM bang6:5000/base_x86

WORKDIR /opt


#RUN apt-get install -y libsdl-mixer-dev libsdl-mixer1.2-dev
# wget https://www.pygame.org/ftp/pygame-1.9.6.tar.gz
# 34  tar xvzf pygame-1.9.6.tar.gz
# 35  cd pygame-1.9.6
# python3 setup.py  install
# python3 -c 'import pygame; print(pygame.__version__, pygame.__file__); pygame.mixer.init()'


RUN touch need-new-update
RUN apt-get update
RUN apt-get install --yes libopenal1 libogg0 pulseaudio-utils python-pygame
COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

ENV SDL_AUDIODRIVER pulse
COPY pulse-client.conf /etc/pulse/client.conf
COPY *.py ./

# ENV UNAME pulseuser
# RUN export UNAME=$UNAME UID=501 GID=501 && \
#     mkdir -p "/home/${UNAME}" && \
#     echo "${UNAME}:x:${UID}:${GID}:${UNAME} User,,,:/home/${UNAME}:/bin/bash" >> /etc/passwd && \
#     echo "${UNAME}:x:${UID}:" >> /etc/group && \
#     mkdir -p /etc/sudoers.d && \
#     echo "${UNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/${UNAME} && \
#     chmod 0440 /etc/sudoers.d/${UNAME} && \
#     chown ${UID}:${GID} -R /home/${UNAME} && \
#     gpasswd -a ${UNAME} audio
# USER $UNAME

EXPOSE 9049

CMD [ "python3", "./playSound.py" ]
