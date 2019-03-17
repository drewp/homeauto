FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py *.html ./

EXPOSE 11014

CMD [ "python", "./store.py" ]
