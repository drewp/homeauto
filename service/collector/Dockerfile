FROM bang5:5000/base_basic

WORKDIR /opt

RUN echo 2021-08-26 && apt-get update
RUN apt-get install -y vim net-tools iputils-ping git

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -Ur requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip'

COPY *.py *.html req* *.ini ./

EXPOSE 9072

CMD [ "python3", "./collector.py" ]
