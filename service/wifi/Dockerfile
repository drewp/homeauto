FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install -y libxml2-dev libxslt1-dev

COPY requirements.txt ./
RUN pip3 install -r requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v2'

COPY *.py *.n3 *.html ./

EXPOSE 9070

CMD [ "python3", "wifi.py" ]
