"""Tests for the model client, against a fake provider on this machine."""

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import httpx2
import openai
import pytest

from docintel.domain.record import ContractRecord
from docintel.extraction.budget import Budget, CeilingReachedError, cost_bound
from docintel.extraction.client import (
    Completion,
    ModelCallError,
    ModelClient,
    RetrySettings,
    read_completion,
)
from docintel.extraction.prices import Prices, call_cost
from docintel.extraction.request import ModelSettings, build_request

RETRY = RetrySettings(timeout_seconds=300, max_attempts=4, first_wait_seconds=10)
SETTINGS = ModelSettings(model="fake-model", max_tokens=1000, reasoning_effort="none")
PRICES = Prices(date(2026, 11, 22), Decimal("0.30"), Decimal("0.006"), Decimal("1.20"))
REQUEST = build_request(SETTINGS, 1, ("A contract.",))
ANSWER = json.dumps(
    {
        "id": "1",
        "object": "chat.completion",
        "created": 1,
        "model": "fake-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "{}"},
            }
        ],
        "usage": {
            "prompt_tokens": 5000,
            "completion_tokens": 700,
            "total_tokens": 5700,
            "prompt_tokens_details": {"cached_tokens": 2000},
        },
    }
).encode()

type Handler = Callable[[httpx2.Request], httpx2.Response]


def fake_client(handler: Handler, waits: list[float]) -> ModelClient:
    """A client whose requests go to `handler`, and whose waits are only noted."""
    sdk = openai.OpenAI(
        base_url="https://provider.test/v1",
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return ModelClient(sdk, RETRY, sleep=waits.append)


def answers_in_turn(*steps: str) -> Handler:
    """A provider that fails or answers in the order given, then answers."""
    remaining = list(steps)

    def handler(request: httpx2.Request) -> httpx2.Response:
        step = "answer"
        if remaining:
            step = remaining.pop(0)
        if step == "time out":
            raise httpx2.ReadTimeout("no answer in time", request=request)
        if step == "answer":
            return httpx2.Response(200, content=ANSWER)
        return httpx2.Response(int(step), json={"error": {"message": "failed"}})

    return handler


def plenty() -> Budget:
    """A budget no test here comes near."""
    return Budget(Decimal(100), PRICES)


def test_an_answer_is_returned_as_the_provider_sent_it() -> None:
    """The bytes are kept as they came, so a cached answer is the same answer."""
    waits: list[float] = []
    client = fake_client(answers_in_turn(), waits)

    assert client.complete(REQUEST, plenty()) == ANSWER
    assert client.calls == 1
    assert waits == []


def test_the_answer_and_its_tokens_are_read_from_the_response() -> None:
    """Cached input is told apart, because it has its own price."""
    assert read_completion(ANSWER) == Completion(
        content="{}",
        cut_off=False,
        input_tokens=5000,
        cached_input_tokens=2000,
        output_tokens=700,
    )


@pytest.mark.parametrize("failure", ["time out", "429", "500", "503"])
def test_a_passing_failure_is_tried_again_after_a_wait(failure: str) -> None:
    """Time-outs, rate limits and server errors are tried again."""
    waits: list[float] = []
    client = fake_client(answers_in_turn(failure, failure), waits)

    assert client.complete(REQUEST, plenty()) == ANSWER
    assert client.calls == 3
    assert waits == [10, 20]


def test_a_call_that_keeps_failing_gives_up_after_the_last_attempt() -> None:
    """The wait doubles each time, and the reason names the last failure."""
    waits: list[float] = []
    client = fake_client(answers_in_turn("429", "time out", "500", "503"), waits)

    with pytest.raises(ModelCallError, match="error 503 on the last of 4 attempts"):
        client.complete(REQUEST, plenty())
    assert client.calls == 4
    assert waits == [10, 20, 40]


@pytest.mark.parametrize("status", ["400", "401", "404", "422"])
def test_a_refused_request_is_not_sent_again(status: str) -> None:
    """A request the provider refuses would be refused again the same way."""
    waits: list[float] = []
    client = fake_client(answers_in_turn(status), waits)
    budget = plenty()

    with pytest.raises(ModelCallError, match=f"refused: Error code: {status}"):
        client.complete(REQUEST, budget)
    assert client.calls == 1
    assert waits == []
    assert budget.spent_usd == 0


def test_the_request_carries_the_record_schema_and_a_time_limit() -> None:
    """What reaches the provider is the schema made from the record type."""
    sent: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, content=ANSWER)

    request = build_request(SETTINGS, 1, ("Page one", "Two"))
    fake_client(handler, []).complete(request, plenty())

    body = json.loads(sent[0].content)
    assert body["response_format"]["json_schema"]["schema"] == (
        ContractRecord.model_json_schema()
    )
    assert body["messages"][1] == {"role": "user", "content": "Page one\n\nTwo"}
    assert body["temperature"] == 0
    assert body["reasoning_effort"] == "none"
    assert sent[0].extensions["timeout"]["read"] == 300


def test_an_answer_is_charged_what_it_cost() -> None:
    """The amount held back before the call is replaced by the real cost."""
    budget = plenty()

    fake_client(answers_in_turn(), []).complete(REQUEST, budget)

    assert budget.spent_usd == call_cost(PRICES, 5000, 2000, 700)


def test_no_call_is_made_when_the_budget_cannot_cover_one() -> None:
    """A ceiling below the cost of one attempt stops the run before any call."""
    client = fake_client(answers_in_turn(), [])
    budget = Budget(cost_bound(PRICES, REQUEST) / 2, PRICES)

    with pytest.raises(CeilingReachedError):
        client.complete(REQUEST, budget)
    assert client.calls == 0
    assert budget.spent_usd == 0


def test_a_retry_the_budget_cannot_cover_is_not_made() -> None:
    """A time-out may have been billed, so its whole bound stays spent."""
    client = fake_client(answers_in_turn("time out"), [])
    budget = Budget(cost_bound(PRICES, REQUEST) * Decimal("1.5"), PRICES)

    with pytest.raises(CeilingReachedError):
        client.complete(REQUEST, budget)
    assert client.calls == 1
    assert budget.spent_usd == cost_bound(PRICES, REQUEST)


def test_a_rate_limited_attempt_costs_nothing() -> None:
    """The provider refused it before doing any work, so it is given back."""
    client = fake_client(answers_in_turn("429"), [])
    budget = Budget(cost_bound(PRICES, REQUEST) * Decimal("1.5"), PRICES)

    client.complete(REQUEST, budget)

    assert client.calls == 2
    assert budget.spent_usd == call_cost(PRICES, 5000, 2000, 700)
