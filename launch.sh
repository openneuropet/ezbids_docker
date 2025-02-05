#!/usr/bin/env bash

# This is the main entry point launching a local/on premises install of ezBIDS.
# Environment variables are loaded from the .env file, then either an SSL HTTPS
# Nginx routed version of ezBIDS is launched or a plain "develoment" version using
# docker's built in network. It's recommended to use the HTTPS version as browsers 
# are getting more and more particular about CORS (Cross Origin Requests).

# If this setup is being run locally and does not require an SSL certificate signed
# by an external authority one can run `create_self_signed_certs.sh` before this 
# script to automatically generate and locate those certificates into the nginx/ssl/ 
# folder.

# check to see if a .env file exists
if [ -f .env ]; then
    echo ".env file exists, loading environment variables from .env file"
else
    echo ".env file does not exist, copying example.env to .env"
    cp example.env .env
fi

# load the environment variables from the .env file
source .env

echo "Setting Environment Variables from .env file:"
# display the environment variables read in from .env, could be a gotcha if 
# the user is unclear about if the .env variables are being used. The .env variables
# will override environment variables set in the shell as they're set once this script 
# is run.
while read line
do
  # if line does not start with # then echo the line
  if [[ $line != \#* ]]; then
    if [[ $line != "" ]]; then
      echo "    ${line}"
    fi
  fi
done < .env

if [ $BRAINLIFE_DEVELOPMENT == true ]; then
  # enable or disable debugging output
  set -ex
else
  set -e
fi

# Check Node.js version
REQUIRED_NODE_VERSION="16"
CURRENT_NODE_VERSION=$(node -v | cut -d '.' -f 1 | sed 's/v//')

if [ "$CURRENT_NODE_VERSION" -ne "$REQUIRED_NODE_VERSION" ]; then
    echo "Warning: You are using Node.js version $CURRENT_NODE_VERSION. It is recommended to use version $REQUIRED_NODE_VERSION."
    echo "Please switch to Node.js version $REQUIRED_NODE_VERSION."
fi

# build local changes and mount them directly into the containers
# api/ and ui/ are mounted as volumes  at /app within the docker-compose.yml
(cd api && npm install) || { echo "npm install failed in api"; exit 1; }
(cd ui && npm install) || { echo "npm install failed in ui"; exit 1; }

# update the bids submodule
git submodule update --init --recursive

# The main differences between the production and development docker-compose files are that the production
# files uses https and the development file uses http. The production file also uses a different nginx.conf
if [[ $BRAINLIFE_PRODUCTION == true ]]; then
  DOCKER_COMPOSE_FILE=docker-compose-production.yml
else
  DOCKER_COMPOSE_FILE=docker-compose.yml
fi

mkdir -p /tmp/upload
mkdir -p /tmp/workdir

#npm run prepare-husky

./generate_keys.sh

# ok docker compose is now included in docker as an option for docker
if [[ $(command -v docker-compose) ]]; then 
    # if the older version is installed use the dash
    docker-compose --file ${DOCKER_COMPOSE_FILE} up
else
    # if the newer version is installed don't use the dash
    docker compose --file ${DOCKER_COMPOSE_FILE} up
fi
