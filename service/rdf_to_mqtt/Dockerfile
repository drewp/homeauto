FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

COPY *.py *.html *.css *.js ./

EXPOSE 10011:10011

CMD [ "python3", "./mqtt_graph_bridge.py" ]
