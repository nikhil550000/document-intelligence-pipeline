"""Rows for a run, and for each contract's extraction in it."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb

from docintel.domain.problems import Problem
from docintel.domain.record import (
    ClauseAnswer,
    ContractRecord,
    DateAnswer,
    DurationAnswer,
    ExpirationDateAnswer,
    PartiesAnswer,
    TextAnswer,
)
from docintel.domain.values import Perpetual


@dataclass(frozen=True)
class StoredText:
    """A stored document and where the text one parser version read from it is."""

    document_id: UUID
    text_sha256: str
    parse_seconds: float


@dataclass(frozen=True)
class Extraction:
    """What one contract gave in a run: a record, problems, or a failure."""

    document_id: UUID
    status: str
    record: ContractRecord | None
    problems: list[Problem]
    failure_reason: str | None
    model: str
    prompt_version: str
    schema_version: str
    request_sha256: str
    response_sha256: str | None
    from_cache: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    parse_seconds: float
    extract_seconds: float
    total_seconds: float


def find_stored_text(
    connection: psycopg.Connection[TupleRow],
    file_name: str,
    parser: str,
    parser_version: str,
) -> StoredText | None:
    """Finds the document with this PDF file name, and its text from this parser."""
    row = connection.execute(
        "SELECT documents.id, parsed_texts.text_sha256, parsed_texts.parse_seconds"
        " FROM documents JOIN parsed_texts ON parsed_texts.document_id = documents.id"
        " WHERE documents.file_name = %s"
        " AND parsed_texts.parser = %s AND parsed_texts.parser_version = %s",
        (file_name, parser, parser_version),
    ).fetchone()
    if row is None:
        return None
    return StoredText(document_id=row[0], text_sha256=row[1], parse_seconds=row[2])


def add_run(
    connection: psycopg.Connection[TupleRow],
    config_name: str,
    config: dict[str, Any],
    git_commit: str,
    contract_list: str,
    cost_ceiling_usd: Decimal,
) -> UUID:
    """Writes the row of a run that is starting, and returns its id."""
    row = connection.execute(
        "INSERT INTO runs"
        " (config_name, config, git_commit, contract_list, cost_ceiling_usd)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (config_name, Jsonb(config), git_commit, contract_list, cost_ceiling_usd),
    ).fetchone()
    # INSERT ... RETURNING gives one row.
    assert row is not None
    run_id: UUID = row[0]
    return run_id


def finish_run(
    connection: psycopg.Connection[TupleRow],
    run_id: UUID,
    status: str,
    stop_reason: str | None,
) -> None:
    """Marks a run complete, or stopped with the reason."""
    connection.execute(
        "UPDATE runs SET status = %s, stop_reason = %s, finished_at = now()"
        " WHERE id = %s",
        (status, stop_reason, run_id),
    )


def find_cached_response(
    connection: psycopg.Connection[TupleRow], request_sha256: str
) -> str | None:
    """Returns the hash of a response already received for this exact request."""
    row = connection.execute(
        "SELECT response_sha256 FROM extractions"
        " WHERE request_sha256 = %s AND response_sha256 IS NOT NULL"
        " ORDER BY id LIMIT 1",
        (request_sha256,),
    ).fetchone()
    if row is None:
        return None
    response_sha256: str = row[0]
    return response_sha256


def add_extraction(
    connection: psycopg.Connection[TupleRow], run_id: UUID, extraction: Extraction
) -> int:
    """Writes the extraction with its field values and problems, all at once."""
    record_json = None
    if extraction.record is not None:
        record_json = Jsonb(extraction.record.model_dump(mode="json"))
    with connection.transaction():
        row = connection.execute(
            "INSERT INTO extractions (run_id, document_id, status, record,"
            " failure_reason, model, prompt_version, schema_version, request_sha256,"
            " response_sha256, from_cache, input_tokens, cached_input_tokens,"
            " output_tokens, cost_usd, parse_seconds, extract_seconds, total_seconds)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s) RETURNING id",
            (
                run_id,
                extraction.document_id,
                extraction.status,
                record_json,
                extraction.failure_reason,
                extraction.model,
                extraction.prompt_version,
                extraction.schema_version,
                extraction.request_sha256,
                extraction.response_sha256,
                extraction.from_cache,
                extraction.input_tokens,
                extraction.cached_input_tokens,
                extraction.output_tokens,
                extraction.cost_usd,
                extraction.parse_seconds,
                extraction.extract_seconds,
                extraction.total_seconds,
            ),
        ).fetchone()
        # INSERT ... RETURNING gives one row.
        assert row is not None
        extraction_id: int = row[0]
        if extraction.record is not None:
            add_field_values(connection, extraction_id, extraction.record)
        for position, problem in enumerate(extraction.problems):
            connection.execute(
                "INSERT INTO validation_issues"
                " (extraction_id, position, layer, rule, field_name, message)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    extraction_id,
                    position,
                    problem.layer,
                    problem.rule,
                    problem.field,
                    problem.message,
                ),
            )
    return extraction_id


def add_field_values(
    connection: psycopg.Connection[TupleRow],
    extraction_id: int,
    record: ContractRecord,
) -> None:
    """Writes one row per field, with the answer in the column of its type."""
    rows = []
    for field_name in ContractRecord.model_fields:
        answer = getattr(record, field_name)
        values: dict[str, Any] = {
            "present": None,
            "date_value": None,
            "perpetual": None,
            "duration_amount": None,
            "duration_unit": None,
            "text_value": None,
            "party_names": None,
        }
        if isinstance(answer, ClauseAnswer):
            values["present"] = answer.present
        elif isinstance(answer, PartiesAnswer):
            values["party_names"] = answer.names
        elif isinstance(answer, TextAnswer):
            values["text_value"] = answer.value
        elif isinstance(answer, DateAnswer):
            values["date_value"] = answer.value
        elif isinstance(answer, ExpirationDateAnswer):
            if answer.value is Perpetual.PERPETUAL:
                values["perpetual"] = True
            else:
                values["date_value"] = answer.value
        elif isinstance(answer, DurationAnswer) and answer.value is not None:
            values["duration_amount"] = answer.value.amount
            values["duration_unit"] = answer.value.unit.value
        evidence = answer.model_dump(mode="json")["evidence"]
        rows.append(
            (
                extraction_id,
                field_name,
                values["present"],
                values["date_value"],
                values["perpetual"],
                values["duration_amount"],
                values["duration_unit"],
                values["text_value"],
                values["party_names"],
                Jsonb(evidence),
            )
        )
    # One COPY for the 41 rows: on this machine every statement costs a round trip.
    with (
        connection.cursor() as cursor,
        cursor.copy(
            "COPY field_values (extraction_id, field_name, present, date_value,"
            " perpetual, duration_amount, duration_unit, text_value, party_names,"
            " evidence) FROM STDIN"
        ) as copy,
    ):
        for row in rows:
            copy.write_row(row)
