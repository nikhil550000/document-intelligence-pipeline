"""List prices of the models, and what a call costs at them."""

import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

PRICES_PATH = Path("configs") / "prices.toml"

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Prices:
    """US dollars per million tokens, as read on one day."""

    read_on: date
    input: Decimal
    cached_input: Decimal
    output: Decimal


def read_price_list(path: Path) -> dict[str, Prices]:
    """Returns the prices of every model in the price file, by model."""
    # Decimal and not float, so that a price of 0.30 stays exactly that.
    with path.open("rb") as file:
        prices_by_model = tomllib.load(file, parse_float=Decimal)
    price_list = {}
    for model, prices in prices_by_model.items():
        price_list[model] = Prices(
            read_on=prices["read_on"],
            input=prices["input"],
            cached_input=prices["cached_input"],
            output=prices["output"],
        )
    return price_list


def read_prices(path: Path, model: str) -> Prices:
    """Returns the prices of one model from the price file.

    Raises:
        KeyError: The file has no prices for the model.
    """
    return read_price_list(path)[model]


def call_cost(
    prices: Prices, input_tokens: int, cached_tokens: int, output_tokens: int
) -> Decimal:
    """Gives the cost of one call from the tokens the provider reported.

    `cached_tokens` are the part of `input_tokens` the provider read from its cache.
    """
    uncached_tokens = input_tokens - cached_tokens
    cost = (
        uncached_tokens * prices.input
        + cached_tokens * prices.cached_input
        + output_tokens * prices.output
    )
    return cost / MILLION
