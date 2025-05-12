#!/usr/bin/env bash

cd "$(dirname "$0")/.."

set -ex

# Explicitly check if a .env file exists in the correct location explicitly:
ENV_PATH="apptainer/.env"
if [ -f "$ENV_PATH" ]; then
    echo ".env file exists at $ENV_PATH, loading environment variables."
else
    echo ".env file does not exist at $ENV_PATH. Creating it explicitly now."
    cat << EOF > "$ENV_PATH"
SERVER_NAME=localhost
BRAINLIFE_PRODUCTION=false
SSL_CERT_PATH=./nginx/ssl/sslcert.cert
SSL_KEY_PATH=./nginx/ssl/sslcert.key
SSL_PASSWORD_PATH=./nginx/ssl/sslpassword
BRAINLIFE_AUTHENTICATION=false
BRAINLIFE_DEVELOPMENT=false
COMPOSE_PROFILES=
VITE_APIHOST=http://localhost:8082
EOF
    echo "Explicitly created .env file at $ENV_PATH explicitly."
fi

# Ensure SERVER_NAME=localhost exists in .env explicitly
if ! grep -q "^SERVER_NAME=" "$ENV_PATH"; then
    echo "SERVER_NAME=localhost" >> "$ENV_PATH"
    echo "Added SERVER_NAME=localhost to $ENV_PATH explicitly."
fi

# Explicitly create required directories explicitly:
required_dirs=("tmp" "tmp/data" "tmp/ezbids-workdir" "tmp/upload" "tmp/workdir")

for dir in "${required_dirs[@]}"; do
    [ ! -d "$dir" ] && mkdir -p "$dir"
done

# Parse arguments explicitly for authentication flag explicitly
BRAINLIFE_AUTHENTICATION=true
while getopts "d" flag; do
 case $flag in
   d) BRAINLIFE_AUTHENTICATION=false ;;
 esac
done
export BRAINLIFE_AUTHENTICATION

# Check Node.js version explicitly
REQUIRED_NODE_VERSION="18"
CURRENT_NODE_VERSION=$(node -v | cut -d '.' -f 1 | sed 's/v//')

if [ "$CURRENT_NODE_VERSION" -ne "$REQUIRED_NODE_VERSION" ]; then
    echo "Warning: You are explicitly using Node.js version $CURRENT_NODE_VERSION. Explicitly recommended version is $REQUIRED_NODE_VERSION."
fi

# Update git submodules and explicitly install dependencies explicitly:
git submodule update --init --recursive
(cd api && npm install)
(cd ui && npm install)

./generate_keys.sh
