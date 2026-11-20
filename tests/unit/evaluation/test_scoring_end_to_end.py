"""Tests that run CUAD's cells through the readers, the scorer and the scores."""

from datetime import date

import pytest

from docintel.domain.fields import ALL_FIELDS, CLAUSE_FIELDS, Field, FieldType
from docintel.domain.values import Duration, DurationUnit
from docintel.evaluation.cuad import (
    MASTER_CLAUSES_PATH,
    CuadAnswer,
    load_cuad_answers,
)
from docintel.evaluation.cuad_gold import read_gold_answers
from docintel.evaluation.gold import AcceptedValues, GoldAnswer, PartyNames, Skipped
from docintel.evaluation.intervals import DRAWS, RESAMPLING_SEED, report_intervals
from docintel.evaluation.metrics import (
    Scores,
    add_up_by_field,
    score_report,
    support,
)
from docintel.evaluation.scoring import (
    Counts,
    ModelAnswer,
    score_answer,
    score_contract,
)

FIELDS = {field.name: field for field in ALL_FIELDS}
PERFECT = Scores(precision=1.0, recall=1.0, f1=1.0)


def made_up_contract(cells: dict[str, CuadAnswer]) -> dict[str, CuadAnswer]:
    """CUAD's cells for one made-up contract; any field not given is empty or No."""
    answers_by_field = {}
    for field in ALL_FIELDS:
        if field.type == FieldType.CLAUSE:
            answers_by_field[field.name] = CuadAnswer("[]", "No")
        else:
            answers_by_field[field.name] = CuadAnswer("[]", "")
    answers_by_field.update(cells)
    return answers_by_field


def model_answers(answers: dict[str, ModelAnswer]) -> dict[str, ModelAnswer]:
    """A model's answers; any field not given is absent or null."""
    answers_by_field: dict[str, ModelAnswer] = {}
    for field in ALL_FIELDS:
        if field.type == FieldType.CLAUSE:
            answers_by_field[field.name] = False
        else:
            answers_by_field[field.name] = None
    answers_by_field.update(answers)
    return answers_by_field


def test_hand_made_wrong_answers_give_the_counts_worked_out_by_hand() -> None:
    """Wrong answers of known kinds give the counts worked out by hand.

    A missed clause, an invented date, a different governing law, one party name
    missing and one extra, and answers given where CUAD's answer is skipped.
    """
    passage = "['the text a person highlighted']"
    cuad_answers = {
        "supply.pdf": made_up_contract(
            {
                "document_name": CuadAnswer(passage, "SUPPLY AGREEMENT"),
                "parties": CuadAnswer(
                    passage, 'Alpha Inc. ("Supplier"); Beta LLC ("Buyer")'
                ),
                "governing_law": CuadAnswer(passage, "New York"),
                "non_compete": CuadAnswer(passage, "Yes"),
                "exclusivity": CuadAnswer(passage, "Yes"),
            }
        ),
        "license.pdf": made_up_contract(
            {
                "document_name": CuadAnswer(passage, "LICENSE AGREEMENT"),
                "parties": CuadAnswer(
                    passage,
                    'Corio Inc. ("CORIO"); Commerce One, Inc. ("COMMERCE ONE")',
                ),
                "agreement_date": CuadAnswer(passage, "5/8/14"),
                "renewal_term": CuadAnswer(passage, "successive 1 year"),
                "governing_law": CuadAnswer(passage, "Delaware"),
            }
        ),
        "form.pdf": made_up_contract(
            {
                "document_name": CuadAnswer(passage, "FRANCHISE AGREEMENT"),
                "parties": CuadAnswer(passage, '[] ("Franchisee"); [] ("Member")'),
                "agreement_date": CuadAnswer(passage, "[]/[]/2020"),
                "expiration_date": CuadAnswer(passage, ""),
            }
        ),
    }
    answers = {
        "supply.pdf": model_answers(
            {
                "document_name": "Supply Agreement",
                "parties": ["Alpha Inc", "Gamma Corp"],
                "expiration_date": date(2030, 12, 31),
                "governing_law": "State of New York",
                "non_compete": True,
                "exclusivity": False,
            }
        ),
        "license.pdf": model_answers(
            {
                "document_name": "License Agreement",
                "parties": ["Corio Inc.", "Commerce One, Inc."],
                "agreement_date": date(2014, 5, 8),
                "renewal_term": Duration(12, DurationUnit.MONTHS),
                "governing_law": "California",
                "non_compete": True,
            }
        ),
        "form.pdf": model_answers(
            {
                "document_name": "FRANCHISE AGREEMENT",
                "parties": ["Franchisee"],
                "agreement_date": date(2020, 1, 1),
                "expiration_date": date(2025, 1, 1),
            }
        ),
    }

    gold_answers = read_gold_answers(cuad_answers)
    counts_by_contract = {}
    for contract, gold_by_field in gold_answers.items():
        counts_by_contract[contract] = score_contract(gold_by_field, answers[contract])
    counts_by_field = add_up_by_field(list(counts_by_contract.values()))
    report = score_report(counts_by_field)

    # Worked out by hand, as (true positives, false positives, false negatives):
    # titles right 3 times; parties Alpha found, Beta missed, Gamma wrong, Corio
    # and Commerce One found; the 2014 date found; 12 months is 1 year; New York
    # found, California wrong and Delaware missed; the 2030 date invented where
    # CUAD has none; non-compete found once and invented once; exclusivity
    # missed. The form's parties, agreement date and expiration date are
    # skipped, so the answers given for them count nothing.
    expected_counts = {
        "document_name": Counts(3, 0, 0),
        "parties": Counts(3, 1, 1),
        "agreement_date": Counts(1, 0, 0),
        "expiration_date": Counts(0, 1, 0),
        "renewal_term": Counts(1, 0, 0),
        "governing_law": Counts(1, 1, 1),
        "non_compete": Counts(1, 1, 0),
        "exclusivity": Counts(0, 0, 1),
    }
    for field in ALL_FIELDS:
        expected = expected_counts.get(field.name, Counts(0, 0, 0))
        assert counts_by_field[field.name] == expected, field.name
    assert "parties" not in counts_by_contract["form.pdf"]
    assert "agreement_date" not in counts_by_contract["form.pdf"]
    assert "expiration_date" not in counts_by_contract["form.pdf"]

    assert report.scores_by_field["parties"] == Scores(0.75, 0.75, 0.75)
    assert report.scores_by_field["governing_law"] == Scores(0.5, 0.5, 0.5)
    assert report.scores_by_field["expiration_date"] == Scores(0.0, None, 0.0)
    assert report.scores_by_field["exclusivity"] == Scores(None, 0.0, 0.0)
    non_compete = report.scores_by_field["non_compete"]
    assert (non_compete.precision, non_compete.recall) == (0.5, 1.0)
    assert non_compete.f1 == pytest.approx(2 / 3)
    # Dates: 1 found, 1 invented. Clauses: 1 found, 1 invented, 1 missed.
    dates = report.scores_by_field_type[FieldType.DATE]
    assert (dates.precision, dates.recall) == (0.5, 1.0)
    assert report.scores_by_field_type[FieldType.CLAUSE] == Scores(0.5, 0.5, 0.5)
    # All fields: 10 found, 4 wrong, 3 missed.
    assert report.micro.precision == pytest.approx(10 / 14)
    assert report.micro.recall == pytest.approx(10 / 13)
    assert report.micro.f1 == pytest.approx(20 / 27)
    # The mean of the 7 precisions, 7 recalls and 8 F1s that exist. The F1s are
    # 1, 0.75, 1, 0, 1, 0.5, 2/3 and 0.
    assert report.macro.precision == pytest.approx(4.75 / 7)
    assert report.macro.recall == pytest.approx(5.25 / 7)
    assert report.macro.f1 == pytest.approx((4.25 + 2 / 3) / 8)


def answer_cuad_would_give(
    field: Field, gold: GoldAnswer, answer_when_skipped: ModelAnswer
) -> ModelAnswer:
    """Builds a model's answer from CUAD's: every party, or the first right value."""
    if isinstance(gold, PartyNames):
        return list(gold.names)
    if isinstance(gold, AcceptedValues):
        return gold.values[0]
    if isinstance(gold, Skipped):
        return answer_when_skipped
    if field.type == FieldType.CLAUSE:
        return False
    return None


def answer_right_for_no_contract(field: Field) -> ModelAnswer:
    """An answer of the field's type that no CUAD answer accepts."""
    if field.type == FieldType.ENTITY_LIST:
        return ["Nobody Holdings Ltd."]
    if field.type == FieldType.DATE:
        return date(1901, 1, 1)
    if field.type == FieldType.DURATION:
        return Duration(99, DurationUnit.YEARS)
    return "Atlantis"


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_cuad_scored_against_itself_is_right_on_every_field() -> None:
    """CUAD's own answers score 100% on all 41 fields over all 510 contracts."""
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))

    counts_by_contract = {}
    counts_with_null_for_skips = []
    for contract, gold_by_field in gold_answers.items():
        answers = {}
        answers_with_null_for_skips = {}
        for field in ALL_FIELDS:
            gold = gold_by_field[field.name]
            answers[field.name] = answer_cuad_would_give(
                field, gold, answer_right_for_no_contract(field)
            )
            answers_with_null_for_skips[field.name] = answer_cuad_would_give(
                field, gold, None
            )
        counts_by_contract[contract] = score_contract(gold_by_field, answers)
        counts_with_null_for_skips.append(
            score_contract(gold_by_field, answers_with_null_for_skips)
        )

    counts_by_field = add_up_by_field(list(counts_by_contract.values()))
    report = score_report(counts_by_field)
    for field in ALL_FIELDS:
        assert report.scores_by_field[field.name] == PERFECT, field.name
    for field_type in FieldType:
        assert report.scores_by_field_type[field_type] == PERFECT, field_type
    assert report.micro == PERFECT
    assert report.macro == PERFECT
    # A wrong answer given for a skipped case changed no count.
    assert add_up_by_field(counts_with_null_for_skips) == counts_by_field

    # The support is what CUAD answered: contracts scored, and names for parties.
    expected_support = {
        "document_name": 510,
        "parties": 1269,
        "agreement_date": 417,
        "effective_date": 325,
        "expiration_date": 308,
        "renewal_term": 150,
        "notice_to_terminate_renewal": 100,
        "governing_law": 431,
    }
    for field_name, expected in expected_support.items():
        assert support(counts_by_field[field_name]) == expected, field_name
    clause_support = 0
    for field in CLAUSE_FIELDS:
        clause_support += support(counts_by_field[field.name])
    assert clause_support == 3688

    intervals = report_intervals(counts_by_contract, RESAMPLING_SEED, DRAWS)
    for field in ALL_FIELDS:
        f1 = intervals.by_field[field.name].f1
        assert f1 is not None
        assert (f1.low, f1.high) == (1.0, 1.0), field.name
    assert intervals.micro.f1 is not None
    assert (intervals.micro.f1.low, intervals.micro.f1.high) == (1.0, 1.0)


@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_every_value_cuad_accepts_is_right_on_its_own() -> None:
    """Where CUAD wrote several values, each one alone is a true positive."""
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))
    right = Counts(true_positives=1, false_positives=0, false_negatives=0)

    checked = 0
    for gold_by_field in gold_answers.values():
        for field in ALL_FIELDS:
            gold = gold_by_field[field.name]
            if not isinstance(gold, AcceptedValues):
                continue
            for value in gold.values:
                assert score_answer(field, gold, value) == right, (field.name, value)
                checked += 1
    # 3,688 clause answers, and 2,281 values of the seven fields other than parties.
    assert checked == 5969
