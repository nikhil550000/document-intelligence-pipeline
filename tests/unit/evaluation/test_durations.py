"""Tests for reading CUAD's duration answers and comparing durations."""

import pytest

from docintel.domain.values import Duration, DurationUnit
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.durations import read_duration_answer, same_duration
from docintel.evaluation.gold import AcceptedValues, Skipped, SkipRule


def accepted(*durations: Duration) -> AcceptedValues:
    """Builds what the reader returns for the given durations."""
    return AcceptedValues(durations)


YEAR = DurationUnit.YEARS
MONTH = DurationUnit.MONTHS
DAY = DurationUnit.DAYS


@pytest.mark.parametrize(
    ("answer", "duration"),
    [
        ("successive 1 year", Duration(1, YEAR)),
        ("2 5 years", Duration(5, YEAR)),
        ("10 successive 1 year", Duration(1, YEAR)),
        ("four successive 10 years", Duration(10, YEAR)),
        ("three (3) years", Duration(3, YEAR)),
        ("(6) months", Duration(6, MONTH)),
        ("60) days", Duration(60, DAY)),
        ("5 year", Duration(5, YEAR)),
        ("12 Months", Duration(12, MONTH)),
    ],
)
def test_the_last_number_and_unit_is_the_duration(
    answer: str, duration: Duration
) -> None:
    """A renewal count or "successive" in front is ignored, and so are brackets."""
    assert read_duration_answer(answer) == accepted(duration)


def test_a_decimal_year_is_held_as_exact_months() -> None:
    """0.5 year is 6 months, with no rounding."""
    assert read_duration_answer("0.5 year") == accepted(Duration(6, MONTH))


def test_weeks_are_held_as_days() -> None:
    """Our record has no weeks, so 6 weeks is 42 days."""
    assert read_duration_answer("6 weeks") == accepted(Duration(42, DAY))


@pytest.mark.parametrize(
    "word",
    ["successive", "Successive", "succesive", "successine", "succsive", "sucessive"],
)
def test_the_six_spellings_of_successive_are_ignored(word: str) -> None:
    """The annotators spelled it six ways."""
    assert read_duration_answer(f"{word} 1 year") == accepted(Duration(1, YEAR))


@pytest.mark.parametrize(
    ("answer", "durations"),
    [
        ("5 years; 2 years", (Duration(5, YEAR), Duration(2, YEAR))),
        ("4 years, 6 months", (Duration(4, YEAR), Duration(6, MONTH))),
        ("180 days / 6 months", (Duration(180, DAY), Duration(6, MONTH))),
    ],
)
def test_an_answer_with_two_values_accepts_both(
    answer: str, durations: tuple[Duration, ...]
) -> None:
    """The model is right on either."""
    assert read_duration_answer(answer) == AcceptedValues(durations)


def test_a_separator_at_the_end_is_ignored() -> None:
    """CUAD has `successive 12 months; successive 6 months;`."""
    assert read_duration_answer("successive 12 months; successive 6 months;") == (
        accepted(Duration(12, MONTH), Duration(6, MONTH))
    )


@pytest.mark.parametrize("answer", ["successive [] years", "successive []"])
def test_a_redacted_answer_is_skipped(answer: str) -> None:
    """A blank where the number or the unit should be."""
    assert read_duration_answer(answer) == Skipped(SkipRule.REDACTED)


@pytest.mark.parametrize("answer", ["perpetual", "Perpetual"])
def test_a_perpetual_renewal_is_skipped(answer: str) -> None:
    """The record cannot say that a term renews for ever."""
    assert read_duration_answer(answer) == Skipped(SkipRule.PERPETUAL_RENEWAL)


def test_dates_only_are_skipped_as_dates() -> None:
    """A date is not a duration."""
    assert read_duration_answer("7/22/2019; 7/22/2022") == Skipped(
        SkipRule.DATE_IN_A_DURATION_FIELD
    )


def test_the_first_dropped_piece_names_the_skip() -> None:
    """`perpetual, 11/15/2014` is counted as a perpetual renewal."""
    assert read_duration_answer("perpetual, 11/15/2014") == Skipped(
        SkipRule.PERPETUAL_RENEWAL
    )
    assert read_duration_answer("11/15/2014, perpetual") == Skipped(
        SkipRule.DATE_IN_A_DURATION_FIELD
    )


def test_a_duration_stays_when_another_piece_is_dropped() -> None:
    """Only the pieces with no use are dropped."""
    assert read_duration_answer("5 years; []") == accepted(Duration(5, YEAR))


@pytest.mark.parametrize("answer", ["soon", "0.5 month", "5 fortnights"])
def test_a_piece_that_is_no_duration_raises(answer: str) -> None:
    """Nothing is dropped without a rule, and a half month is not a whole number."""
    with pytest.raises(ValueError):
        read_duration_answer(answer)


def test_twelve_months_equals_one_year() -> None:
    """Years and months are compared as months."""
    assert same_duration(Duration(12, MONTH), Duration(1, YEAR))


def test_thirty_days_does_not_equal_one_month() -> None:
    """Days never equal months."""
    assert not same_duration(Duration(30, DAY), Duration(1, MONTH))


def test_different_amounts_are_different() -> None:
    """The same unit with another number is a different duration."""
    assert not same_duration(Duration(5, YEAR), Duration(2, YEAR))


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_has_the_published_shapes() -> None:
    """Every answer of the two fields reads, with the shapes found by hand."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)

    # Field: (one duration, two durations, perpetual, dates only, redacted only),
    # counted on what the reader returns.
    expected = {
        "renewal_term": (147, 3, 10, 1, 2),
        "notice_to_terminate_renewal": (97, 3, 0, 0, 0),
    }
    for field_name, expected_counts in expected.items():
        counts = {
            "one": 0,
            "two": 0,
            SkipRule.PERPETUAL_RENEWAL: 0,
            SkipRule.DATE_IN_A_DURATION_FIELD: 0,
            SkipRule.REDACTED: 0,
        }
        for answers_by_field in answers.values():
            answer = answers_by_field[field_name].answer
            if answer in ("", "[]"):
                continue
            gold = read_duration_answer(answer)
            if isinstance(gold, Skipped):
                counts[gold.rule] += 1
            elif len(gold.values) == 2:
                counts["two"] += 1
            else:
                counts["one"] += 1
        assert tuple(counts.values()) == expected_counts, field_name
