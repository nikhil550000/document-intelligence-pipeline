"""Tests for reading CUAD's date answers."""

from datetime import date

import pytest

from docintel.domain.values import Perpetual
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.dates import read_date_answer
from docintel.evaluation.gold import AcceptedValues, Skipped, SkipRule


def test_month_comes_first() -> None:
    """`5/8/14` is 8 May 2014, and a leading zero changes nothing."""
    assert read_date_answer("5/8/14", "agreement_date") == AcceptedValues(
        (date(2014, 5, 8),)
    )
    assert read_date_answer("09/01/2006", "effective_date") == AcceptedValues(
        (date(2006, 9, 1),)
    )


def test_two_digit_years_split_at_fifty() -> None:
    """90 is 1990 and 45 is 2045."""
    assert read_date_answer("12/1/90", "agreement_date") == AcceptedValues(
        (date(1990, 12, 1),)
    )
    assert read_date_answer("9/1/45", "expiration_date") == AcceptedValues(
        (date(2045, 9, 1),)
    )


def test_a_first_number_above_twelve_is_the_day() -> None:
    """CUAD wrote one expiration date day first."""
    assert read_date_answer("31/01/2025", "expiration_date") == AcceptedValues(
        (date(2025, 1, 31),)
    )


def test_perpetual_is_read_for_the_expiration_date_in_any_case() -> None:
    """Capitals do not matter."""
    assert read_date_answer("Perpetual", "expiration_date") == AcceptedValues(
        (Perpetual.PERPETUAL,)
    )


def test_perpetual_for_another_date_field_raises() -> None:
    """Only a contract's end can be perpetual."""
    with pytest.raises(ValueError):
        read_date_answer("perpetual", "agreement_date")


def test_an_answer_with_two_values_accepts_both() -> None:
    """The model is right on either, cut at the semicolon."""
    assert read_date_answer("09/05/2019; perpetual", "expiration_date") == (
        AcceptedValues((date(2019, 9, 5), Perpetual.PERPETUAL))
    )
    assert read_date_answer("09/01/2006; 8/31/2007", "effective_date") == (
        AcceptedValues((date(2006, 9, 1), date(2007, 8, 31)))
    )


def test_a_redacted_piece_is_dropped_and_the_rest_is_kept() -> None:
    """The readable date stays when the other piece has a blank."""
    assert read_date_answer("07/31/2000; 07/[]/2000", "agreement_date") == (
        AcceptedValues((date(2000, 7, 31),))
    )


@pytest.mark.parametrize("answer", ["[]/[]/2020", "04/30/[]"])
def test_a_partly_readable_date_is_skipped_as_a_whole(answer: str) -> None:
    """A year alone is not scored."""
    assert read_date_answer(answer, "effective_date") == Skipped(SkipRule.REDACTED)


def test_a_date_that_is_not_a_real_day_raises() -> None:
    """February has no 30th, so the answer is a mistake and must not pass quietly."""
    with pytest.raises(ValueError):
        read_date_answer("2/30/14", "agreement_date")


def test_a_piece_that_is_not_a_date_raises() -> None:
    """Nothing is dropped without a rule."""
    with pytest.raises(ValueError):
        read_date_answer("May 8, 2014", "agreement_date")


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_has_the_published_shapes() -> None:
    """Every answer of the three fields reads, with the shapes found by hand."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)

    # Field: (one date, perpetual only, two values, redacted only), counted on
    # what the reader returns. `07/31/2000; 07/[]/2000` has one readable date.
    expected = {
        "agreement_date": (417, 0, 0, 48),
        "effective_date": (324, 0, 1, 34),
        "expiration_date": (241, 66, 1, 21),
    }
    for field_name, expected_counts in expected.items():
        one_date = 0
        perpetual_only = 0
        two_values = 0
        redacted_only = 0
        for answers_by_field in answers.values():
            answer = answers_by_field[field_name].answer
            if answer in ("", "[]"):
                continue
            gold = read_date_answer(answer, field_name)
            if isinstance(gold, Skipped):
                redacted_only += 1
            elif len(gold.values) == 2:
                two_values += 1
            elif gold.values == (Perpetual.PERPETUAL,):
                perpetual_only += 1
            else:
                one_date += 1
        counts = (one_date, perpetual_only, two_values, redacted_only)
        assert counts == expected_counts, field_name
