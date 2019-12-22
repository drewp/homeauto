FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get update
RUN apt-get install -y openjdk-11-jre-headless unzip

RUN wget https://github.com/marytts/marytts/releases/download/v5.2/marytts-5.2.zip && \
        unzip marytts-5.2.zip && \
        rm marytts-5.2.zip

RUN wget -O ./cast https://github.com/barnybug/go-cast/releases/download/0.1.0/cast-linux-amd64 && chmod 755 ./cast

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

COPY *.py *.html ./

EXPOSE 9010

CMD [ "python3", "./announce.py" ]
