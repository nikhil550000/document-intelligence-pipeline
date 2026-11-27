"""Tests for workers taking a run's contracts from the queue, with a fake model."""

import json
import threading
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import httpx2
import openai
import psycopg
import pytest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from docintel import worker
from docintel.extraction.budget import cost_bound
from docintel.extraction.prices import PRICES_PATH, call_cost, read_prices
from docintel.extraction.request import build_request
from docintel.parsing.pdfium import PARSER_NAME, PARSER_VERSION
from docintel.pipeline import (
    PACKAGE_FOLDER,
    hash_of_code,
    read_run_config,
    store_contract,
)
from docintel.storage import jobs
from docintel.storage.jobs import add_jobs, claim_job
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.objects import get_object
from docintel.storage.runs import add_run, find_stored_text, resume_run

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

CONFIG, CONFIG_AS_READ = read_run_config(Path("configs") / "pdfium-deepseek-flash.toml")
# Two attempts at the model and no wait between them, so a failure is quick.
FAST_CONFIG = {
    **CONFIG_AS_READ,
    "retries": {"timeout_seconds": 300, "max_attempts": 2, "first_wait_seconds": 0},
}
PRICES = read_prices(PRICES_PATH, CONFIG.model.model)
CODE = hash_of_code(PACKAGE_FOLDER)

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


class FakeProvider:
    """Answers every request with `handler`, and keeps each request's body."""

    def __init__(self, handler: Handler) -> None:
        """Starts with no request seen."""
        self.handler = handler
        self.requests: list[str] = []

    def answer(self, request: httpx2.Request) -> httpx2.Response:
        """Keeps the request, then answers it."""
        self.requests.append(request.content.decode())
        return self.handler(request)

    def sdk_for(self, base_url: str) -> openai.OpenAI:
        """The SDK whose requests come here, whatever the address."""
        return openai.OpenAI(
            base_url=base_url,
            api_key="test-key",
            max_retries=0,
            http_client=httpx2.Client(transport=httpx2.MockTransport(self.answer)),
        )


def store(
    connection: psycopg.Connection,
    s3_client: "S3Client",
    bucket: str,
    make_pdf: Callable[[list[str]], bytes],
    words: list[str],
) -> list[UUID]:
    """Stores one small contract for each word, and returns their documents."""
    document_ids = []
    for word in words:
        file_name = f"{word}.pdf"
        store_contract(connection, s3_client, bucket, file_name, make_pdf([word]))
        stored = find_stored_text(connection, file_name, PARSER_NAME, PARSER_VERSION)
        assert stored is not None
        document_ids.append(stored.document_id)
    return document_ids


def queue_run(
    connection: psycopg.Connection,
    document_ids: list[UUID],
    ceiling: Decimal,
    config: dict[str, Any] = FAST_CONFIG,
    trace_contract_text: bool = False,
) -> UUID:
    """Writes a run, of the fast configuration unless told, with a job per document."""
    run_id = add_run(
        connection,
        "pdfium-deepseek-flash",
        config,
        "0" * 40,
        CODE,
        "smoke",
        ceiling,
        trace_contract_text,
    )
    add_jobs(connection, run_id, document_ids)
    return run_id


def start_worker(
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    provider: FakeProvider,
    stop: threading.Event,
    outcomes: list[str],
) -> threading.Thread:
    """Starts a worker in a thread of its own, with its own two connections."""

    def work() -> None:
        with (
            psycopg.connect(database_url, autocommit=True) as connection,
            psycopg.connect(database_url, autocommit=True) as heartbeat_connection,
        ):
            worker.run_worker(
                connection,
                heartbeat_connection,
                s3_client,
                bucket,
                provider.sdk_for,
                CODE,
                stop,
                on_job=lambda job, outcome: outcomes.append(outcome),
            )

    thread = threading.Thread(target=work)
    thread.start()
    return thread


def work_until_run_ends(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    run_id: UUID,
    provider: FakeProvider,
    workers: int = 1,
) -> list[list[str]]:
    """Runs workers until the run is no longer running; returns each one's outcomes.

    Raises:
        TimeoutError: The run is still running after 30 seconds.
    """
    stop = threading.Event()
    outcomes: list[list[str]] = [[] for _ in range(workers)]
    threads = []
    for own_outcomes in outcomes:
        threads.append(
            start_worker(database_url, s3_client, bucket, provider, stop, own_outcomes)
        )
    deadline = time.monotonic() + 30
    try:
        while run_status(connection, run_id) == "running":
            if time.monotonic() > deadline:
                raise TimeoutError(f"run {run_id} did not end")
            time.sleep(0.05)
    finally:
        stop.set()
        for thread in threads:
            thread.join()
    return outcomes


def run_status(connection: psycopg.Connection, run_id: UUID) -> str:
    """The run's status."""
    row = connection.execute("SELECT status FROM runs WHERE id = %s", (run_id,))
    found = row.fetchone()
    assert found is not None
    status: str = found[0]
    return status


def extraction_rows(connection: psycopg.Connection, run_id: UUID) -> list[Any]:
    """Each extraction of the run: status, reason, cache, tokens, cost, response."""
    return connection.execute(
        "SELECT documents.file_name, status, failure_reason, from_cache,"
        " input_tokens, output_tokens, cost_usd, record IS NOT NULL, response_sha256"
        " FROM extractions JOIN documents ON documents.id = extractions.document_id"
        " WHERE run_id = %s ORDER BY documents.file_name",
        (run_id,),
    ).fetchall()


def test_a_worker_stores_each_record_with_its_values_and_completes_the_run(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """Every contract ends with a record, 41 field values and its cost."""
    empty_record["non_compete"] = {"evidence": [{"text": "Alpha"}], "present": True}
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    provider = FakeProvider(lambda request: response(json.dumps(empty_record)))
    run_id = queue_run(connection, documents, Decimal(1))

    (outcomes,) = work_until_run_ends(
        connection, database_url, s3_client, bucket, run_id, provider
    )

    assert outcomes == ["valid", "valid"]
    assert len(provider.requests) == 2
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
    states = connection.execute("SELECT state, attempt FROM jobs").fetchall()
    assert states == [("succeeded", 1), ("succeeded", 1)]


def test_a_second_run_takes_every_answer_from_the_cache_and_spends_nothing(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """With a ceiling of zero the replay still completes, with no call made."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    first = FakeProvider(lambda request: response(json.dumps(empty_record)))
    first_run = queue_run(connection, documents, Decimal(1))
    work_until_run_ends(connection, database_url, s3_client, bucket, first_run, first)

    replay = FakeProvider(lambda request: response("never asked"))
    run_id = queue_run(connection, documents, Decimal(0))
    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, replay)

    assert run_status(connection, run_id) == "complete"
    assert replay.requests == []
    for row in extraction_rows(connection, run_id):
        assert row[1:4] == ("valid", None, True)


def test_a_contract_whose_calls_keep_failing_is_stored_failed_after_its_last_attempt(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each of the job's attempts calls the model; the run goes on and completes."""
    monkeypatch.setattr(jobs, "WAITS_BETWEEN_ATTEMPTS", (timedelta(0), timedelta(0)))
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])

    def handler(request: httpx2.Request) -> httpx2.Response:
        if "Alpha" in request.content.decode():
            return httpx2.Response(503, json={"error": {"message": "busy"}})
        return response(json.dumps(empty_record))

    provider = FakeProvider(handler)
    run_id = queue_run(connection, documents, Decimal(1))
    (outcomes,) = work_until_run_ends(
        connection, database_url, s3_client, bucket, run_id, provider
    )

    assert sorted(outcomes) == ["failed", "queued_again", "queued_again", "valid"]
    alpha_calls = [body for body in provider.requests if "Alpha" in body]
    # Two calls in each of the job's three attempts.
    assert len(alpha_calls) == 2 * jobs.MAX_ATTEMPTS
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
    assert run_status(connection, run_id) == "complete"


def test_output_that_does_not_load_is_kept_with_its_problems_for_review(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """A cut-off answer has no record, but its response and problems are stored."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    half = json.dumps(empty_record)[:500]
    provider = FakeProvider(lambda request: response(half, finish_reason="length"))
    run_id = queue_run(connection, documents, Decimal(1))

    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, provider)

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


def test_a_run_stopped_by_its_ceiling_goes_on_once_the_ceiling_is_raised(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """Enough for one contract: the run stops, and after raising only Beta is called."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    one_attempt = cost_bound(PRICES, build_request(CONFIG.model, 1, ("Alpha",)))
    # After Alpha only its real cost stays spent, so this leaves just short of
    # the most Beta's call could cost.
    ceiling = one_attempt + call_cost(PRICES, 3000, 0, 900) - Decimal("0.000001")
    provider = FakeProvider(lambda request: response(json.dumps(empty_record)))
    run_id = queue_run(connection, documents, ceiling)

    (outcomes,) = work_until_run_ends(
        connection, database_url, s3_client, bucket, run_id, provider
    )

    assert outcomes == ["valid", "stopped"]
    assert len(provider.requests) == 1
    run = connection.execute("SELECT status, stop_reason FROM runs").fetchone()
    assert run is not None
    assert run[0] == "stopped"
    assert run[1].startswith("the ceiling was reached: the next attempt could cost")
    # Beta is waiting with its attempt given back, and no worker takes it.
    waiting = connection.execute(
        "SELECT state, attempt FROM jobs WHERE state <> 'succeeded'"
    ).fetchall()
    assert waiting == [("queued", 0)]
    assert claim_job(connection, worker.LEASE, CODE) is None

    resume_run(connection, run_id, Decimal(1))
    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, provider)

    assert run_status(connection, run_id) == "complete"
    assert len(provider.requests) == 2
    assert "Beta" in provider.requests[1]
    assert [row[1] for row in extraction_rows(connection, run_id)] == [
        "valid",
        "valid",
    ]


def test_two_workers_share_a_run_and_each_contract_is_extracted_once(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """Twenty contracts, two workers: twenty calls, each to a different contract."""
    words = [f"Contract{number}" for number in range(20)]
    documents = store(connection, s3_client, bucket, pdf_of_pages, words)

    def slow_answer(request: httpx2.Request) -> httpx2.Response:
        # Long enough that both workers are busy at once.
        time.sleep(0.02)
        return response(json.dumps(empty_record))

    provider = FakeProvider(slow_answer)
    run_id = queue_run(connection, documents, Decimal(1))

    first, second = work_until_run_ends(
        connection, database_url, s3_client, bucket, run_id, provider, workers=2
    )

    assert run_status(connection, run_id) == "complete"
    assert len(provider.requests) == 20
    assert len(set(provider.requests)) == 20
    assert first
    assert second
    assert len(first) + len(second) == 20
    assert len(extraction_rows(connection, run_id)) == 20
    starts = connection.execute(
        "SELECT count(*), count(DISTINCT job_id) FROM audit_events"
        " WHERE event = 'started'"
    ).fetchone()
    assert starts == (20, 20)


def test_a_worker_told_to_stop_finishes_the_contract_it_holds(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
) -> None:
    """The stop comes mid-call: that contract is stored, the next is left queued."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha", "Beta"])
    stop = threading.Event()

    def answer_after_stop(request: httpx2.Request) -> httpx2.Response:
        stop.set()
        return response(json.dumps(empty_record))

    provider = FakeProvider(answer_after_stop)
    queue_run(connection, documents, Decimal(1))
    outcomes: list[str] = []

    thread = start_worker(database_url, s3_client, bucket, provider, stop, outcomes)
    thread.join(timeout=30)

    assert not thread.is_alive()
    assert outcomes == ["valid"]
    states = connection.execute(
        "SELECT documents.file_name, state FROM jobs"
        " JOIN documents ON documents.id = jobs.document_id ORDER BY 1"
    ).fetchall()
    assert states == [("Alpha.pdf", "succeeded"), ("Beta.pdf", "queued")]


def test_the_heartbeat_keeps_a_slow_contract_from_a_second_worker(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A call three times the lease long is not given up while its worker lives."""
    monkeypatch.setattr(worker, "LEASE", timedelta(seconds=1))
    monkeypatch.setattr(worker, "HEARTBEAT_SECONDS", 0.2)
    monkeypatch.setattr(worker, "IDLE_SECONDS", 0.1)
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])

    def slow_answer(request: httpx2.Request) -> httpx2.Response:
        time.sleep(3)
        return response(json.dumps(empty_record))

    provider = FakeProvider(slow_answer)
    run_id = queue_run(connection, documents, Decimal(1))

    first, second = work_until_run_ends(
        connection, database_url, s3_client, bucket, run_id, provider, workers=2
    )

    assert len(provider.requests) == 1
    assert sorted(first + second) == ["valid"]
    events = connection.execute(
        "SELECT event, attempt FROM audit_events ORDER BY id"
    ).fetchall()
    assert events == [("queued", 0), ("started", 1), ("succeeded", 1)]


@pytest.fixture(scope="session")
def span_store() -> InMemorySpanExporter:
    """Keeps the spans of every worker of the session.

    A process can set its tracer provider only once, so every test shares it.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    # Sent as each span ends, in the worker's own thread, so an export that
    # failed into the worker would show up in the job.
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture
def spans(span_store: InMemorySpanExporter) -> InMemorySpanExporter:
    """The spans of this test's workers only."""
    span_store.clear()
    return span_store


def finished_spans(exporter: InMemorySpanExporter) -> dict[str, list[ReadableSpan]]:
    """Each finished span, by its name, in the order they started."""
    by_name: dict[str, list[ReadableSpan]] = {}
    in_order = sorted(exporter.get_finished_spans(), key=lambda span: span.start_time)
    for span in in_order:
        by_name.setdefault(span.name, []).append(span)
    return by_name


def texts_in(by_name: dict[str, list[ReadableSpan]]) -> list[str]:
    """Every piece of text the spans carry: attributes, statuses and events."""
    texts = []
    for spans_of_name in by_name.values():
        for span in spans_of_name:
            values = list((span.attributes or {}).values())
            for event in span.events:
                values.extend((event.attributes or {}).values())
            for value in values:
                if isinstance(value, tuple):
                    texts.extend(str(item) for item in value)
                else:
                    texts.append(str(value))
            texts.append(span.status.description or "")
    return texts


def parent_of(span: ReadableSpan) -> int | None:
    """The id of the span's parent, or None for a trace's first span."""
    if span.parent is None:
        return None
    return span.parent.span_id


def test_a_contract_leaves_one_trace_with_a_span_for_each_step(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    spans: InMemorySpanExporter,
) -> None:
    """The steps hang from the contract, the call from the extraction; no text."""
    empty_record["non_compete"] = {"evidence": [{"text": "Alpha"}], "present": True}
    (document,) = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    provider = FakeProvider(lambda request: response(json.dumps(empty_record)))
    run_id = queue_run(connection, [document], Decimal(1))

    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, provider)

    by_name = finished_spans(spans)
    assert sorted(by_name) == [
        "check structure",
        "contract",
        "extract",
        "model call",
        "read text",
        "store",
    ]
    for spans_of_name in by_name.values():
        assert len(spans_of_name) == 1
    (contract,) = by_name["contract"]
    (extract,) = by_name["extract"]
    assert parent_of(contract) is None
    for name in ["read text", "extract", "check structure", "store"]:
        assert parent_of(by_name[name][0]) == contract.context.span_id
    assert parent_of(by_name["model call"][0]) == extract.context.span_id
    trace_ids = set()
    for spans_of_name in by_name.values():
        trace_ids.add(spans_of_name[0].context.trace_id)
    assert len(trace_ids) == 1

    job = connection.execute("SELECT id FROM jobs").fetchone()
    assert job is not None
    assert contract.attributes == {
        "openinference.span.kind": "CHAIN",
        "docintel.run_id": str(run_id),
        "docintel.job_id": str(job[0]),
        "docintel.attempt": 1,
        "docintel.document_id": str(document),
        "docintel.outcome": "valid",
    }
    cost = float(call_cost(PRICES, 3000, 0, 900))
    assert extract.attributes is not None
    assert extract.attributes["llm.token_count.prompt"] == 3000
    assert extract.attributes["llm.token_count.completion"] == 900
    assert extract.attributes["llm.token_count.total"] == 3900
    assert extract.attributes["llm.cost.total"] == cost
    assert extract.attributes["docintel.cost.paid_usd"] == cost
    assert extract.attributes["docintel.from_cache"] is False
    for text in texts_in(by_name):
        assert "Alpha" not in text


def test_a_run_that_asks_for_it_sends_the_request_and_the_answer(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    spans: InMemorySpanExporter,
) -> None:
    """The extraction carries the contract's text in the request, and the answer."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    answer = json.dumps(empty_record)
    provider = FakeProvider(lambda request: response(answer))
    run_id = queue_run(connection, documents, Decimal(1), trace_contract_text=True)

    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, provider)

    (extract,) = finished_spans(spans)["extract"]
    assert extract.attributes is not None
    assert "Alpha" in str(extract.attributes["input.value"])
    assert extract.attributes["output.value"] == answer


def test_each_attempt_at_the_model_has_its_own_span(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    spans: InMemorySpanExporter,
) -> None:
    """Two server errors, then an answer: three spans, the failures marked."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    answers = [
        httpx2.Response(503, json={"error": {"message": "busy"}}),
        httpx2.Response(503, json={"error": {"message": "busy"}}),
        response(json.dumps(empty_record)),
    ]
    provider = FakeProvider(lambda request: answers.pop(0))
    three_attempts = {
        **CONFIG_AS_READ,
        "retries": {"timeout_seconds": 300, "max_attempts": 3, "first_wait_seconds": 0},
    }
    run_id = queue_run(connection, documents, Decimal(1), config=three_attempts)

    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, provider)

    calls = finished_spans(spans)["model call"]
    outcomes = []
    statuses = []
    for call in calls:
        assert call.attributes is not None
        outcomes.append(call.attributes["docintel.outcome"])
        statuses.append(call.status.status_code)
    assert outcomes == ["error 503", "error 503", "answered"]
    assert statuses == [StatusCode.ERROR, StatusCode.ERROR, StatusCode.UNSET]
    first = calls[0].attributes
    assert first is not None
    # The provider may have done the work, so the attempt stays counted.
    assert first["docintel.cost.settled_usd"] == first["docintel.cost.reserved_usd"]


def test_an_answer_from_the_cache_shows_its_price_and_that_nothing_was_paid(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    spans: InMemorySpanExporter,
) -> None:
    """The replay's extraction has the answer's list price, no call, and $0 paid."""
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    first = FakeProvider(lambda request: response(json.dumps(empty_record)))
    first_run = queue_run(connection, documents, Decimal(1))
    work_until_run_ends(connection, database_url, s3_client, bucket, first_run, first)
    spans.clear()

    replay = FakeProvider(lambda request: response("never asked"))
    run_id = queue_run(connection, documents, Decimal(0))
    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, replay)

    by_name = finished_spans(spans)
    assert "model call" not in by_name
    (extract,) = by_name["extract"]
    assert extract.attributes is not None
    assert extract.attributes["docintel.from_cache"] is True
    assert extract.attributes["llm.cost.total"] == float(
        call_cost(PRICES, 3000, 0, 900)
    )
    assert extract.attributes["docintel.cost.paid_usd"] == 0


def test_each_failed_attempt_at_a_job_is_a_trace_marked_with_its_reason(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    pdf_of_pages: Callable[[list[str]], bytes],
    spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three attempts, three traces of the same job, each an error with the reason."""
    monkeypatch.setattr(jobs, "WAITS_BETWEEN_ATTEMPTS", (timedelta(0), timedelta(0)))
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    provider = FakeProvider(
        lambda request: httpx2.Response(503, json={"error": {"message": "busy"}})
    )
    run_id = queue_run(connection, documents, Decimal(1))

    work_until_run_ends(connection, database_url, s3_client, bucket, run_id, provider)

    contracts = finished_spans(spans)["contract"]
    trace_ids = set()
    job_ids = set()
    attempts = []
    for contract in contracts:
        assert contract.attributes is not None
        trace_ids.add(contract.context.trace_id)
        job_ids.add(contract.attributes["docintel.job_id"])
        attempts.append(contract.attributes["docintel.attempt"])
        assert contract.status.status_code == StatusCode.ERROR
        assert contract.status.description == "error 503 on the last of 2 attempts"
    assert attempts == [1, 2, 3]
    assert len(trace_ids) == 3
    assert len(job_ids) == 1


def test_a_tracing_endpoint_that_refuses_everything_leaves_the_job_done(
    connection: psycopg.Connection,
    database_url: str,
    s3_client: "S3Client",
    bucket: str,
    empty_record: dict[str, Any],
    pdf_of_pages: Callable[[list[str]], bytes],
    spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every span goes to an address where nothing listens; the contract is stored."""
    nobody_listening = OTLPSpanExporter(
        endpoint="http://127.0.0.1:9/v1/traces", timeout=1
    )
    monkeypatch.setattr(spans, "export", nobody_listening.export)
    documents = store(connection, s3_client, bucket, pdf_of_pages, ["Alpha"])
    provider = FakeProvider(lambda request: response(json.dumps(empty_record)))
    run_id = queue_run(connection, documents, Decimal(1))

    (outcomes,) = work_until_run_ends(
        connection, database_url, s3_client, bucket, run_id, provider
    )

    assert outcomes == ["valid"]
    assert run_status(connection, run_id) == "complete"
    assert spans.get_finished_spans() == ()
