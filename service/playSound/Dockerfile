FROM bang6:5000/base_x86

WORKDIR /opt

RUN touch need-new-update
RUN apt-get update

RUN apt-get install --yes libopenal1 libogg0 pulseaudio-utils python-pygame

COPY pulse-client.conf /etc/pulse/client.conf
COPY *.py *.wav ./

ENV UNAME pulseuser
RUN export UNAME=$UNAME UID=501 GID=501 && \
    mkdir -p "/home/${UNAME}" && \
    echo "${UNAME}:x:${UID}:${GID}:${UNAME} User,,,:/home/${UNAME}:/bin/bash" >> /etc/passwd && \
    echo "${UNAME}:x:${UID}:" >> /etc/group && \
    mkdir -p /etc/sudoers.d && \
    echo "${UNAME} ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/${UNAME} && \
    chmod 0440 /etc/sudoers.d/${UNAME} && \
    chown ${UID}:${GID} -R /home/${UNAME} && \
    gpasswd -a ${UNAME} audio
# USER $UNAME

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

COPY run.sh ./

ENV HOME /home/pulseuser
RUN mkdir -p ${HOME}/.config/pulse
RUN chown pulseuser ${HOME}

ENV PULSE_SERVER 172.17.0.1

EXPOSE 9049

CMD [ "python3", "./playSound.py" ]
