"""Tests for finding the SQL files and hashing them."""

from pathlib import Path

import pytest

from docintel.storage.migrations import (
    MIGRATIONS_FOLDER,
    MigrationError,
    list_migration_files,
    sha256_of_sql,
)


def write_files(folder: Path, names: list[str]) -> None:
    """Writes a one-line SQL file under each name."""
    for name in names:
        (folder / name).write_text("SELECT 1;", encoding="utf-8")


def test_files_are_listed_in_number_order(tmp_path: Path) -> None:
    """Files apply by number, whatever order the folder lists them in."""
    write_files(tmp_path, ["0010_later.sql", "0002_second.sql", "0001_first.sql"])

    names = [path.name for path in list_migration_files(tmp_path)]

    assert names == ["0001_first.sql", "0002_second.sql", "0010_later.sql"]


def test_files_that_are_not_sql_are_ignored(tmp_path: Path) -> None:
    """A note next to the SQL files is not run as a change to the tables."""
    write_files(tmp_path, ["0001_first.sql", "notes.txt"])

    names = [path.name for path in list_migration_files(tmp_path)]

    assert names == ["0001_first.sql"]


@pytest.mark.parametrize("name", ["1_first.sql", "0001-first.sql", "0001_First.sql"])
def test_a_badly_named_file_is_refused(tmp_path: Path, name: str) -> None:
    """Without four digits, `10_x.sql` would sort before `9_x.sql` and run first."""
    write_files(tmp_path, [name])

    with pytest.raises(MigrationError, match="is not named like"):
        list_migration_files(tmp_path)


def test_two_files_with_one_number_are_refused(tmp_path: Path) -> None:
    """Two branches that both added file 0001 must not both be applied unnoticed."""
    write_files(tmp_path, ["0001_first.sql", "0001_other.sql"])

    with pytest.raises(MigrationError, match="Two files are numbered 0001"):
        list_migration_files(tmp_path)


def test_line_endings_do_not_change_the_hash() -> None:
    """A Windows checkout of an applied file must not count as a changed file."""
    windows_text = b"SELECT 1;\r\nSELECT 2;\r\n"
    unix_text = b"SELECT 1;\nSELECT 2;\n"

    assert sha256_of_sql(windows_text) == sha256_of_sql(unix_text)


def test_the_project_files_are_named_correctly() -> None:
    """The files that ship with the package pass the naming rule."""
    assert list_migration_files(MIGRATIONS_FOLDER)
