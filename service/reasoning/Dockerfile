FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -U 'https://github.com/drewp/cyclone/archive/python3.zip?v2'

COPY FuXi/ FuXi
RUN pip3 install ./FuXi

RUN pip3 install pytype

COPY *.n3 *.py *.html req* ./
COPY input ./input

EXPOSE 9071

CMD [ "python3", "./reasoning.py" ]
