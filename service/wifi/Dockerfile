FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install -y libxml2-dev libxslt1-dev

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py *.n3 *.json *.html ./

EXPOSE 9070

CMD [ "python", "tomatoWifi.py" ]
