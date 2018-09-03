FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY twisted_sse_demo ./twisted_sse_demo
COPY *.n3 *.py req* ./
COPY input ./input

EXPOSE 9071

CMD [ "python", "./reasoning.py" ]
