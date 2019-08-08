FROM bang6:5000/base_x86

WORKDIR /opt

RUN apt-get install -y arduino-mk indent

COPY requirements.txt ./
RUN pip install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

COPY arduino-libraries/ ./arduino-libraries/
COPY *.py ./
COPY config/ ./config/

EXPOSE 9059

CMD [ "python", "./arduinoNode.py" ]
