FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install -y vim

COPY requirements.txt ./
RUN pip3 install -Ur requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip'

COPY stubs ./stubs
COPY twisted_sse_demo ./twisted_sse_demo
COPY *.py req* ./

EXPOSE 9072

CMD [ "python3", "./sse_collector.py" ]
