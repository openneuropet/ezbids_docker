[![Docker Build (Local)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-local.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-local.yml)
[![Docker Build (Nginx)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-nginx.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/docker-build-nginx.yml)
[![Test Local Upload](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-local.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-local.yml)
[![Test Nginx Upload](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-nginx.yml/badge.svg)](https://github.com/openneuropet/ezbids_docker/actions/workflows/test-upload-nginx.yml)

# THIS FORK INCLUDES ADDITIONAL SUPPORT SPECIFICALLY FOR PET ([ORIGINAL PROJECT](https://github.com/brainlife/ezbids_docker))

# ezBIDS

The secure, cloud-based service for the semi-automated mapping of entire
sessions of neuroimaging data to the Brain Imaging Data Structure
([BIDS](https://bids.neuroimaging.io/)) standard.

<img width="1450" alt="Screenshot 2023-11-01 at 11 50 48 AM" src="https://github.com/brainlife/ezbids/assets/2119795/2c054297-1503-4ebb-8718-336012c80b48">

### About

This is the repository for a semi-supervised web-service for converting
neuroimaging data files to [BIDS](https://bids.neuroimaging.io/). This specific
repository exists for users wishing to deploy this web service on premise.

Unlike other BIDS converters, ezBIDS eliminates the need for coding and command
line interfaces (CLI), doing the bulk of the work behind the scenes to save
users time. Importantly, ezBIDS does not require an organizational structure for
uploaded data.

A series of inferenial heuritics analyze the uploaded data to provide a _first
guess_ BIDS structure, which is presented to users through the web-browser user
interface. Users verify the _first guess_ and modify the information provided as
needed so as to best match the final BIDS structure.

Data from all major scanner vendors are accepted by ezBIDS. ezBIDS enables
pseudo-anonymization by providing options for the defacing of anatomical
sequences, and removes all identifying metadata information (e.g. `PatientName`)
before final conversion to BIDS.

The BIDS output can then be downloaded back to the user's computer, or uploaded
to open repositories such as [brainlife.io](https://brainlife.io/) or
[OpenNeuro.org](https://openneuro.org/).

Helpful links:

1. [ezBIDS website](https://brainlife.io/ezbids)
2. [ezBIDS user documentation](https://brainlife.io/docs/using_ezBIDS/)
3. [ezBIDS tutorial](https://brainlife.io/docs/tutorial/ezBIDS/)
4. [ezBIDS tutorial video](https://www.youtube.com/embed/L8rWA8qgnpo)

### Browser Requirements

ezBIDS supports uploads from modern browsers, including Google Chrome,
Microsoft Edge, Firefox, Safari, Brave, Opera, and other Chromium-based
browsers.

Chrome and Edge are recommended for large datasets. They use the
[File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API)
to traverse selected or dropped directories and read files lazily as upload
batches are prepared. This reduces browser memory pressure and makes large
uploads faster and more reliable.

Browsers without the File System Access API use directory/file selection and
drag-and-drop fallbacks. These browsers are supported, although large uploads
may initialize and upload more slowly. If a browser cannot read a dropped
directory, use the **Select Directory** button instead.

### Usage

Users do not need to organize their uploaded data in any specific manner, and
users may choose to compress (e.g. zip, tar) their uploaded data.

Should users feel the need to anonymize data before uploading, we strongly
recommend that subjects (and sessions, if applicable) be organized into subject
(and session) folders, with explicit labeling of the preferred subjects (and
sessions) IDs (e.g. `MRI_data/sub-01/ses-01/DICOMS`). Failure to do so for
non-anonymized data may result in an inaccurate _first guess_ and require
additional edits in the web browser.

#### Local Usage

There are three methods for deploying this service one for local use, another
using nginx for sitewide deployments, and an apptainer option for local use
where docker is unavailable.

For users that can are not setting this service up for others it's recommended
to run without nginx. Additionally, for impermanent deployments users can be up
and running with 1 command and no other configuration:

```bash
docker compose up
# or to hide the output
docker compose up -d
```

**Apptainer Use**

The apptainer image must be built from the `EverythingDockerfile`, which is in
turn dependent on the images defined/tagged in `docker-compose.yml` being built.
To create the apptainer image one must do the following:

```bash
git clone https://github.com/openneuropet/ezbids_docker.git
cd ezbids_docker
docker compose build
docker build -f EverythingDockerfile -t ezbids-everything .
```

[!NOTE]
This combined docker image can be run with the following command: 
`docker run -p 27017:27017 -p 8082:8082 -p 3000:3000 -p 8000:8000 -v /tmp/ezbids-workdir:/tmp ezbids-everything`

Next build the apptainer image: 

```bash
apptainer build ezbids-everything.sif docker-daemon://ezbids-everything:latest
```

Then run the following apptainer command:

```bash
apptainer instance run --fakeroot --writable-tmpfs --cleanenv --no-home ezbids-everything.sif ezbids-apptainer
```

To stop:

```bash
apptainer instance stop ezbids-apptainer
```

It should be noted that apptainer occasionally changes which ports it maps the
ezBIDS UI to, but that will be mentioned in the console following the instance
run step above. Additionally, using `apptainer run` can lead to orphaned
processes when the container exits. Use `apptainer instance run` for this image.

**Back to Docker**

For a sitewide deployment, the initial setup requires configuring the local
environment via a `.env` file. The first steps are to copy the `example.env`
file in this repo to `.env`:

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

# Set to true for Brainlife login; false enables local account registration and login.
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

- `BRAINLIFE_AUTHENTICATION`: Set to `true` for Brainlife login. When false or
  unset, optional local account registration and login are enabled by default.
- `PRESORT`: Enable this option if your data is a flat folder full of dicoms,
  otherwise it's best to organize your such that a single scan/session/modality
  is contained in it's own folder. In order to extract the necessary PET
  metadata (information from spreadsheets) this variable should be disabled with
  `false`
- `EZBIDS_TMP_DIR`: By default ezBIDS will write data to `/tmp/ezbids-workdir`,
  you can change that default path by providing a different path here.
- `BRAINLIFE_USE_NGINX`: Enable with `true` if you want to host this service to
  multiple clients. Nginx requires ssl certificates to function, you have the
  option of generating self signed or providing certificates from a registered
  authority.
- `SERVER_NAME`: Defaults to local host, if using Nginx then set this to the
  host name matching the server/ssl certificate.

#### Local accounts and private session history

Optional local account registration and login are enabled by default when
`BRAINLIFE_AUTHENTICATION` is false or unset. The equivalent explicit configuration
in `.env` is shown below. Rebuild/recreate the API and UI services after changes:

```dotenv
EZBIDS_AUTH_MODE=local
EZBIDS_REGISTRATION_ENABLED=true
EZBIDS_ALLOWED_ORIGINS=http://localhost:3000
EZBIDS_SECURE_COOKIES=false
```

For an HTTPS deployment, set `EZBIDS_ALLOWED_ORIGINS` to the public origin
(for example `https://ezbids.example.org`, without a trailing slash) and set
`EZBIDS_SECURE_COOKIES=true`. Multiple allowed origins can be comma-separated.
The certificate setup script writes these HTTPS settings into its generated `.env`.
For older `.env` files missing these settings, `launch.sh` supplies defaults based
on `SERVER_NAME` and `BRAINLIFE_USE_NGINX`, preserving explicit values. When
switching an existing configuration to HTTPS, update any explicit HTTP origins
and set secure cookies to `true`.
For remote development with the default Compose setup, forward both UI port
3000 and API port 8082, and open `http://localhost:3000/ezbids/`.

The deployment entry points receive settings differently:

| Deployment | Where settings come from | Origin/cookie defaults when unset |
| --- | --- | --- |
| HTTP Compose (`docker-compose.yml`, `docker-compose-dev.yaml`) | Project `.env` or exported shell variables | UI at `http://SERVER_NAME:3000` plus localhost origins; secure cookies off |
| HTTPS Compose (`docker-compose-nginx.yml`) | Project `.env` or exported shell variables | `https://SERVER_NAME`; secure cookies on |
| `launch.sh` | Sources `.env`, copying `example.env` if missing | Chooses the HTTP/HTTPS defaults above; explicit values win |
| Combined Docker image | `docker run --env-file runtime.env` or `-e` | Local HTTP origins; secure cookies off |
| Apptainer | Explicit `--env-file runtime.env` or `--env` with `--cleanenv` | Local HTTP origins; secure cookies off |

For combined Docker and Apptainer deployments, a project `.env` is not loaded
automatically. Pass a runtime environment file explicitly. For example, for local
HTTP use:

```dotenv
BRAINLIFE_AUTHENTICATION=false
EZBIDS_REGISTRATION_ENABLED=true
EZBIDS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
EZBIDS_SECURE_COOKIES=false
VITE_APIHOST=http://localhost:8082
```

Pass this file with `docker run --env-file runtime.env ...` or
`apptainer instance run --cleanenv --env-file runtime.env ...`. Apptainer's
[environment options](https://apptainer.org/docs/user/latest/environment_and_metadata.html)
allow explicit settings alongside `--cleanenv`. Replace the origin and browser API
URL for remote access. For an external HTTPS proxy, set secure cookies to `true`.
The combined image inherits auth settings into its services; the UI queries the
API for the active mode. Explicit `VITE_*` values override UI entrypoint defaults.
For the nginx image, UI assets are built ahead of time; runtime auth configuration
comes from the API, rather than Compose's UI environment at container startup.

Users can convert as guests without registering or logging in. Guests access their
work using an opaque browser cookie backed by MongoDB (valid for 30 days); other browsers and accounts
cannot open those sessions. Guest work is not added to an account's history.
Users who register and log in can open their own previous uploads from **My sessions**.
Session reads, uploads, changes, and downloads enforce ownership on the server;
local accounts cannot share sessions or access another account's session by URL.
Password-hashing work is limited independently of client connections, so closing
a request does not leak a slot or release one while hashing is still running.
Login limits use the socket peer IP by default. The nginx Compose deployment
trusts only addresses resolved for its private `nginx` service, refreshing that
resolution and failing closed if DNS is unavailable. Direct API ports ignore
forwarding headers. For a different reverse proxy, explicitly set
`EZBIDS_TRUSTED_PROXIES` to its exact peer addresses/CIDRs, or
`EZBIDS_TRUSTED_PROXY_NAMES` to trusted private-network DNS names. Do not trust
arbitrary forwarding headers or the whole container subnet.

Passwords use salted scrypt hashes. Login cookies are HttpOnly, expire after seven
days, and are revoked on logout. Set `EZBIDS_REGISTRATION_ENABLED=false` to close
registration while allowing existing users to log in. There is no email
verification or self-service password reset in this version.

Existing anonymous sessions are hidden in local mode because their original
owner cannot be determined safely. An operator who has verified ownership can
assign specific anonymous session IDs to an existing local account:

```bash
docker compose exec api npm run assign-legacy-sessions -- --email user@example.org SESSION_ID [SESSION_ID ...]
```

The script refuses a batch if any ID is missing or already belongs to an account.
It does not claim anonymous sessions automatically during registration.

Leaving `EZBIDS_AUTH_MODE` unset selects `brainlife` when
`BRAINLIFE_AUTHENTICATION=true`, and `local` otherwise. Explicit modes are
`disabled`, `brainlife`, and `local`; unrestricted anonymous access requires an explicit
`EZBIDS_AUTH_MODE=disabled`.
Disabling authentication allows anonymous access, so use `local` consistently on
all API instances when deploying private accounts.

Run `npm run test:auth` to exercise policy, security, and credentialed-download
regressions. Tests transpile API TypeScript in memory rather than overwriting
JavaScript used by running services. To include the database integration suite,
set `EZBIDS_TEST_MONGO_URL=mongodb://HOST:PORT/ezbids_auth_test` to an explicitly
disposable MongoDB instance. That suite creates accounts/sessions, uses a separate
temporary upload directory, and drops only that test database when finished; it
refuses any other database name. Run the bundled client checks with
`python3 -m unittest discover -s test -p client_cookie_test.py`.

Deployment configuration checks run separately with
`python3 -m unittest discover -s test -p deployment_config_test.py`. They render
Compose configuration and stub service launches and certificate generation;
they do not start or restart the application stack. To also check Supervisor
runtime environment inheritance, set `EZBIDS_TEST_COMBINED_IMAGE` to a locally
built combined image when running the same command. That optional check starts
an isolated container with networking disabled and substitutes environment-reporting
processes for the API and UI.

#### Guest authentication upgrade and recovery

New guest cookies are opaque random tokens; only their hashes and expiry are
stored in MongoDB. They survive image/key replacement as long as the existing
database is preserved. Image-generated RSA keys continue to serve short-lived
download tokens; they are no longer the persistent credential for new guests.

Before replacing a deployment that has signed guest cookies from commit
`b5af806`, preserve its **public verification key** in the database. Do this while
the old API is still running, using the candidate image's migration command:

1. Record the current API image and MongoDB volume, and take your normal database
   backup. Keep the existing database/volume attached; do not use `down -v` or
   renew anonymous volumes. Named-volume conversion is a separate migration.
2. Copy the public key from the **currently running API**, before rebuilding or
   replacing it. Substitute its actual container name below:

   ```bash
   docker cp ezbids-api:/app/api/ezbids.pub /tmp/ezbids-legacy-guest.pub
   ```

3. Build the candidate API image while the old service continues running. Using
   your deployment's Compose file, run this one-shot command against the same
   database. It does not start the API or process uploads:

   ```bash
   docker compose run --rm --no-deps \
     -v /tmp/ezbids-legacy-guest.pub:/migration/guest.pub:ro \
     api bash -lc '../node_modules/.bin/tsc && node preserve-guest-key.js --public-key /migration/guest.pub'
   ```

   Repeat for each old signing key if API replicas used different images. The
   import is an idempotent atomic upsert and stores public keys only. A failed
   import leaves the running old API untouched; stop the rollout and correct it
   before replacing any service. Never export or print private keys.
4. Schedule API replacement after active uploads have finished. A single-instance
   replacement has an availability gap; these scripts do not implement rolling
   deployment. The new API listens (and passes health checks) only after database
   setup and guest-key migration checks succeed. It refuses readiness if existing
   legacy guest-owned sessions are found without a preserved verification key.
5. Old signed cookies keep their guest identity and original expiry when exchanged
   for opaque cookies. No anonymous legacy sessions are automatically claimed.
   Preserve MongoDB and the imported keys during recovery. Once opaque cookies
   have been issued, rollback must use an opaque-cookie-compatible image, or a
   forward fix: `b5af806` cannot read the new cookie format. Do not rotate/delete
   the old verifier or replace the database as a recovery step.

For combined Docker/Apptainer, import the current public key into the same
persistent MongoDB using the migration script before replacing the image. Do not
assume a new image's generated key can verify an older deployment's cookies. No
private-key bind mounts or automatic key/file replacement are introduced here.
Existing ten-minute download links may still expire during an image replacement.

“Send to OpenNeuro” remains an untested integration requiring separate OAuth and
sharing design. Local-mode downloads still require the owner cookie plus a
short-lived token; that protection is not relaxed to support third-party imports.
No OpenNeuro transfer is performed by these tests. Niivue receives authenticated
image bytes through the same credential-aware client as other browser downloads.

#### Nginx Setup

There are some additional steps required for running this service with nginx and
https, namely providing ssl certificates. To create self signed certificates run
the `create_self_signed_certs.sh` script and provide the hostname/ipaddress of
the host as the first argument. This will create all of the certificates you
need and locate them in the `nginx/ssl/` folder. If you want to provide your own
certificates place them manually in the `nginx/ssl/` folder and rename them to
follow this convention:

`sslcert.cert`, `sslcert.key`, and if your certificate is encrypted provide the
password file as `sslpassword`.

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

If you're using a password make sure to uncomment the line in the nginx config
file (`nginx/production_nginx.conf`) for that password file.

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

Once you've completed your configuring, you can start the application with the
`launch.sh` script. It will export the variables set in the `.env` file to your
environment and based on your choices launch ezBIDS at `localhost:3000` or
`https://yourhostname/`

If you're switching between nginx or the localhost option make sure to rebuild
the containers with:

```
docker compose build -f docker-compose.yml (or docker-compose-nginx.yml) --build --no-cache
```

Using `--no-cache` might slow things down, but it's a way to ensure you don't
run into issues with "stale" containers. The `--parallel` flag can speed things
up as it will build multiple containers at once.

### TODO

- [ ] In a separate conversion fix, exclude `derivatives/` trees from input
  discovery, including after archive extraction. FreeSurfer registration `.dat`
  files inside derivatives are currently mistaken for MEG recordings. Cover this
  case with a regression test; keep the fix outside the local-login feature branch.

### Authors

- [Daniel Levitas](djlevitas208@gmail.com)\*
- [Soichi Hayashi](soichih@gmail.com)\*
- [Sophia Vinci-Booher](sophia.vinci-booher@vanderbilt.edu)
- [Anibal Heinsfeld](anibalsolon@utexas.edu)
- [Dheeraj Bhatia](dheeraj.bhatia@utexas.edu)
- [Nicholas Lee](niconal902@gmail.com)
- [Anthony Galassi](anthony.galassi@nih.gov)
- [Guiomar Niso](guiomar.niso@ctb.upm.es)
- [Franco Pestilli](pestilli@utexas.edu)

* _Both authors contributed equally to this project_

### Funding Acknowledgement

brainlife.io is publicly funded, and for the sustainability of the project it is
helpful to acknowledge the use of the platform. We kindly ask that you
acknowledge the funding below in your code and publications. Copy and past the
following lines into your repository when using this code.

[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://grantome.com/grant/NIH/R01-EB029272-01)
[![NIH-NIMH-R01MH126699](https://img.shields.io/badge/NIH_NIMH-R01MH126699-green.svg)](https://grantome.com/grant/NIH/R01-EB029272)

### Citations

Please use the following citation when using ezBIDS:

Levitas, Daniel, et al. "ezBIDS: Guided standardization of neuroimaging data
interoperable with major data archives and platforms."
[Article](https://www.nature.com/articles/s41597-024-02959-0).

Copyright © 2022 brainlife.io at University of Texas at Austin
