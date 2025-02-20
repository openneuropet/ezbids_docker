import os
import time
import subprocess
from pydicom import dcmread
from pathlib import Path
from datetime import datetime
import shutil

def benchmark_pydicom(folder_path):
    """Benchmark reading DICOM headers using pydicom"""
    start_time = time.time()
    count = 0
    
    for file in Path(folder_path).glob('*.dcm'):
        try:
            # Read only the header (stop_before_pixels=True for efficiency)
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
        # Use find with -exec to process files (more direct than xargs)
        cmd = f"find {folder_path} -name '*.dcm' -exec dcmdump {{}} \\;"
        print(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        # Count the number of files processed (each file starts with "# dcmdump")
        count = stdout.count(b'# Dicom-File-Format')
        
    except Exception as e:
        print(f"Error running dcmdump: {e}")
    
    end_time = time.time()
    return end_time - start_time, count

def organize_dicoms(source_folder, output_base):
    """
    Organize DICOM files by patient/participant and scan date.
    
    Args:
        source_folder (str): Path to folder containing DICOM files
        output_base (str): Base path where organized files will be stored
    """
    source_path = Path(source_folder)
    output_path = Path(output_base)
    
    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Track what we've processed for reporting
    processed_count = 0
    error_count = 0
    
    for dicom_file in source_path.glob('*.dcm'):
        try:
            # Read DICOM header
            ds = dcmread(str(dicom_file), stop_before_pixels=True)
            
            # Get patient ID (fall back to patient name if ID not available)
            patient_id = getattr(ds, 'PatientID', None) or getattr(ds, 'PatientName', 'unknown_patient')
            patient_id = str(patient_id).replace('^', '_')  # Clean up potential special characters
            
            # Get study date and convert to ISO format
            study_date = getattr(ds, 'StudyDate', None)
            if study_date:
                try:
                    # Convert DICOM date (YYYYMMDD) to ISO format
                    date_obj = datetime.strptime(study_date, '%Y%m%d')
                    iso_date = date_obj.strftime('%Y%m%d')
                except ValueError:
                    iso_date = 'unknown_date'
            else:
                iso_date = 'unknown_date'
            
            # Create directory structure
            patient_dir = output_path / f'sub-{patient_id}'
            session_dir = patient_dir / f'ses-{iso_date}'
            
            # Create directories
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy the file
            shutil.copy2(dicom_file, session_dir / dicom_file.name)
            
            processed_count += 1
            
        except Exception as e:
            print(f"Error processing {dicom_file}: {e}")
            error_count += 1
    
    return processed_count, error_count

if __name__ == "__main__":
    folder_path = "/home/anthony/ezbids/OpenNeuroPET-Phantoms/sourcedata/GeneralElectricAdvance-NIMH/consolidated_dicoms"
    
    source_folder = folder_path
    output_base = "/home/anthony/ezbids/OpenNeuroPET-Phantoms/sourcedata/GeneralElectricAdvance-NIMH/organized_dicoms"
    
    print(f"\nStarting DICOM organization from {source_folder}")
    print(f"Output will be written to {output_base}")
    
    processed, errors = organize_dicoms(source_folder, output_base)
    
    print(f"\nOrganization complete:")
    print(f"Successfully processed: {processed} files")
    print(f"Errors encountered: {errors} files") 