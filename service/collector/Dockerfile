FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt
RUN pip install py-spy

COPY twisted_sse_demo ./twisted_sse_demo
COPY *.py req* ./

EXPOSE 9072

CMD [ "python", "./sse_collector.py" ]
