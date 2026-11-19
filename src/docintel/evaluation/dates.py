"""Read CUAD's answers for the three date fields."""

import re
from datetime import date

from docintel.domain.values import Perpetual
from docintel.evaluation.gold import AcceptedValues, Skipped, SkipRule
from docintel.evaluation.pieces import cut_into_pieces

# CUAD's annotators wrote every date as month/day/year, whatever the contract prints.
DATE_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})")


def read_date_answer(answer: str, field_name: str) -> AcceptedValues | Skipped:
    """Reads CUAD's answer for a date field into the dates that count as right.

    A piece with a blank in it, such as `04/30/[]`, is dropped. When every piece
    is dropped, the answer is skipped.

    Raises:
        ValueError: A piece is not a real date, or is `perpetual` for a field
            other than the expiration date.
    """
    values: list[date | Perpetual] = []
    for piece in cut_into_pieces(answer):
        text = piece.replace(" ", "")
        if "[" in text:
            continue
        values.append(read_piece(text, field_name))

    if not values:
        return Skipped(SkipRule.REDACTED)
    return AcceptedValues(tuple(values))


def read_piece(text: str, field_name: str) -> date | Perpetual:
    """Reads one piece of an answer, already in lower case and without spaces."""
    if text == "perpetual":
        if field_name != "expiration_date":
            raise ValueError(
                f"perpetual is only read for the expiration date: {field_name}"
            )
        return Perpetual.PERPETUAL

    match = DATE_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"not a date: {text!r}")
    first, second, year_text = match.groups()
    month = int(first)
    day = int(second)
    # Only one answer is day first, 31/01/2025, and it is the only one that can be told.
    if month > 12:
        month, day = day, month

    year = int(year_text)
    if len(year_text) == 2:
        # Every two-digit year in the file is 90 to 99 or 00 to 45.
        year += 1900 if year >= 50 else 2000
    return date(year, month, day)
