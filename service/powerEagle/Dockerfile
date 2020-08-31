FROM bang5:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./

RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

COPY *.py *.html ./

EXPOSE 10016

CMD [ "python3", "reader.py" ]
