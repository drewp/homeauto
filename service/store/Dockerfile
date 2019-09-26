FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

COPY *.py *.html ./

EXPOSE 10015

CMD [ "python", "./store.py" ]
