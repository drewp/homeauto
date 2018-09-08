FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY pytradfri pytradfri
COPY libcoap libcoap
COPY *.py req* ./

EXPOSE 10009

CMD [ "python", "./tradfri.py" ]
