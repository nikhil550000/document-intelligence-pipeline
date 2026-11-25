"""Tests for the price file and the cost of a call."""

from datetime import date
from decimal import Decimal

import pytest

from docintel.extraction.prices import PRICES_PATH, Prices, call_cost, read_prices

PRICES = Prices(
    read_on=date(2026, 11, 22),
    input=Decimal("0.30"),
    cached_input=Decimal("0.006"),
    output=Decimal("1.20"),
)


def test_the_committed_file_has_the_prices_of_the_model_in_use() -> None:
    """The file is read exactly, with the day the prices were read."""
    prices = read_prices(
        PRICES_PATH, "accounts/fireworks/models/deepseek-v4p1-flash-1017"
    )

    assert prices == PRICES


def test_a_model_without_prices_is_an_error() -> None:
    """A call is never costed at a price nobody read."""
    with pytest.raises(KeyError):
        read_prices(PRICES_PATH, "accounts/fireworks/models/unknown")


def test_cached_input_is_costed_at_its_own_price() -> None:
    """10,000 tokens in, 4,000 of them cached, and 2,000 out."""
    cost = call_cost(
        PRICES, input_tokens=10_000, cached_tokens=4_000, output_tokens=2_000
    )

    # 6,000 x 0.30 + 4,000 x 0.006 + 2,000 x 1.20, per million.
    assert cost == Decimal("0.004224")
