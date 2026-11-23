import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import fetch_phantoms as fixture


class PhantomFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="ezbids-fixture-test-", dir="/tmp"
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "cached.zip"

    def make_archive(self, names=("slice.dcm",)):
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name in names:
                archive.writestr(
                    fixture.SERIES_PREFIX + name, b"original DICOM fixture"
                )
            archive.writestr(
                "OpenNeuroPET-Phantoms/sub-unrelated/pet/preconverted.nii", b"skip"
            )
        constants = patch.multiple(
            fixture,
            ARCHIVE_BYTES=self.archive.stat().st_size,
            ARCHIVE_SHA256=hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            SERIES_FILES=len(names),
            SERIES_BYTES=len(names) * len(b"original DICOM fixture"),
        )
        constants.start()
        self.addCleanup(constants.stop)

    def test_only_original_series_extracts_and_verified_cache_reuses(self):
        self.make_archive()
        result = fixture.fetch_phantoms(self.root / "cache", self.archive)
        self.assertEqual([path.name for path in result.iterdir()], ["slice.dcm"])
        self.assertEqual((result / "slice.dcm").read_bytes(), b"original DICOM fixture")
        self.assertEqual(
            fixture.fetch_phantoms(self.root / "cache", self.archive), result
        )

    def test_modified_archive_cannot_extract(self):
        self.make_archive()
        with self.archive.open("ab") as archive:
            archive.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "archive integrity"):
            fixture.fetch_phantoms(self.root / "cache", self.archive)

    def test_modified_extracted_data_cannot_silently_reuse(self):
        self.make_archive()
        result = fixture.fetch_phantoms(self.root / "cache", self.archive)
        (result / "slice.dcm").write_bytes(b"modified fixture")
        with self.assertRaisesRegex(ValueError, "cache integrity"):
            fixture.fetch_phantoms(self.root / "cache", self.archive)

    def test_archive_path_traversal_is_rejected(self):
        self.make_archive(("../escape.dcm",))
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            fixture.fetch_phantoms(self.root / "cache", self.archive)

    def test_symlink_cache_entries_are_rejected(self):
        self.make_archive()
        result = fixture.fetch_phantoms(self.root / "cache", self.archive)
        external = self.root / "outside.dcm"
        external.write_bytes(b"original DICOM fixture")
        (result / "slice.dcm").unlink()
        (result / "slice.dcm").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            fixture.fetch_phantoms(self.root / "cache", self.archive)

    def test_cache_cannot_store_data_in_the_checkout(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            fixture.fetch_phantoms(
                Path(fixture.__file__).resolve().parent / "dicoms", self.archive
            )


if __name__ == "__main__":
    unittest.main()
