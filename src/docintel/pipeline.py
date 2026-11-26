"""Runs the stages of the pipeline in order for one contract."""

import hashlib
import json
import time
import tomllib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import TupleRow

from docintel.domain.record import SCHEMA_VERSION
from docintel.extraction.budget import Budget
from docintel.extraction.client import ModelClient, RetrySettings, read_completion
from docintel.extraction.prices import call_cost
from docintel.extraction.request import ModelSettings, build_request, request_sha256
from docintel.parsing.parsed_text import ParsedText
from docintel.parsing.pdfium import PARSER_NAME, PARSER_VERSION, parse_pdf
from docintel.storage.documents import add_document, add_parsed_text, has_parsed_text
from docintel.storage.objects import get_object, put_object
from docintel.storage.runs import Extraction, StoredText, find_cached_response
from docintel.validation.structure import check_structure

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@dataclass(frozen=True)
class RunConfig:
    """What a run does to each contract, read from one configuration file."""

    parser: str
    prompt_version: int
    base_url: str
    model: ModelSettings
    retry: RetrySettings


def store_contract(
    connection: psycopg.Connection[TupleRow],
    s3_client: "S3Client",
    bucket: str,
    file_name: str,
    pdf: bytes,
) -> ParsedText | None:
    """Stores a PDF and the text PDFium reads from it, with a row for each.

    Returns:
        The text read, or None when this version of the parser had read the PDF
        before, in which case nothing is written.
    """
    sha256 = hashlib.sha256(pdf).hexdigest()
    if has_parsed_text(connection, sha256, PARSER_NAME, PARSER_VERSION):
        return None

    # The files go first, so that no row ever names a file that is not stored.
    put_object(s3_client, bucket, pdf)
    parsed = parse_pdf(pdf)
    text_sha256 = put_object(s3_client, bucket, json.dumps(parsed.pages).encode())
    with connection.transaction():
        document_id = add_document(connection, sha256, file_name, len(pdf))
        add_parsed_text(
            connection,
            document_id,
            parsed.parser,
            parsed.parser_version,
            text_sha256,
            parsed.seconds,
        )
    return parsed


def read_run_config(path: Path) -> tuple[RunConfig, dict[str, Any]]:
    """Reads a run configuration, and returns it also as read, to be stored.

    Raises:
        ValueError: The configuration names a parser that is not built.
    """
    with path.open("rb") as file:
        config = tomllib.load(file)
    return run_config_from(config), config


def run_config_from(config: dict[str, Any]) -> RunConfig:
    """Reads a run configuration as stored with its run.

    Raises:
        ValueError: The configuration names a parser that is not built.
    """
    if config["parser"] != PARSER_NAME:
        raise ValueError(f"the only parser so far is {PARSER_NAME}: {config['parser']}")
    model = config["model"]
    retries = config["retries"]
    return RunConfig(
        parser=config["parser"],
        prompt_version=config["prompt_version"],
        base_url=model["base_url"],
        model=ModelSettings(
            model=model["name"],
            max_tokens=model["max_tokens"],
            reasoning_effort=model["reasoning_effort"],
        ),
        retry=RetrySettings(
            timeout_seconds=retries["timeout_seconds"],
            max_attempts=retries["max_attempts"],
            first_wait_seconds=retries["first_wait_seconds"],
        ),
    )


def longest_job(config: RunConfig) -> timedelta:
    """The longest one contract can take, so a worker still on it past that is stuck.

    The case counted is every attempt at the model running to its time limit,
    with every wait between attempts.
    """
    retry = config.retry
    seconds = retry.max_attempts * retry.timeout_seconds
    wait = retry.first_wait_seconds
    for _ in range(retry.max_attempts - 1):
        seconds += wait
        wait = wait * 2
    # The text is parsed before the run. Reading it and storing the answer take
    # well under a second; a minute leaves room for a slow database.
    seconds += 60
    return timedelta(seconds=seconds)


def extract_contract(
    connection: psycopg.Connection[TupleRow],
    s3_client: "S3Client",
    bucket: str,
    config: RunConfig,
    stored: StoredText,
    client: ModelClient,
    budget: Budget,
) -> Extraction:
    """Asks the model for one contract's record, and returns what to store.

    A response received before for exactly this request is used again, so it
    costs nothing and never touches the budget. A new response is kept in the
    object store at once, so a paid answer is never lost.

    Raises:
        CeilingReachedError: The budget cannot cover the next attempt.
        ModelCallError: Every attempt at the model failed.
    """
    start = time.perf_counter()
    pages = tuple(json.loads(get_object(s3_client, bucket, stored.text_sha256)))
    request = build_request(config.model, config.prompt_version, pages)
    request_key = request_sha256(request)

    response_sha256 = find_cached_response(connection, request_key)
    from_cache = response_sha256 is not None
    if response_sha256 is not None:
        response = get_object(s3_client, bucket, response_sha256)
    else:
        response = client.complete(request, budget)
        response_sha256 = put_object(s3_client, bucket, response)
    extract_seconds = time.perf_counter() - start

    completion = read_completion(response)
    result = check_structure(completion.content, completion.cut_off)
    record = None
    problems = []
    status = "valid"
    if isinstance(result, list):
        problems = result
        status = "needs_review"
    else:
        record = result
    return Extraction(
        document_id=stored.document_id,
        status=status,
        record=record,
        problems=problems,
        failure_reason=None,
        model=config.model.model,
        prompt_version=str(config.prompt_version),
        schema_version=SCHEMA_VERSION,
        request_sha256=request_key,
        response_sha256=response_sha256,
        from_cache=from_cache,
        input_tokens=completion.input_tokens,
        cached_input_tokens=completion.cached_input_tokens,
        output_tokens=completion.output_tokens,
        # The list price of the answer, also when it came from the cache, so
        # that configurations compare on what their answers cost.
        cost_usd=call_cost(
            budget.prices,
            completion.input_tokens,
            completion.cached_input_tokens,
            completion.output_tokens,
        ),
        parse_seconds=stored.parse_seconds,
        extract_seconds=extract_seconds,
        total_seconds=stored.parse_seconds + time.perf_counter() - start,
    )
