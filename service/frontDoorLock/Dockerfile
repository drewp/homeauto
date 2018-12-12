FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py *.html *.css *.js ./

EXPOSE 10011:10011

CMD [ "python", "./front_door_lock.py", "-v" ]
