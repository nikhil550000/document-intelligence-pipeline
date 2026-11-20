"""95% intervals on the scores, found by drawing the contracts again at random."""

import random
from dataclasses import dataclass

from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.evaluation.metrics import Report, Scores, add_up_by_field, score_report
from docintel.evaluation.scoring import Counts

# Fixed before any score was computed, so that it cannot be picked after seeing one.
RESAMPLING_SEED = 2026
DRAWS = 1000


@dataclass(frozen=True)
class Interval:
    """The range that holds 95% of a score's results over the draws.

    `draws` is the number of draws in which the score had something to divide
    by. The range is taken over those draws only.
    """

    low: float
    high: float
    draws: int


@dataclass(frozen=True)
class ScoreIntervals:
    """An interval for each score, or None where no draw had the score."""

    precision: Interval | None
    recall: Interval | None
    f1: Interval | None


@dataclass(frozen=True)
class IntervalReport:
    """The interval of every score, per field, per field type and overall."""

    by_field: dict[str, ScoreIntervals]
    by_field_type: dict[FieldType, ScoreIntervals]
    micro: ScoreIntervals
    macro: ScoreIntervals


def report_intervals(
    counts_by_contract: dict[str, dict[str, Counts]], seed: int, draws: int
) -> IntervalReport:
    """Finds a 95% interval for every score of one set of answers.

    Whole contracts are drawn, so the names of one contract's parties, which are
    not independent of each other, are always drawn together.

    Args:
        counts_by_contract: For each contract file name, the counts of each of
            its fields that is not skipped.
        seed: Seed for the draws.
        draws: How many times the contracts are drawn again.
    """
    reports = []
    for contracts in draw_contracts(list(counts_by_contract), seed, draws):
        reports.append(score_drawn_contracts(counts_by_contract, contracts))
    return intervals_of_reports(reports)


def difference_intervals(
    first: dict[str, dict[str, Counts]],
    second: dict[str, dict[str, Counts]],
    seed: int,
    draws: int,
) -> IntervalReport:
    """Finds a 95% interval for each score of the first set minus the second.

    Both sets are scored on the same draws, so the difference comes from the
    answers and not from which contracts were drawn. A draw in which either set
    has no value for a score is left out of that score's difference.

    Raises:
        ValueError: The two sets of answers are not for the same contracts.
    """
    if sorted(first) != sorted(second):
        raise ValueError("the two sets of answers are not for the same contracts")

    differences = []
    for contracts in draw_contracts(list(first), seed, draws):
        first_report = score_drawn_contracts(first, contracts)
        second_report = score_drawn_contracts(second, contracts)
        differences.append(subtract_reports(first_report, second_report))
    return intervals_of_reports(differences)


def draw_contracts(contracts: list[str], seed: int, draws: int) -> list[list[str]]:
    """Draws as many contracts as there are, at random with repeats, many times."""
    # Sorted first, so the draws do not depend on the order the contracts came in.
    in_order = sorted(contracts)
    generator = random.Random(seed)
    drawn = []
    for _ in range(draws):
        drawn.append(generator.choices(in_order, k=len(in_order)))
    return drawn


def score_drawn_contracts(
    counts_by_contract: dict[str, dict[str, Counts]], contracts: list[str]
) -> Report:
    """Scores one draw. A contract drawn twice counts twice."""
    drawn_counts = []
    for contract in contracts:
        drawn_counts.append(counts_by_contract[contract])
    return score_report(add_up_by_field(drawn_counts))


def subtract_reports(first: Report, second: Report) -> Report:
    """Gives every score of the first report minus the same score of the second."""
    scores_by_field = {}
    for field_name, scores in first.scores_by_field.items():
        scores_by_field[field_name] = subtract_scores(
            scores, second.scores_by_field[field_name]
        )
    scores_by_field_type = {}
    for field_type, scores in first.scores_by_field_type.items():
        scores_by_field_type[field_type] = subtract_scores(
            scores, second.scores_by_field_type[field_type]
        )
    micro = subtract_scores(first.micro, second.micro)
    macro = subtract_scores(first.macro, second.macro)
    return Report(scores_by_field, scores_by_field_type, micro, macro)


def subtract_scores(first: Scores, second: Scores) -> Scores:
    """Gives each score of the first minus the second, None where either is None."""
    return Scores(
        precision=subtract(first.precision, second.precision),
        recall=subtract(first.recall, second.recall),
        f1=subtract(first.f1, second.f1),
    )


def subtract(first: float | None, second: float | None) -> float | None:
    """Gives the first minus the second, or None when either has no value."""
    if first is None or second is None:
        return None
    return first - second


def intervals_of_reports(reports: list[Report]) -> IntervalReport:
    """Finds the interval of every score over the reports of all draws."""
    by_field = {}
    for field in ALL_FIELDS:
        scores_of_field = []
        for report in reports:
            scores_of_field.append(report.scores_by_field[field.name])
        by_field[field.name] = intervals_of_scores(scores_of_field)

    by_field_type = {}
    for field_type in FieldType:
        scores_of_type = []
        for report in reports:
            scores_of_type.append(report.scores_by_field_type[field_type])
        by_field_type[field_type] = intervals_of_scores(scores_of_type)

    micro_scores = []
    macro_scores = []
    for report in reports:
        micro_scores.append(report.micro)
        macro_scores.append(report.macro)
    return IntervalReport(
        by_field,
        by_field_type,
        intervals_of_scores(micro_scores),
        intervals_of_scores(macro_scores),
    )


def intervals_of_scores(scores_list: list[Scores]) -> ScoreIntervals:
    """Finds the interval of precision, of recall and of F1 over the draws."""
    precisions = []
    recalls = []
    f1s = []
    for scores in scores_list:
        precisions.append(scores.precision)
        recalls.append(scores.recall)
        f1s.append(scores.f1)
    return ScoreIntervals(interval(precisions), interval(recalls), interval(f1s))


def interval(results: list[float | None]) -> Interval | None:
    """Gives the range that holds 95% of the results.

    A draw without the score, None, is left out: counted as 0, it would pull
    the range down for no reason the answers gave.
    """
    defined = []
    for result in results:
        if result is not None:
            defined.append(result)
    if not defined:
        return None

    defined.sort()
    # 2.5%, one result in 40, is left out at each end, so 95% are inside.
    left_out = len(defined) // 40
    return Interval(
        low=defined[left_out],
        high=defined[len(defined) - 1 - left_out],
        draws=len(defined),
    )
