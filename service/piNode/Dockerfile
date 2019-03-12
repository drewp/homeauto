FROM bang6:5000/base_pi

# super slow build
RUN pip install grpcio==1.18.0

COPY requirements.txt ./

RUN pip install -r requirements.txt

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

ADD https://projects.bigasterisk.com/rdfdb/more2.tgz ./
RUN tar xvzf more2.tgz

COPY *.py ./
COPY config/ ./config/

CMD [ "python", "./piNode.py" ]
