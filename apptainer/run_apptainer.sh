#!/usr/bin/env bash

# Disable setuid to avoid requiring sudo
export APPTAINER_ALLOW_SETUID=0

# Add /sbin to PATH for iptables
export PATH="/sbin:$PATH"

source ../.env

# Set default if not set in .env
EZBIDS_TMP_DIR=${EZBIDS_TMP_DIR:-/tmp}

# Check and install required tools
if [ ! -x "/sbin/iptables" ]; then
    echo "iptables not found. Please install iptables:"
    echo "apt-get update && apt-get install -y iptables"
    exit 1
fi

echo "Showing existing environment"
env 

# Function to get container IP
get_container_ip() {
    local container_name=$1
    local ip
    ip=$(apptainer instance list | grep "^${container_name} " | awk '{print $3}')
    if [ -z "$ip" ]; then
        echo "Error: Could not get IP for container ${container_name}" >&2
        exit 1
    fi
    echo "$ip"
}

# Create necessary directories
mkdir -p ${EZBIDS_TMP_DIR}/data/db

if [ ! -e "mongodb.sif" ]; then
    apptainer build mongodb.sif docker://mongo:4.4.15
fi

if [ ! -e "nginx.sif" ]; then
    apptainer build nginx.sif docker://nginx:latest
fi

if [ ! -e "api_overlay.img" ]; then
    apptainer overlay create api_overlay.img
fi

if [ ! -e "handler_overlay.img" ]; then
    apptainer overlay create handler_overlay.img
fi

if [ ! -e "mongo_overlay.img" ]; then
    apptainer overlay create mongo_overlay.img
fi

if [ ! -e "ui_overlay.img" ]; then
    apptainer overlay create ui_overlay.img
fi

if [ ! -e "nginx_overlay.img" ]; then
    apptainer overlay create nginx_overlay.img
fi

# Clean up any existing instances
echo "Cleaning up existing instances..."
for instance in $(apptainer instance list | tail -n +2 | awk '{print $1}'); do
    echo "Stopping $instance..."
    apptainer instance stop $instance
done

# Start MongoDB container first
echo "Starting MongoDB container..."
apptainer instance start \
    --net --network-args "portmap=27017:27017/tcp" \
    --bind ${EZBIDS_TMP_DIR}/data/db:/data/db \
    mongodb.sif mongodb

# Start MongoDB process
echo "Starting MongoDB process..."
apptainer exec instance://mongodb bash -c "mongod --bind_ip 0.0.0.0 --dbpath /data/db &"

echo "Waiting for MongoDB to initialize..."
sleep 10

# Get MongoDB IP and export it
export MONGO_IP=$(get_container_ip "mongodb")
export MONGO_CONNECTION_STRING="mongodb://${MONGO_IP}:27017/ezbids"
echo "MongoDB IP: ${MONGO_IP}"
echo "MongoDB Connection String: ${MONGO_CONNECTION_STRING}"

# Verify MongoDB is running and accessible
echo "Verifying MongoDB is running..."
max_attempts=12
attempt=1
mongo_running=false

while [ $attempt -le $max_attempts ]; do
    if apptainer exec instance://mongodb mongo --eval "db.serverStatus()" > /dev/null 2>&1; then
        echo "MongoDB is running and accessible"
        mongo_running=true
        break
    fi
    echo "Attempt $attempt/$max_attempts: MongoDB not yet accessible, waiting..."
    sleep 5
    ((attempt++))
done

if [ "$mongo_running" = false ]; then
    echo "ERROR: MongoDB failed to start properly. Exiting."
    exit 1
fi

# Start the API container
echo "Starting API container..."
apptainer instance start \
    --net --network-args "portmap=8082:8082/tcp" \
    --env MONGO_CONNECTION_STRING=${MONGO_CONNECTION_STRING} \
    --env NODE_ENV=production \
    --env DEBUG=* \
    --bind ../api:/app/api \
    --bind ${EZBIDS_TMP_DIR}:/tmp \
    api.sif api

# Create log file and set permissions
echo "Setting up log file..."
apptainer exec instance://api bash -c "touch /tmp/ezbids.log && chmod 666 /tmp/ezbids.log"

# Install npm dependencies in API container
echo "Installing dependencies in API container..."
apptainer exec instance://api bash -c "cd /app/api && npm install"

# Start the API process
echo "Starting API process..."
apptainer exec instance://api bash -c "cd /app/api && chmod +x start.sh && ./start.sh"

# Get API IP and export it
export API_IP=$(get_container_ip "api")
echo "API IP: ${API_IP}"

# Wait for API to be healthy
echo "$(date '+%H:%M:%S') Waiting for API to be healthy..."
while true; do
    if curl -f http://${API_IP}:8082/health; then
        echo "$(date '+%H:%M:%S') API is healthy"
        break
    fi
    echo "$(date '+%H:%M:%S') API not yet healthy, waiting..."
    echo "Node process status:"
    apptainer exec instance://api ps aux | grep node || echo "No Node process found"
    echo "Recent API logs:"
    apptainer exec instance://api bash -c "cd /app/api && tail -n 50 /tmp/ezbids.log" || true
    sleep 5
done

# Start the Handler container
echo "Starting Handler container..."
apptainer instance start \
    --net \
    --env MONGO_CONNECTION_STRING=${MONGO_CONNECTION_STRING} \
    --env PRESORT=${PRESORT:-false} \
    --bind ..:/app \
    --bind ${EZBIDS_TMP_DIR}:/tmp \
    handler.sif handler \
    pm2 start handler.js --no-daemon

# Start the UI container
echo "Starting UI container..."
apptainer instance start \
    --net --network-args "portmap=3000:3000/tcp" \
    --env VITE_APIHOST="https://${SERVER_NAME}/api" \
    --env VITE_BRAINLIFE_AUTHENTICATION="${BRAINLIFE_AUTHENTICATION}" \
    --bind ../ui:/ui \
    ui.sif ui \
    bash -c "cd /ui && npm install && npm run build"

# Get UI IP and export it
export UI_IP=$(get_container_ip "ui")
echo "UI IP: ${UI_IP}"

# Update nginx config with API IP and SERVER_NAME
echo "Updating nginx config with API IP and SERVER_NAME..."
cp ../nginx/production_nginx.conf /tmp/production_nginx.conf
sed -i "s|http://api:8082/|http://${API_IP}:8082/|g" /tmp/production_nginx.conf
sed -i "s|\$SERVER_NAME|${SERVER_NAME}|g" /tmp/production_nginx.conf

echo "SERVER_NAME=${SERVER_NAME}"

# Start nginx container
echo "Starting nginx container..."
apptainer instance start \
    --net \
    --network-args "portmap=443:443/tcp" \
    --overlay nginx_overlay.img \
    --bind ../nginx/ssl/:/etc/nginx/conf.d/ssl/ \
    --bind /tmp/production_nginx.conf:/etc/nginx/conf.d/default.conf \
    --bind ../ui/dist:/usr/share/nginx/html/ezbids:ro \
    nginx.sif nginx

# Start nginx process with error logging but keep it running in daemon mode
echo "Starting nginx process..."
apptainer exec instance://nginx bash -c 'nginx && tail -f /var/log/nginx/error.log'

# Get nginx IP and export it
export NGINX_IP=$(get_container_ip "nginx")
echo "NGINX IP: ${NGINX_IP}"

# Start Telemetry container (if enabled)
if [ "${COMPOSE_PROFILES}" = "telemetry" ]; then
    echo "Starting Telemetry container..."
    apptainer instance start \
        --net \
        --env MONGO_CONNECTION_STRING \
        telemetry.sif telemetry
fi

echo "All services started. Use 'apptainer instance list' to see running instances."
echo "Environment variables set:"
echo "MONGO_IP=${MONGO_IP}"
echo "MONGO_CONNECTION_STRING=${MONGO_CONNECTION_STRING}"
echo "API_IP=${API_IP}"
echo "UI_IP=${UI_IP}"
echo "NGINX_IP=${NGINX_IP}"
