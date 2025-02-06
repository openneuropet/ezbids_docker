#!/bin/bash

set -e
set -x

if [ -z $1 ]; then
    echo "please specify root dir"
    exit 1
fi
root=$1

datasetName=`jq -r '.datasetDescription.Name' $root/finalized.json`

rootDir="$root/bids/$datasetName"

#clean up from previous run
rm -rf $root/bids

# run MEG BIDS conversion if relevant data found
echo "converting MEG data (if present)"
./convert_meg.py $root/finalized.json $rootDir

echo "converting output to bids"
./convert.js $root

echo "output bids directory structure"
tree "$rootDir" > $root/tree.log

echo "running bids validator"
bids-validator "$rootDir" > $root/validator.log || true
bids-validator --json "$rootDir" > $root/validator.json || true

echo "Copying finalized.json file to ezBIDS_template.json"
cp -r $root/finalized.json $root/ezBIDS_template.json

# Create telemetry-specific files
echo "Creating ezBIDS telemetry files"
./telemetry.py $root

pet2bids_server="http://openneuropet.org/telemetry/"

# Telemetry (to hard-coded pet2bids server)
if [ -f $root/validator.json ]; then
    curl -H 'Content-Type: application/json' -d @$root/validator.json -X POST $pet2bids_server || {
        echo "Failed to send validator.json to $pet2bids_server"
        true
    }
fi

if [ -f $root/ezBIDS_core_telemetry.json ]; then
    curl -H 'Content-Type: application/json' -d @$root/ezBIDS_core_telemetry.json -X POST $pet2bids_server || {
        echo "Failed to send ezBIDS_core_telemetry.json to $pet2bids_server"
        true
    }
fi

if [ -f $root/ezBIDS_finalized_telemetry.json ]; then
    curl -H 'Content-Type: application/json' -d @$root/ezBIDS_finalized_telemetry.json -X POST $pet2bids_server || {
        echo "Failed to send ezBIDS_finalized_telemetry.json to $pet2bids_server"
        true
    }
fi