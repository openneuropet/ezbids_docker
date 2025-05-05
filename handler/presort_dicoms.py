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
                organization[subject_id][session_id] = {"dicoms": [], "other": []}
            
            organization[subject_id][session_id]["dicoms"].append(dicom_file)
            
        except Exception as e:
            print(f"Error inspecting {dicom_file}: {e}")
            error_count += 1
    
    # now we collect the folder paths that contain dicoms and associate those
    # with subject and session id's
    for subject_id in organization.keys():
        for session_id in organization[subject_id].keys():
            # next we get the common paths
            common_path = os.path.commonpath(organization[subject_id][session_id].get('dicoms'))
            non_dicoms = [file for file in Path(common_path).iterdir() if file not in dicom_files]
            for non_dicom in non_dicoms:
                if non_dicom.is_file():
                    organization[subject_id][session_id]["other"].append(non_dicom)
    
    return organization, error_count, dicom_files

def copy_organized_dicoms(organization, output_base):
    """
    Move DICOM files to their organized locations using generic subject/session IDs.
    
    Args:
        organization (dict): Nested dictionary mapping subjects and sessions to DICOM files
        output_base (str): Base path where organized files will be stored
    
    Returns:
        tuple: (moved_count, error_count, id_mapping)
        id_mapping is a dict containing the mapping between original and generic IDs
    """
    output_path = Path(output_base)
    output_path.mkdir(parents=True, exist_ok=True)
    
    moved_count = 0
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
    
    # Now move the files using the generic IDs
    copied_files = []
    new_session_folders = set()
    for subject_id, sessions in organization.items():
        generic_subject = id_mapping['subjects'][subject_id]
        for session_id in sessions.keys():
            generic_session = id_mapping['sessions'][(subject_id, session_id)]
            # Create session directory with generic IDs
            session_dir = output_path / generic_subject / generic_session
            session_dir.mkdir(parents=True, exist_ok=True)
            new_session_folders.add(session_dir)
            
            
            # Move DICOM files
            for dicom_file in organization[subject_id][session_id]['dicoms']:
                try:
                    shutil.move(dicom_file, session_dir / dicom_file.name)
                    moved_count += 1
                except Exception as e:
                    print(f"Error moving {dicom_file}: {e}")
                    error_count += 1
            
            # Copy non-dicom files
            for other in organization[subject_id][session_id]['other']:
                try:
                    shutil.copy2(other, session_dir / other.name)
                    copied_files.append(other)
                except Exception as e:
                    print(f"Error reorganizing over non-dicom file {other}")
                    error_count += 1
    
    copied_files = list(set(copied_files))
    for copy in copied_files:
        print(f"removing source file {copy}")
        copy.unlink()

    return moved_count, error_count, id_mapping, list(new_session_folders)


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
    from pprint import pprint
    pprint(organization)
    
    print(f"\nFound:")
    for subject_id, sessions in organization.items():
        print(f"  {subject_id}:")
        for session_id, files in sessions.items():
            print(f"    {session_id}: {len(files)} files")
    
    print(f"\nCopying files to {output_base}")
    moved, move_errors, id_mapping, new_session_folders = copy_organized_dicoms(organization, output_base)
    
    print(f"\nID Mappings:")
    print("Subjects:")
    for original, generic in id_mapping['subjects'].items():
        print(f"  {original} -> {generic}")
    print("\nSessions:")
    for (subject, session), generic in id_mapping['sessions'].items():
        print(f"  {subject}, {session} -> {generic}")
    
    print(f"\nOrganization complete:")
    print(f"Successfully moved: {moved} DICOM files")
    print(f"Errors during inspection: {inspect_errors}")
    print(f"Errors during moving: {move_errors}")

    return new_session_folders

if __name__ == "__main__":
    args = parse_args()
    source_folder = args.source
    output_base = args.destination
    presort(source_folder, output_base)