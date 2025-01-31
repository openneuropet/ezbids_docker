#! /bin/bash
# we're going to use this script to walk us through how to:
# 1) generate some self signed ssl certs, making sure to follow the following 
    # the following files are required for https to work:" 
    #   nginx/ssl/sslcert.cert"
    #   nginx/ssl/sslcert.key"
    #   nginx/ssl/sslpassword" # note you can disable the password requirement for nginx by omitting this field and commenting or deleting the requirement in the  nginx production NGINX_CONFIG_FILE
    # for https to work"
# 2) copy the example.env file to .env
# 3) Move the ssl certs to the nginx/ssl folder

# lets start by collecting the host name from this machine and using that to autogenerate the ssl certs
HOSTNAME=$(hostname)
echo "Host name: $HOSTNAME"

# you should modify statename, cityname, companyname ,and company section name to suit your installation

openssl req -x509 -newkey rsa:4096 -keyout sslcert.key -out sslcert.cert -sha256 -days 3650 -nodes -subj "/C=XX/ST=StateName/L=CityName/O=CompanyName/OU=CompanySectionName/CN=$HOSTNAME"

# now we need to move the sslcert.key and sslcert.cert to the nginx/ssl folder
mv sslcert.key nginx/ssl/
mv sslcert.cert nginx/ssl/

# now we need to copy the example.env file to .env
cp example.env .env


