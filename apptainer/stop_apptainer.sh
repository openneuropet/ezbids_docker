#!/usr/bin/env bash

echo "Stopping containers..."
apptainer instance stop api
apptainer instance stop handler
apptainer instance stop mongodb
apptainer instance stop ui
if [ "$PROFILE" == "development" ]; then
    apptainer instance stop telementry
fi
