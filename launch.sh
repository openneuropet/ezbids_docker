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

# update the bids submodule
git submodule update --init --recursive

# The main differences between the docker-compose-nginx.yml and  docker-compose.yml files 
# are that the nginx file uses https via nginx and while the other file uses http.
# and serves this application at localhost:3000. If you don't need to reach ezBIDS
# from outside of the computer it's hosted on, you don't need nginx.
if [[ $BRAINLIFE_USE_NGINX == true ]]; then
  DOCKER_COMPOSE_FILE=docker-compose-nginx.yml
else
  DOCKER_COMPOSE_FILE=docker-compose.yml
fi

if [[ ${EZBIDS_TMP_DIR} ]]; then
  # set working dir to the temp dir specified in above variable
  EZBIDS_WORKING_DIR=${EZBIDS_TMP_DIR}
  # check to see if it exists
else:
  EZBIDS_WORKING_DIR=/tmp/ezbids-workdir/
    mkdir ${EZBIDS_TMP_DIR}
fi
if [ ! -d ${EZBIDS_WORKING_DIR} ]; then
  mkdir ${EZBIDS_WORKING_DIR}
fi

./generate_keys.sh

# ok docker compose is now included in docker as an option for docker
if [[ $(command -v docker-compose) ]]; then 
    # if the older version is installed use the dash
    docker-compose --file ${DOCKER_COMPOSE_FILE} up
else
    # if the newer version is installed don't use the dash
    docker compose --file ${DOCKER_COMPOSE_FILE} up
fi
