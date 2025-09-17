[![Docker Build (Local)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-local.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-local.yml)
[![Docker Build (Nginx)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-nginx.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-nginx.yml)
[![Test Local Upload](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-local.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-local.yml)
[![Test Nginx Upload](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-nginx.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-nginx.yml)

# THIS FORK INCLUDES ADDITIONAL SUPPORT SPECIFICALLY FOR PET ([ORIGINAL PROJECT](https://github.com/brainlife/ezbids))

# ezBIDS

The secure, cloud-based service for the semi-automated mapping of entire sessions of neuroimaging data to the Brain Imaging Data Structure ([BIDS](https://bids.neuroimaging.io/)) standard.  

<img width="1450" alt="Screenshot 2023-11-01 at 11 50 48 AM" src="https://github.com/brainlife/ezbids/assets/2119795/2c054297-1503-4ebb-8718-336012c80b48">

### About

This is the repository for a semi-supervised web-service for converting neuroimaging data files to [BIDS](https://bids.neuroimaging.io/). This specific repository exists for users wishing to deploy this web service on premise.

Unlike other BIDS converters, ezBIDS eliminates the need for coding and command line interfaces (CLI), doing the bulk of the work behind the scenes to save users time. Importantly, ezBIDS does not require an organizational structure for uploaded data.

A series of inferenial heuritics analyze the uploaded data to provide a *first guess* BIDS structure, which is presented to users through the web-browser user interface. Users verify the *first guess* and modify the information provided as needed so as to best match the final BIDS structure. 

Data from all major scanner vendors are accepted by ezBIDS. ezBIDS enables pseudo-anonymization by providing options for the defacing of anatomical sequences, and removes all identifying metadata information (e.g. `PatientName`) before final conversion to BIDS.

The BIDS output can then be downloaded back to the user's computer, or uploaded to open repositories such as
[brainlife.io](https://brainlife.io/) or [OpenNeuro.org](https://openneuro.org/).

Helpful links:
1. [ezBIDS website](https://brainlife.io/ezbids) (Chrome or Firefox browsers preferred)
2. [ezBIDS user documentation](https://brainlife.io/docs/using_ezBIDS/)
3. [ezBIDS tutorial](https://brainlife.io/docs/tutorial/ezBIDS/)
4. [ezBIDS tutorial video](https://www.youtube.com/embed/L8rWA8qgnpo)

### Usage

Users do not need to organize their uploaded data in any specific manner, and users may choose to compress (e.g. zip, tar) their uploaded data.

Should users feel the need to anonymize data before uploading, we strongly recommend that subjects (and sessions, if applicable) be organized into subject (and session) folders, with explicit labeling of the preferred subjects (and sessions) IDs (e.g. `MRI_data/sub-01/ses-01/DICOMS`). Failure to do so for non-anonymized data may result in an inaccurate *first guess* and require additional edits in the web browser.

#### Local Usage

There are three methods for deploying this service one for local use, another using nginx for sitewide deployments, and an apptainer option for local use
where docker is unavailable.

For users that can are not setting this service up for others it's recommended to run without nginx. Additionally, for impermanent deployments
users can be up and running with 1 command and no other configuration:

```bash
docker compose up
# or to hide the output
docker compose up -d
```

**Apptainer Use**

The apptainer image must be built from the `EverythingDockerfile`, which is in turn dependent on the images defined/tagged in `docker-compose.yml` being
built. To create the apptainer image one must do the following:

```bash
git clone https://github.com/openneuropet/ezbids_docker.git
cd ezbids_docker
docker compose build
docker build -f EverythingDockerfile -t ezbids-everything .
```

Then the run the following apptainer commands:
```bash
apptainer build ezbids-everything.sif docker-daemon://ezbids-everything:latest
apptainer run --fakeroot --writable-tmpfs --cleanenv --no-home ezbids-everything.sif
```

It should be noted that apptainer occasionally changes which ports it maps the ezBIDS ui to, but that will be mentioned in the console following 
the apptainer run step above.

**Back to Docker**

For a sitewide deployment, the initial setup requires configuring the local environment via
a `.env` file. The first steps are to copy the `example.env` file in this repo 
to `.env`:

```bash
cd ezbids_docker
cp example.env .env
```
The env file you've created should look something like the following:

<details>


```bash
# Create/Copy this file as .env in the root of the project to set default environment variables

# insert your host name here, it should match your ssl certificate and/or the output
# of echo $HOSTNAME
SERVER_NAME=localhost

# Set the BRAINLIFE_USE_NGINX environment variable to true to use https"
# (this will launch the services on port 443) and run with nginx/production_nginx.conf"
# this will require providing the correct paths for the SSL_CERT_PATH, SSL_KEY_PATH and SSL_PASSWORD_PATH
# with false the UI will run on 3000"
BRAINLIFE_USE_NGINX=false

SSL_CERT_PATH=./nginx/ssl/sslcert.cert
SSL_KEY_PATH=./nginx/ssl/sslcert.key
SSL_PASSWORD_PATH=./nginx/ssl/sslpassword #if your key is not encrypted use an arbitrary path here

# Set the BRAINLIFE_AUTHENTICATION environment variable to true, if you're not running"
# this with brainlife don't use."
BRAINLIFE_AUTHENTICATION=false

# Set the BRAINLIFE_DEVELOPMENT enables additional debugging output and mounts 
# the ezbids repo/folder into the various containers default is false"
BRAINLIFE_DEVELOPMENT=false

# Define which profiles to use, e.g. set to COMPOSE_PROFILES=telemetry to enable telemetry 
COMPOSE_PROFILES=

# Choose whether to pre-sort flat folders full of dicoms, if enabled ezBIDS will attempt
# to organize a flat folder of dicoms into sub-< indexed subject number > and if applicable
# ses-< indexed session number> folders.
PRESORT=false

# can set a custom workingdir/temp dir all uploaded files and work will be performed in
# this directory, defaults to /tmp in the docker compose file if it's not set here.
EZBIDS_TMP_DIR=
```

</details>

#### Environment Variable Details

- `BRAINLIFE_AUTHENTICATION`: This version of ezBIDS has only been tested without user authentication. You will want to keep this value set to false.
- `PRESORT`: Enable this option if your data is a flat folder full of dicoms, otherwise it's best to organize your such that a single scan/session/modality is contained in it's own folder. In order to extract the necessary PET metadata (information from spreadsheets) this variable should be disabled with `false`
- `EZBIDS_TMP_DIR`: By default ezBIDS will write data to `/tmp/ezbids-workdir`, you can change that default path by providing a different path here.
- `BRAINLIFE_USE_NGINX`: Enable with `true` if you want to host this service to multiple clients. Nginx requires ssl certificates to function, you have the option of
generating self signed or providing certificates from a registered authority.
- `SERVER_NAME`: Defaults to local host, if using Nginx then set this to the host name matching the server/ssl certificate.


#### Nginx Setup

There are some additional steps required for running this service with nginx and https, namely providing ssl certificates. To create self signed certificates run the 
`create_self_signed_certs.sh` script and provide the hostname/ipaddress of the host
as the first argument. This will create all of the certificates you need and locate
them in the `nginx/ssl/` folder. If you want to provide your own certificates place 
them manually in the `nginx/ssl/` folder and rename them to follow this convention:

`sslcert.cert`, `sslcert.key`, and if your certificate is encrypted provide the password file as `sslpassword`.

The Nginx folder exists solely to hold certs and configuration files:

```bash
tree nginx/
nginx/
├── production_nginx.conf
└── ssl
    ├── sslpassword # optional file
    ├── sslcert.cert
    └── sslcert.key

2 directories, 3 files
```

If you're using a password make sure to uncomment the line in the nginx config file (`nginx/production_nginx.conf`) for that password file.

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/conf.d/ssl/sslcert.cert;
    ssl_certificate_key /etc/nginx/conf.d/ssl/sslcert.key;
    # password file is optional, un-comment and generate/rename your file if required
    #ssl_password_file /etc/nginx/conf.d/ssl/sslpassword;
    server_name  $SERVER_NAME;
    client_max_body_size 1200M;
}
```

Once you've completed your configuring, you can start the application with the `launch.sh` script. It will export the variables set in the `.env` file to your environment and based on your choices launch ezBIDS at `localhost:3000` or `https://yourhostname/`

If you're switching between nginx or the localhost option make sure to rebuild the
containers with:

```
docker compose build -f docker-compose.yml (or docker-compose-nginx.yml) --build --no-cache
```
Using `--no-cache` might slow things down, but it's a way to ensure you don't run into issues with "stale" containers. The `--parallel` flag can speed things up as it
will build multiple containers at once.

### Authors

-   [Daniel Levitas](djlevitas208@gmail.com)*
-   [Soichi Hayashi](soichih@gmail.com)*
-   [Sophia Vinci-Booher](sophia.vinci-booher@vanderbilt.edu)
-   [Anibal Heinsfeld](anibalsolon@utexas.edu)
-   [Dheeraj Bhatia](dheeraj.bhatia@utexas.edu)
-   [Nicholas Lee](niconal902@gmail.com)
-   [Anthony Galassi](niconal902@gmail.com)
-   [Guiomar Niso](guiomar.niso@ctb.upm.es)
-   [Franco Pestilli](pestilli@utexas.edu)
* _Both authors contributed equally to this project_

### Funding Acknowledgement

brainlife.io is publicly funded, and for the sustainability of the project it is helpful to acknowledge the use of the platform. We kindly ask that you acknowledge the funding below in your code and publications. Copy and past the following lines into your repository when using this code.

[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://grantome.com/grant/NIH/R01-EB029272-01)
[![NIH-NIMH-R01MH126699](https://img.shields.io/badge/NIH_NIMH-R01MH126699-green.svg)](https://grantome.com/grant/NIH/R01-EB029272)

### Citations

Please use the following citation when using ezBIDS:

Levitas, Daniel, et al. "ezBIDS: Guided standardization of neuroimaging data interoperable with major data archives and platforms." [Article](https://www.nature.com/articles/s41597-024-02959-0).


Copyright © 2022 brainlife.io at University of Texas at Austin
