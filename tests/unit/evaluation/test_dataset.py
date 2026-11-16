"""Tests for downloading, verifying and unpacking the dataset."""

import hashlib
import zipfile
from pathlib import Path

import pytest

from docintel.evaluation.dataset import (
    ChecksumError,
    UnsafeArchiveError,
    check_md5,
    md5_of_file,
    unpack_archive,
)


def test_md5_of_known_file(tmp_path: Path) -> None:
    """The MD5 of the bytes "hello" is a published, well-known value."""
    path = tmp_path / "hello.txt"
    path.write_bytes(b"hello")
    assert md5_of_file(path) == "5d41402abc4b2a76b9719d911017c592"


def test_check_md5_accepts_matching_value(tmp_path: Path) -> None:
    """A matching MD5 raises nothing."""
    path = tmp_path / "hello.txt"
    path.write_bytes(b"hello")
    check_md5(path, hashlib.md5(b"hello").hexdigest())


def test_check_md5_rejects_wrong_value(tmp_path: Path) -> None:
    """A wrong MD5 raises an error that names both values."""
    path = tmp_path / "hello.txt"
    path.write_bytes(b"hello")
    with pytest.raises(ChecksumError, match="expected 0000"):
        check_md5(path, "0000")


def test_unpack_archive_writes_entries(tmp_path: Path) -> None:
    """A small archive is unpacked with its folder structure."""
    archive_path = tmp_path / "small.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("top.txt", "one")
        archive.writestr("folder/inner.txt", "two")
    target = tmp_path / "out"

    unpack_archive(archive_path, target)

    assert (target / "top.txt").read_text() == "one"
    assert (target / "folder" / "inner.txt").read_text() == "two"


def test_unpack_archive_refuses_entry_outside_folder(tmp_path: Path) -> None:
    """An entry that climbs out of the folder is refused and nothing is written."""
    archive_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("fine.txt", "ok")
        archive.writestr("../escaped.txt", "bad")
    target = tmp_path / "out"
    target.mkdir()

    with pytest.raises(UnsafeArchiveError):
        unpack_archive(archive_path, target)

    assert not (tmp_path / "escaped.txt").exists()
    assert not (target / "fine.txt").exists()
