#!/usr/bin/env bash

cd ..

set -ex

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

# Update git submodules
git submodule update --init --recursive

# Install dependencies for api and ui
(cd api && npm install)
(cd ui && npm install)

# Create necessary directories
mkdir -p /tmp/upload
mkdir -p /tmp/workdir

# Prepare husky (if using it for git hooks)
npm run prepare-husky

# Generate keys (assuming this is a necessary setup step)
./generate_keys.sh

