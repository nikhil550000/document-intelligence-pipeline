"""Tests for precision, recall and F1 per field, per field type and overall."""

import pytest

from docintel.domain.fields import FieldType
from docintel.evaluation.metrics import (
    Scores,
    is_low_support,
    score_report,
    scores_from_counts,
    support,
)
from docintel.evaluation.scoring import Counts


def counts(true_positives: int, false_positives: int, false_negatives: int) -> Counts:
    """Counts in the order: true positives, false positives, false negatives."""
    return Counts(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def test_scores_of_each_field_match_the_counts_worked_out_by_hand() -> None:
    """Two contracts; each field adds up its counts over both, then divides."""
    report = score_report(
        [
            {
                "governing_law": counts(1, 0, 0),
                "agreement_date": counts(0, 1, 1),
                "parties": counts(2, 0, 1),
            },
            {
                "governing_law": counts(0, 0, 1),
                "agreement_date": counts(1, 0, 0),
                "parties": counts(1, 1, 0),
            },
        ]
    )

    # Governing law: 1 right of 1 given, 1 found of 2; F1 is 2 x 1 / (2 + 0 + 1).
    assert report.counts_by_field["governing_law"] == counts(1, 0, 1)
    governing_law = report.scores_by_field["governing_law"]
    assert governing_law.precision == 1.0
    assert governing_law.recall == 0.5
    assert governing_law.f1 == pytest.approx(2 / 3)
    assert report.scores_by_field["agreement_date"] == Scores(0.5, 0.5, 0.5)
    # Parties: 3 of 4 names given are right, and 3 of 4 names are found.
    assert report.scores_by_field["parties"] == Scores(0.75, 0.75, 0.75)


def test_a_field_type_adds_up_the_counts_of_its_fields() -> None:
    """The three date fields count as one, before dividing."""
    report = score_report(
        [
            {"agreement_date": counts(1, 1, 1), "expiration_date": counts(1, 0, 0)},
            {"effective_date": counts(0, 0, 1), "governing_law": counts(5, 0, 0)},
        ]
    )

    dates = report.scores_by_field_type[FieldType.DATE]
    assert dates.precision == pytest.approx(2 / 3)
    assert dates.recall == 0.5
    assert report.scores_by_field_type[FieldType.JURISDICTION] == Scores(1.0, 1.0, 1.0)
    assert report.scores_by_field_type[FieldType.CLAUSE] == Scores(None, None, None)


def test_micro_and_macro_averages_differ_on_the_same_counts() -> None:
    """A common field weighs more in the micro-average; in the macro each weighs one."""
    common = [{"governing_law": counts(1, 0, 0)}] * 90
    common_missed = [{"governing_law": counts(0, 0, 1)}] * 10
    rare = [{"source_code_escrow": counts(1, 0, 0)}]
    rare_missed = [{"source_code_escrow": counts(0, 0, 1)}] * 9

    report = score_report(common + common_missed + rare + rare_missed)

    # Micro: 91 found of 110. Macro: the mean of 0.9 and 0.1.
    assert report.micro.recall == pytest.approx(91 / 110)
    assert report.macro.recall == pytest.approx(0.5)
    assert report.micro.precision == 1.0
    assert report.macro.precision == 1.0


@pytest.mark.parametrize(
    ("field_counts", "expected"),
    [(counts(3, 7, 2), 5), (counts(0, 4, 0), 0), (counts(0, 0, 6), 6)],
)
def test_support_is_the_number_of_cuad_answers(
    field_counts: Counts, expected: int
) -> None:
    """Each CUAD answer is found or missed; a wrong extra answer is neither."""
    assert support(field_counts) == expected


@pytest.mark.parametrize(
    ("field_counts", "expected"),
    [
        (counts(9, 0, 0), True),
        (counts(5, 8, 4), True),
        (counts(10, 0, 0), False),
        (counts(6, 0, 4), False),
    ],
)
def test_a_field_is_marked_low_support_under_10(
    field_counts: Counts, expected: bool
) -> None:
    """With 9 answers, one contract moves recall by more than 10 points."""
    assert is_low_support(field_counts) == expected


def test_a_field_the_model_never_answered_has_no_precision() -> None:
    """Nothing was given, so there is nothing to be right or wrong about."""
    assert scores_from_counts(counts(0, 0, 3)) == Scores(None, 0.0, 0.0)


def test_a_field_without_precision_still_enters_the_macro_recall_and_f1() -> None:
    """Silence on a field costs its recall and F1, and is left out of mean precision."""
    report = score_report(
        [{"governing_law": counts(2, 0, 0), "renewal_term": counts(0, 0, 3)}]
    )

    assert report.macro == Scores(precision=1.0, recall=0.5, f1=0.5)


def test_answers_where_cuad_has_nothing_give_a_precision_and_no_recall() -> None:
    """Two wrong answers and nothing to find: precision 0, and F1 0, not undefined."""
    assert scores_from_counts(counts(0, 2, 0)) == Scores(0.0, None, 0.0)


def test_a_field_with_nothing_to_score_is_left_out_of_every_mean() -> None:
    """No CUAD answer and no model answer: there is no score, not a score of 0."""
    report = score_report([{"governing_law": counts(1, 1, 0)}])

    assert report.scores_by_field["non_compete"] == Scores(None, None, None)
    assert report.macro == report.scores_by_field["governing_law"]
    assert report.macro == Scores(0.5, 1.0, pytest.approx(2 / 3))
