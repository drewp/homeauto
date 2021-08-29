FROM bang5:5000/base_basic

WORKDIR /opt

RUN echo 2021-08-26 && apt-get update
RUN apt-get install -y git
COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt

COPY package.json5 pnpm-lock.yaml  ./
RUN pnpm install

COPY tsconfig.json rollup.config.js ./
COPY src/ ./src
RUN pnpm build

COPY *.py *.html ./
COPY conf/ ./conf

CMD [ "python3", "./mqtt_to_rdf.py", "-v" ]
