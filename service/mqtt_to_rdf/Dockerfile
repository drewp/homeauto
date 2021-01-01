FROM bang5:5000/base_x86

WORKDIR /opt

RUN apt-get update
RUN apt-get remove -y nodejs
RUN apt-get install -y wget xz-utils && \
    wget --output-document=node.tar.xz https://nodejs.org/dist/v14.15.3/node-v14.15.3-linux-x64.tar.xz && \
    tar xf node.tar.xz && \
    ln -s node*x64 nodejs

ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/workspace/nodejs/bin
RUN /opt/nodejs/bin/node /opt/nodejs/bin/npm install -g pnpm \
    && ln -s /opt/nodejs/bin/node /usr/local/bin/node \
    && ln -s /opt/nodejs/bin/pnpm /usr/local/bin/pnpm

RUN pip3 uninstall --yes enum34
RUN pip3 install -U attrs

COPY requirements.txt ./
RUN pip3 install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
RUN pip3 install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'

COPY package.json5 pnpm-lock.yaml  ./
RUN pnpm install

COPY tsconfig.json rollup.config.js ./
COPY src/ ./src
RUN pnpm build

COPY *.py *.html ./
COPY conf/ ./conf

CMD [ "python3", "./mqtt_to_rdf.py", "-v" ]
