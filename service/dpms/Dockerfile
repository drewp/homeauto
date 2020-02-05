FROM bang6:5000/base_x86
RUN apt-get install -y x11-xserver-utils

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
# not sure why this doesn't work from inside requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

COPY *.py ./

EXPOSE 9095

CMD [ "python3", "./dpms_service.py" ]
