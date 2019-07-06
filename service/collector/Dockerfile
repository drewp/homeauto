FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install -y vim

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -Ur requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -U 'https://github.com/drewp/cyclone/archive/python3.zip'

COPY stubs ./stubs
COPY *.py req* *.ini ./

EXPOSE 9072

CMD [ "python3", "./sse_collector.py" ]
