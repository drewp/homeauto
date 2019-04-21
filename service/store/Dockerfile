FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py *.html ./

EXPOSE 10015

CMD [ "python", "./store.py" ]
