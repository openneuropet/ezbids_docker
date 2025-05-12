FROM node:20

WORKDIR /ui

# explicitly critical
COPY .env /ui/.env

# Explicitly copy package files
COPY package.json package-lock.json ./

# Explicitly set environment to development to ensure devDependencies are installed
ENV NODE_ENV=development

# Explicitly install dependencies
RUN npm install

# Explicitly copy the rest of your UI files
COPY . .

# Explicitly copy entrypoint.sh and set executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/entrypoint.sh"]
