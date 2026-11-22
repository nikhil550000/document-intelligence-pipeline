"""Tests for storing a contract's PDF and the text read from it, on real services."""

import hashlib
import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import psycopg
import pytest

from docintel.parsing.pdfium import PARSER_NAME, PARSER_VERSION
from docintel.pipeline import store_contract
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.objects import get_object

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to a database that has every table."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def stored_rows(connection: psycopg.Connection) -> list[tuple[Any, ...]]:
    """Returns each document with each text read from it."""
    return connection.execute(
        "SELECT documents.sha256, documents.file_name, documents.byte_size,"
        " parsed_texts.parser, parsed_texts.parser_version, parsed_texts.text_sha256"
        " FROM documents JOIN parsed_texts ON parsed_texts.document_id = documents.id"
    ).fetchall()


def stored_keys(s3_client: "S3Client", bucket: str) -> list[str]:
    """Returns the keys of the objects in the bucket, sorted."""
    listing = s3_client.list_objects_v2(Bucket=bucket)
    keys = []
    for stored in listing.get("Contents", []):
        keys.append(stored["Key"])
    return sorted(keys)


def test_a_contract_is_stored_with_its_text_and_a_row_for_each(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    three_page_pdf: bytes,
) -> None:
    """The PDF and its pages are kept under their hashes, and the rows name both."""
    parsed = store_contract(
        connection, s3_client, bucket, "contract.pdf", three_page_pdf
    )

    assert parsed is not None
    rows = stored_rows(connection)
    assert len(rows) == 1
    sha256, file_name, byte_size, parser, parser_version, text_sha256 = rows[0]
    assert get_object(s3_client, bucket, sha256) == three_page_pdf
    assert (file_name, byte_size) == ("contract.pdf", len(three_page_pdf))
    assert (parser, parser_version) == (PARSER_NAME, PARSER_VERSION)
    pages = json.loads(get_object(s3_client, bucket, text_sha256))
    assert pages == ["First page", "", "Third page"]


def test_storing_the_same_contract_again_writes_nothing(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    three_page_pdf: bytes,
) -> None:
    """A second run finds the text already read and leaves everything as it was."""
    store_contract(connection, s3_client, bucket, "contract.pdf", three_page_pdf)
    rows_before = stored_rows(connection)
    keys_before = stored_keys(s3_client, bucket)

    again = store_contract(
        connection, s3_client, bucket, "contract.pdf", three_page_pdf
    )

    assert again is None
    assert stored_rows(connection) == rows_before
    assert stored_keys(s3_client, bucket) == keys_before


def test_a_document_stored_before_keeps_its_row_and_gets_its_text(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    three_page_pdf: bytes,
) -> None:
    """A PDF already stored, by an upload or an older parser, is not stored twice."""
    connection.execute(
        "INSERT INTO documents (sha256, file_name, byte_size)"
        " VALUES (%s, 'upload.pdf', %s)",
        (hashlib.sha256(three_page_pdf).hexdigest(), len(three_page_pdf)),
    )

    store_contract(connection, s3_client, bucket, "contract.pdf", three_page_pdf)

    rows = stored_rows(connection)
    assert len(rows) == 1
    assert rows[0][1] == "upload.pdf"


def test_one_version_of_a_parser_reads_a_document_once(
    connection: psycopg.Connection,
) -> None:
    """Two texts from the same code would leave a choice of which one to use."""
    row = connection.execute(
        "INSERT INTO documents (sha256, file_name, byte_size)"
        " VALUES (%s, 'contract.pdf', 1000) RETURNING id",
        ("a" * 64,),
    ).fetchone()
    assert row is not None
    insert_text = (
        "INSERT INTO parsed_texts"
        " (document_id, parser, parser_version, text_sha256, parse_seconds)"
        " VALUES (%s, 'pdfium', %s, %s, 0.5)"
    )
    connection.execute(insert_text, (row[0], "1", "b" * 64))
    # A newer version reads the same document again, next to the old text.
    connection.execute(insert_text, (row[0], "2", "c" * 64))

    with pytest.raises(psycopg.errors.UniqueViolation):
        connection.execute(insert_text, (row[0], "1", "d" * 64))
