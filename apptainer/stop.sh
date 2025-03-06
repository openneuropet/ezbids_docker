#!/usr/bin/env bash

# Stop nginx
echo "Stopping nginx..."
sudo systemctl stop nginx

# Stop all Apptainer instances
echo "Stopping Apptainer instances..."
for instance in $(apptainer instance list | tail -n +2 | awk '{print $1}'); do
    echo "Stopping $instance..."
    apptainer instance stop $instance
done

echo "All services stopped." 