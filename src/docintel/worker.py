"""A worker: takes contracts from the job queue one at a time, until told to stop."""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import openai
import psycopg
from psycopg.rows import TupleRow

from docintel.extraction.budget import Budget, CeilingReachedError
from docintel.extraction.client import ModelCallError, ModelClient
from docintel.extraction.prices import PRICES_PATH, read_prices
from docintel.parsing.pdfium import PARSER_VERSION
from docintel.pipeline import RunConfig, extract_contract, longest_job, run_config_from
from docintel.storage.jobs import (
    MAX_ATTEMPTS,
    Job,
    JobLostError,
    claim_job,
    extend_job,
    give_up_abandoned,
    mark_failed,
    mark_succeeded,
    return_job,
)
from docintel.storage.runs import add_extraction, finish_run, read_stored_text
from docintel.storage.scores import read_run

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# A job stays held this long after the worker's last heartbeat, so the contract
# of a worker that dies is taken by another within about two minutes.
LEASE = timedelta(minutes=2)
HEARTBEAT_SECONDS = 30.0
# How long a worker with nothing to do waits before it looks at the queue again.
IDLE_SECONDS = 2.0


@dataclass(frozen=True)
class RunHeld:
    """What a worker keeps for each run it has taken a job of."""

    config: RunConfig
    client: ModelClient
    # Each worker holds the ceiling for its own calls only.
    budget: Budget


def run_worker(
    connection: psycopg.Connection[TupleRow],
    heartbeat_connection: psycopg.Connection[TupleRow],
    s3_client: "S3Client",
    bucket: str,
    sdk_for: Callable[[str], openai.OpenAI],
    code_sha256: str,
    stop: threading.Event,
    on_job: Callable[[Job, str], None] = lambda job, outcome: None,
) -> None:
    """Takes one job at a time and works on it, until `stop` is set.

    The job held when `stop` is set is finished first.

    Args:
        connection: For the queue and the pipeline.
        heartbeat_connection: Only for the heartbeat, which runs while
            `connection` is busy with the job.
        s3_client: The object store.
        bucket: The bucket the texts and responses are in.
        sdk_for: Gives the model SDK for a provider's address.
        code_sha256: The hash of this worker's code; it takes only jobs of
            runs made from the same code.
        stop: Set to make the worker exit after the job it holds.
        on_job: Told each job and how it ended.
    """
    runs: dict[UUID, RunHeld] = {}
    while not stop.is_set():
        give_up_abandoned(connection)
        job = claim_job(connection, LEASE, code_sha256)
        if job is None:
            stop.wait(IDLE_SECONDS)
            continue
        try:
            outcome = work_on(
                connection, heartbeat_connection, s3_client, bucket, sdk_for, runs, job
            )
        except JobLostError:
            # Its time ran out and another worker took it, so that worker's
            # answer is the one kept.
            outcome = "lost"
        on_job(job, outcome)


def work_on(
    connection: psycopg.Connection[TupleRow],
    heartbeat_connection: psycopg.Connection[TupleRow],
    s3_client: "S3Client",
    bucket: str,
    sdk_for: Callable[[str], openai.OpenAI],
    runs: dict[UUID, RunHeld],
    job: Job,
) -> str:
    """Runs the pipeline for the job's contract, and ends the job with the result.

    Returns:
        The extraction's status, or how the job ended without one:
        `queued_again`, `failed`, or `stopped` by the run's ceiling.

    Raises:
        JobLostError: The job was given up as abandoned while this worker had it.
    """
    run = read_run(connection, job.run_id)
    # A job's run cannot be removed while the job exists.
    assert run is not None
    held = runs.get(job.run_id)
    if held is None:
        config = run_config_from(run.config)
        prices = read_prices(PRICES_PATH, config.model.model)
        client = ModelClient(sdk_for(config.base_url), config.retry)
        held = RunHeld(config, client, Budget(run.cost_ceiling_usd, prices))
        runs[job.run_id] = held
    # A ceiling raised to carry on a stopped run counts from the next contract.
    held.budget.ceiling_usd = run.cost_ceiling_usd

    stored = read_stored_text(
        connection, job.document_id, held.config.parser, PARSER_VERSION
    )
    if stored is None:
        reason = f"no text read by {held.config.parser} {PARSER_VERSION}"
        return fail_attempt(connection, job, reason)
    try:
        with heartbeat(heartbeat_connection, job, longest_job(held.config)):
            extraction = extract_contract(
                connection,
                s3_client,
                bucket,
                held.config,
                stored,
                held.client,
                held.budget,
            )
    except ModelCallError as error:
        return fail_attempt(connection, job, str(error))
    except CeilingReachedError as error:
        reason = f"the ceiling was reached: {error}"
        with connection.transaction():
            return_job(connection, job, reason)
            finish_run(connection, job.run_id, "stopped", reason)
        return "stopped"
    # Together, so a contract is never stored without its job ending, or the
    # other way round, and a worker that lost its job stores nothing.
    with connection.transaction():
        mark_succeeded(connection, job)
        add_extraction(connection, job.run_id, extraction)
    return extraction.status


def fail_attempt(
    connection: psycopg.Connection[TupleRow], job: Job, reason: str
) -> str:
    """Ends the attempt without an answer, and says whether the job will run again."""
    mark_failed(connection, job, reason)
    if job.attempt == MAX_ATTEMPTS:
        return "failed"
    return "queued_again"


@contextmanager
def heartbeat(
    connection: psycopg.Connection[TupleRow], job: Job, longest: timedelta
) -> Iterator[None]:
    """Keeps the job held while the block runs, from a thread of its own."""
    done = threading.Event()
    thread = threading.Thread(
        target=keep_held, args=(connection, job, longest, done), daemon=True
    )
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()


def keep_held(
    connection: psycopg.Connection[TupleRow],
    job: Job,
    longest: timedelta,
    done: threading.Event,
) -> None:
    """Extends the job at every heartbeat, until `done` is set or the job is lost."""
    while not done.wait(HEARTBEAT_SECONDS):
        if not extend_job(connection, job, LEASE, longest):
            return
