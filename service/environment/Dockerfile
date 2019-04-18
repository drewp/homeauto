FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

# upstream this
RUN apt-get install -y tzdata

COPY twisted_sse_demo ./twisted_sse_demo
COPY *.py req* *.n3 *.html ./


EXPOSE 9075

CMD [ "python", "environment.py" ]
