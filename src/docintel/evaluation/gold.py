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
    """The values that count as right. The model is right when it gives any one."""

    # Text is kept as CUAD wrote it, so an error report shows "Corio Inc." and
    # not the form used for comparing.
    values: tuple[date | Perpetual | Duration | str | bool, ...]

    def __post_init__(self) -> None:
        """Refuses an empty list, which would mark every model answer wrong."""
        # An answer with nothing usable left is a skip, so an empty list is a bug.
        if not self.values:
            raise ValueError("no accepted values: the answer should be a skip")


@dataclass(frozen=True)
class PartyNames:
    """The parties CUAD names. Each name is scored on its own."""

    # Kept as CUAD wrote them, for the same reason as accepted values.
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        """Refuses an empty list, for the same reason as accepted values."""
        # A parties answer with no name left is a skip.
        if not self.names:
            raise ValueError("no party names: the answer should be a skip")


@dataclass(frozen=True)
class NoAnswer:
    """CUAD labelled nothing, so an answer from the model is a false positive."""


@dataclass(frozen=True)
class Skipped:
    """The model's answer is not looked at, and the rule that says why is kept."""

    rule: SkipRule


type GoldAnswer = AcceptedValues | PartyNames | NoAnswer | Skipped
