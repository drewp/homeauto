FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install --yes libpulse0
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py req* ./

CMD [ "python", "./audioInputLevelsPulse.py", "--source", "alsa_input.pci-0000_00_1f.3.analog-stereo" ]
