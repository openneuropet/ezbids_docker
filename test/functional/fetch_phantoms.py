"""Fetch a pinned public PET phantom and extract one original DICOM series."""

import argparse
import hashlib
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile

URL = "https://openneuropet.s3.amazonaws.com/US-sourced-OpenNeuroPET-Phantoms.zip"
ARCHIVE_NAME = "US-sourced-OpenNeuroPET-Phantoms.zip"
ARCHIVE_BYTES = 115449025
ARCHIVE_SHA256 = "85dc5d2e962f8dc0ee7e476812cd40d25990cbf277cf46dedcaf0979d3697851"
SERIES_PREFIX = (
    "OpenNeuroPET-Phantoms/sourcedata/" "GeneralElectricAdvance-NIMH/2d_unif_lt_ramp/"
)
SERIES_FILES = 35
SERIES_BYTES = 1330838
DEFAULT_CACHE = Path(tempfile.gettempdir()) / "ezbids-phantoms-cache"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path):
    if path.stat().st_size != ARCHIVE_BYTES or sha256(path) != ARCHIVE_SHA256:
        raise ValueError(f"Phantom archive integrity check failed: {path}")


def fetch_phantoms(cache_dir=DEFAULT_CACHE, archive=None):
    cache = Path(cache_dir).expanduser().resolve()
    repository = Path(__file__).resolve().parents[2]
    if cache == repository or repository in cache.parents:
        raise ValueError("Choose a fixture cache outside the ezBIDS checkout")
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = (
        Path(archive).expanduser().resolve() if archive else cache / ARCHIVE_NAME
    )
    if not archive_path.exists():
        if archive:
            raise FileNotFoundError(archive_path)
        print(
            f"Downloading public phantom archive ({ARCHIVE_BYTES} bytes)",
            file=sys.stderr,
        )
        with tempfile.NamedTemporaryFile(
            dir=cache, suffix=".zip.part", delete=False
        ) as target:
            partial = Path(target.name)
            try:
                with urllib.request.urlopen(URL, timeout=90) as response:
                    total = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > ARCHIVE_BYTES:
                            raise ValueError("Phantom archive exceeds its pinned size")
                        target.write(chunk)
                target.flush()
                verify_archive(partial)
            except BaseException:
                partial.unlink(missing_ok=True)
                raise
        partial.replace(archive_path)
    verify_archive(archive_path)

    destination = cache / "ge-advance-2d"
    if destination.is_symlink():
        raise ValueError(f"Refusing a symlink fixture directory: {destination}")
    with zipfile.ZipFile(archive_path) as source:
        members = [
            member
            for member in source.infolist()
            if member.filename.startswith(SERIES_PREFIX)
            and member.filename.endswith(".dcm")
        ]
        if (
            len(members) != SERIES_FILES
            or sum(m.file_size for m in members) != SERIES_BYTES
        ):
            raise ValueError("Unexpected phantom DICOM series contents")
        names = set()
        for member in members:
            name = member.filename[len(SERIES_PREFIX) :]
            if (
                not name
                or name in (".", "..")
                or "/" in name
                or "\\" in name
                or name in names
            ):
                raise ValueError("Unsafe or duplicate phantom archive member")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Symlinks are not permitted in the phantom fixture")
            names.add(name)
        if destination.exists():
            if (
                not destination.is_dir()
                or set(p.name for p in destination.iterdir()) != names
            ):
                raise ValueError(f"Fixture cache contents changed: {destination}")
            for member in members:
                target = destination / Path(member.filename).name
                if target.is_symlink() or not target.is_file():
                    raise ValueError(f"Unsafe fixture cache entry: {target}")
                if sha256(target) != hashlib.sha256(source.read(member)).hexdigest():
                    raise ValueError(f"Fixture cache integrity check failed: {target}")
            return destination
        with tempfile.TemporaryDirectory(prefix=".extract-", dir=cache) as temporary:
            staging = Path(temporary) / "ge-advance-2d"
            staging.mkdir()
            for member in members:
                with (
                    source.open(member) as original,
                    (staging / Path(member.filename).name).open("wb") as output,
                ):
                    shutil.copyfileobj(original, output)
            staging.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--archive", type=Path, help="Verify and reuse an already downloaded archive"
    )
    args = parser.parse_args()
    try:
        print(fetch_phantoms(args.cache_dir, args.archive))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Phantom fixture preparation failed: {error}\n")


if __name__ == "__main__":
    main()
