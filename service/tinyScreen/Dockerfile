FROM bang6:5000/base_x86

WORKDIR /opt

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY font ./font
COPY anim ./anim
COPY *.py *.html ./

EXPOSE 11013

CMD [ "python", "./tiny_screen.py" ]
