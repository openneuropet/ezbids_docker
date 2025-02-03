# Apptainer for ezBIDS

## Converting docker to apptainer

First you run:

docker-compose up --build

When the containers are running:

docker-compose down

Then you export the images

docker save -o api_image.tar brainlife_ezbids-api
docker save -o handler_image.tar brainlife_ezbids-handler
docker save -o ui_image.tar brainlife_ezbids-ui
docker save -o telemetry_image.tar brainlife_ezbids-telemetry

for more information: [https://docs.docker.com/reference/cli/docker/image/save/](https://docs.docker.com/reference/cli/docker/image/save/)


Then run following command:

apptainer build api.sif docker-archive:api_image.tar
apptainer build handler.sif docker-archive:handler_image.tar
apptainer build ui.sif docker-archive:ui_image.tar
apptainer build telemetry.sif docker-archive:telemetry_image.tar

## Usage

To start the containers run following command:

./run_apptainer.sh

To stop the containers run following command:
./stop_apptainer.sh