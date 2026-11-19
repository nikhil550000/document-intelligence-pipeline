"""Read CUAD's answers for the two duration fields, and compare durations."""

import re
from fractions import Fraction

from docintel.domain.values import Duration, DurationUnit
from docintel.evaluation.dates import DATE_PATTERN
from docintel.evaluation.gold import AcceptedValues, Skipped, SkipRule
from docintel.evaluation.pieces import cut_into_pieces

# Taken last in the piece, because a renewal count or "successive" may come first.
# The optional bracket covers `three (3) years` and the slip `60) days`.
DURATION_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\)?\s*(day|week|month|year)s?")

UNITS = {
    "day": DurationUnit.DAYS,
    "month": DurationUnit.MONTHS,
    "year": DurationUnit.YEARS,
}


def read_duration_answer(answer: str) -> AcceptedValues | Skipped:
    """Reads CUAD's answer for a duration field into the durations that count as right.

    A piece with a blank, a `perpetual` or a date in it is dropped. When every
    piece is dropped, the answer is skipped under the rule of the first one.

    Raises:
        ValueError: A piece is none of those and holds no duration.
    """
    values = []
    dropped_for = []
    for piece in cut_into_pieces(answer):
        rule = rule_that_drops(piece)
        if rule is None:
            values.append(read_duration_piece(piece))
        else:
            dropped_for.append(rule)

    if values:
        return AcceptedValues(tuple(values))
    return Skipped(dropped_for[0])


def rule_that_drops(piece: str) -> SkipRule | None:
    """Gives the rule that drops a piece, or None when the piece is a duration."""
    if "[" in piece:
        return SkipRule.REDACTED
    if piece == "perpetual":
        return SkipRule.PERPETUAL_RENEWAL
    if DATE_PATTERN.fullmatch(piece):
        return SkipRule.DATE_IN_A_DURATION_FIELD
    return None


def read_duration_piece(piece: str) -> Duration:
    """Reads the last number and unit of a piece, already in lower case."""
    matches = DURATION_PATTERN.findall(piece)
    if not matches:
        raise ValueError(f"not a duration: {piece!r}")
    amount_text, unit_word = matches[-1]

    # A fraction is exact, so 0.5 year is 6 months with no rounding.
    amount = Fraction(amount_text)
    if unit_word == "week":
        amount *= 7
        unit = DurationUnit.DAYS
    elif unit_word == "year" and amount.denominator != 1:
        amount *= 12
        unit = DurationUnit.MONTHS
    else:
        unit = UNITS[unit_word]

    if amount.denominator != 1:
        raise ValueError(f"not a whole number of {unit_word}s: {piece!r}")
    return Duration(int(amount), unit)


def same_duration(first: Duration, second: Duration) -> bool:
    """Tells whether two durations are equal. Days never equal months."""
    return in_months_or_days(first) == in_months_or_days(second)


def in_months_or_days(duration: Duration) -> Duration:
    """Gives years as months, and leaves months and days as they are."""
    if duration.unit == DurationUnit.YEARS:
        return Duration(duration.amount * 12, DurationUnit.MONTHS)
    return duration
