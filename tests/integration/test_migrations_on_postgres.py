"""Tests for applying the SQL files to a real Postgres."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest

from docintel.storage.migrations import (
    MIGRATIONS_FOLDER,
    MigrationError,
    apply_migrations,
)

FIRST_TABLES = {
    "documents",
    "runs",
    "extractions",
    "field_values",
    "gold_values",
    "scores",
}


def table_names(database_url: str) -> set[str]:
    """Returns the names of the tables in the database."""
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables"
            " WHERE table_schema = 'public'"
        ).fetchall()
    names = set()
    for (name,) in rows:
        names.add(name)
    return names


def applied_file_names(database_url: str) -> list[str]:
    """Returns the files the database records as applied, in order."""
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            "SELECT file_name FROM schema_migrations ORDER BY file_name"
        ).fetchall()
    names = []
    for (name,) in rows:
        names.append(name)
    return names


def test_the_first_run_applies_every_file_and_a_second_run_applies_none(
    database_url: str,
) -> None:
    """The project's own files make the first tables, and only once."""
    first_run = apply_migrations(database_url, MIGRATIONS_FOLDER)
    second_run = apply_migrations(database_url, MIGRATIONS_FOLDER)

    assert first_run == ["0001_first_tables.sql", "0002_parsed_texts.sql"]
    assert second_run == []
    assert table_names(database_url) >= FIRST_TABLES


def test_only_the_new_file_is_applied(database_url: str, tmp_path: Path) -> None:
    """A database that is one file behind gets that one file."""
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (x int);", encoding="utf-8")
    apply_migrations(database_url, tmp_path)
    (tmp_path / "0002_b.sql").write_text("CREATE TABLE b (x int);", encoding="utf-8")

    applied = apply_migrations(database_url, tmp_path)

    assert applied == ["0002_b.sql"]
    assert applied_file_names(database_url) == ["0001_a.sql", "0002_b.sql"]


def test_a_failing_file_leaves_nothing_behind(
    database_url: str, tmp_path: Path
) -> None:
    """A file that breaks halfway is undone whole, and is not recorded as applied."""
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (x int);", encoding="utf-8")
    (tmp_path / "0002_b.sql").write_text(
        "CREATE TABLE b (x int); SELECT * FROM no_such_table;", encoding="utf-8"
    )

    with pytest.raises(psycopg.errors.UndefinedTable):
        apply_migrations(database_url, tmp_path)

    assert "a" in table_names(database_url)
    assert "b" not in table_names(database_url)
    assert applied_file_names(database_url) == ["0001_a.sql"]


def test_a_file_changed_after_it_was_applied_is_refused(
    database_url: str, tmp_path: Path
) -> None:
    """An edit to an applied file never reaches the database, so it is an error."""
    file = tmp_path / "0001_a.sql"
    file.write_text("CREATE TABLE a (x int);", encoding="utf-8")
    apply_migrations(database_url, tmp_path)
    file.write_text("CREATE TABLE a (x bigint);", encoding="utf-8")

    with pytest.raises(MigrationError, match="changed after it was applied"):
        apply_migrations(database_url, tmp_path)


def test_an_applied_file_that_is_gone_is_refused(
    database_url: str, tmp_path: Path
) -> None:
    """The database has a change that the code no longer knows about."""
    file = tmp_path / "0001_a.sql"
    file.write_text("CREATE TABLE a (x int);", encoding="utf-8")
    apply_migrations(database_url, tmp_path)
    file.unlink()

    with pytest.raises(MigrationError, match="its file is gone"):
        apply_migrations(database_url, tmp_path)


def test_a_new_file_numbered_before_an_applied_one_is_refused(
    database_url: str, tmp_path: Path
) -> None:
    """It would run after 0003 here but before 0003 on a new database."""
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (x int);", encoding="utf-8")
    (tmp_path / "0003_c.sql").write_text("CREATE TABLE c (x int);", encoding="utf-8")
    apply_migrations(database_url, tmp_path)
    (tmp_path / "0002_b.sql").write_text("CREATE TABLE b (x int);", encoding="utf-8")

    with pytest.raises(MigrationError, match="numbered before 0003_c.sql"):
        apply_migrations(database_url, tmp_path)


def test_two_processes_migrating_at_once_apply_each_file_once(
    database_url: str, tmp_path: Path
) -> None:
    """Started together, the second waits for the first and then finds nothing to do."""
    # The sleep keeps the first one inside its transaction while the second starts.
    (tmp_path / "0001_a.sql").write_text(
        "CREATE TABLE a (x int); SELECT pg_sleep(1);", encoding="utf-8"
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(apply_migrations, database_url, tmp_path)
        second = pool.submit(apply_migrations, database_url, tmp_path)
        results = [first.result(), second.result()]

    assert sorted(results) == [[], ["0001_a.sql"]]
    assert applied_file_names(database_url) == ["0001_a.sql"]
