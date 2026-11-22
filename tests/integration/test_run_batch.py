"""Tests for a run over a list of contracts, on real services, with a fake model."""

import json
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2
import openai
import psycopg
import pytest

from docintel.extraction.budget import Budget, cost_bound
from docintel.extraction.client import ModelClient, RetrySettings
from docintel.extraction.prices import Prices, call_cost
from docintel.extraction.request import build_request
from docintel.parsing.pdfium import PARSER_NAME, PARSER_VERSION
from docintel.pipeline import read_run_config, run_batch, store_contract
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.objects import get_object
from docintel.storage.runs import StoredText, add_run, find_stored_text

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

CONFIG, CONFIG_AS_READ = read_run_config(Path("configs") / "pdfium-deepseek-flash.toml")
PRICES = Prices(date(2026, 11, 22), Decimal("0.30"), Decimal("0.006"), Decimal("1.20"))
NO_WAIT = RetrySettings(timeout_seconds=300, max_attempts=2, first_wait_seconds=0)

type Handler = Callable[[httpx2.Request], httpx2.Response]


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to a database that has every table."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def response(content: str, finish_reason: str = "stop") -> httpx2.Response:
    """A provider's answer with the given content and made-up token counts."""
    body = {
        "id": "1",
        "object": "chat.completion",
        "created": 1,
        "model": CONFIG.model.model,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {
            "prompt_tokens": 3000,
            "completion_tokens": 900,
            "total_tokens": 3900,
        },
    }
    return httpx2.Response(200, json=body)


def fake_client(handler: Handler) -> ModelClient:
    """A client whose requests go to `handler`."""
    sdk = openai.OpenAI(
        base_url="https://provider.test/v1",
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return ModelClient(sdk, NO_WAIT, sleep=lambda seconds: None)


def store(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    make_pdf: Callable[[list[str]], bytes],
    words: list[str],
) -> dict[str, StoredText]:
    """Stores one small contract for each word, and returns their stored texts."""
    contracts = {}
    for word in words:
        file_name = f"{word}.pdf"
        store_contract(connection, s3_client, bucket, file_name, make_pdf([word]))
        stored = find_stored_text(connection, file_name, PARSER_NAME, PARSER_VERSION)
        assert stored is not None
        contracts[file_name] = stored
    return contracts


def new_run(connection: psycopg.Connection, ceiling: Decimal) -> Any:
    """Writes the row of a run of the committed configuration."""
    return add_run(
        connection, "pdfium-deepseek-flash", CONFIG_AS_READ, "0" * 40, "smoke", ceiling
    )


def extraction_rows(connection: psycopg.Connection, run_id: Any) -> list[Any]:
    """Each extraction of the run: status, reason, cache, tokens, cost."""
    return connection.execute(
        "SELECT documents.file_name, status, failure_reason, from_cache,"
        " input_tokens, output_tokens, cost_usd, record IS NOT NULL, response_sha256"
        " FROM extractions JOIN documents ON documents.id = extractions.document_id"
        " WHERE run_id = %s ORDER BY documents.file_name",
        (run_id,),
    ).fetchall()


def test_a_run_stores_each_record_with_its_values_and_completes(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """Every contract ends with a record, 41 field values and its cost."""
    empty_record["non_compete"] = {"evidence": [{"text": "Alpha"}], "present": True}
    contracts = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    client = fake_client(lambda request: response(json.dumps(empty_record)))
    run_id = new_run(connection, Decimal(1))

    outcome = run_batch(
        connection,
        s3_client,
        bucket,
        run_id,
        CONFIG,
        contracts,
        client,
        Budget(Decimal(1), PRICES),
    )

    assert outcome.status == "complete"
    assert outcome.statuses == {"Alpha.pdf": "valid", "Beta.pdf": "valid"}
    assert client.calls == 2
    cost = call_cost(PRICES, 3000, 0, 900)
    for row in extraction_rows(connection, run_id):
        assert row[1:8] == ("valid", None, False, 3000, 900, cost, True)
        stored = json.loads(get_object(s3_client, bucket, row[8]))
        assert stored["usage"]["completion_tokens"] == 900
    values = connection.execute(
        "SELECT count(*), count(*) FILTER (WHERE present), max(evidence::text)"
        " FILTER (WHERE field_name = 'non_compete') FROM field_values"
    ).fetchone()
    assert values == (82, 2, '[{"text": "Alpha"}]')
    run = connection.execute(
        "SELECT status, stop_reason, finished_at IS NOT NULL FROM runs"
    ).fetchone()
    assert run == ("complete", None, True)


def test_a_second_run_takes_every_answer_from_the_cache_and_spends_nothing(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """With a budget of zero the replay still completes, with no call made."""
    contracts = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    first = fake_client(lambda request: response(json.dumps(empty_record)))
    run_batch(
        connection,
        s3_client,
        bucket,
        new_run(connection, Decimal(1)),
        CONFIG,
        contracts,
        first,
        Budget(Decimal(1), PRICES),
    )

    replay = fake_client(lambda request: response("never asked"))
    budget = Budget(Decimal(0), PRICES)
    run_id = new_run(connection, Decimal(0))
    outcome = run_batch(
        connection, s3_client, bucket, run_id, CONFIG, contracts, replay, budget
    )

    assert outcome.status == "complete"
    assert replay.calls == 0
    assert budget.spent_usd == 0
    for row in extraction_rows(connection, run_id):
        assert row[1:4] == ("valid", None, True)


def test_a_contract_whose_calls_all_fail_is_stored_as_failed_and_the_run_goes_on(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """The failure keeps its reason; the next contract is still extracted."""
    contracts = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])

    def handler(request: httpx2.Request) -> httpx2.Response:
        if "Alpha" in request.content.decode():
            return httpx2.Response(503, json={"error": {"message": "busy"}})
        return response(json.dumps(empty_record))

    client = fake_client(handler)
    run_id = new_run(connection, Decimal(1))
    outcome = run_batch(
        connection,
        s3_client,
        bucket,
        run_id,
        CONFIG,
        contracts,
        client,
        Budget(Decimal(1), PRICES),
    )

    assert outcome.status == "complete"
    assert outcome.statuses == {"Alpha.pdf": "failed", "Beta.pdf": "valid"}
    alpha, beta = extraction_rows(connection, run_id)
    assert alpha[1:9] == (
        "failed",
        "error 503 on the last of 2 attempts",
        False,
        0,
        0,
        0,
        False,
        None,
    )
    assert beta[1] == "valid"


def test_output_that_does_not_load_is_kept_with_its_problems_for_review(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """A cut-off answer has no record, but its response and problems are stored."""
    contracts = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    half = json.dumps(empty_record)[:500]
    client = fake_client(lambda request: response(half, finish_reason="length"))
    run_id = new_run(connection, Decimal(1))

    run_batch(
        connection,
        s3_client,
        bucket,
        run_id,
        CONFIG,
        contracts,
        client,
        Budget(Decimal(1), PRICES),
    )

    (row,) = extraction_rows(connection, run_id)
    assert row[1:4] == ("needs_review", None, False)
    assert row[7] is False
    stored = json.loads(get_object(s3_client, bucket, row[8]))
    assert stored["choices"][0]["message"]["content"] == half
    issues = connection.execute(
        "SELECT position, layer, rule, field_name FROM validation_issues ORDER BY 1"
    ).fetchall()
    assert issues == [
        (0, "structure", "cut_off", None),
        (1, "structure", "json_invalid", None),
    ]
    assert connection.execute("SELECT count(*) FROM field_values").fetchone() == (0,)


def test_a_run_stops_before_a_call_its_budget_cannot_cover(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """Enough for one contract: the second is not called, and the run says why."""
    contracts = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    pages = ("Alpha",)
    one_attempt = cost_bound(PRICES, build_request(CONFIG.model, 1, pages))
    client = fake_client(lambda request: response(json.dumps(empty_record)))
    # After Alpha only its real cost stays spent, so this leaves just short of
    # the most Beta's call could cost.
    ceiling = one_attempt + call_cost(PRICES, 3000, 0, 900) - Decimal("0.000001")
    budget = Budget(ceiling, PRICES)
    run_id = new_run(connection, budget.ceiling_usd)

    outcome = run_batch(
        connection, s3_client, bucket, run_id, CONFIG, contracts, client, budget
    )

    assert outcome.status == "stopped"
    assert outcome.statuses == {"Alpha.pdf": "valid"}
    assert client.calls == 1
    assert budget.spent_usd <= budget.ceiling_usd
    run = connection.execute("SELECT status, stop_reason FROM runs").fetchone()
    assert run is not None
    assert run[0] == "stopped"
    assert run[1].startswith("stopped before Beta.pdf: the next attempt could cost")
    assert len(extraction_rows(connection, run_id)) == 1
