import os
import pathlib
import sys
import time
import pytest
from socket import gethostname

import requests
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import InsecureRequestWarning

# Add the test directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from browser import check_text_on_page, find_and_click_button, generate_css_selector
from utilities import (
    mark_upload_complete,
    upload_files,
    create_session,
    get_session_status,
)

# Configuration
test_data = {"FlatFolderMixed": pathlib.Path("test_data/mixed_dicoms").resolve()}

# Get the hostname for testing
hostname = gethostname()

# Configure test hosts based on environment
test_hosts = {
    "localhost": {
        "url": "http://localhost:3000",
        "api": "http://localhost:8082",
        "use_nginx": False,
    },
    hostname: {
        "url": f"https://{hostname}/ezbids/",
        "api": f"https://{hostname}/api/",
        "use_nginx": True,
    },
}

# For remote testing, we need to use the same hostname for both frontend and API
# to avoid CORS issues. This will be the hostname that's accessible from your browser.
REMOTE_HOST = "localhost"  # Change this to your server's public hostname if needed

# Disable SSL verification for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


@pytest.fixture(scope="module")
def active_host():
    """Find an active ezBIDS instance to test against."""
    urls_to_test = {}
    for host, host_data in test_hosts.items():
        try:
            endpoint_status = requests.get(
                host_data.get("url"), verify=False, timeout=2
            ).status_code
            if endpoint_status == 200:
                urls_to_test[host] = host_data
        except (ConnectionRefusedError, requests.exceptions.ConnectionError):
            pass

    if len(urls_to_test) < 1:
        pytest.skip("No active ezBIDS instances found")

    # Return the first available host
    return next(iter(urls_to_test.values()))


@pytest.fixture(scope="function")
def web_driver():
    """Create and yield a headless Firefox webdriver."""
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    yield driver
    driver.quit()


@pytest.fixture(scope="function")
def session(active_host):
    """Create a new session for testing."""
    session = create_session(api_url=active_host.get("api"))
    return session


def test_upload_flat_folder_of_dicoms(active_host, web_driver, session):
    """Test uploading a flat folder of DICOM files and verify all statuses."""
    api_url = active_host.get("api")
    host_url = active_host.get("url")
    session_id = session["_id"]

    print(f"\n=== Starting ezBIDS Upload Test at {host_url} ===\n")
    sys.stdout.flush()

    # Test data setup
    local_test_data_path = test_data["FlatFolderMixed"]
    print(f"Using FlatFolderMixed at {local_test_data_path}")
    sys.stdout.flush()

    files_to_upload = []
    for root, _, files in os.walk(local_test_data_path):
        for file in files:
            files_to_upload.append(os.path.join(root, file))

    print(f"Found {len(files_to_upload)} files to upload")
    sys.stdout.flush()
    assert len(files_to_upload) > 0, "No files found to upload"

    # Navigate to the application
    print("\nOpening browser to view progress...")
    sys.stdout.flush()
    web_driver.get(host_url)

    # Test initial page load and get started button
    get_started_button = WebDriverWait(web_driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".el-button--primary"))
    )
    get_started_button.click()

    # Navigate to specific session
    if "/ezbids/" in host_url:
        session_url = f"{host_url}/convert#{session_id}"
    else:
        session_url = f"{host_url}/ezbids/convert#{session_id}"

    # Use print with flush=True to ensure output is visible even with pytest
    print("\n" + "=" * 80, flush=True)
    print(f"SESSION URL: {session_url}", flush=True)
    print("=" * 80 + "\n", flush=True)
    print(
        "NOTE: If you don't see the session URL above, run pytest with -s flag:",
        flush=True,
    )
    print("pytest test/upload_flat_folder_of_dicoms.py -v -s", flush=True)
    print("\n", flush=True)

    web_driver.get(session_url)
    time.sleep(1)
    web_driver.refresh()

    # Upload files in batches
    batch_size = 100
    for i in range(0, len(files_to_upload), batch_size):
        batch = files_to_upload[i : i + batch_size]
        print(
            f"Uploading batch {i//batch_size + 1}/{(len(files_to_upload) + batch_size - 1)//batch_size} ({len(batch)} files)"
        )
        sys.stdout.flush()
        upload_files(session_id, batch, api_url)

    # Mark upload as complete
    print("Marking upload as complete...")
    sys.stdout.flush()
    mark_upload_complete(session_id, api_url)

    print("\n=== API Status Checks ===\n")
    sys.stdout.flush()

    # Test session status progression
    steps = {}
    max_wait_time = 300  # 5 minutes timeout
    start_time = time.time()

    while time.time() - start_time < max_wait_time:
        session_status = get_session_status(session_id, api_url)
        status = session_status.get("status")
        print(f"Current status: {status}")
        sys.stdout.flush()

        if status == "uploaded" and not steps.get("uploaded"):
            steps["uploaded"] = True
            print("✓ Uploaded status reached")
            sys.stdout.flush()
        elif status == "preprocessing" and not steps.get("preprocessing"):
            steps["preprocessing"] = True
            print("✓ Preprocessing status reached")
            sys.stdout.flush()
        elif "analyzed" in status:
            steps["analyzed"] = True
            print("✓ Analyzed status reached")
            sys.stdout.flush()
            break
        elif status in ["failed", "finalized"]:
            print(f"Session failed with status: {status}")
            sys.stdout.flush()
            pytest.fail(f"Session failed with status: {status}")

        time.sleep(0.1)

    print("\n=== Test Summary ===\n")
    print("API Status Checks:")
    print(f"{'✓' if steps.get('uploaded') else '✗'} Status 'uploaded'")
    print(f"{'✓' if steps.get('preprocessing') else '✗'} Status 'preprocessing'")
    print(
        f"{'✓' if steps.get('analyzed') else '✗'} Status 'analyzed - successfully run preprocess.sh'"
    )
    sys.stdout.flush()

    # Individual assertions for each step
    assert steps.get("uploaded"), "Upload step failed - status 'uploaded' not reached"
    assert steps.get(
        "preprocessing"
    ), "Preprocessing step failed - status 'preprocessing' not reached"
    assert steps.get("analyzed"), "Analysis step failed - status 'analyzed' not reached"
