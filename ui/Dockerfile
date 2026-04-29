FROM node:20

COPY . /ui
WORKDIR /ui

RUN npm install
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="$HOME/.deno/bin:$PATH"


COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
