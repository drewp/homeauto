FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

COPY *.py ./

EXPOSE 11012

CMD [ "python3", "./bluetooth_buttons.py" ]
