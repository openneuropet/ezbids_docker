"""Assertions shared by the real-browser workflow and its small fixture tests."""

import gzip
import json
import math
import re
import struct
import zipfile
import zlib
from contextlib import ExitStack
from pathlib import Path


def load_profile(path):
    profile = json.loads(Path(path).read_text())
    name = profile.get("dataset_name", "")
    if not name or any(char in name for char in "/\\\x00") or name in (".", ".."):
        raise ValueError("dataset_name must be a single directory name")
    for key in ("subjects", "series"):
        if not isinstance(profile.get(key), list) or not profile[key]:
            raise ValueError(f"profile needs a nonempty {key} list")
    descriptions = [series["description"] for series in profile["series"]]
    if len(set(descriptions)) != len(descriptions):
        raise ValueError("series descriptions must be unique")
    for subject in profile["subjects"]:
        labels = [subject["subject"], *subject.get("sessions", [])]
        if not re.fullmatch(r"[a-zA-Z0-9]+", labels[0]):
            raise ValueError("subject labels must be alphanumeric")
        if any(
            label and not re.fullmatch(r"[a-zA-Z0-9]+", label) for label in labels[1:]
        ):
            raise ValueError("session labels must be alphanumeric or empty")
    if (
        not isinstance(profile.get("expected_images"), int)
        or profile["expected_images"] < 1
    ):
        raise ValueError("expected_images must be a positive integer")
    for series in profile["series"]:
        if series.get("datatype") in (None, "", "exclude"):
            raise ValueError("every fixture series must be included")
        for field in series.get("metadata", {}):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", field):
                raise ValueError(f"invalid metadata field {field!r}")
    return profile


def validator_errors(report):
    """Fail closed for both validator generations shipped in ezBIDS images."""
    if not isinstance(report, dict) or not isinstance(report.get("issues"), dict):
        raise AssertionError("Validator report has no recognized issues object")
    issues = report["issues"]
    if "issues" in issues:
        records = issues["issues"]
        if not isinstance(records, list) or any(
            not isinstance(issue, dict)
            or issue.get("severity") not in ("error", "warning", "ignore")
            for issue in records
        ):
            raise AssertionError("Malformed validator issue records")
        return [issue for issue in records if issue["severity"] == "error"]
    if "errors" in issues:
        if not isinstance(issues["errors"], list):
            raise AssertionError("Malformed validator errors list")
        return issues["errors"]
    raise AssertionError("Unrecognized validator JSON schema")


def metadata_value(value):
    return value["value"] if isinstance(value, dict) and "value" in value else value


def inspect_nifti(archive, image):
    """Read the downloaded voxel payload, including the gzip checksum/trailer."""
    # Field offsets and datatype sizes follow nifti_clib's nifti1.h/nifti2.h.
    bits_per_voxel = {
        2: 8,
        4: 16,
        8: 32,
        16: 32,
        32: 64,
        64: 64,
        128: 24,
        256: 8,
        512: 16,
        768: 32,
        1024: 64,
        1280: 64,
        1536: 128,
        1792: 128,
        2048: 256,
        2304: 32,
    }
    try:
        with ExitStack() as stack:
            stream = stack.enter_context(archive.open(image))
            if image.endswith(".gz"):
                stream = stack.enter_context(gzip.GzipFile(fileobj=stream))
            prefix = stream.read(4)
            assert len(prefix) == 4, f"Truncated NIfTI header: {image}"
            endian = "<" if struct.unpack("<i", prefix)[0] in (348, 540) else ">"
            size = struct.unpack(endian + "i", prefix)[0]
            assert size in (348, 540), f"Invalid NIfTI header size: {image}"
            header = prefix + stream.read(size - 4)
            assert len(header) == size, f"Truncated NIfTI header: {image}"
            if size == 348:
                assert header[344:348] == b"n+1\0", f"Invalid NIfTI magic: {image}"
                dimensions = struct.unpack_from(endian + "8h", header, 40)
                datatype, bitpix = struct.unpack_from(endian + "2h", header, 70)
                offset = struct.unpack_from(endian + "f", header, 108)[0]
            else:
                assert (
                    header[4:12] == b"n+2\0\r\n\x1a\n"
                ), f"Invalid NIfTI magic: {image}"
                dimensions = struct.unpack_from(endian + "8q", header, 16)
                datatype, bitpix = struct.unpack_from(endian + "2h", header, 12)
                offset = struct.unpack_from(endian + "q", header, 168)[0]
            assert 1 <= dimensions[0] <= 7, f"Invalid NIfTI dimension count: {image}"
            shape = dimensions[1 : dimensions[0] + 1]
            assert all(
                length > 0 for length in shape
            ), f"Invalid NIfTI dimensions: {image}"
            assert (
                bits_per_voxel.get(datatype) == bitpix
            ), f"Invalid NIfTI datatype/bitpix: {image}"
            assert (
                math.isfinite(offset) and offset >= size + 4 and int(offset) == offset
            ), f"Invalid NIfTI voxel offset: {image}"
            expected_size = int(offset) + math.prod(shape) * bitpix // 8
            # Consume the full stream so truncated or corrupt gzip trailers also
            # fail, without loading a potentially large volume into host memory.
            actual_size = size + sum(
                len(chunk) for chunk in iter(lambda: stream.read(1024 * 1024), b"")
            )
            assert actual_size >= expected_size, (
                f"Truncated NIfTI voxel payload: {image} "
                f"({actual_size} bytes, expected at least {expected_size})"
            )
    except (OSError, EOFError, zlib.error, struct.error) as error:
        raise AssertionError(f"Invalid NIfTI download {image}: {error}") from error


def inspect_download(archive_path, profile):
    """Check actual downloaded images and values saved through the metadata form."""
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None, "Corrupt BIDS download"
        names = archive.namelist()
        images = [name for name in names if name.endswith((".nii", ".nii.gz"))]
        assert len(images) == profile["expected_images"], images
        modality = profile.get("expected_modality")
        if modality:
            assert all(f"/{modality}/" in name for name in images), images
        description = json.loads(archive.read("bids/dataset_description.json"))
        assert description["Name"] == profile["dataset_name"]
        expected_sessions = {
            (subject["subject"], session)
            for subject in profile["subjects"]
            for session in (subject.get("sessions") or [""])
        }
        actual_sessions = set()
        sidecars = []
        for image in images:
            parts = image.split("/")[:-1]
            subjects = [
                part[4:] for part in parts if re.fullmatch(r"sub-[a-zA-Z0-9]+", part)
            ]
            sessions = [
                part[4:] for part in parts if re.fullmatch(r"ses-[a-zA-Z0-9]+", part)
            ]
            assert (
                len(subjects) == 1 and len(sessions) <= 1
            ), f"Invalid subject/session path: {image}"
            actual_sessions.add((subjects[0], sessions[0] if sessions else ""))
            inspect_nifti(archive, image)
            stem = image[:-7] if image.endswith(".nii.gz") else image[:-4]
            sidecars.append(json.loads(archive.read(stem + ".json")))
        assert (
            actual_sessions == expected_sessions
        ), f"Downloaded subject/session labels {actual_sessions} do not match {expected_sessions}"
        for series in profile["series"]:
            expected = {
                key: metadata_value(value)
                for key, value in series.get("metadata", {}).items()
            }
            assert any(
                all(sidecar.get(key) == value for key, value in expected.items())
                for sidecar in sidecars
            ), f"No downloaded sidecar preserved metadata for {series['description']}: {expected}"
        return images
