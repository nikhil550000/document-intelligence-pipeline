"""Tests for the cost ceiling."""

import json
from datetime import date
from decimal import Decimal

import pytest

from docintel.extraction.budget import Budget, CeilingReachedError, cost_bound
from docintel.extraction.prices import Prices

PRICES = Prices(date(2026, 11, 22), Decimal("0.30"), Decimal("0.006"), Decimal("1.20"))


def test_the_bound_counts_a_token_for_every_byte_and_the_longest_answer() -> None:
    """A request of 1,000 bytes allowing 500 tokens out costs at most this."""
    request = {"max_tokens": 500, "padding": ""}
    request["padding"] = "x" * (1000 - len(json.dumps(request)))
    assert len(json.dumps(request)) == 1000

    # 1,000 x 0.30 + 500 x 1.20, per million.
    assert cost_bound(PRICES, request) == Decimal("0.0009")


def test_letters_outside_ascii_raise_the_bound_and_never_lower_it() -> None:
    """A word such as LECLANCHÉ takes more bytes than letters, so more tokens."""
    plain = {"max_tokens": 0, "text": "LECLANCHE"}
    accented = {"max_tokens": 0, "text": "LECLANCHÉ"}

    assert cost_bound(PRICES, accented) > cost_bound(PRICES, plain)


def test_spending_stops_at_the_ceiling() -> None:
    """The ceiling can be reached exactly, but never passed."""
    request = {"max_tokens": 1000}
    bound = cost_bound(PRICES, request)
    budget = Budget(bound * 2, PRICES)

    budget.reserve(request)
    budget.reserve(request)

    with pytest.raises(CeilingReachedError, match="left of its"):
        budget.reserve(request)
    assert budget.spent_usd == bound * 2


def test_settling_gives_back_what_was_held_beyond_the_real_cost() -> None:
    """After the call, only what it cost stays spent."""
    budget = Budget(Decimal(1), PRICES)
    reserved = budget.reserve({"max_tokens": 1000})

    budget.settle(reserved, Decimal("0.0001"))

    assert budget.spent_usd == Decimal("0.0001")
