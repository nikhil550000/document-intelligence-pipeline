"""Rows for CUAD's answers and for the scores of a run, and what a report reads."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import TupleRow
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class RunRow:
    """What a run was and how it ended."""

    run_id: UUID
    config_name: str
    config: dict[str, Any]
    git_commit: str
    contract_list: str
    cost_ceiling_usd: Decimal
    status: str
    stop_reason: str | None
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class ExtractionRow:
    """One contract of a run, as the report needs it."""

    extraction_id: int
    document_id: UUID
    file_name: str
    status: str
    record: dict[str, Any] | None
    # Why there is no record: the failure, or the first problem found.
    reason: str | None
    model: str
    prompt_version: str
    schema_version: str
    from_cache: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    extract_seconds: float | None
    total_seconds: float


def replace_gold_values(
    connection: psycopg.Connection[TupleRow],
    rows: list[tuple[UUID, str, str, str | None, list[Any] | None]],
) -> None:
    """Writes CUAD's answer for each field of some documents, replacing older ones.

    Args:
        connection: The database.
        rows: Document, field, kind, skip rule and accepted values.
    """
    document_ids = []
    for row in rows:
        if row[0] not in document_ids:
            document_ids.append(row[0])
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM gold_values WHERE document_id = ANY(%s)", (document_ids,)
        )
        # One COPY for all rows: on this machine every statement costs a round trip.
        with cursor.copy(
            "COPY gold_values"
            " (document_id, field_name, kind, skip_rule, accepted_values) FROM STDIN"
        ) as copy:
            for document_id, field_name, kind, skip_rule, accepted_values in rows:
                values = None
                if accepted_values is not None:
                    values = Jsonb(accepted_values)
                copy.write_row((document_id, field_name, kind, skip_rule, values))


def read_gold_values(
    connection: psycopg.Connection[TupleRow], document_ids: list[UUID]
) -> dict[UUID, list[tuple[str, str, str | None, list[Any] | None]]]:
    """Reads CUAD's answer for each field of the documents, by document."""
    rows = connection.execute(
        "SELECT document_id, field_name, kind, skip_rule, accepted_values"
        " FROM gold_values WHERE document_id = ANY(%s)",
        (document_ids,),
    ).fetchall()
    by_document: dict[UUID, list[tuple[str, str, str | None, list[Any] | None]]] = {}
    for document_id, field_name, kind, skip_rule, accepted_values in rows:
        by_document.setdefault(document_id, []).append(
            (field_name, kind, skip_rule, accepted_values)
        )
    return by_document


def read_run(connection: psycopg.Connection[TupleRow], run_id: UUID) -> RunRow | None:
    """Reads a run's row, or None when there is no such run."""
    row = connection.execute(
        "SELECT id, config_name, config, git_commit, contract_list,"
        " cost_ceiling_usd, status, stop_reason, started_at, finished_at"
        " FROM runs WHERE id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return RunRow(*row)


def read_extractions(
    connection: psycopg.Connection[TupleRow], run_id: UUID
) -> list[ExtractionRow]:
    """Reads every contract of a run, in file name order."""
    rows = connection.execute(
        "SELECT extractions.id, documents.id, documents.file_name, status, record,"
        " coalesce(failure_reason, (SELECT message FROM validation_issues"
        "   WHERE extraction_id = extractions.id ORDER BY position LIMIT 1)),"
        " model, prompt_version, schema_version, from_cache, input_tokens,"
        " cached_input_tokens, output_tokens, cost_usd, extract_seconds,"
        " total_seconds"
        " FROM extractions JOIN documents ON documents.id = extractions.document_id"
        " WHERE run_id = %s ORDER BY documents.file_name",
        (run_id,),
    ).fetchall()
    return [ExtractionRow(*row) for row in rows]


def replace_scores(
    connection: psycopg.Connection[TupleRow],
    run_id: UUID,
    rows: list[tuple[int, str, int, int, int, str | None]],
) -> None:
    """Writes the counts of every field of a run's extractions, replacing older ones.

    Args:
        connection: The database.
        run_id: The run whose scores are replaced, all at once.
        rows: Extraction, field, the three counts and the skip rule.
    """
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM scores USING extractions"
            " WHERE extractions.id = scores.extraction_id AND extractions.run_id = %s",
            (run_id,),
        )
        with cursor.copy(
            "COPY scores (extraction_id, field_name, true_positives, false_positives,"
            " false_negatives, skip_rule) FROM STDIN"
        ) as copy:
            for row in rows:
                copy.write_row(row)


def read_scores(
    connection: psycopg.Connection[TupleRow], run_id: UUID
) -> list[tuple[str, str, int, int, int, str | None]]:
    """Reads the stored counts of a run: contract, field, the three counts, rule."""
    rows = connection.execute(
        "SELECT documents.file_name, scores.field_name, true_positives,"
        " false_positives, false_negatives, skip_rule"
        " FROM scores JOIN extractions ON extractions.id = scores.extraction_id"
        " JOIN documents ON documents.id = extractions.document_id"
        " WHERE extractions.run_id = %s ORDER BY 1, 2",
        (run_id,),
    ).fetchall()
    return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]
