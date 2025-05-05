#!/bin/bash

# we're going to use this script to walk us through how to:
# 1) generate some self signed ssl certs, making sure to follow the following 
    # the following files are required for https to work:" 
    #   nginx/ssl/sslcert.cert"
    #   nginx/ssl/sslcert.key"
    # for https to work"
# 2) copy the example.env file to .env
# 3) Move the ssl certs to the nginx/ssl folder

# Use provided hostname or get it from system
if [ -z "$1" ]; then
    HOSTNAME=$(hostname)
    echo "No hostname provided, using system hostname: $HOSTNAME"
else
    HOSTNAME=$1
    echo "Using provided hostname: $HOSTNAME"
fi

# you should modify statename, cityname, companyname ,and company section name to suit your installation

openssl req -x509 -newkey rsa:4096 -keyout sslcert.key -out sslcert.cert -sha256 -days 3650 -nodes -subj "/C=XX/ST=StateName/L=CityName/O=CompanyName/OU=CompanySectionName/CN=$HOSTNAME"

# now we need to move the sslcert.key and sslcert.cert to the nginx/ssl folder
mv sslcert.key nginx/ssl/
mv sslcert.cert nginx/ssl/

# now we need to setup the .env file, for simplicity's sake we create one here:
cat <<EOL > .env
SERVER_NAME=$HOSTNAME

NGINX_CONFIG_FILE=nginx/production_nginx.conf

BRAINLIFE_USE_NGINX=true

# Set the BRAINLIFE_AUTHENTICATION environment variable to true, if you're not running
# this with brainlife don't use.
BRAINLIFE_AUTHENTICATION=false

# Set the BRAINLIFE_DEVELOPMENT enables additional debugging output and mounts 
# the ezbids repo/folder into the various containers default is false
BRAINLIFE_DEVELOPMENT=false

# Collect telemetry data and store it locally using the telemetry container
HOST_LOCAL_TELEMETRY=false
EOL

echo ".env file created successfully."
