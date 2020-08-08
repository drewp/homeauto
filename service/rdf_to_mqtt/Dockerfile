FROM bang5:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'
RUN pip3 install -U attrs

COPY *.py *.html *.js ./

EXPOSE 10011:10011

CMD [ "python3", "./rdf_to_mqtt.py", "-v" ]
