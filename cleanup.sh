#!/bin/bash

echo "Stopping all running instances..."
for instance in $(apptainer instance list | tail -n +2 | awk '{print $1}'); do
    echo "Stopping $instance..."
    apptainer instance stop $instance
done

echo "Cleanup complete!" 