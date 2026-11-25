"""Tests for the record extracted from one contract."""

import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.domain.record import (
    ClauseAnswer,
    ContractRecord,
    DateAnswer,
    DurationAnswer,
    ExpirationDateAnswer,
    PartiesAnswer,
    TextAnswer,
)
from docintel.domain.values import Duration, DurationUnit, Perpetual

ANSWER_TYPE_OF_FIELD_TYPE = {
    FieldType.TEXT: TextAnswer,
    FieldType.ENTITY_LIST: PartiesAnswer,
    FieldType.DATE: DateAnswer,
    FieldType.DURATION: DurationAnswer,
    FieldType.JURISDICTION: TextAnswer,
    FieldType.CLAUSE: ClauseAnswer,
}


def test_the_record_has_every_field_in_order_with_the_answer_of_its_type() -> None:
    """The record and the field list cannot drift apart."""
    names = list(ContractRecord.model_fields)
    assert names == [field.name for field in ALL_FIELDS]
    for field in ALL_FIELDS:
        annotation = ContractRecord.model_fields[field.name].annotation
        if field.name == "expiration_date":
            assert annotation is ExpirationDateAnswer
        else:
            assert annotation is ANSWER_TYPE_OF_FIELD_TYPE[field.type]


def test_a_record_reads_every_kind_of_answer(empty_record: dict[str, Any]) -> None:
    """Dates, perpetual, durations, names and clauses become their own types."""
    record = empty_record
    record["parties"] = {
        "evidence": [{"text": "between Corio Inc. and AT&T Corp."}],
        "names": ["Corio Inc.", "AT&T Corp."],
    }
    record["agreement_date"]["value"] = "2014-05-08"
    record["expiration_date"]["value"] = "perpetual"
    record["renewal_term"]["value"] = {"amount": 1, "unit": "years"}
    record["non_compete"] = {
        "evidence": [{"text": "shall not compete"}],
        "present": True,
    }

    read = ContractRecord.model_validate_json(json.dumps(record))

    assert read.parties.names == ["Corio Inc.", "AT&T Corp."]
    assert read.parties.evidence[0].text == "between Corio Inc. and AT&T Corp."
    assert read.agreement_date.value == date(2014, 5, 8)
    assert read.expiration_date.value is Perpetual.PERPETUAL
    assert read.renewal_term.value == Duration(1, DurationUnit.YEARS)
    assert read.non_compete.present is True
    assert read.document_name.value is None


@pytest.mark.parametrize(
    ("field_name", "answer"),
    [
        # A clause must say present or absent; null would hide a forgotten field.
        ("non_compete", {"evidence": [], "present": None}),
        ("parties", {"evidence": [], "names": None}),
        ("agreement_date", {"evidence": [], "value": "2014-02-30"}),
        ("agreement_date", {"evidence": [], "value": "May 8, 2014"}),
        ("expiration_date", {"evidence": [], "value": "forever"}),
        ("renewal_term", {"evidence": [], "value": {"amount": 2, "unit": "weeks"}}),
        ("renewal_term", {"evidence": [], "value": {"amount": "1", "unit": "years"}}),
        ("non_compete", {"evidence": [], "present": "yes"}),
        # The page is found by the grounding check, so the model may not give one.
        ("non_compete", {"evidence": [{"text": "a", "page": 3}], "present": True}),
        ("non_compete", {"evidence": [], "present": True, "reason": "obvious"}),
        ("non_compete", {"present": True}),
    ],
)
def test_a_wrong_answer_is_refused(
    empty_record: dict[str, Any], field_name: str, answer: dict[str, Any]
) -> None:
    """Each answer must have its field's type, its quotes and nothing more."""
    record = empty_record
    record[field_name] = answer

    with pytest.raises(ValidationError):
        ContractRecord.model_validate_json(json.dumps(record))


def test_a_missing_field_is_refused(empty_record: dict[str, Any]) -> None:
    """A field left out is not taken as null: every field must be answered."""
    record = empty_record
    del record["governing_law"]

    with pytest.raises(ValidationError):
        ContractRecord.model_validate_json(json.dumps(record))


def test_the_schema_requires_every_field_and_allows_no_other() -> None:
    """The schema sent to the model asks for all 41 fields and only those."""
    schema = ContractRecord.model_json_schema()

    assert schema["required"] == [field.name for field in ALL_FIELDS]
    assert schema["additionalProperties"] is False
    assert "page" not in schema["$defs"]["Quote"]["properties"]
