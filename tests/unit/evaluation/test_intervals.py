"""Tests for the 95% intervals on the scores."""

import pytest

from docintel.evaluation.intervals import (
    DRAWS,
    RESAMPLING_SEED,
    Interval,
    difference_intervals,
    draw_contracts,
    interval,
    report_intervals,
)
from docintel.evaluation.scoring import Counts

FOUND = Counts(true_positives=1, false_positives=0, false_negatives=0)
MISSED = Counts(true_positives=0, false_positives=0, false_negatives=1)
NOTHING = Counts(true_positives=0, false_positives=0, false_negatives=0)


def governing_law_answers(found: int, missed: int) -> dict[str, dict[str, Counts]]:
    """Made-up contracts whose governing law the model found or missed, found first."""
    counts_by_contract = {}
    for number in range(found + missed):
        counts = FOUND
        if number >= found:
            counts = MISSED
        counts_by_contract[f"contract_{number:03}.pdf"] = {"governing_law": counts}
    return counts_by_contract


def test_the_same_seed_gives_the_same_intervals() -> None:
    """A reported interval can be computed again and comes out the same."""
    answers = governing_law_answers(found=7, missed=3)

    first = report_intervals(answers, seed=RESAMPLING_SEED, draws=DRAWS)
    second = report_intervals(answers, seed=RESAMPLING_SEED, draws=DRAWS)

    assert first == second


def test_a_different_seed_gives_other_draws() -> None:
    """The seed is really used."""
    contracts = list(governing_law_answers(found=7, missed=3))
    assert draw_contracts(contracts, seed=1, draws=5) != draw_contracts(
        contracts, seed=2, draws=5
    )


def test_each_draw_takes_as_many_contracts_as_the_set_with_repeats() -> None:
    """A contract can be drawn twice and another not at all, so the counts vary."""
    contracts = list(governing_law_answers(found=7, missed=3))

    draws = draw_contracts(contracts, seed=RESAMPLING_SEED, draws=20)

    assert len(draws) == 20
    for drawn in draws:
        assert len(drawn) == 10
        assert set(drawn) <= set(contracts)
    assert any(len(set(drawn)) < 10 for drawn in draws)


def test_the_draws_do_not_depend_on_the_order_of_the_contracts() -> None:
    """The contracts are sorted before drawing, so a reordered set draws the same."""
    contracts = list(governing_law_answers(found=7, missed=3))
    reordered = list(reversed(contracts))

    assert draw_contracts(reordered, seed=5, draws=3) == draw_contracts(
        contracts, seed=5, draws=3
    )


def test_a_field_right_on_every_contract_has_the_interval_100_to_100() -> None:
    """Every draw holds only right answers, so every draw scores 100%."""
    intervals = report_intervals(
        governing_law_answers(found=20, missed=0), seed=RESAMPLING_SEED, draws=DRAWS
    )

    governing_law = intervals.by_field["governing_law"]
    assert governing_law.precision == Interval(low=1.0, high=1.0, draws=DRAWS)
    assert governing_law.recall == Interval(low=1.0, high=1.0, draws=DRAWS)
    assert governing_law.f1 == Interval(low=1.0, high=1.0, draws=DRAWS)


def test_the_interval_is_narrower_with_100_contracts_than_with_10() -> None:
    """The same share of right answers is less certain on fewer contracts."""
    few = report_intervals(
        governing_law_answers(found=7, missed=3), seed=RESAMPLING_SEED, draws=DRAWS
    )
    many = report_intervals(
        governing_law_answers(found=70, missed=30), seed=RESAMPLING_SEED, draws=DRAWS
    )

    few_recall = few.by_field["governing_law"].recall
    many_recall = many.by_field["governing_law"].recall
    assert few_recall is not None
    assert many_recall is not None
    assert few_recall.low < 0.7 < few_recall.high
    assert many_recall.low < 0.7 < many_recall.high
    assert many_recall.high - many_recall.low < few_recall.high - few_recall.low


def test_draws_without_anything_to_divide_by_are_left_out_and_counted() -> None:
    """One contract of 10 has the clause; a draw that misses it has no recall."""
    answers = {}
    for number in range(10):
        answers[f"contract_{number:03}.pdf"] = {"source_code_escrow": NOTHING}
    answers["contract_000.pdf"] = {"source_code_escrow": FOUND}

    intervals = report_intervals(answers, seed=RESAMPLING_SEED, draws=DRAWS)

    recall = intervals.by_field["source_code_escrow"].recall
    assert recall is not None
    assert recall.low == 1.0
    assert recall.high == 1.0
    # About 0.9 to the power of 10, a third of the draws, miss the one contract.
    assert 550 < recall.draws < 750


def test_a_field_no_draw_can_score_has_no_interval() -> None:
    """With nothing to find and nothing given, there is no score to give a range to."""
    intervals = report_intervals(
        governing_law_answers(found=5, missed=0), seed=RESAMPLING_SEED, draws=50
    )
    assert intervals.by_field["non_compete"].recall is None


def test_two_identical_sets_of_answers_differ_by_0_to_0() -> None:
    """Both are scored on the same draws, so every draw gives the same two scores."""
    answers = governing_law_answers(found=7, missed=3)

    difference = difference_intervals(
        answers, answers, seed=RESAMPLING_SEED, draws=DRAWS
    )

    assert difference.micro.f1 == Interval(low=0.0, high=0.0, draws=DRAWS)
    assert difference.by_field["governing_law"].recall == Interval(
        low=0.0, high=0.0, draws=DRAWS
    )


def test_a_clearly_better_set_of_answers_has_a_difference_above_zero() -> None:
    """Right on 90 of 100 against 50 of 100: the whole interval is above zero."""
    better = governing_law_answers(found=90, missed=10)
    worse = governing_law_answers(found=50, missed=50)

    difference = difference_intervals(better, worse, seed=RESAMPLING_SEED, draws=DRAWS)

    assert difference.micro.f1 is not None
    assert difference.micro.f1.low > 0
    reversed_difference = difference_intervals(
        worse, better, seed=RESAMPLING_SEED, draws=DRAWS
    )
    assert reversed_difference.micro.f1 is not None
    assert reversed_difference.micro.f1.high < 0


def test_a_score_either_set_lacks_has_no_difference() -> None:
    """A set that never answered has no precision, so there is no precision gap."""
    answered = governing_law_answers(found=10, missed=0)
    silent = {}
    for contract in answered:
        silent[contract] = {"governing_law": MISSED}

    difference = difference_intervals(answered, silent, seed=RESAMPLING_SEED, draws=50)

    governing_law = difference.by_field["governing_law"]
    assert governing_law.precision is None
    assert governing_law.recall == Interval(low=1.0, high=1.0, draws=50)


def test_two_sets_of_answers_for_different_contracts_cannot_be_compared() -> None:
    """A difference on other contracts would measure the contracts, not the answers."""
    with pytest.raises(ValueError):
        difference_intervals(
            governing_law_answers(found=5, missed=5),
            governing_law_answers(found=5, missed=6),
            seed=RESAMPLING_SEED,
            draws=10,
        )


def test_the_interval_leaves_out_the_lowest_and_highest_2_5_percent() -> None:
    """Of 1,000 results, the 25 lowest and the 25 highest are outside the range."""
    results: list[float | None] = []
    for number in range(1000):
        results.append(float(number))

    assert interval(results) == Interval(low=25.0, high=974.0, draws=1000)


def test_results_without_a_score_are_left_out_before_the_cut() -> None:
    """Draws without a score do not count as 0; the range is over the others."""
    results: list[float | None] = [None, 0.5, None, 0.25, 1.0]

    assert interval(results) == Interval(low=0.25, high=1.0, draws=3)
    assert interval([None, None]) is None
