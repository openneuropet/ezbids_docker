import os
import time
import subprocess
import re
import contextlib
import io
import sys
from pydicom import dcmread
from pathlib import Path
from datetime import datetime
import shutil
import argparse

@contextlib.contextmanager
def nostdout():
    """Suppress stdout temporarily"""
    save_stdout = sys.stdout
    sys.stdout = io.StringIO()
    yield
    sys.stdout = save_stdout

def is_potential_dicom(file_path):
    """
    Check if a file might be a DICOM based on its name/extension.
    
    Args:
        file_path (Path): Path object to the file
    
    Returns:
        bool: True if the file might be a DICOM
    """
    suffix = file_path.suffix
    
    # if there are multiple suffixes, join them together
    if len(file_path.suffixes) > 1:
        suffix = "".join(file_path.suffixes)
    
    return (suffix.lower() in [".dcm", ".ima", ".img", ""] or
            "mr" in str(file_path.name).lower() or
            bool(re.search(r"\d", suffix.lower())))

def find_dicom_files(folder_path):
    """
    Find all potential DICOM files in a folder.
    
    Args:
        folder_path (str or Path): Path to the folder to search
    
    Returns:
        list: List of Path objects for potential DICOM files
    """
    folder_path = Path(folder_path)
    return [f for f in folder_path.iterdir() if f.is_file() and is_potential_dicom(f)]

def benchmark_pydicom(folder_path):
    """Benchmark reading DICOM headers using pydicom"""
    start_time = time.time()
    count = 0
    
    for file in find_dicom_files(folder_path):
        try:
            with nostdout():
                ds = dcmread(str(file), stop_before_pixels=True)
            count += 1
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    end_time = time.time()
    return end_time - start_time, count

def benchmark_dcmdump(folder_path):
    """Benchmark reading DICOM headers using dcmdump"""
    start_time = time.time()
    count = 0
    
    try:
        # Create a temporary file with the list of potential DICOM files
        dicom_files = find_dicom_files(folder_path)
        cmd = f"find {folder_path} -type f -exec dcmdump {{}} \\;"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        count = stdout.count(b'# Dicom-File-Format')
        
    except Exception as e:
        print(f"Error running dcmdump: {e}")
    
    end_time = time.time()
    return end_time - start_time, count

def inspect_dicoms(source_folder):
    """
    Inspect DICOM files and create a mapping of files to their subject/session organization.
    
    Args:
        source_folder (str): Path to folder containing DICOM files
    
    Returns:
        dict: Nested dictionary of structure:
            {
                'sub-<patient_id>': {
                    'ses-<date>': [list_of_dicom_paths]
                }
            }
    """
    source_path = Path(source_folder)
    organization = {}
    error_count = 0
    dicom_files = find_dicom_files(source_folder)
    for dicom_file in dicom_files:
        try:
            with nostdout():
                ds = dcmread(str(dicom_file), stop_before_pixels=True)
            
            # Get patient ID (fall back to patient name if ID not available)
            patient_id = getattr(ds, 'PatientID', None) or getattr(ds, 'PatientName', 'unknown_patient')
            patient_id = str(patient_id).replace('^', '_')  # Clean up potential special characters
            subject_id = f'sub-{patient_id}'
            
            # Get study date and convert to ISO format
            study_date = getattr(ds, 'StudyDate', None)
            if study_date:
                try:
                    date_obj = datetime.strptime(study_date, '%Y%m%d')
                    iso_date = date_obj.strftime('%Y%m%d')
                except ValueError:
                    iso_date = 'unknown_date'
            else:
                iso_date = 'unknown_date'
            session_id = f'ses-{iso_date}'
            
            # Build the organization dictionary
            if subject_id not in organization:
                organization[subject_id] = {}
            if session_id not in organization[subject_id]:
                organization[subject_id][session_id] = []
            
            organization[subject_id][session_id].append(dicom_file)
            
        except Exception as e:
            print(f"Error inspecting {dicom_file}: {e}")
            error_count += 1
    
    return organization, error_count, dicom_files

def copy_organized_dicoms(organization, output_base):
    """
    Copy DICOM files to their organized locations using generic subject/session IDs.
    
    Args:
        organization (dict): Nested dictionary mapping subjects and sessions to DICOM files
        output_base (str): Base path where organized files will be stored
    
    Returns:
        tuple: (copied_count, error_count, id_mapping)
        id_mapping is a dict containing the mapping between original and generic IDs
    """
    output_path = Path(output_base)
    output_path.mkdir(parents=True, exist_ok=True)
    
    copied_count = 0
    error_count = 0
    
    # Create mappings for generic IDs
    id_mapping = {
        'subjects': {},  # original_id -> generic_id
        'sessions': {}   # (subject_id, original_session) -> generic_session
    }
    
    # First, create the subject mappings
    for i, subject_id in enumerate(sorted(organization.keys()), 1):
        generic_subject = f"sub-{i:03d}"  # Creates sub-001, sub-002, etc.
        id_mapping['subjects'][subject_id] = generic_subject
    
    # Then create session mappings for each subject
    for subject_id in organization:
        session_numbers = {}  # Keep track of session numbers per subject
        for session_id in sorted(organization[subject_id].keys()):
            if subject_id not in session_numbers:
                session_numbers[subject_id] = 1
            generic_session = f"ses-{session_numbers[subject_id]:03d}"  # Creates ses-001, ses-002, etc.
            id_mapping['sessions'][(subject_id, session_id)] = generic_session
            session_numbers[subject_id] += 1
    
    # Now copy the files using the generic IDs
    for subject_id, sessions in organization.items():
        generic_subject = id_mapping['subjects'][subject_id]
        
        for session_id, dicom_files in sessions.items():
            generic_session = id_mapping['sessions'][(subject_id, session_id)]
            
            # Create session directory with generic IDs
            session_dir = output_path / generic_subject / generic_session
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files
            for dicom_file in dicom_files:
                try:
                    shutil.copy2(dicom_file, session_dir / dicom_file.name)
                    copied_count += 1
                except Exception as e:
                    print(f"Error copying {dicom_file}: {e}")
                    error_count += 1
    
    return copied_count, error_count, id_mapping

def cleanup_source_files(organization, copied_count):
    """
    Remove original DICOM files after successful copy.
    Only proceeds if all files were copied successfully.
    
    Args:
        organization (dict): Nested dictionary mapping subjects and sessions to DICOM files
        copied_count (int): Number of successfully copied files
    
    Returns:
        tuple: (deleted_count, error_count)
    """
    # Count total files to verify all were copied
    total_files = sum(len(files) for sessions in organization.values() 
                     for files in sessions.values())
    
    if copied_count != total_files:
        print(f"Warning: Not all files were copied successfully "
              f"({copied_count} of {total_files}). Skipping cleanup.")
        return 0, 0
    
    deleted_count = 0
    error_count = 0
    
    # Iterate through all files in the organization
    for sessions in organization.values():
        for dicom_files in sessions.values():
            for dicom_file in dicom_files:
                try:
                    dicom_file.unlink()  # Delete the file
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {dicom_file}: {e}")
                    error_count += 1
    
    return deleted_count, error_count

def handle_non_dicom_files(source_folder, organization, output_base, dicom_files=None):
    """
    Copy non-DICOM files to each session folder.
    
    Args:
        source_folder (str): Path to source folder
        organization (dict): Nested dictionary of subject/session organization
        output_base (str): Base path where organized files are stored
    
    Returns:
        tuple: (copied_count, error_count, list_of_files)
    """
    source_path = Path(source_folder)
    output_path = Path(output_base)
    copied_count = 0
    error_count = 0
    non_dicom_files = []
    
    # Find all non-DICOM files
    if dicom_files is None:
        dicom_files = set(find_dicom_files(source_folder))
    
    for file_path in source_path.iterdir():
        if file_path.is_file() and file_path not in dicom_files:
            non_dicom_files.append(file_path)
    
    if not non_dicom_files:
        return 0, 0, []
    
    # Copy each non-DICOM file to each session directory
    for subject_id, sessions in organization.items():
        for session_id, _ in sessions.items():
            session_dir = output_path / subject_id / session_id
            
            for file_path in non_dicom_files:
                try:
                    shutil.copy2(file_path, session_dir / file_path.name)
                    copied_count += 1
                except Exception as e:
                    print(f"Error copying non-DICOM file {file_path}: {e}")
                    error_count += 1
    
    return copied_count, error_count, non_dicom_files


def parse_args():
    parser = argparse.ArgumentParser(description='Presort DICOM files')
    parser.add_argument('--source', type=str, help='Path to source folder', required=True)
    parser.add_argument('--destination', type=str, help='Path to destination folder, if not provided, will use the source folder', default=None)
    args = parser.parse_args()

    if args.destination is None:
        args.destination = args.source
    return args

def presort(source_folder, output_base=None):

    if output_base is None:
        output_base = source_folder
    
    #source_folder = folder_path
    #output_base = "/home/anthony/ezbids/OpenNeuroPET-Phantoms/sourcedata/GeneralElectricAdvance-NIMH/organized_dicoms"
    
    print(f"\nInspecting DICOM files in {source_folder}")
    organization, inspect_errors, dicom_files = inspect_dicoms(source_folder)
    
    print(f"\nFound:")
    for subject_id, sessions in organization.items():
        print(f"  {subject_id}:")
        for session_id, files in sessions.items():
            print(f"    {session_id}: {len(files)} files")
    
    print(f"\nCopying files to {output_base}")
    copied, copy_errors, id_mapping = copy_organized_dicoms(organization, output_base)
    
    print("\nHandling non-DICOM files...")
    non_dicom_copied, non_dicom_errors, non_dicom_files = handle_non_dicom_files(
        source_folder, organization, output_base
    )
    if non_dicom_files:
        print(f"Found {len(non_dicom_files)} non-DICOM files:")
        for file_path in non_dicom_files:
            print(f"  {file_path.name}")
        print(f"Made {non_dicom_copied} copies")
        print(f"Encountered {non_dicom_errors} errors")
    else:
        print("No non-DICOM files found")
    
    print(f"\nID Mappings:")
    print("Subjects:")
    for original, generic in id_mapping['subjects'].items():
        print(f"  {original} -> {generic}")
    print("\nSessions:")
    for (subject, session), generic in id_mapping['sessions'].items():
        print(f"  {subject}, {session} -> {generic}")
    
    print(f"\nOrganization complete:")
    print(f"Successfully copied: {copied} DICOM files")
    print(f"Errors during inspection: {inspect_errors}")
    print(f"Errors during copying: {copy_errors}")
    
    if copy_errors == 0 and inspect_errors == 0 and non_dicom_errors == 0 and (source_folder == output_base):
        print("\nCleaning up source files...")
        deleted, delete_errors = cleanup_source_files(organization, copied)
        print(f"Successfully deleted: {deleted} files")
        print(f"Errors during cleanup: {delete_errors}")
        
        # Clean up non-DICOM files if they were all copied successfully
        if non_dicom_files and non_dicom_errors == 0:
            print("\nCleaning up non-DICOM files...")
            for file_path in non_dicom_files:
                try:
                    file_path.unlink()
                    print(f"Deleted: {file_path.name}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

if __name__ == "__main__":
    args = parse_args()
    source_folder = args.source
    output_base = args.destination
    presort(source_folder, output_base)