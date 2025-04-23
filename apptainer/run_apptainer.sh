#!/usr/bin/env bash

# Get the Ezbids directory
EZBIDS_DIR=$(dirname `pwd`)

# Run development script
./dev_apptainer.sh

# load the environment variables from the .env file
source .env

if [ ! -e "mongodb.sif" ]; then

    apptainer build mongodb.sif docker://mongo:4.4.15

fi

# Start MongoDB container
echo "Starting MongoDB container..."
apptainer instance run --bind $EZBIDS_DIR:$EZBIDS_DIR --bind $EZBIDS_DIR/tmp:/tmp --bind $EZBIDS_DIR/tmp/data:/data --hostname mongodb mongodb.sif mongodb ./start_mongodb.sh

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
sleep 10  # Adjust this based on your needs (or add a health check here)

# Start the API container
echo "Starting API container..."
apptainer instance run --bind $EZBIDS_DIR:$EZBIDS_DIR --bind $EZBIDS_DIR/tmp:/tmp --no-mount /etc/hosts --bind mongo_host:/etc/hosts api.sif api ./start_api.sh

# Wait for API to be ready
echo "Waiting for API to be ready..."
sleep 5  # Adjust based on your setup

# Start the Handler container
echo "Starting Handler container..."
apptainer instance run --bind $EZBIDS_DIR:$EZBIDS_DIR --bind $EZBIDS_DIR/tmp:/tmp  --no-mount /etc/hosts --bind mongo_host:/etc/hosts handler.sif handler ./start_handler.sh

# Wait for Handler to be ready (optional)
echo "Waiting for Handler to be ready..."
sleep 5  # Adjust as needed

# Start the UI container
echo "Starting UI container..."
apptainer instance run --bind $EZBIDS_DIR:$EZBIDS_DIR --env "VITE_APIHOST=http://$SERVER_NAME:8082"  ui.sif ui ./start_ui.sh

# Start Telemetry container (if in development profile)
if [ "$PROFILE" == "development" ]; then
    echo "Starting Telemetry container..."
    apptainer instance --bind $EZBIDS_DIR:$EZBIDS_DIR run telemetry.sif telementry ./start_telementry.sh
fi

# Inform user that containers are running
echo "All containers are running"
