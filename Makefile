.PHONY: gettestdata clean-testdata

# Create test_data directory if it doesn't exist
test/test_data:
	mkdir -p test/test_data

# Initialize and update submodules for test data
gettestdata: test/test_data
	test/gettestdata

# Clean test data (remove submodules and their directories)
clean-testdata:
	test/cleantestdata