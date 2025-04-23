#!/usr/bin/env bash

cd ..

set -ex

# check to see if a .env file exists
if [ -f apptainer/.env ]; then
    echo ".env file exists, loading environment variables from .env file"
else
    echo ".env file does not exist, copying example.env to .env"
    cp example.env apptainer/.env
fi

# Ensure SERVER_NAME=localhost exists in .env
if ! grep -q "^SERVER_NAME=" apptainer/.env; then
     echo "SERVER_NAME=localhost" >> apptainer/.env
     echo "Added SERVER_NAME=localhost to .env"
fi

# check if reqired dir exists
# Define the required structure
required_dirs=("tmp" "tmp/data" "tmp/ezbids-workdir" "tmp/upload" "tmp/workdir")

# Check and create each directory if missing
for dir in "${required_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Creating: $dir"
        mkdir -p "$dir"
    fi
done

# Parse arguments for authentication flag
BRAINLIFE_AUTHENTICATION=true
while getopts "d" flag; do
 case $flag in
   d)
     BRAINLIFE_AUTHENTICATION=false
   ;;
   \?)
   ;;
 esac
done

export BRAINLIFE_AUTHENTICATION
# Check Node.js version
REQUIRED_NODE_VERSION="16"
CURRENT_NODE_VERSION=$(node -v | cut -d '.' -f 1 | sed 's/v//')

if [ "$CURRENT_NODE_VERSION" -ne "$REQUIRED_NODE_VERSION" ]; then
    echo "Warning: You are using Node.js version $CURRENT_NODE_VERSION. It is recommended to use version $REQUIRED_NODE."
    echo "Please switch to Node.js version $REQUIRED_NODE_VERSION."
fi

# Update git submodules
git submodule update --init --recursive

# Install dependencies for api and ui
(cd api && npm install)
(cd ui && npm install)

# Prepare husky (if using it for git hooks)
npm install husky --save-dev
npm run prepare-husky

# Generate keys (assuming this is a necessary setup step)
./generate_keys.sh

