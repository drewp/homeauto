FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt
RUN apt-get install -y arduino-mk indent

COPY arduino-libraries/ ./arduino-libraries/
COPY *.py ./
COPY static/ ./static/
COPY config/ ./config/

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

EXPOSE 9059

CMD [ "python", "./arduinoNode.py" ]
