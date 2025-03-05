#!/usr/bin/env bash

# Get the Ezbids directory
EZBIDS_DIR=$(dirname `pwd`)

# Check if dd and mkfs.ext3 are installed
if ! command -v dd &> /dev/null || ! command -v mkfs.ext3 &> /dev/null; then
    echo "Warning: 'dd' or 'mkfs.ext3' not found. Using directory-based overlays instead of image-based overlays."
    USE_DIR_OVERLAYS=true
else
    USE_DIR_OVERLAYS=false
fi

# Run development script
./dev_apptainer.sh

# Check if overlays need to be created
if [ "$USE_DIR_OVERLAYS" = false ]; then
    if [ ! -e "mongodb.sif" ]; then
	apptainer build mongodb.sif docker://mongo:4.4.15
    fi

    if [ ! -e "api_overlay.img" ]; then
	apptainer overlay create api_overlay.img
	API_OVERLAY="api_overlay.img"
    fi

    # Maybe not needed? Does the handler create data elsewhere than tmp?
    if [ ! -e "handler_overlay.img" ]; then
	apptainer overlay create handler_overlay.img
	HANDLER_OVERLAY="handler_overlay.img"
    fi

    if [ ! -e "mongo_overlay.img" ]; then
	apptainer overlay create mongo_overlay.img
	MONGO_OVERLAY="mongo_overlay.img"
    fi
else
    # Use directory overlays if dd or mkfs.ext3 are missing
    if [ ! -d "api_overlay" ]; then
        mkdir api_overlay
	API_OVERLAY="api_overlay"
    fi
    if [ ! -d "handler_overlay" ]; then
        mkdir handler_overlay
	HANDLER_OVERLAY="handler_overlay"
    fi
    if [ ! -d "mongo_overlay" ]; then
        mkdir mongo_overlay
	MONGO_OVERLAY="mongo_overlay"
    fi
fi

# Start MongoDB container
echo "Starting MongoDB container..."
apptainer instance run --bind "$EZBIDS_DIR:$EZBIDS_DIR" --hostname mongodb --overlay $MONGO_OVERLAY  mongodb.sif mongodb ./start_mongodb.sh

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
sleep 10  # Adjust this based on your needs (or add a health check here)

# Start the API container
echo "Starting API container..."
apptainer instance run --bind "$EZBIDS_DIR:$EZBIDS_DIR" --overlay $API_OVERLAY --no-mount /etc/hosts --bind mongo_host:/etc/hosts api.sif api ./start_api.sh

# Wait for API to be ready
echo "Waiting for API to be ready..."
sleep 5  # Adjust based on your setup

# Start the Handler container
echo "Starting Handler container..."
apptainer instance run --bind "$EZBIDS_DIR:$EZBIDS_DIR" --overlay $HANDLER_OVERLAY --no-mount /etc/hosts --bind mongo_host:/etc/hosts handler.sif handler ./start_handler.sh

# Wait for Handler to be ready (optional)
echo "Waiting for Handler to be ready..."
sleep 5  # Adjust as needed

# Start the UI container
echo "Starting UI container..."
apptainer instance run --bind "$EZBIDS_DIR:$EZBIDS_DIR" --env "VITE_APIHOST=http://localhost:8082"  ui.sif ui ./start_ui.sh

# Start Telemetry container (if in development profile)
if [ "$PROFILE" == "development" ]; then
    echo "Starting Telemetry container..."
    apptainer instance --bind "$EZBIDS_DIR:$EZBIDS_DIR" run telemetry.sif telementry ./start_telementry.sh
fi

# Inform user that containers are running
echo "All containers are running"
