#!/usr/bin/env bash

cd ..

set -ex

# Update git submodules
git submodule update --init --recursive

# Install dependencies for api and ui
(cd api && npm install)
(cd ui && npm install)

# Create necessary directories
mkdir -p /tmp/upload
mkdir -p /tmp/workdir

# Generate keys (assuming this is a necessary setup step)
./generate_keys.sh

