import os
import pathlib
import sys
import time
from socket import gethostname

import requests
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import InsecureRequestWarning
from browser import check_text_on_page, find_and_click_button, generate_css_selector
from utilities import (
    mark_upload_complete,
    upload_files,
    create_session,
    get_session_status,
)

# Configuration
test_data = {
    "FlatFolderMixed": pathlib.Path("test_data/mixed_dicoms").resolve()
}
hostname = gethostname()
test_hosts = {
    "localhost": {"url": "http://localhost:3000", "api": "http://localhost:8082"},
    #hostname: {"url": f"https://{hostname}", "api": f"https://{hostname}/api"},
    #"3.14.255.13": {"url": "https://3.14.255.13", "api": "https://3.14.255.13/api"},
}

# Disable SSL verification for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def main():
    # check to see if endpoints are up by making a request to each one
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
        raise Exception(
            f"No active ezBIDS instances located, \
start ezbids or update paths at urls_to_test {urls_to_test}"
        )
    for host, host_data in urls_to_test.items():
        test_url(host_data, test_data)


def test_url(host_data, test_data):
    api_url = host_data.get("api")
    host_url = host_data.get("url")

    print(f"\n=== Starting ezBIDS Upload Test at {host_url} ===\n")
    sys.stdout.flush()
    for name, data in test_data.items():
        print(f"Using {name} at {data}")
        local_test_data_path = data

        # Get all files in the directory
        files_to_upload = []
        for root, _, files in os.walk(local_test_data_path):
            for file in files:
                files_to_upload.append(os.path.join(root, file))

        print(f"Found {len(files_to_upload)} files to upload")
        sys.stdout.flush()

        # Create a new session
        session = create_session(api_url=api_url)
        session_id = session["_id"]
        print(f"Created session with ID: {session_id}")
        sys.stdout.flush()

        # Open the browser and navigate to the session immediately
        print("\nOpening browser to view progress...")
        sys.stdout.flush()

        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
        driver.get(host_url)

        # Wait for and click the "Get Started" button
        get_started_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".el-button--primary"))
        )
        get_started_button.click()

        # Navigate to the specific session
        # Check if the URL already contains /ezbids/ before adding it
        if "/ezbids/" in host_url:
            session_url = f"{host_url}/convert#{session_id}"
        else:
            session_url = f"{host_url}/ezbids/convert#{session_id}"

        driver.get(session_url)

        # Refresh the page after 1 second
        time.sleep(1)
        driver.refresh()

        # Upload files in batches
        batch_size = 100
        for i in range(0, len(files_to_upload), batch_size):
            batch = files_to_upload[i : i + batch_size]
            print(
                f"Uploading batch {i//batch_size + 1}/{(len(files_to_upload) + batch_size - 1)//batch_size} ({len(batch)} files)"
            )
            sys.stdout.flush()
            upload_files(session_id, batch, api_url)

        # Mark the upload as complete
        print("Marking upload as complete...")
        mark_upload_complete(session_id, api_url)

        print("\n=== API Status Checks ===\n")
        sys.stdout.flush()

        # Check the status of the session
        steps = {}
        while True:
            session_status = get_session_status(session_id, api_url)
            status = session_status.get("status")
            print(f"Current status: {status}")  # Add status logging
            sys.stdout.flush()

            # Track specific status messages
            if status == "uploaded" and not steps.get("uploaded"):
                steps["uploaded"] = True
                print("✓ Uploaded status reached")
            elif status == "preprocessing" and not steps.get("preprocessing"):
                steps["preprocessing"] = True
                print("✓ Preprocessing status reached")
            elif "analyzed" in status:
                steps["analyzed"] = True
                print("✓ Analyzed status reached")
                # Stop the browser and script after reaching analyzed status
                print("\n=== Test Summary ===\n")
                print("API Status Checks:")
                print(f"{'✓' if steps.get('uploaded') else '✗'} Status 'uploaded'")
                print(
                    f"{'✓' if steps.get('preprocessing') else '✗'} Status 'preprocessing'"
                )
                print(
                    f"{'✓' if steps.get('analyzed') else '✗'} Status 'analyzed - successfully run preprocess.sh'"
                )

                print("\nAll tests passed successfully!")
                break

            if status in ["failed", "finalized"]:
                break

            time.sleep(0.1)  # Check every 5 seconds

        print(f"\nProcessing completed with status: {session_status.get('status')}")
        print(f"Session URL: {session_url}")
        sys.stdout.flush()

        # Wait for 10 seconds before quitting the driver
        time.sleep(10)
        analysis_complete = check_text_on_page(
            driver, "Analysis complete!", timeout=30, check_interval=0.5
        )
        if analysis_complete.get("found"):
            print("Analysis complete!")
        else:
            print("Analysis not complete!")

        # Use the new find_and_click_button method to click the Next button
        find_and_click_button(driver, "Next")

        # wait for ctrl c to quit the script
        input("Press Ctrl+C to quit the script")

        driver.quit()


if __name__ == "__main__":
    main()
