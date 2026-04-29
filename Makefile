.PHONY: gettestdata clean-testdata setup-test test-upload clean-test format-md

# Create test_data directory if it doesn't exist
test/test_data:
	mkdir -p test/test_data

# Initialize and update submodules for test data
get-test-data: test/test_data
	test/gettestdata
	test/createmixedfolder

# Clean test data (remove submodules and their directories)
clean-testdata:
	test/cleantestdata

# Test environment setup
setup-test:
	cd test && uv venv .venv
	cd test && uv pip install -e .

# Run upload test
test-upload: setup-test
	cd test && uv run pytest upload_flat_folder_of_dicoms.py -v -s

# Clean test environment
clean-test:
	rm -rf test/.venv
	rm -rf test/__pycache__
	rm -rf test/.pytest_cache

# build local (non-nginx)
docker-build-local:
	EZBIDS_VERSION=$(shell git describe --tags --always) docker compose build

# build nginx (non-nginx)
docker-build-nginx:
	EZBIDS_VERSION=$(shell git describe --tags --always) docker compose -f docker-compose-nginx.yml build

docker-local-push:
	EZBIDS_VERSION=$(shell git describe --tags --always) docker compose push

docker-nginx-push:
	EZBIDS_VERSION=$(shell git describe --tags --always) docker compose -f docker-compose-nginx.yml push

docker-build-everything:
	docker build -f EverythingDockerfile -t openneuropet/ezbids-everything:latest .
	docker build -f EverythingDockerfile -t openneuropet/ezbids-everything:$(shell git describe --tags --always) .

docker-push-everything:
	docker push openneuropet/ezbids-everything:latest
	docker push openneuropet/ezbids-everything:$(shell git describe --tags --always)

# Format all markdown files with prettier (80 char line wrap)
format-md:
	@command -v npx >/dev/null 2>&1 || { echo "npx not found. Install Node.js first."; exit 1; }
	npx prettier --prose-wrap always --print-width 80 --write "**/*.md"