"""Tests for the outcome of one field of one contract."""

from datetime import date

import pytest

from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.domain.values import Duration, DurationUnit, Perpetual
from docintel.evaluation.cuad import CuadAnswer
from docintel.evaluation.cuad_gold import read_gold_answer
from docintel.evaluation.gold import (
    AcceptedValues,
    GoldAnswer,
    NoAnswer,
    PartyNames,
    Skipped,
    SkipRule,
)
from docintel.evaluation.scoring import (
    Counts,
    ModelAnswer,
    score_answer,
    score_contract,
)

FIELDS = {field.name: field for field in ALL_FIELDS}
PASSAGE = "['the text a person highlighted']"


def cuad(field_name: str, answer: str) -> GoldAnswer:
    """Reads one of CUAD's answers into its scoring form, as the scorer receives it."""
    return read_gold_answer(FIELDS[field_name], CuadAnswer(PASSAGE, answer))


@pytest.mark.parametrize(
    ("cuad_answer", "model_answer", "expected"),
    [
        ("Yes", True, Counts(true_positives=1, false_positives=0, false_negatives=0)),
        ("No", True, Counts(true_positives=0, false_positives=1, false_negatives=0)),
        ("Yes", False, Counts(true_positives=0, false_positives=0, false_negatives=1)),
        ("No", False, Counts(true_positives=0, false_positives=0, false_negatives=0)),
    ],
)
def test_clause_outcomes(
    cuad_answer: str, model_answer: bool, expected: Counts
) -> None:
    """Present is the model's answer and absent is no answer, so a No counts nothing."""
    gold = cuad("non_compete", cuad_answer)
    assert score_answer(FIELDS["non_compete"], gold, model_answer) == expected


@pytest.mark.parametrize(
    ("gold", "model_answer", "expected"),
    [
        (
            AcceptedValues((date(2014, 5, 8),)),
            date(2014, 5, 8),
            Counts(true_positives=1, false_positives=0, false_negatives=0),
        ),
        (
            AcceptedValues((date(2014, 5, 8),)),
            date(2015, 5, 8),
            Counts(true_positives=0, false_positives=1, false_negatives=1),
        ),
        (
            AcceptedValues((date(2014, 5, 8),)),
            None,
            Counts(true_positives=0, false_positives=0, false_negatives=1),
        ),
        (
            NoAnswer(),
            date(2014, 5, 8),
            Counts(true_positives=0, false_positives=1, false_negatives=0),
        ),
        (
            NoAnswer(),
            None,
            Counts(true_positives=0, false_positives=0, false_negatives=0),
        ),
    ],
)
def test_outcomes_of_the_other_fields(
    gold: GoldAnswer, model_answer: ModelAnswer, expected: Counts
) -> None:
    """A different answer counts twice: a wrong one given, the right one missed."""
    assert score_answer(FIELDS["agreement_date"], gold, model_answer) == expected


@pytest.mark.parametrize("model_answer", [date(2020, 1, 1), None])
def test_a_skipped_case_has_no_outcome_whatever_the_model_answers(
    model_answer: ModelAnswer,
) -> None:
    """A redacted date has nothing to compare with, so nothing is counted."""
    gold = cuad("agreement_date", "[]/[]/2020")
    assert gold == Skipped(SkipRule.REDACTED)
    assert score_answer(FIELDS["agreement_date"], gold, model_answer) is None


RIGHT = Counts(true_positives=1, false_positives=0, false_negatives=0)
WRONG = Counts(true_positives=0, false_positives=1, false_negatives=1)


@pytest.mark.parametrize(
    ("field_name", "cuad_answer", "model_answer", "expected"),
    [
        ("governing_law", "Illinois; New York", "Illinois", RIGHT),
        ("governing_law", "Illinois; New York", "New York", RIGHT),
        ("governing_law", "Illinois; New York", "Delaware", WRONG),
        ("effective_date", "09/01/2006; 8/31/2007", date(2007, 8, 31), RIGHT),
        ("expiration_date", "09/05/2019; perpetual", Perpetual.PERPETUAL, RIGHT),
    ],
)
def test_an_answer_with_several_values_is_right_on_any_one(
    field_name: str, cuad_answer: str, model_answer: ModelAnswer, expected: Counts
) -> None:
    """CUAD wrote two or three values; the model is right if it gives one of them."""
    gold = cuad(field_name, cuad_answer)
    assert score_answer(FIELDS[field_name], gold, model_answer) == expected


@pytest.mark.parametrize(
    ("field_name", "cuad_answer", "model_answer", "expected"),
    [
        # Worked out by the annotator: one year after 10 September 2015.
        ("expiration_date", "9/10/16", date(2016, 9, 9), WRONG),
        ("expiration_date", "perpetual", date(2030, 12, 31), WRONG),
        ("expiration_date", "12/31/04", Perpetual.PERPETUAL, WRONG),
        (
            "renewal_term",
            "3 successive 1 year",
            Duration(12, DurationUnit.MONTHS),
            RIGHT,
        ),
        (
            "notice_to_terminate_renewal",
            "60 days",
            Duration(2, DurationUnit.MONTHS),
            WRONG,
        ),
        ("governing_law", "New York", "State of New York", RIGHT),
        ("governing_law", "New York", "the laws of the State of New York", WRONG),
        ("document_name", "SPONSORSHIP AGREEMENT", "Sponsorship Agreement", RIGHT),
    ],
)
def test_each_field_type_is_compared_its_own_way(
    field_name: str, cuad_answer: str, model_answer: ModelAnswer, expected: Counts
) -> None:
    """Dates match to the day; durations, places and titles by their own comparison."""
    gold = cuad(field_name, cuad_answer)
    assert score_answer(FIELDS[field_name], gold, model_answer) == expected


def test_parties_are_scored_name_by_name() -> None:
    """Corio Inc is found, Commerce One, Inc. missed, and Commerce One is wrong."""
    gold = cuad("parties", 'Corio Inc. ("CORIO"); Commerce One, Inc. ("COMMERCE ONE")')

    counts = score_answer(FIELDS["parties"], gold, ["Corio Inc", "Commerce One"])

    assert counts == Counts(true_positives=1, false_positives=1, false_negatives=1)


def test_a_party_name_given_twice_counts_once() -> None:
    """A name repeated by CUAD or by the model is still one party."""
    gold = cuad(
        "parties",
        'HOF Village, LLC ("Village Media Company"); HOF Village, LLC ("HOFV")',
    )
    assert gold == PartyNames(("HOF Village, LLC", "HOF Village, LLC"))

    counts = score_answer(
        FIELDS["parties"], gold, ["HOF Village, LLC", "HOF Village LLC"]
    )

    assert counts == Counts(true_positives=1, false_positives=0, false_negatives=0)


def test_every_party_named_where_cuad_has_nothing_is_wrong() -> None:
    """With no party to find, each name the model gives is a false positive."""
    counts = score_answer(FIELDS["parties"], NoAnswer(), ["Alpha Inc.", "Beta LLC"])
    assert counts == Counts(true_positives=0, false_positives=2, false_negatives=0)


@pytest.mark.parametrize("model_answer", [None, []])
def test_every_party_is_missed_when_the_model_names_none(
    model_answer: ModelAnswer,
) -> None:
    """Null and an empty list both name no party."""
    gold = cuad(
        "parties",
        'Freeze Tag Inc. ("Company"); American Diabetes Association ("Association")',
    )
    counts = score_answer(FIELDS["parties"], gold, model_answer)
    assert counts == Counts(true_positives=0, false_positives=0, false_negatives=2)


def test_a_parties_answer_that_is_not_a_list_raises() -> None:
    """A single string would be read as letters, one false party each."""
    gold = cuad("parties", 'Freeze Tag Inc. ("Company")')
    with pytest.raises(TypeError):
        score_answer(FIELDS["parties"], gold, "Freeze Tag Inc.")


def test_a_contract_gets_counts_for_every_field_that_is_not_skipped() -> None:
    """The redacted agreement date has no counts; every other field has."""
    gold_by_field: dict[str, GoldAnswer] = {}
    model_answers: dict[str, ModelAnswer] = {}
    for field in ALL_FIELDS:
        gold_by_field[field.name] = NoAnswer()
        if field.type == FieldType.CLAUSE:
            model_answers[field.name] = False
        else:
            model_answers[field.name] = None
    gold_by_field["agreement_date"] = cuad("agreement_date", "[]/[]/2020")
    gold_by_field["governing_law"] = cuad("governing_law", "Nevada")
    model_answers["governing_law"] = "Nevada"

    counts_by_field = score_contract(gold_by_field, model_answers)

    assert "agreement_date" not in counts_by_field
    assert len(counts_by_field) == 40
    assert counts_by_field["governing_law"] == RIGHT
    assert counts_by_field["non_compete"] == Counts(
        true_positives=0, false_positives=0, false_negatives=0
    )


def test_a_field_missing_from_the_model_answers_raises() -> None:
    """The model must answer every field, so a missing one is not read as null."""
    gold_by_field: dict[str, GoldAnswer] = {}
    for field in ALL_FIELDS:
        gold_by_field[field.name] = NoAnswer()
    with pytest.raises(KeyError):
        score_contract(gold_by_field, {})
