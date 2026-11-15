"""Download, verify and unpack the CUAD dataset."""

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

CUAD_URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip?download=1"
CUAD_MD5 = "c38f490a984420b8a62600db401fafd5"
CUAD_ARCHIVE_NAME = "CUAD_v1.zip"
CUAD_FOLDER_NAME = "CUAD_v1"

READ_CHUNK_BYTES = 1024 * 1024


class ChecksumError(Exception):
    """A file's MD5 does not match the expected value."""


class UnsafeArchiveError(Exception):
    """An archive entry would be written outside the target folder."""


def md5_of_file(path: Path) -> str:
    """Returns the MD5 of a file as lowercase hex, read in chunks."""
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as file:
        # A 100 MB archive should not be read into memory at once.
        while chunk := file.read(READ_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def check_md5(path: Path, expected_md5: str) -> None:
    """Raises ChecksumError if the file's MD5 is not the expected one."""
    actual_md5 = md5_of_file(path)
    if actual_md5 != expected_md5:
        raise ChecksumError(
            f"{path} has MD5 {actual_md5}, expected {expected_md5}. "
            "Delete the file and download it again."
        )


def unpack_archive(archive_path: Path, target_folder: Path) -> None:
    """Unpacks a zip archive, refusing any entry that lands outside the folder.

    Raises:
        UnsafeArchiveError: An entry path leads outside `target_folder`. Nothing
            is written in that case.
    """
    target_root = target_folder.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        # Check every entry first so an unsafe archive leaves no partial output.
        for entry_name in archive.namelist():
            destination = (target_root / entry_name).resolve()
            if not destination.is_relative_to(target_root):
                raise UnsafeArchiveError(
                    f"Archive entry {entry_name!r} would be written outside "
                    f"{target_folder}."
                )
        archive.extractall(target_root)


def download_file(url: str, destination: Path) -> None:
    """Downloads a URL to a file, streaming it to disk."""
    with urllib.request.urlopen(url) as response, destination.open("wb") as file:
        shutil.copyfileobj(response, file)


def ensure_dataset(
    data_folder: Path,
    url: str = CUAD_URL,
    expected_md5: str = CUAD_MD5,
) -> bool:
    """Makes sure the CUAD archive is in `data_folder`, verified and unpacked.

    Returns:
        True if anything was downloaded or unpacked, False if there was nothing
        to do.

    Raises:
        ChecksumError: The archive on disk, or the one just downloaded, has the
            wrong MD5. A file that was already on disk is left in place.
    """
    archive_path = data_folder / CUAD_ARCHIVE_NAME
    unpacked_folder = data_folder / CUAD_FOLDER_NAME
    did_something = False

    data_folder.mkdir(parents=True, exist_ok=True)

    if archive_path.exists():
        check_md5(archive_path, expected_md5)
    else:
        # Download under another name so a stopped download is never mistaken
        # for a finished one.
        partial_path = archive_path.with_name(archive_path.name + ".part")
        download_file(url, partial_path)
        try:
            check_md5(partial_path, expected_md5)
        except ChecksumError:
            partial_path.unlink()
            raise
        partial_path.replace(archive_path)
        did_something = True

    if not unpacked_folder.exists():
        unpack_archive(archive_path, unpacked_folder)
        did_something = True

    return did_something
