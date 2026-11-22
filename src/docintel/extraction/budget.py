"""The cost ceiling of a run, checked before every paid attempt."""

import json
from decimal import Decimal
from typing import Any

from docintel.extraction.prices import MILLION, Prices


class CeilingReachedError(Exception):
    """The next attempt might cost more than the run has left, so it was not made."""


def cost_bound(prices: Prices, request: dict[str, Any]) -> Decimal:
    """Gives a cost the attempt cannot exceed, before it is sent.

    The input is counted as one token for every byte of the request: a token is
    never shorter than a byte, so the real count is lower. The output is the
    longest answer the request allows.
    """
    input_bound = len(json.dumps(request).encode())
    output_bound: int = request["max_tokens"]
    return (input_bound * prices.input + output_bound * prices.output) / MILLION


class Budget:
    """What a run may still spend. An attempt is paid for before it is made."""

    def __init__(self, ceiling_usd: Decimal, prices: Prices) -> None:
        """Starts with nothing spent."""
        self.ceiling_usd = ceiling_usd
        self.prices = prices
        self.spent_usd = Decimal(0)

    def reserve(self, request: dict[str, Any]) -> Decimal:
        """Counts the most the attempt can cost as spent, and returns that amount.

        Raises:
            CeilingReachedError: That amount is more than the run has left.
        """
        bound = cost_bound(self.prices, request)
        left = self.ceiling_usd - self.spent_usd
        if bound > left:
            raise CeilingReachedError(
                f"the next attempt could cost up to ${bound:.4f} and the run has "
                f"${left:.4f} left of its ${self.ceiling_usd} ceiling"
            )
        self.spent_usd += bound
        return bound

    def settle(self, reserved_usd: Decimal, cost_usd: Decimal) -> None:
        """Replaces a reserved amount with what the attempt really cost."""
        self.spent_usd += cost_usd - reserved_usd
