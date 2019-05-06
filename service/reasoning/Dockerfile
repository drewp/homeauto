FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

COPY *.n3 *.py *.html req* ./
COPY input ./input

EXPOSE 9071

CMD [ "python", "./reasoning.py" ]
