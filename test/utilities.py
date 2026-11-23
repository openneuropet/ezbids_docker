import argparse
import atexit
from contextlib import ExitStack
import os
import sys
import time
from pathlib import Path
from socket import gethostname
from typing import Union
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL verification for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# A guest identity lives in a cookie. Reuse one client for every operation
# against the same API, including callers that use the legacy helper functions.
_http_sessions = {}


def http_session(api_url: str):
    key = api_url.rstrip('/')
    if key not in _http_sessions:
        _http_sessions[key] = requests.Session()
        atexit.register(_http_sessions[key].close)
    return _http_sessions[key]


def create_session(api_url: str):
    """Create a new session for file upload"""
    # Remove any trailing slashes from the API URL
    api_url = api_url.rstrip("/")

    response = http_session(api_url).post(f"{api_url}/session", json={}, verify=False)
    if response.status_code != 200:
        raise Exception(f"Failed to create session: {response.text}")
    return response.json()


def upload_files(session_id: str, files: list, api_url: str, root_dir=None):
    """Upload files with session-relative POSIX paths and the creating guest cookie."""
    api_url = api_url.rstrip('/')
    paths = [Path(name).resolve() for name in files]
    if not paths:
        raise ValueError('No files to upload')
    base = Path(root_dir).resolve() if root_dir is not None else Path(os.path.commonpath([str(name.parent) for name in paths]))
    data = {'paths': [name.relative_to(base).as_posix() for name in paths],
            'mtimes': [int(name.stat().st_mtime * 1000) for name in paths]}
    with ExitStack() as stack:
        file_objects = [('files', stack.enter_context(name.open('rb'))) for name in paths]
        response = http_session(api_url).post(f'{api_url}/upload-multi/{session_id}',
                                              data=data, files=file_objects, verify=False)
    if response.status_code != 200:
        raise Exception(f'Failed to upload files: {response.text}')
    return response.text


def mark_upload_complete(session_id, api_url):
    """Mark the upload as complete"""
    # Remove any trailing slashes from the API URL
    api_url = api_url.rstrip("/")

    response = http_session(api_url).patch(f"{api_url}/session/uploaded/{session_id}", verify=False)
    if response.status_code != 200:
        raise Exception(f"Failed to mark upload as complete: {response.text}")
    return response.text


def get_session_status(session_id, api_url):
    """Get the current status of the session"""
    # Make sure we're using the correct URL format
    # Remove any trailing slashes from the API URL
    api_url = api_url.rstrip("/")

    response = http_session(api_url).get(f"{api_url}/session/{session_id}", verify=False)
    if response.status_code != 200:
        raise Exception(f"Failed to get session status: {response.text}")
    return response.json()


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        type=str,
        help="Url of ezBIDS service, this script will attempt to upload "
        "to the correct api endpoint",
        required=True,
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Folder that you wish to upload to ezBIDS",
    )
    parser.add_argument("--local", action="store_true", default=False)
    parser.add_argument(
        "--batchsize",
        type=int,
        help="Number of files to upload simultaneously, default is 100",
        default=100,
    )

    args = parser.parse_args()

    # Determine the API URL based on the provided URL
    if args.local:
        # For local development, use HTTP
        api_url = "http://localhost:8082"
    elif "api" not in args.url:
        # For production, keep the original protocol (HTTPS)
        api_url = args.url.strip("/") + "/api"
    else:
        # If API is already in the URL, use it as is
        api_url = args.url

    print(f"Using API URL: {api_url}")
    sys.stdout.flush()

    # Create a new session
    try:
        session = create_session(api_url=api_url)
        session_id = session["_id"]
        print(f"Created session with ID: {session_id}")
        sys.stdout.flush()
    except Exception as e:
        print(f"Error creating session: {str(e)}")
        return

    # Get all files to upload
    files_to_upload = []
    try:
        for root, _, files in os.walk(args.data):
            for f in files:
                files_to_upload.append(os.path.join(root, f))
        print(f"Found {len(files_to_upload)} files to upload")
        sys.stdout.flush()
    except Exception as e:
        print(f"Error scanning directory: {str(e)}")
        return

    # Upload files in batches
    try:
        for i in range(0, len(files_to_upload), args.batchsize):
            batch = files_to_upload[i : i + args.batchsize]
            print(
                f"Uploading batch {i//args.batchsize + 1}/{(len(files_to_upload) + args.batchsize - 1)//args.batchsize} ({len(batch)} files)"
            )
            sys.stdout.flush()
            upload_files(session_id, batch, api_url, root_dir=args.data)
    except Exception as e:
        print(f"Error uploading files: {str(e)}")
        return

    # Mark the upload as complete
    try:
        print("Marking upload as complete...")
        mark_upload_complete(session_id, api_url)
        print("Upload marked as complete")
        sys.stdout.flush()
    except Exception as e:
        print(f"Error marking upload as complete: {str(e)}")
        return

    # Monitor the status
    print("\n=== Monitoring Upload Status ===\n")
    sys.stdout.flush()

    try:
        steps = {}
        while True:
            session_status = get_session_status(session_id, api_url)
            status = session_status.get("status")

            # Track specific status messages
            if status == "uploaded" and not steps.get("uploaded"):
                steps["uploaded"] = True
                print("✓ Status 'uploaded'")
            elif status == "preprocessing" and not steps.get("preprocessing"):
                steps["preprocessing"] = True
                print("✓ Status 'preprocessing'")
            elif "analyzed" in status and not steps.get("analyzed"):
                steps["analyzed"] = True
                print("✓ Status 'analyzed'")
                print("\nAll processing completed successfully!")
                break

            if status in ["failed", "finalized"]:
                print(f"\nProcessing completed with status: {status}")
                break

            time.sleep(2)  # Check every 2 seconds
    except Exception as e:
        print(f"Error monitoring status: {str(e)}")

    # Generate the session URL
    if "/ezbids/" in args.url:
        session_url = f"{args.url}/convert#{session_id}"
    else:
        session_url = f"{args.url}/ezbids/convert#{session_id}"

    print(f"\nCheck your conversion/upload status at {session_url}")
    print("Guest access belongs to this HTTP client; a separate browser does not automatically share its cookie.")
    print("You can close this window when done.")


if __name__ == "__main__":
    cli()
