"""Applies the numbered SQL files in order, and records which ones have run."""

import hashlib
import re
from pathlib import Path

import psycopg

MIGRATIONS_FOLDER = Path(__file__).parent / "sql"

# Any fixed number works, as long as every process that migrates uses the same one.
MIGRATION_LOCK_KEY = 4301002

FILE_NAME_PATTERN = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class MigrationError(Exception):
    """The SQL files and the database's record of applied files disagree."""


def list_migration_files(folder: Path) -> list[Path]:
    """Returns the SQL files in the order they are applied.

    Raises:
        MigrationError: A file is not named like `0001_first_tables.sql`, or two
            files share a number.
    """
    # Four digits sort by name in the same order as by number.
    files = sorted(folder.glob("*.sql"))
    numbers_seen = set()
    for path in files:
        match = FILE_NAME_PATTERN.match(path.name)
        if match is None:
            raise MigrationError(
                f"{path.name} is not named like 0001_first_tables.sql."
            )
        number = match.group(1)
        if number in numbers_seen:
            raise MigrationError(f"Two files are numbered {number}.")
        numbers_seen.add(number)
    return files


def sha256_of_sql(sql: bytes) -> str:
    """Returns the SHA-256 of a SQL file, the same whatever its line endings."""
    # Git may check a file out with Windows line endings on one machine and Unix
    # ones on another, and that must not look like a changed file.
    return hashlib.sha256(sql.replace(b"\r\n", b"\n")).hexdigest()


def apply_migrations(database_url: str, folder: Path) -> list[str]:
    """Applies the files the database has not run yet, each in its own transaction.

    Returns:
        The names of the files applied, in order. Empty when nothing was pending.

    Raises:
        MigrationError: An applied file has changed or is gone, or a new file is
            numbered before one that is already applied.
    """
    files = list_migration_files(folder)
    applied_now = []
    # Autocommit, so that each transaction below is a real one and not a savepoint.
    with psycopg.connect(database_url, autocommit=True) as connection:
        # Two processes starting at once must not both apply the same file. The
        # lock is held until the connection closes.
        connection.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " file_name text PRIMARY KEY,"
            " sha256 text NOT NULL,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )
        rows = connection.execute(
            "SELECT file_name, sha256 FROM schema_migrations"
        ).fetchall()
        applied_hashes: dict[str, str] = dict(rows)

        file_names = []
        for path in files:
            file_names.append(path.name)
        for file_name in applied_hashes:
            if file_name not in file_names:
                raise MigrationError(f"{file_name} was applied, but its file is gone.")

        last_applied_name = max(applied_hashes, default="")
        for path in files:
            sql = path.read_bytes()
            sha256 = sha256_of_sql(sql)
            if path.name in applied_hashes:
                if applied_hashes[path.name] != sha256:
                    raise MigrationError(
                        f"{path.name} changed after it was applied. "
                        "Put the change in a new file instead."
                    )
                continue
            # Applying it now would run it after files that were written later.
            if path.name < last_applied_name:
                raise MigrationError(
                    f"{path.name} is new but numbered before {last_applied_name}, "
                    "which is already applied. Give it the next free number."
                )
            with connection.transaction():
                connection.execute(sql)
                connection.execute(
                    "INSERT INTO schema_migrations (file_name, sha256) VALUES (%s, %s)",
                    (path.name, sha256),
                )
            applied_now.append(path.name)
    return applied_now
