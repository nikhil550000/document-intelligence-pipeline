"""Runs the stages of the pipeline in order, for one contract."""

import hashlib
import json
from typing import TYPE_CHECKING

import psycopg
from psycopg.rows import TupleRow

from docintel.parsing.parsed_text import ParsedText
from docintel.parsing.pdfium import PARSER_NAME, PARSER_VERSION, parse_pdf
from docintel.storage.documents import add_document, add_parsed_text, has_parsed_text
from docintel.storage.objects import put_object

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def store_contract(
    connection: psycopg.Connection[TupleRow],
    s3_client: "S3Client",
    bucket: str,
    file_name: str,
    pdf: bytes,
) -> ParsedText | None:
    """Stores a PDF and the text PDFium reads from it, with a row for each.

    Returns:
        The text read, or None when this version of the parser had read the PDF
        before, in which case nothing is written.
    """
    sha256 = hashlib.sha256(pdf).hexdigest()
    if has_parsed_text(connection, sha256, PARSER_NAME, PARSER_VERSION):
        return None

    # The files go first, so that no row ever names a file that is not stored.
    put_object(s3_client, bucket, pdf)
    parsed = parse_pdf(pdf)
    text_sha256 = put_object(s3_client, bucket, json.dumps(parsed.pages).encode())
    with connection.transaction():
        document_id = add_document(connection, sha256, file_name, len(pdf))
        add_parsed_text(
            connection,
            document_id,
            parsed.parser,
            parsed.parser_version,
            text_sha256,
            parsed.seconds,
        )
    return parsed
