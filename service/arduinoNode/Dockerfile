FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY arduino-libraries/ ./arduino-libraries/
COPY *.py ./
COPY static/ ./static/

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

EXPOSE 9059

CMD [ "python", "./arduinoNode.py" ]
