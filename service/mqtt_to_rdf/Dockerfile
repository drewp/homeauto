FROM bang5:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip3 uninstall --yes enum34

RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'
RUN pip3 install -U attrs

COPY *.py *.html *.css *.js *.n3 ./
COPY build/bundle.js build/

EXPOSE 10018:10018

CMD [ "python3", "./mqtt_to_rdf.py" ]
