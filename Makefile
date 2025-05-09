.PHONY: gettestdata clean-testdata

# Create test_data directory if it doesn't exist
test/test_data:
	mkdir -p test/test_data

# Initialize and update submodules for test data
gettestdata: test/test_data
	@if [ ! -d "test/test_data/dcm_qa_nih" ]; then \
		git submodule add --force https://github.com/neurolabusc/dcm_qa_nih.git test/test_data/dcm_qa_nih; \
	fi
	@if [ ! -d "test/test_data/dcm_qa_uih" ]; then \
		git submodule add --force https://github.com/neurolabusc/dcm_qa_uih.git test/test_data/dcm_qa_uih; \
	fi
	@if [ ! -d "test/test_data/petdicoms" ]; then \
		git submodule add --force https://github.com/openneuropet/petdicoms.git test/test_data/petdicoms; \
	fi
	git submodule update --init test/test_data/dcm_qa_nih
	git submodule update --init test/test_data/dcm_qa_uih
	git submodule update --init test/test_data/petdicoms
	# Prevent accidental commits to submodules
	git config submodule.test/test_data/dcm_qa_nih.ignore dirty
	git config submodule.test/test_data/dcm_qa_uih.ignore dirty
	git config submodule.test/test_data/petdicoms.ignore dirty

# Clean test data (remove submodules and their directories)
clean-testdata:
	git submodule deinit -f test/test_data/dcm_qa_nih
	git submodule deinit -f test/test_data/dcm_qa_uih
	git submodule deinit -f test/test_data/petdicoms
	git rm -f test/test_data/dcm_qa_nih
	git rm -f test/test_data/dcm_qa_uih
	git rm -f test/test_data/petdicoms
	rm -rf .git/modules/test/test_data/dcm_qa_uih
	rm -rf .git/modules/test/test_data/dcm_qa_nih
	rm -rf .git/modules/test/test_data/petdicoms
	rm -rf test/test_data 