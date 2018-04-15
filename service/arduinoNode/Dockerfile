FROM alpine:3.7

WORKDIR /opt
RUN apk add --no-cache gcc build-base jpeg-dev lapack-dev libffi-dev linux-headers musl-dev openssl-dev py2-cffi py2-numpy py2-numpy-f2py py2-pip python2 python2-dev indent 

COPY requirements.txt ./
RUN pip download --cache-dir /tmp/pip-cache -r requirements.txt
RUN pip install --cache-dir /tmp/pip-cache -r requirements.txt

COPY *.py ./
COPY static/ ./static/

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

EXPOSE 9059

CMD [ "python", "./arduinoNode.py" ]
