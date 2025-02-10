#docker compose up --build

#docker compose down

docker save -o apptainer/api_image.tar ezbids-api
docker save -o apptainer/handler_image.tar ezbids-handler
docker save -o apptainer/ui_image.tar ezbids-ui

cd apptainer/

apptainer build api.sif docker-archive:api_image.tar
apptainer build handler.sif docker-archive:handler_image.tar
apptainer build ui.sif docker-archive:ui_image.tar

