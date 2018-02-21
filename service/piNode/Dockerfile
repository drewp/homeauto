FROM arm32v6/python:2-alpine3.7


WORKDIR /opt
RUN apk add --no-cache git gcc linux-headers musl-dev libffi-dev py2-numpy openssl-dev jpeg-dev py2-cffi py2-cryptography py2-numpy py2-numpy-f2py

COPY requirements.txt ./
RUN pip download --cache-dir /tmp/pip-cache -r requirements.txt

RUN pip install --cache-dir /tmp/pip-cache -r requirements.txt

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

COPY *.py ./
COPY config/ ./config/

# merge this with above
RUN apk add --no-cache libc6-compat

CMD [ "python", "./piNode.py" ]
