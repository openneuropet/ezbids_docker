#!/usr/bin/env bash

source ../.env

echo "Showing existing environment"
env 

./dev_apptainer.sh

if [ ! -e "mongodb.sif" ]; then
    apptainer build mongodb.sif docker://mongo:4.4.15
fi

if [ ! -e "api_overlay.img" ]; then
    apptainer overlay create api_overlay.img
fi

# Maybe not needed?
# Does the handler create data else where than tmp?
if [ ! -e "handler_overlay.img" ]; then
    apptainer overlay create handler_overlay.img
fi

if [ ! -e "mongo_overlay.img" ]; then
    apptainer overlay create mongo_overlay.img
fi

# Start MongoDB container
echo "Starting MongoDB container..."
apptainer instance run --hostname mongodb --overlay mongo_overlay.img mongodb.sif mongodb ./start_mongodb.sh

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
sleep 10  # Adjust this based on your needs (or add a health check here)

# Start the API container
echo "Starting API container..."
apptainer instance run --overlay api_overlay.img --no-mount /etc/hosts --bind mongo_host:/etc/hosts api.sif api ./start_api.sh

# Wait for API to be ready
echo "Waiting for API to be ready..."
sleep 5  # Adjust based on your setup

# Start the Handler container
echo "Starting Handler container..."
apptainer instance run --overlay handler_overlay.img --no-mount /etc/hosts --bind mongo_host:/etc/hosts handler.sif handler ./start_handler.sh

# Wait for Handler to be ready (optional)
echo "Waiting for Handler to be ready..."
sleep 5  # Adjust as needed

# Start the UI container
echo "Starting UI container..."
apptainer instance run --env "VITE_APIHOST=http://localhost:8082"  ui.sif ui ./start_ui.sh

# Start Telemetry container (if in development profile)
if [ "$PROFILE" == "development" ]; then
    echo "Starting Telemetry container..."
    apptainer instance run telemetry.sif telementry ./start_telementry.sh
fi

# Inform user that containers are running
echo "All containers are running"
