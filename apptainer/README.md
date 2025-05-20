Below is the original readme that instructed a user on how to export this docker compose based project
into singularity. For "simplicity's" sake, the building of both docker and singularity images was moved
to the Makefile at the top of this repository. To get this singularity/apptainer codebase up and running
try (emphasis on try) to execute the following commands:

```bash
make export-and-build
```

# Apptainer for ezBIDS

This guide provides steps to convert Docker containers into Apptainer images and run them efficiently.

## Converting Docker to Apptainer

### Step 1: Build and Stop Docker Containers
Run the following command to build and start the Docker containers:
```sh
docker-compose up --build
```

Once the containers are running, stop them with:
```sh
docker-compose down
```

### Step 2: Export Docker Images
Save the running images to `.tar` files:
```sh
docker save -o api_image.tar brainlife_ezbids-api
docker save -o handler_image.tar brainlife_ezbids-handler
docker save -o ui_image.tar brainlife_ezbids-ui
docker save -o telemetry_image.tar brainlife_ezbids-telemetry
```
For more information, refer to the Docker documentation: [Docker Save Command](https://docs.docker.com/reference/cli/docker/image/save/)

### Step 3: Convert Docker Images to Apptainer Images
Use the following commands to convert each exported Docker image to an Apptainer `.sif` image:
```sh
apptainer build api.sif docker-archive:api_image.tar
apptainer build handler.sif docker-archive:handler_image.tar
apptainer build ui.sif docker-archive:ui_image.tar
apptainer build telemetry.sif docker-archive:telemetry_image.tar
```

## Usage

### Starting the Containers
Run the following command to start the Apptainer containers:
```sh
./run_apptainer.sh
```

### Stopping the Containers
To stop the Apptainer containers, execute:
```sh
./stop_apptainer.sh
```