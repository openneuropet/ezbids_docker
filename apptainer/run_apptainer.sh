#!/usr/bin/env bash

EZBIDS_DIR=/home/martinnorgaard/Documents/GitHub/ezbids
cd "$EZBIDS_DIR"

# Load environment variables explicitly from the .env file
source "$EZBIDS_DIR/apptainer/.env"

"$EZBIDS_DIR/apptainer/dev_apptainer.sh"

if [ ! -e "$EZBIDS_DIR/apptainer/mongodb.sif" ]; then
    apptainer build "$EZBIDS_DIR/apptainer/mongodb.sif" docker://mongo:4.4.15
fi

# Stop previously running instances explicitly
apptainer instance stop mongodb api handler ui >/dev/null 2>&1

# Explicitly start MongoDB container (port 27017 explicitly exposed)
echo "Starting MongoDB container..."
apptainer instance run \
  --fakeroot --writable-tmpfs \
  --bind "$EZBIDS_DIR/tmp":/tmp \
  --bind "$EZBIDS_DIR/tmp/data":/data/db \
  --bind "$EZBIDS_DIR/apptainer":/app \
  --hostname mongodb \
  "$EZBIDS_DIR/apptainer/mongodb.sif" mongodb bash -c "cd /app && ./start_mongodb.sh --bind_ip_all" &

sleep 5

# Explicitly start API container (port 8082 explicitly exposed)
echo "Starting API container..."
apptainer instance run \
  --fakeroot \
  --writable-tmpfs \
  --bind "$EZBIDS_DIR/api":/app/api \
  --bind "$EZBIDS_DIR/apptainer":/app/apptainer \
  --bind "$EZBIDS_DIR/tmp":/tmp \
  "$EZBIDS_DIR/apptainer/api.sif" api bash -c "cd /app/api && npm install && npm install --save-dev ts-node-dev typescript @types/node && npm run dev" &

sleep 5

# Explicitly start Handler container explicitly
echo "Starting Handler container..."
apptainer instance run \
  --fakeroot \
  --writable-tmpfs \
  --env "PRESORT=$PRESORT" \
  --bind "$EZBIDS_DIR/handler":/app/handler \
  --bind "$EZBIDS_DIR/apptainer":/app/apptainer \
  --bind "$EZBIDS_DIR/tmp":/tmp \
  "$EZBIDS_DIR/apptainer/handler.sif" handler bash -c "cd /app/handler && chmod +x ./start.sh && ./start.sh" &

sleep 5

# Explicitly start UI container explicitly (port 3000 explicitly exposed)
echo "Starting UI container explicitly..."
apptainer instance run \
  --bind "$EZBIDS_DIR/ui":/ui \
  --bind "$EZBIDS_DIR/tmp":/tmp \
  --env "VITE_APIHOST=http://localhost:8082" \
  --env "BRAINLIFE_PRODUCTION=false" \
  "$EZBIDS_DIR/apptainer/ui.sif" ui bash -c "cd /ui && ./entrypoint.sh"

sleep 5

if [ "$PROFILE" == "development" ]; then
    echo "Starting Telemetry container..."
    apptainer instance run \
      --bind "$EZBIDS_DIR":/app \
      "$EZBIDS_DIR/apptainer/telemetry.sif" telemetry bash -c "cd /app/apptainer && ./start_telemetry.sh" &
fi

echo "All containers are running explicitly"

