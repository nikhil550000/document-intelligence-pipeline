"""Tests for the rules the first tables enforce on the rows written to them."""

from collections.abc import Iterator
from uuid import UUID

import psycopg
import pytest

from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations

SHA256 = "a" * 64
GIT_COMMIT = "b" * 40


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to a database that has the first tables."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def insert_document(connection: psycopg.Connection) -> UUID:
    """Writes a document row and returns its id."""
    row = connection.execute(
        "INSERT INTO documents (sha256, file_name, byte_size)"
        " VALUES (%s, 'contract.pdf', 1000) RETURNING id",
        (SHA256,),
    ).fetchone()
    assert row is not None
    document_id: UUID = row[0]
    return document_id


def insert_run(connection: psycopg.Connection) -> UUID:
    """Writes a run row and returns its id."""
    row = connection.execute(
        "INSERT INTO runs"
        " (config_name, config, git_commit, contract_list, cost_ceiling_usd)"
        " VALUES ('a-config', '{}', %s, 'smoke', 1) RETURNING id",
        (GIT_COMMIT,),
    ).fetchone()
    assert row is not None
    run_id: UUID = row[0]
    return run_id


def insert_extraction(
    connection: psycopg.Connection,
    status: str,
    record: str | None,
    failure_reason: str | None,
) -> int:
    """Writes an extraction of a new document in a new run and returns its id.

    A failed call has no response; every other extraction has one.
    """
    response_sha256 = None
    if status != "failed":
        response_sha256 = SHA256
    row = connection.execute(
        "INSERT INTO extractions (run_id, document_id, status, record,"
        " failure_reason, model, prompt_version, schema_version, request_sha256,"
        " response_sha256, from_cache, input_tokens, cached_input_tokens,"
        " output_tokens, cost_usd, total_seconds)"
        " VALUES (%s, %s, %s, %s, %s, 'a-model', '1', '1', %s, %s, false, 100, 0,"
        " 50, 0.01, 2.5) RETURNING id",
        (
            insert_run(connection),
            insert_document(connection),
            status,
            record,
            failure_reason,
            SHA256,
            response_sha256,
        ),
    ).fetchone()
    assert row is not None
    extraction_id: int = row[0]
    return extraction_id


def test_a_document_id_is_a_time_ordered_uuid(
    connection: psycopg.Connection,
) -> None:
    """Version 7 UUIDs start with the time, so new rows land at the end of the index."""
    assert insert_document(connection).version == 7


def test_a_hash_that_is_not_sha256_is_refused(connection: psycopg.Connection) -> None:
    """A row whose hash cannot name a stored object is refused when written."""
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            "INSERT INTO documents (sha256, file_name, byte_size)"
            " VALUES ('not-a-hash', 'contract.pdf', 1000)"
        )


def test_the_same_pdf_is_stored_once(connection: psycopg.Connection) -> None:
    """The same bytes uploaded twice are one document."""
    insert_document(connection)

    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_document(connection)


def test_a_failed_extraction_needs_a_reason(connection: psycopg.Connection) -> None:
    """A failure with no reason could not be explained in the report."""
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_extraction(connection, "failed", None, None)


def test_a_failed_extraction_cannot_have_a_record(
    connection: psycopg.Connection,
) -> None:
    """A record means the model answered, so the contract did not fail."""
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_extraction(connection, "failed", "{}", "the provider timed out")


def test_a_record_that_needs_review_is_stored(connection: psycopg.Connection) -> None:
    """A record that fails its checks is kept for a reviewer, not dropped."""
    assert insert_extraction(connection, "needs_review", "{}", None) > 0


def test_output_that_did_not_load_is_stored_for_review_without_a_record(
    connection: psycopg.Connection,
) -> None:
    """Its response and problems are kept even though no record could be made."""
    assert insert_extraction(connection, "needs_review", None, None) > 0


def test_a_valid_extraction_must_have_a_record(connection: psycopg.Connection) -> None:
    """Valid means the output loaded, so its record is there."""
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_extraction(connection, "valid", None, None)


def test_a_stopped_run_must_say_why(connection: psycopg.Connection) -> None:
    """A run that did not finish names the reason, such as its ceiling."""
    run_id = insert_run(connection)

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            "UPDATE runs SET status = 'stopped' WHERE id = %s", (run_id,)
        )


def test_a_date_and_perpetual_cannot_both_be_set(
    connection: psycopg.Connection,
) -> None:
    """A contract cannot both end on a date and never end."""
    extraction_id = insert_extraction(connection, "valid", "{}", None)

    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            "INSERT INTO field_values"
            " (extraction_id, field_name, date_value, perpetual, evidence)"
            " VALUES (%s, 'expiration_date', '2030-12-31', true, '[]')",
            (extraction_id,),
        )
