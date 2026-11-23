#!/usr/bin/env bash
# Run the real API, MongoDB, conversion handler, and UI against disposable state.
set -Eeuo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
data=${EZBIDS_E2E_DATA:-}
profile=${EZBIDS_E2E_PROFILE:-pet-phantom.json}
artifacts=${EZBIDS_E2E_ARTIFACTS:-}
python=${EZBIDS_E2E_PYTHON:-"$repo_root/test/.venv/bin/python"}
wait_timeout=${EZBIDS_E2E_STARTUP_TIMEOUT:-180}

usage() {
    cat <<'EOF'
Usage: test/functional/run.sh --data DIRECTORY [--profile PROFILE.json] [--artifacts DIRECTORY]

Runs host Selenium pytest against fresh source images and isolated container data.
The data directory is read by the browser test and is never mounted into a container.
Use EZBIDS_E2E_DATA, EZBIDS_E2E_PROFILE, EZBIDS_E2E_ARTIFACTS, EZBIDS_E2E_PYTHON,
or EZBIDS_E2E_STARTUP_TIMEOUT to supply the corresponding defaults.
EZBIDS_E2E_PYTEST_ARGS supplies additional pytest arguments (for example, -x).
All containers and volumes created by this invocation are removed on exit.
EOF
}

while (($#)); do
    case $1 in
        --data|--profile|--artifacts)
            if (($# < 2)); then echo "Missing value for $1" >&2; exit 2; fi
            case $1 in
                --data) data=$2 ;;
                --profile) profile=$2 ;;
                --artifacts) artifacts=$2 ;;
            esac
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z $data || ! -d $data ]]; then
    echo 'Provide an existing input directory with --data or EZBIDS_E2E_DATA.' >&2
    exit 2
fi
if [[ ! -x $python ]]; then
    echo "Python interpreter not executable: $python (set EZBIDS_E2E_PYTHON)." >&2
    exit 2
fi
if [[ ! $wait_timeout =~ ^[1-9][0-9]*$ ]]; then
    echo 'EZBIDS_E2E_STARTUP_TIMEOUT must be a positive integer.' >&2
    exit 2
fi
if [[ $profile != */* ]]; then profile="$repo_root/test/functional/profiles/$profile"; fi
if [[ ! -f $profile ]]; then echo "Profile does not exist: $profile" >&2; exit 2; fi
profile=$("$python" -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$profile")
command -v docker >/dev/null
docker compose version >/dev/null
docker info >/dev/null
data=$(cd -- "$data" && pwd)
run_dir=$(mktemp -d /tmp/ezbids-e2e.XXXXXXXX)
run_id=$(basename "$run_dir" | tr '[:upper:].' '[:lower:]-')
artifacts=${artifacts:-"/tmp/$run_id-artifacts"}
mkdir -p -- "$artifacts"
artifacts=$(cd -- "$artifacts" && pwd)
export EZBIDS_E2E_DATA="$data" EZBIDS_E2E_PROFILE="$profile" EZBIDS_E2E_ARTIFACTS="$artifacts"
export EZBIDS_E2E_BUILD_CONTEXT="$run_dir/source"
export EZBIDS_E2E_API_IMAGE="$run_id:api"
export EZBIDS_E2E_HANDLER_IMAGE="$run_id:handler"
export EZBIDS_E2E_UI_IMAGE="$run_id:ui"
compose=(docker compose --env-file /dev/null --project-name "$run_id" --project-directory "$repo_root" -f "$repo_root/test/functional/compose.yml")
compose_ready=false

cleanup() {
    result=$?
    trap - EXIT INT TERM
    set +e
    down_result=0
    if [[ $compose_ready == true ]]; then
        "${compose[@]}" logs --no-color --timestamps >"$artifacts/stack.log" 2>&1
        "${compose[@]}" ps --all --format json >"$artifacts/containers.json" 2>&1
        "${compose[@]}" down --volumes --remove-orphans --timeout 15 >"$artifacts/teardown.log" 2>&1
        down_result=$?
    fi
    docker image rm "$EZBIDS_E2E_API_IMAGE" "$EZBIDS_E2E_HANDLER_IMAGE" "$EZBIDS_E2E_UI_IMAGE" >>"$artifacts/teardown.log" 2>&1
    rm -rf -- "$run_dir"
    if ((result == 0 && down_result != 0)); then result=$down_result; fi
    echo "Functional-test artifacts: $artifacts"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Resolve ports before starting the API so its explicit browser origin is correct.
# The ports are allocated together, then released for Docker's loopback bindings.
read -r EZBIDS_E2E_API_PORT EZBIDS_E2E_UI_PORT < <("$python" - <<'PY'
import socket
with socket.socket() as api, socket.socket() as ui:
    api.bind(('127.0.0.1', 0))
    ui.bind(('127.0.0.1', 0))
    print(api.getsockname()[1], ui.getsockname()[1])
PY
)
export EZBIDS_E2E_API_PORT EZBIDS_E2E_UI_PORT
export EZBIDS_E2E_API_URL="http://127.0.0.1:$EZBIDS_E2E_API_PORT"
export EZBIDS_E2E_UI_URL="http://127.0.0.1:$EZBIDS_E2E_UI_PORT/ezbids/"

# Stage current working-tree bytes, including uncommitted tracked changes. Limit
# the context to application sources; never send .env, keys, uploads, or backups.
"$python" - "$repo_root" "$EZBIDS_E2E_BUILD_CONTEXT" <<'PY'
import pathlib
import shutil
import subprocess
import sys

root, target = map(pathlib.Path, sys.argv[1:])
target.mkdir()
paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--', 'api', 'handler', 'ui'], text=True).split('\0')
paths += ['package.json', 'package-lock.json']
for name in filter(None, paths):
    path = pathlib.PurePosixPath(name)
    if (path.suffix in {'.key', '.pub', '.map'} or path.name.startswith('.env')
            or path.parts[0] in {'api', 'handler'} and path.suffix == '.js'
            or 'node_modules' in path.parts or '__pycache__' in path.parts):
        continue
    source = root / path
    if not source.is_file():
        continue
    if source.is_symlink():
        raise SystemExit(f'Refusing a source symlink in the build context: {name}')
    destination = target / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
PY

# Reuse dependencies only when every installed locked package has the expected
# version. Changed manifests fall back to a lockfile install during image build.
cat >"$EZBIDS_E2E_BUILD_CONTEXT/check-dependencies.cjs" <<'JS'
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[2];
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json')));
if (!lock.packages) process.exit(1);
for (const [name, pkg] of Object.entries(lock.packages)) {
    if (!name.startsWith('node_modules/') || !pkg.version) continue;
    let installed;
    try {
        installed = JSON.parse(fs.readFileSync(path.join(root, name, 'package.json')));
    } catch (error) {
        if (pkg.optional && error.code === 'ENOENT') continue;
        process.exit(1);
    }
    if (installed.version !== pkg.version) process.exit(1);
}
JS

cat >"$EZBIDS_E2E_BUILD_CONTEXT/Dockerfile.api" <<'DOCKER'
ARG BASE_IMAGE=openneuropet/ezbids-api:latest
FROM ${BASE_IMAGE}
USER root
WORKDIR /app
RUN rm -rf /app/api /app/handler /app/ui /app/.env /app/.git
COPY package.json package-lock.json ./
COPY check-dependencies.cjs /check-dependencies.cjs
RUN node /check-dependencies.cjs /app || npm ci --no-audit --no-fund
COPY api ./api
RUN node node_modules/typescript/bin/tsc --project api/tsconfig.json \
    && openssl genrsa -out api/ezbids.key 2048 \
    && chmod 600 api/ezbids.key \
    && openssl rsa -in api/ezbids.key -pubout -out api/ezbids.pub
WORKDIR /app/api
ENTRYPOINT ["node"]
CMD ["ezbids.js"]
DOCKER

cat >"$EZBIDS_E2E_BUILD_CONTEXT/Dockerfile.handler" <<'DOCKER'
ARG BASE_IMAGE=openneuropet/ezbids-handler:latest
FROM ${BASE_IMAGE}
USER root
WORKDIR /app
RUN rm -rf /app/api /app/handler /app/ui /app/.env /app/.git
COPY package.json package-lock.json ./
COPY check-dependencies.cjs /check-dependencies.cjs
RUN node /check-dependencies.cjs /app || npm ci --no-audit --no-fund
COPY api ./api
COPY handler ./handler
COPY ui/src/assets/schema/rules/entities.json ./ui/src/assets/schema/rules/entities.json
RUN node node_modules/typescript/bin/tsc --project api/tsconfig.json \
    && node node_modules/typescript/bin/tsc --project handler/tsconfig.json \
    && chmod +x handler/convert.js
WORKDIR /app/handler
ENTRYPOINT ["node"]
CMD ["handler.js"]
DOCKER

cat >"$EZBIDS_E2E_BUILD_CONTEXT/Dockerfile.ui" <<'DOCKER'
ARG BASE_IMAGE=openneuropet/ezbids-ui:latest
FROM ${BASE_IMAGE}
USER root
WORKDIR /ui
RUN find /ui -mindepth 1 -maxdepth 1 ! -name node_modules -exec rm -rf {} +
COPY ui/ ./
COPY check-dependencies.cjs /check-dependencies.cjs
RUN node /check-dependencies.cjs /ui || npm ci --no-audit --no-fund
ARG VITE_APIHOST
ARG VITE_EZBIDS_AUTH_MODE=local
ARG VITE_BRAINLIFE_AUTHENTICATION=false
ENV VITE_APIHOST=${VITE_APIHOST} \
    VITE_EZBIDS_AUTH_MODE=${VITE_EZBIDS_AUTH_MODE} \
    VITE_BRAINLIFE_AUTHENTICATION=${VITE_BRAINLIFE_AUTHENTICATION}
RUN npm run build
ENTRYPOINT ["node_modules/.bin/vite"]
CMD ["preview", "--host", "0.0.0.0", "--port", "3000", "--strictPort"]
DOCKER

"${compose[@]}" config >"$artifacts/compose.yml"
compose_ready=true
"${compose[@]}" build --pull=false 2>&1 | tee "$artifacts/build.log"
"${compose[@]}" up --detach --no-build --pull never --wait --wait-timeout "$wait_timeout" 2>&1 | tee "$artifacts/startup.log"

"$python" - "$EZBIDS_E2E_API_URL/health" "$EZBIDS_E2E_UI_URL" <<'PY'
import sys
import urllib.request
for url in sys.argv[1:]:
    request = urllib.request.Request(url, headers={'Accept': 'text/html'} if url.endswith('/ezbids/') else {})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise SystemExit(f'Unexpected readiness status from {url}: {response.status}')
PY

cd -- "$repo_root"
mapfile -d '' -t pytest_args < <("$python" - <<'PY'
import os
import shlex
import sys
for arg in shlex.split(os.environ.get('EZBIDS_E2E_PYTEST_ARGS', '')):
    sys.stdout.write(arg + '\0')
PY
)
"$python" -m pytest -v -s test/functional/test_browser_workflow.py \
    --junitxml="$artifacts/junit.xml" "${pytest_args[@]}" 2>&1 | tee "$artifacts/pytest.log"
