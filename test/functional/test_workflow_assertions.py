import gzip
import json
import struct
import zipfile

import pytest

from workflow import inspect_download, load_profile, validator_errors


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"issues": {}},
        {"issues": {"errors": None}},
        {"issues": {"issues": [{}]}},
        {"issues": {"issues": "not-a-list"}},
    ],
)
def test_invalid_validator_reports_cannot_pass(report):
    with pytest.raises(AssertionError):
        validator_errors(report)


def test_validator_generations_report_errors():
    assert validator_errors({"issues": {"errors": []}}) == []
    assert validator_errors({"issues": {"issues": [{"severity": "warning"}]}}) == []
    error = {"severity": "error", "code": "JSON_SCHEMA_VALIDATION_ERROR"}
    assert validator_errors({"issues": {"issues": [error]}}) == [error]
    assert validator_errors({"issues": {"errors": [{"code": 1}]}}) == [{"code": 1}]


def test_an_empty_dataset_cannot_pass_even_with_a_clean_validator(tmp_path):
    archive = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("bids/dataset_description.json", '{"Name":"fixture"}')
    with pytest.raises(AssertionError):
        inspect_download(archive, {"expected_images": 1})


def test_profiles_cannot_exclude_the_fixture_or_create_unsafe_paths(tmp_path):
    profile = {
        "dataset_name": "fixture",
        "subjects": [{"subject": "phantom"}],
        "series": [{"description": "PET", "datatype": "exclude"}],
        "expected_images": 1,
    }
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="included"):
        load_profile(path)
    profile["series"][0]["datatype"] = "pet/pet"
    profile["dataset_name"] = "../escape"
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="directory"):
        load_profile(path)


def nifti_image(version=1, endian="<"):
    """A 2 x 3 x 1 float32 volume in the standard single-file layouts."""
    size, offset = (348, 352) if version == 1 else (540, 544)
    image = bytearray(offset + 2 * 3 * 1 * 4)
    struct.pack_into(endian + "i", image, 0, size)
    if version == 1:
        image[344:348] = b"n+1\0"
        struct.pack_into(endian + "8h", image, 40, 3, 2, 3, 1, 1, 1, 1, 1)
        struct.pack_into(endian + "2h", image, 70, 16, 32)
        struct.pack_into(endian + "f", image, 108, offset)
    else:
        image[4:12] = b"n+2\0\r\n\x1a\n"
        struct.pack_into(endian + "8q", image, 16, 3, 2, 3, 1, 1, 1, 1, 1)
        struct.pack_into(endian + "2h", image, 12, 16, 32)
        struct.pack_into(endian + "q", image, 168, offset)
    struct.pack_into(endian + "6f", image, offset, 1, 2, 3, 4, 5, 6)
    return bytes(image)


def downloaded_dataset(
    tmp_path, payload, *, compressed=True, session="", expected_sessions=None
):
    profile = {
        "dataset_name": "fixture",
        "subjects": [{"subject": "phantom", "sessions": expected_sessions or [""]}],
        "series": [{"description": "PET", "metadata": {"TracerName": "FDG"}}],
        "expected_images": 1,
        "expected_modality": "pet",
    }
    entity = f"_ses-{session}" if session else ""
    directory = f"ses-{session}/" if session else ""
    stem = f"bids/sub-phantom/{directory}pet/sub-phantom{entity}_pet"
    image = stem + (".nii.gz" if compressed else ".nii")
    path = tmp_path / "download.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("bids/dataset_description.json", '{"Name":"fixture"}')
        archive.writestr(image, payload)
        archive.writestr(stem + ".json", '{"TracerName":"FDG"}')
    return path, profile, image


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("endian", ["<", ">"])
@pytest.mark.parametrize("compressed", [False, True])
def test_download_contains_readable_nifti_voxels(tmp_path, version, endian, compressed):
    payload = nifti_image(version, endian)
    if compressed:
        payload = gzip.compress(payload)
    path, profile, image = downloaded_dataset(tmp_path, payload, compressed=compressed)
    assert inspect_download(path, profile) == [image]


@pytest.mark.parametrize(
    "payload,message",
    [
        (gzip.compress(b""), "header"),
        (gzip.compress(nifti_image()[:100]), "header"),
        (gzip.compress(nifti_image()[:-1]), "voxel payload"),
        (gzip.compress(nifti_image())[:-5], "Invalid NIfTI download"),
        (b"not a gzip stream", "Invalid NIfTI download"),
    ],
)
def test_download_rejects_truncated_or_invalid_image_bytes(tmp_path, payload, message):
    path, profile, _ = downloaded_dataset(tmp_path, payload)
    with pytest.raises(AssertionError, match=message):
        inspect_download(path, profile)


@pytest.mark.parametrize(
    "offset,format,value,message",
    [
        (0, "i", 0, "header size"),
        (344, "4s", b"ni1\0", "magic"),
        (40, "h", 8, "dimension count"),
        (42, "h", 0, "dimensions"),
        (44, "h", -1, "dimensions"),
        (70, "h", 0, "datatype/bitpix"),
        (72, "h", 8, "datatype/bitpix"),
        (108, "f", 0, "voxel offset"),
        (108, "f", 352.5, "voxel offset"),
        (108, "f", float("nan"), "voxel offset"),
    ],
)
def test_download_rejects_malformed_nifti_headers(
    tmp_path, offset, format, value, message
):
    payload = bytearray(nifti_image())
    struct.pack_into("<" + format, payload, offset, value)
    path, profile, _ = downloaded_dataset(tmp_path, gzip.compress(payload))
    with pytest.raises(AssertionError, match=message):
        inspect_download(path, profile)


def test_download_preserves_configured_session_labels(tmp_path):
    path, profile, image = downloaded_dataset(
        tmp_path,
        gzip.compress(nifti_image()),
        session="baseline",
        expected_sessions=["baseline"],
    )
    assert inspect_download(path, profile) == [image]


@pytest.mark.parametrize(
    "actual,expected",
    [
        ("", ["baseline"]),
        ("wrong", ["baseline"]),
        ("unexpected", [""]),
        ("baseline", ["baseline", "followup"]),
    ],
)
def test_download_cannot_drop_or_change_session_labels(tmp_path, actual, expected):
    path, profile, _ = downloaded_dataset(
        tmp_path,
        gzip.compress(nifti_image()),
        session=actual,
        expected_sessions=expected,
    )
    with pytest.raises(AssertionError, match="subject/session labels"):
        inspect_download(path, profile)
