"""A problem that validation found in a model's output."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    """One problem, kept with the record so that a reviewer can see it.

    `field` is None when the problem belongs to the output as a whole, such as
    output that is not JSON.
    """

    layer: str
    rule: str
    field: str | None
    message: str
