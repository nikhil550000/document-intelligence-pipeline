"""Tests for giving Phoenix the price list."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from docintel import telemetry
from docintel.extraction.prices import Prices

PRICES = Prices(
    read_on=date(2026, 11, 22),
    input=Decimal("0.30"),
    cached_input=Decimal("0.006"),
    output=Decimal("1.20"),
)


class FakePhoenix:
    """Answers the model list in pages, and keeps every change it is asked for."""

    def __init__(self, pages: list[list[dict[str, str]]]) -> None:
        """Starts with these pages of models and no change asked for."""
        self.pages = pages
        self.changes: list[tuple[str, dict[str, Any]]] = []

    def ask(
        self, phoenix_url: str, api_key: str, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """Answers one query as Phoenix would."""
        if query == telemetry.MODELS_QUERY:
            page_number = int(variables["after"] or 0)
            edges = []
            for node in self.pages[page_number]:
                edges.append({"node": node})
            next_page = page_number + 1
            page_info = {
                "hasNextPage": next_page < len(self.pages),
                "endCursor": str(next_page),
            }
            return {"generativeModels": {"pageInfo": page_info, "edges": edges}}
        self.changes.append((query, variables["input"]))
        return {}


def test_a_model_without_our_price_is_added_with_the_three_token_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A built-in model of the same name does not count as ours."""
    phoenix = FakePhoenix([[{"id": "1", "name": "a/model", "kind": "BUILT_IN"}]])
    monkeypatch.setattr(telemetry, "ask_phoenix", phoenix.ask)

    done = telemetry.write_prices("http://phoenix", "key", {"a/model": PRICES})

    assert done == ["Added the prices of a/model, read on 2026-11-22."]
    ((query, fields),) = phoenix.changes
    assert query == telemetry.CREATE_MODEL
    assert fields == {
        "name": "a/model",
        "namePattern": "^a/model$",
        "costs": [
            {"tokenType": "input", "kind": "PROMPT", "costPerMillionTokens": 0.3},
            {
                "tokenType": "cache_read",
                "kind": "PROMPT",
                "costPerMillionTokens": 0.006,
            },
            {"tokenType": "output", "kind": "COMPLETION", "costPerMillionTokens": 1.2},
        ],
        "startTime": "2026-11-22T00:00:00Z",
        "modelType": "LLM",
    }


def test_a_model_with_our_price_on_a_later_page_is_updated_not_added_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every page of the model list is read before deciding."""
    phoenix = FakePhoenix(
        [
            [{"id": "1", "name": "other", "kind": "BUILT_IN"}],
            [{"id": "7", "name": "a.model", "kind": "CUSTOM"}],
        ]
    )
    monkeypatch.setattr(telemetry, "ask_phoenix", phoenix.ask)

    done = telemetry.write_prices("http://phoenix", "key", {"a.model": PRICES})

    assert done == ["Updated the prices of a.model, read on 2026-11-22."]
    ((query, fields),) = phoenix.changes
    assert query == telemetry.UPDATE_MODEL
    assert fields["id"] == "7"
    # A dot in a model's name matches only a dot.
    assert fields["namePattern"] == r"^a\.model$"
    assert "modelType" not in fields
