FROM bang6:5000/base_pi

# super slow build
RUN pip install grpcio==1.22.0

WORKDIR /opt

COPY requirements.txt ./

RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
## not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

# fold these into requirements.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple "devices_shared==0.4.0"
RUN apt install -y vim

COPY *.py ./
COPY config/ ./config/

EXPOSE 9059

CMD [ "python3", "./piNode.py" ]
