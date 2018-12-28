FROM bang6:5000/base_x86
RUN apt-get install -y x11-xserver-utils

COPY requirements.txt ./
RUN pip install -r requirements.txt

ADD https://projects.bigasterisk.com/rdfdb/more.tgz ./
RUN tar xvzf more.tgz

COPY *.py ./

EXPOSE 9095

CMD [ "python", "./dpms_service.py" ]
