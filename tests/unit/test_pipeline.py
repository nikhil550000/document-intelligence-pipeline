"""Tests for the parts of the pipeline that need no services."""

from datetime import timedelta
from pathlib import Path

from docintel.pipeline import hash_of_code, longest_job, read_run_config


def test_the_longest_job_counts_every_attempt_timing_out_and_every_wait() -> None:
    """Four attempts of 300 s, waits of 10, 20 and 40 s, and a minute to store."""
    config, _ = read_run_config(Path("configs") / "pdfium-deepseek-flash.toml")

    assert longest_job(config) == timedelta(seconds=4 * 300 + 10 + 20 + 40 + 60)


def write_package(folder: Path, line_ending: str) -> Path:
    """Writes a small package of two files, with the given line ending."""
    (folder / "storage").mkdir(parents=True)
    (folder / "worker.py").write_bytes(f"a = 1{line_ending}b = 2{line_ending}".encode())
    (folder / "storage" / "jobs.sql").write_bytes(f"SELECT 1;{line_ending}".encode())
    return folder


def test_the_hash_of_the_code_is_the_same_with_either_line_ending(
    tmp_path: Path,
) -> None:
    """A checkout on Windows and one on Linux have the same code."""
    unix = write_package(tmp_path / "unix", "\n")
    windows = write_package(tmp_path / "windows", "\r\n")

    assert hash_of_code(unix) == hash_of_code(windows)


def test_the_hash_of_the_code_changes_with_any_file_but_not_with_compiled_files(
    tmp_path: Path,
) -> None:
    """Python's compiled files differ by machine, so they are left out."""
    package = write_package(tmp_path / "package", "\n")
    before = hash_of_code(package)

    (package / "__pycache__").mkdir()
    (package / "__pycache__" / "worker.cpython-313.pyc").write_bytes(b"\x00\x01")
    assert hash_of_code(package) == before

    (package / "storage" / "jobs.sql").write_bytes(b"SELECT 2;\n")
    assert hash_of_code(package) != before
