"""Precision, recall and F1 per field, per field type and over all fields."""

from dataclasses import dataclass
from statistics import mean

from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.evaluation.scoring import Counts

# With fewer answers than this, one contract moves a field's recall by over 10 points.
LOW_SUPPORT_LIMIT = 10


@dataclass(frozen=True)
class Scores:
    """Precision, recall and F1. Each is None when there is nothing to divide by."""

    precision: float | None
    recall: float | None
    f1: float | None


@dataclass(frozen=True)
class Report:
    """The scores of one set of answers, per field, per field type and overall.

    `micro` adds up the counts of all fields before dividing, so common fields
    weigh more. `macro` is the plain mean of the fields' scores.
    """

    scores_by_field: dict[str, Scores]
    scores_by_field_type: dict[FieldType, Scores]
    micro: Scores
    macro: Scores


def add_up_by_field(counts_by_contract: list[dict[str, Counts]]) -> dict[str, Counts]:
    """Adds up the counts of each field over the contracts of a set.

    Args:
        counts_by_contract: For each contract of the set, the counts of each of
            its fields that is not skipped.

    Returns:
        The counts of every field. A field skipped in every contract has none.
    """
    counts_by_field = {}
    for field in ALL_FIELDS:
        counts_of_field = []
        for contract_counts in counts_by_contract:
            if field.name in contract_counts:
                counts_of_field.append(contract_counts[field.name])
        counts_by_field[field.name] = add_counts(counts_of_field)
    return counts_by_field


def score_report(counts_by_field: dict[str, Counts]) -> Report:
    """Computes the scores of one set of answers from the counts of every field."""
    scores_by_field = {}
    for field_name, field_counts in counts_by_field.items():
        scores_by_field[field_name] = scores_from_counts(field_counts)

    scores_by_field_type = {}
    for field_type in FieldType:
        counts_of_type = []
        for field in ALL_FIELDS:
            if field.type == field_type:
                counts_of_type.append(counts_by_field[field.name])
        type_counts = add_counts(counts_of_type)
        scores_by_field_type[field_type] = scores_from_counts(type_counts)

    micro = scores_from_counts(add_counts(list(counts_by_field.values())))
    macro = mean_scores(list(scores_by_field.values()))
    return Report(scores_by_field, scores_by_field_type, micro, macro)


def add_counts(counts_list: list[Counts]) -> Counts:
    """Adds up counts."""
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    for counts in counts_list:
        true_positives += counts.true_positives
        false_positives += counts.false_positives
        false_negatives += counts.false_negatives
    return Counts(true_positives, false_positives, false_negatives)


def support(counts: Counts) -> int:
    """Gives the number of CUAD answers: contracts with an answer, or party names."""
    # Each CUAD answer is either found or missed.
    return counts.true_positives + counts.false_negatives


def is_low_support(counts: Counts) -> bool:
    """Tells whether a field's score rests on too few CUAD answers to be read alone."""
    return support(counts) < LOW_SUPPORT_LIMIT


def scores_from_counts(counts: Counts) -> Scores:
    """Computes precision, recall and F1 from counts."""
    true_positives = counts.true_positives
    answers_given = true_positives + counts.false_positives

    # No answer given: the score says nothing, so it is not 0, which would mean
    # every answer was wrong.
    precision = None
    if answers_given > 0:
        precision = true_positives / answers_given

    recall = None
    if support(counts) > 0:
        recall = true_positives / support(counts)

    # The same number as 2PR / (P + R), and still defined when only one of the two
    # is: a field with answers to find and none given has F1 0.
    f1 = None
    every_count = 2 * true_positives + counts.false_positives + counts.false_negatives
    if every_count > 0:
        f1 = 2 * true_positives / every_count
    return Scores(precision, recall, f1)


def mean_scores(scores_list: list[Scores]) -> Scores:
    """Takes the plain mean of each score, over the fields where it is defined."""
    precisions = []
    recalls = []
    f1s = []
    for scores in scores_list:
        precisions.append(scores.precision)
        recalls.append(scores.recall)
        f1s.append(scores.f1)
    return Scores(
        mean_of_defined(precisions), mean_of_defined(recalls), mean_of_defined(f1s)
    )


def mean_of_defined(values: list[float | None]) -> float | None:
    """Takes the mean of the values that are not None, or gives None if all are."""
    defined = []
    for value in values:
        if value is not None:
            defined.append(value)
    if not defined:
        return None
    return mean(defined)
