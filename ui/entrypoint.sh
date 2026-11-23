#! /usr/bin/env bash

# The combined Docker/Apptainer image passes shared settings directly to all services.
# Compose can also set VITE_* explicitly; preserve those values when provided.
export VITE_APIHOST="${VITE_APIHOST:-http://${SERVER_NAME:-localhost}:8082}"
export VITE_BRAINLIFE_AUTHENTICATION="${VITE_BRAINLIFE_AUTHENTICATION:-${BRAINLIFE_AUTHENTICATION:-false}}"
export VITE_EZBIDS_AUTH_MODE="${VITE_EZBIDS_AUTH_MODE:-${EZBIDS_AUTH_MODE:-}}"

# If we're in production we want to build the ui and allow nginx to serve the files, 
# otherwise we run npm install which will create a ui page and use vite to serve it
# in "development" mode
if [ "${BRAINLIFE_USE_NGINX:-false}" = "true" ]; then
  npm run build
else
  npm run dev
fi
