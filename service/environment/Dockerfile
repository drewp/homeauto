FROM bang6:5000/base_x86

WORKDIR /opt

# upstream this
RUN apt-get install -y tzdata

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -U 'https://github.com/drewp/cyclone/archive/python3.zip?v2'

COPY *.py req* *.n3 *.html ./


EXPOSE 9075

CMD [ "python3", "environment.py" ]
