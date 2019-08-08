FROM bang6:5000/base_pi

# super slow build
RUN pip install grpcio==1.22.0

WORKDIR /opt

COPY requirements.txt ./

RUN pip install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

# when we go to py3:
## not sure why this doesn't work from inside requirements.txt
#RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

COPY *.py ./
COPY config/ ./config/

EXPOSE 9059

CMD [ "python", "./piNode.py" ]
