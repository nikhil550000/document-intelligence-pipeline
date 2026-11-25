"""Tests for CUAD's answers as database rows, and stored records as answers."""

import json
from datetime import date
from typing import Any

import pytest

from docintel.domain.fields import ALL_FIELDS
from docintel.domain.values import Duration, DurationUnit, Perpetual
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.cuad_gold import read_gold_answers
from docintel.evaluation.gold import (
    AcceptedValues,
    GoldAnswer,
    NoAnswer,
    PartyNames,
    Skipped,
    SkipRule,
)
from docintel.evaluation.stored_gold import (
    answers_of_record,
    gold_rows,
    read_gold_row,
    score_rows,
)

FIELDS = {field.name: field for field in ALL_FIELDS}


def every_field_has_nothing() -> dict[str, GoldAnswer]:
    """CUAD's answers for a contract where it labelled nothing."""
    return {field.name: NoAnswer() for field in ALL_FIELDS}


def read_back(gold_by_field: dict[str, GoldAnswer]) -> dict[str, GoldAnswer]:
    """Writes the answers as rows, as JSON in the database would, and reads them."""
    read = {}
    for field_name, kind, rule, values in gold_rows(gold_by_field):
        values = json.loads(json.dumps(values))
        read[field_name] = read_gold_row(FIELDS[field_name], kind, rule, values)
    return read


def test_every_kind_of_answer_reads_back_as_it_was_written() -> None:
    """Dates, perpetual, durations, names, clauses, skips and nothing."""
    gold = every_field_has_nothing()
    gold["parties"] = PartyNames(("Corio Inc.", "AT&T Corp."))
    gold["agreement_date"] = AcceptedValues((date(2014, 5, 8),))
    gold["expiration_date"] = AcceptedValues((Perpetual.PERPETUAL,))
    gold["renewal_term"] = AcceptedValues(
        (Duration(1, DurationUnit.YEARS), Duration(12, DurationUnit.MONTHS))
    )
    gold["governing_law"] = AcceptedValues(("Nevada",))
    gold["effective_date"] = Skipped(SkipRule.REDACTED)
    gold["non_compete"] = AcceptedValues((True,))

    assert read_back(gold) == gold


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_every_cuad_answer_reads_back_as_it_was_written() -> None:
    """Storing CUAD's 510 x 41 answers loses nothing the scorer reads."""
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))

    for contract, gold_by_field in gold_answers.items():
        assert read_back(gold_by_field) == gold_by_field, contract


def test_a_record_gives_the_scorer_an_answer_of_each_fields_type(
    empty_record: dict[str, Any],
) -> None:
    """A stored record's JSON becomes dates, durations, names and booleans."""
    empty_record["parties"]["names"] = ["Corio Inc."]
    empty_record["agreement_date"]["value"] = "2014-05-08"
    empty_record["expiration_date"]["value"] = "perpetual"
    empty_record["renewal_term"]["value"] = {"amount": 1, "unit": "years"}
    empty_record["non_compete"]["present"] = True

    answers = answers_of_record(empty_record)

    assert answers["parties"] == ["Corio Inc."]
    assert answers["agreement_date"] == date(2014, 5, 8)
    assert answers["expiration_date"] is Perpetual.PERPETUAL
    assert answers["renewal_term"] == Duration(1, DurationUnit.YEARS)
    assert answers["non_compete"] is True
    assert answers["exclusivity"] is False
    assert answers["document_name"] is None


def test_a_contract_without_a_record_misses_every_answer_cuad_has() -> None:
    """A failed contract answers null everywhere: CUAD's answers are missed."""
    gold = every_field_has_nothing()
    gold["governing_law"] = AcceptedValues(("Nevada",))
    gold["parties"] = PartyNames(("Corio Inc.", "AT&T Corp."))
    gold["non_compete"] = AcceptedValues((True,))
    gold["effective_date"] = Skipped(SkipRule.PASSAGE_ONLY)

    rows = {row[0]: row[1:] for row in score_rows(gold, answers_of_record(None))}

    assert rows["governing_law"] == (0, 0, 1, None)
    assert rows["parties"] == (0, 0, 2, None)
    assert rows["non_compete"] == (0, 0, 1, None)
    assert rows["effective_date"] == (0, 0, 0, "passage only")
    assert rows["exclusivity"] == (0, 0, 0, None)
    assert len(rows) == 41
