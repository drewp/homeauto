FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py *.html *.css *.js ./

EXPOSE 10008:10008

CMD [ "python", "./mqtt_graph_bridge.py", "-v" ]
