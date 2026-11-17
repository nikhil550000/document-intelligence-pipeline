"""The values in a contract record that Python has no ready type for."""

from dataclasses import dataclass
from enum import Enum


class DurationUnit(Enum):
    """The units a duration can be given in."""

    DAYS = "days"
    MONTHS = "months"
    YEARS = "years"


@dataclass(frozen=True)
class Duration:
    """A length of time, such as 30 days or 1 year."""

    amount: int
    unit: DurationUnit


class Perpetual(Enum):
    """Stands where an expiration date would stand when a contract has no end."""

    PERPETUAL = "perpetual"
