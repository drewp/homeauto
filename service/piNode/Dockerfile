FROM bang6:5000/base_pi

# fold these into base image
RUN apt install -y vim

WORKDIR /opt

COPY requirements_*.txt ./
RUN pip3 install -v --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements_slow.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements_external.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements_local.txt

## not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

COPY *.py ./
COPY config/ ./config/

EXPOSE 9059

CMD [ "python3", "./piNode.py" ]
