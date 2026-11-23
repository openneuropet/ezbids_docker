# Full browser functional tests

These tests run Chrome against a disposable, containerized UI, API, MongoDB and conversion handler built from the
current tracked working-tree sources. The browser selects a directory, uploads the original DICOMs, edits dataset and
subject labels and PET metadata, advances through each wizard page, finalizes, and clicks Download BIDS. Both guest and
registered-account workflows run. The account test also logs out/in, reopens its session, and verifies a second account
cannot browse or open it.

Passing requires a recognized validator JSON report with zero errors, the expected number of downloaded NIfTI images,
and the metadata values actually saved in their JSON sidecars. A finished conversion or an empty dataset cannot pass.
Validator warnings are permitted, matching the application's current `--ignoreWarnings` invocation.

## Run

Install Docker with Compose v2 (`up --wait` support), Chrome or Chromium, and the Python test dependencies:

```bash
make setup-test
```

Selenium uses chromedriver from `PATH` or its driver cache; set `CHROMEDRIVER` to an explicit executable if needed.
`EZBIDS_E2E_BROWSER_BINARY` selects a Chromium binary. Its first run may download the driver. The runner uses the
existing `openneuropet/ezbids-{api,handler,ui}:latest` images for system tools and locked dependencies, and builds thin
layers containing the current app sources. Pull or build these base images beforehand. Override them using
`EZBIDS_E2E_API_BASE`, `EZBIDS_E2E_HANDLER_BASE`, and `EZBIDS_E2E_UI_BASE` to use specific tags or digests.

Prepare the small public PET fixture:

```bash
test/.venv/bin/python test/functional/fetch_phantoms.py
```

This downloads the public 110 MiB archive referenced by PET2BIDS's phantom script, checks its pinned SHA256, and
extracts only the 35 original GE Advance DICOMs (about 1.3 MiB) into `/tmp/ezbids-phantoms-cache/ge-advance-2d`. It
rechecks cached files before reuse. `--cache-dir` and `--archive` support another cache or an already downloaded
archive. S3 is the source for these DICOMs; download them when needed and keep only a disposable local cache outside
the checkout. Do not commit source DICOMs or the downloaded archive. Git ignores local DICOM files, `sourcedata/`
directories, and this phantom archive as an additional safeguard.
`test/gettestdata` and `test/createmixedfolder` use this same S3 fetcher for PET inputs; no PET DICOM submodule is needed.

```bash
test/functional/run.sh --data /tmp/ezbids-phantoms-cache/ge-advance-2d
```

Equivalent Make entry point:

```bash
EZBIDS_E2E_DATA=/tmp/ezbids-phantoms-cache/ge-advance-2d make test-functional
```

Use `--artifacts /absolute/path` to choose the diagnostics directory. Otherwise the runner prints its unique directory
under `/tmp`. It saves screenshots, validator/core/finalized JSON, the downloaded BIDS ZIP, container/build logs, JUnit
results, and teardown results. These artifacts contain the supplied test data and should stay outside Git.
`EZBIDS_E2E_HEADED=true` shows Chrome when a display is available; `EZBIDS_E2E_TIMEOUT=900` changes the per-conversion
timeout. `EZBIDS_E2E_PYTEST_ARGS=-x` stops after the first failure.

Each run has unique container/image names, loopback ports, a private network, MongoDB volume, and upload volume. Test
images generate signing keys during their build; host signing keys are never copied. The runner reads no deployment
`.env` and discovers no existing service. Cleanup removes its containers, data volumes, and temporary image tags on
success or failure. Existing sessions are untouched. The database has no external network, and handler telemetry is
disabled. The handler retains access to the application's public Cognitive Atlas task catalog. API/UI ports use a
separate bridge for loopback browser access. The browser blocks external HTTP(S) requests while permitting the loopback
app. No OpenNeuro transfer is attempted.

The GitHub Actions **Full browser functional tests** workflow runs this same public phantom scenario on manual dispatch.
It retains diagnostics for seven days. Local runs do not publish artifacts.

## Other data

```bash
test/functional/run.sh --data /path/to/original/dicoms --profile /path/to/profile.json
```

Start with [profiles/pet-phantom.json](profiles/pet-phantom.json). Profiles specify every expected subject/session,
series description (or anchored description pattern), datatype, entity values, metadata, and expected image count.
Values must describe the actual acquisition. The supplied profile documents its source and timing choices.
`{"type":"string","value":"n/a"}` selects a permitted alternative type before entering the value; array values are
entered through the form as comma-separated text. `expected_metadata_edits` requires a field that is absent before
editing, so the test exercises missing metadata entry. The default profile is for the selected single series, not the
entire archive.

Focused assertions and fixture checks can run without Docker or a browser:

```bash
test/.venv/bin/python -m pytest test/functional/test_workflow_assertions.py test/functional/test_fetch_phantoms.py test/telemetry_opt_out_test.py
node --test test/metadata-form.test.js
```
