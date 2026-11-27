"""Tests for scoring a stored run and writing its report, on real services."""

import hashlib
import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest

from docintel.cli import RunNotReportableError, report_run
from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.domain.record import SCHEMA_VERSION, ContractRecord
from docintel.evaluation.contracts import LEFT_OUT, PDF_FOLDER, find_contract_pdfs
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.cuad_gold import read_gold_answers
from docintel.evaluation.gold import (
    AcceptedValues,
    GoldAnswer,
    NoAnswer,
    PartyNames,
)
from docintel.evaluation.metrics import add_up_by_field
from docintel.evaluation.report import compute_report
from docintel.evaluation.scoring import score_contract
from docintel.evaluation.stored_gold import answers_of_record, value_as_json
from docintel.storage.documents import add_document
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.runs import Extraction, add_extraction, add_run, finish_run


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to a database that has every table."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def nothing_labelled() -> dict[str, GoldAnswer]:
    """CUAD's answers for a contract where it labelled nothing."""
    return {field.name: NoAnswer() for field in ALL_FIELDS}


def extraction(
    document_id: UUID, record: dict[str, Any] | None, failure: str | None
) -> Extraction:
    """An extraction with a record, or a failure with its reason."""
    status = "valid"
    response = "b" * 64
    if failure is not None:
        status = "failed"
        response = None
    read = None
    if record is not None:
        read = ContractRecord.model_validate_json(json.dumps(record))
    return Extraction(
        document_id=document_id,
        status=status,
        record=read,
        problems=[],
        failure_reason=failure,
        model="a-model",
        prompt_version="1",
        schema_version=SCHEMA_VERSION,
        request_sha256="a" * 64,
        response_sha256=response,
        from_cache=False,
        input_tokens=0 if failure else 1000,
        cached_input_tokens=0,
        output_tokens=0 if failure else 100,
        cost_usd=Decimal(0) if failure else Decimal("0.001"),
        parse_seconds=0.1,
        extract_seconds=1.0,
        total_seconds=1.1,
    )


def new_run(connection: psycopg.Connection) -> UUID:
    """Writes the row of a run that has started."""
    config = {"parser": "pdfium", "prompt_version": 1, "model": {"name": "a-model"}}
    return add_run(
        connection, "a-config", config, "c" * 40, "d" * 64, "dev", Decimal(1), False
    )


def document(connection: psycopg.Connection, file_name: str) -> UUID:
    """Writes a document row for a file name, with a made-up hash."""
    sha256 = hashlib.sha256(file_name.encode()).hexdigest()
    return add_document(connection, sha256, file_name, 1000)


def test_a_failed_contract_reaches_the_report_as_missed_answers(
    connection: psycopg.Connection, tmp_path: Path, empty_record: dict[str, Any]
) -> None:
    """Stored, scored, exported and queried, a failure cannot disappear."""
    gold = {"found.pdf": nothing_labelled(), "failed.pdf": nothing_labelled()}
    for contract in gold:
        gold[contract]["governing_law"] = AcceptedValues(("Nevada",))
        gold[contract]["parties"] = PartyNames(("Alpha Inc.", "Beta LLC"))
        gold[contract]["non_compete"] = AcceptedValues((True,))
    empty_record["governing_law"]["value"] = "Nevada"
    empty_record["parties"]["names"] = ["Alpha Inc.", "Beta LLC"]
    empty_record["non_compete"]["present"] = True
    run_id = new_run(connection)
    add_extraction(
        connection,
        run_id,
        extraction(document(connection, "found.pdf"), empty_record, None),
    )
    add_extraction(
        connection,
        run_id,
        extraction(
            document(connection, "failed.pdf"),
            None,
            "timed out on the last of 4 attempts",
        ),
    )
    finish_run(connection, run_id, "complete", None)

    folder = report_run(connection, run_id, gold, tmp_path)

    report = compute_report(folder)
    lines = {line.name: line for line in report.by_field}
    # Found in one contract, missed in the one that failed; nothing wrong was given.
    assert lines["governing_law"].scores.recall == 0.5
    assert lines["governing_law"].scores.precision == 1.0
    assert lines["parties"].counts.false_negatives == 2
    assert lines["non_compete"].counts.false_negatives == 1
    assert (report.attempted, report.answered) == (2, 1)
    markdown = (folder / "report.md").read_text(encoding="utf-8")
    assert "Contracts answered: **1 of 2**" in markdown
    assert "| failed.pdf | failed | timed out on the last of 4 attempts |" in markdown
    stored = connection.execute(
        "SELECT sum(false_negatives) FROM scores WHERE field_name = 'parties'"
    ).fetchone()
    assert stored == (2,)


def test_a_run_that_did_not_finish_is_not_reported(
    connection: psycopg.Connection, tmp_path: Path
) -> None:
    """A stopped run lacks contracts, so its scores would mislead."""
    run_id = new_run(connection)
    finish_run(connection, run_id, "stopped", "stopped before b.pdf: the ceiling")

    with pytest.raises(RunNotReportableError, match="stopped, not complete"):
        report_run(connection, run_id, {}, tmp_path)


def record_cuad_would_give(gold_by_field: dict[str, GoldAnswer]) -> dict[str, Any]:
    """A record whose answers are CUAD's own: every party, the first value."""
    record: dict[str, Any] = {}
    for field in ALL_FIELDS:
        gold = gold_by_field[field.name]
        if field.type == FieldType.CLAUSE:
            record[field.name] = {
                "evidence": [],
                "present": isinstance(gold, AcceptedValues),
            }
        elif field.type == FieldType.ENTITY_LIST:
            names: list[str] = []
            if isinstance(gold, PartyNames):
                names = list(gold.names)
            record[field.name] = {"evidence": [], "names": names}
        else:
            value = None
            if isinstance(gold, AcceptedValues):
                value = value_as_json(gold.values[0])
            record[field.name] = {"evidence": [], "value": value}
    return record


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_cuad_scored_against_itself_through_the_database_is_right_everywhere(
    connection: psycopg.Connection, tmp_path: Path
) -> None:
    """The 506 kept contracts, stored, scored and reported, score 100%.

    The counts equal the scorer's own on the same answers, so nothing is lost
    on the way through the database, the files and the SQL.
    """
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))
    pdfs_by_row = find_contract_pdfs(PDF_FOLDER, list(gold_answers))
    gold_by_file_name = {}
    run_id = new_run(connection)
    expected = []
    # One transaction for the setup, so it does not pay for 506 commits.
    with connection.transaction():
        for row_name, pdf_path in pdfs_by_row.items():
            if row_name in LEFT_OUT:
                continue
            gold_by_field = gold_answers[row_name]
            gold_by_file_name[pdf_path.name] = gold_by_field
            record = record_cuad_would_give(gold_by_field)
            document_id = document(connection, pdf_path.name)
            add_extraction(connection, run_id, extraction(document_id, record, None))
            expected.append(score_contract(gold_by_field, answers_of_record(record)))
    finish_run(connection, run_id, "complete", None)

    folder = report_run(connection, run_id, gold_by_file_name, tmp_path)

    report = compute_report(folder)
    counts_by_field = add_up_by_field(expected)
    assert len(gold_by_file_name) == 506
    for line in report.by_field:
        assert line.counts == counts_by_field[line.name], line.name
        assert line.scores.f1 == 1.0, line.name
    for line in report.by_field_type:
        assert line.scores.f1 == 1.0, line.name
    assert report.micro.scores.f1 == 1.0
    assert report.macro.f1 == 1.0
    assert (report.attempted, report.answered) == (506, 506)
