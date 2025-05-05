FROM node:20

COPY . /app

WORKDIR /app

# generate keys for api
RUN ./generate_keys.sh

RUN npm install -g npm@9.5.1 pm2 typescript tsc-watch

# build the api and the ui
RUN cd /app/api && npm install
RUN cd /app/ui && npm install
