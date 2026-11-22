"""Rows for the stored documents and for the text each parser read from them."""

from uuid import UUID

import psycopg
from psycopg.rows import TupleRow


def has_parsed_text(
    connection: psycopg.Connection[TupleRow],
    sha256: str,
    parser: str,
    parser_version: str,
) -> bool:
    """Says whether this version of the parser has read the PDF with this hash."""
    row = connection.execute(
        "SELECT 1 FROM parsed_texts"
        " JOIN documents ON documents.id = parsed_texts.document_id"
        " WHERE documents.sha256 = %s"
        " AND parsed_texts.parser = %s AND parsed_texts.parser_version = %s",
        (sha256, parser, parser_version),
    ).fetchone()
    return row is not None


def add_document(
    connection: psycopg.Connection[TupleRow],
    sha256: str,
    file_name: str,
    byte_size: int,
) -> UUID:
    """Writes a row for the PDF unless it has one, and returns the row's id."""
    connection.execute(
        "INSERT INTO documents (sha256, file_name, byte_size) VALUES (%s, %s, %s)"
        " ON CONFLICT (sha256) DO NOTHING",
        (sha256, file_name, byte_size),
    )
    row = connection.execute(
        "SELECT id FROM documents WHERE sha256 = %s", (sha256,)
    ).fetchone()
    # Written just above, or there already.
    assert row is not None
    document_id: UUID = row[0]
    return document_id


def add_parsed_text(
    connection: psycopg.Connection[TupleRow],
    document_id: UUID,
    parser: str,
    parser_version: str,
    text_sha256: str,
    parse_seconds: float,
) -> None:
    """Writes the row that ties a document to the text a parser read from it."""
    connection.execute(
        "INSERT INTO parsed_texts"
        " (document_id, parser, parser_version, text_sha256, parse_seconds)"
        " VALUES (%s, %s, %s, %s, %s)",
        (document_id, parser, parser_version, text_sha256, parse_seconds),
    )
