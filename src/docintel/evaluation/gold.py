"""The form in which CUAD's answer for one field of one contract is scored."""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from docintel.domain.values import Duration, Perpetual


class SkipRule(Enum):
    """Why CUAD's answer for one field of one contract cannot be scored fairly."""

    REDACTED = "redacted"
    PASSAGE_ONLY = "passage only"
    PERPETUAL_RENEWAL = "perpetual renewal"
    DATE_IN_A_DURATION_FIELD = "date in a duration field"
    NO_NAMED_PLACE = "no named place"


@dataclass(frozen=True)
class AcceptedValues:
    """The values that count as right.

    For parties each value is one name, and each name is scored on its own. For
    every other field the model is right when it gives any one of the values.
    """

    # Text is kept as CUAD wrote it, so an error report shows "Corio Inc." and
    # not the form used for comparing.
    values: tuple[date | Perpetual | Duration | str | bool, ...]


@dataclass(frozen=True)
class NoAnswer:
    """CUAD labelled nothing, so an answer from the model is a false positive."""


@dataclass(frozen=True)
class Skipped:
    """The model's answer is not looked at, and the rule that says why is kept."""

    rule: SkipRule


type GoldAnswer = AcceptedValues | NoAnswer | Skipped
