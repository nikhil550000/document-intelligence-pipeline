"""The job queue: one row per contract to process, taken by one worker at a time.

Every time is the database's clock, so workers on machines whose clocks differ
still agree on when a job is ready or abandoned.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import psycopg
from psycopg.rows import TupleRow

from docintel.domain.record import SCHEMA_VERSION

# The waits before the second and the third attempt. They grow so that a
# provider down for some minutes does not use up every waiting job's attempts.
WAITS_BETWEEN_ATTEMPTS = (timedelta(minutes=1), timedelta(minutes=5))
MAX_ATTEMPTS = len(WAITS_BETWEEN_ATTEMPTS) + 1
ABANDONED = "abandoned: still running when its time ran out"


class JobLostError(Exception):
    """The job is no longer held by this attempt: it was given up as abandoned."""


@dataclass(frozen=True)
class Job:
    """One attempt at a job, as held by the worker that took it."""

    id: UUID
    run_id: UUID
    document_id: UUID
    attempt: int


def add_jobs(
    connection: psycopg.Connection[TupleRow], run_id: UUID, document_ids: list[UUID]
) -> None:
    """Queues one job per document of a run, each with its audit row."""
    # One statement for every job and its audit row: on this machine every
    # statement costs a round trip, and a run has hundreds of contracts.
    connection.execute(
        "WITH added AS ("
        " INSERT INTO jobs (run_id, document_id) SELECT %s, unnest(%s::uuid[])"
        " RETURNING id, run_id, document_id, attempt)"
        " INSERT INTO audit_events (event, job_id, run_id, document_id, attempt)"
        " SELECT 'queued', id, run_id, document_id, attempt FROM added",
        (run_id, document_ids),
    )


def claim_job(
    connection: psycopg.Connection[TupleRow], lease: timedelta, code_sha256: str
) -> Job | None:
    """Takes the oldest job that is ready, or returns None when there is none.

    Args:
        connection: The worker's connection.
        lease: How long the job stays held unless the worker extends it. Past
            it, the job is given up as abandoned.
        code_sha256: The hash of the worker's code. Only jobs of runs made from
            the same code are taken.
    """
    with connection.transaction():
        # A row another worker is taking right now is skipped, not waited for.
        # A stopped run's jobs wait until its ceiling is raised.
        row = connection.execute(
            "SELECT id, run_id, document_id, attempt FROM jobs"
            " WHERE state = 'queued' AND available_at <= now()"
            " AND run_id IN (SELECT id FROM runs"
            " WHERE status = 'running' AND code_sha256 = %s)"
            " ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED",
            (code_sha256,),
        ).fetchone()
        if row is None:
            return None
        job = Job(id=row[0], run_id=row[1], document_id=row[2], attempt=row[3] + 1)
        connection.execute(
            "UPDATE jobs SET state = 'running', attempt = %s, taken_at = now(),"
            " taken_until = now() + %s WHERE id = %s",
            (job.attempt, lease, job.id),
        )
        add_event(connection, "started", job, None)
    return job


def extend_job(
    connection: psycopg.Connection[TupleRow],
    job: Job,
    lease: timedelta,
    longest: timedelta,
) -> bool:
    """Holds the job for `lease` from now, but never past `longest` after it was taken.

    The cap means a worker that is alive but stuck still loses its job.

    Returns:
        False when the job is no longer held by this attempt.
    """
    row = connection.execute(
        "UPDATE jobs SET taken_until = least(now() + %s, taken_at + %s)"
        " WHERE id = %s AND state = 'running' AND attempt = %s RETURNING id",
        (lease, longest, job.id, job.attempt),
    ).fetchone()
    return row is not None


def mark_succeeded(connection: psycopg.Connection[TupleRow], job: Job) -> None:
    """Ends the job as done, and completes its run if it was the last one.

    Raises:
        JobLostError: The job was given up as abandoned while this attempt ran.
    """
    with connection.transaction():
        hold(connection, job)
        connection.execute(
            "UPDATE jobs SET state = 'succeeded', finished_at = now(),"
            " taken_at = NULL, taken_until = NULL WHERE id = %s",
            (job.id,),
        )
        add_event(connection, "succeeded", job, None)
        complete_run_if_ended(connection, job.run_id)


def mark_failed(
    connection: psycopg.Connection[TupleRow], job: Job, reason: str
) -> None:
    """Ends the attempt without an answer: queues the job again, or fails it.

    Raises:
        JobLostError: The job was given up as abandoned while this attempt ran.
    """
    with connection.transaction():
        hold(connection, job)
        end_attempt(connection, job, reason)


def return_job(connection: psycopg.Connection[TupleRow], job: Job, reason: str) -> None:
    """Queues the job again at once, with this attempt not counted.

    For an attempt that could not be made, such as one the run's ceiling cannot
    cover: the contract is not at fault, so it keeps its attempts.

    Raises:
        JobLostError: The job was given up as abandoned while this attempt ran.
    """
    with connection.transaction():
        hold(connection, job)
        connection.execute(
            "UPDATE jobs SET state = 'queued', attempt = attempt - 1,"
            " taken_at = NULL, taken_until = NULL WHERE id = %s",
            (job.id,),
        )
        add_event(connection, "queued_again", job, reason)


def give_up_abandoned(connection: psycopg.Connection[TupleRow]) -> list[Job]:
    """Ends every running job past its time, as a failed attempt, and returns them."""
    with connection.transaction():
        # In the order of their runs, so two workers giving up jobs of the same
        # runs lock those runs in the same order and never wait for each other.
        rows = connection.execute(
            "SELECT id, run_id, document_id, attempt FROM jobs"
            " WHERE state = 'running' AND taken_until < now()"
            " ORDER BY run_id FOR UPDATE SKIP LOCKED"
        ).fetchall()
        abandoned = []
        for row in rows:
            job = Job(id=row[0], run_id=row[1], document_id=row[2], attempt=row[3])
            end_attempt(connection, job, ABANDONED)
            abandoned.append(job)
    return abandoned


def hold(connection: psycopg.Connection[TupleRow], job: Job) -> None:
    """Locks the job's row, if it is still running as this attempt.

    Raises:
        JobLostError: The job is no longer running as this attempt.
    """
    row = connection.execute(
        "SELECT 1 FROM jobs WHERE id = %s AND state = 'running' AND attempt = %s"
        " FOR UPDATE",
        (job.id, job.attempt),
    ).fetchone()
    if row is None:
        raise JobLostError(f"job {job.id} is no longer held by attempt {job.attempt}")


def end_attempt(
    connection: psycopg.Connection[TupleRow], job: Job, reason: str
) -> None:
    """Queues the job again after its wait, or fails it after its last attempt.

    A failed job's contract is stored as failed, with the reason, so that the
    run's report still counts it.
    """
    if job.attempt < MAX_ATTEMPTS:
        wait = WAITS_BETWEEN_ATTEMPTS[job.attempt - 1]
        connection.execute(
            "UPDATE jobs SET state = 'queued', available_at = now() + %s,"
            " taken_at = NULL, taken_until = NULL WHERE id = %s",
            (wait, job.id),
        )
        add_event(connection, "queued_again", job, reason)
        return
    # The time is the last attempt's, so it is read before the job is ended.
    connection.execute(
        "INSERT INTO extractions (run_id, document_id, status, failure_reason,"
        " model, prompt_version, schema_version, from_cache, input_tokens,"
        " cached_input_tokens, output_tokens, cost_usd, total_seconds)"
        " SELECT jobs.run_id, jobs.document_id, 'failed', %s,"
        " runs.config -> 'model' ->> 'name', runs.config ->> 'prompt_version', %s,"
        " false, 0, 0, 0, 0, extract(epoch FROM now() - jobs.taken_at)"
        " FROM jobs JOIN runs ON runs.id = jobs.run_id WHERE jobs.id = %s",
        (reason, SCHEMA_VERSION, job.id),
    )
    connection.execute(
        "UPDATE jobs SET state = 'failed', failure_reason = %s,"
        " finished_at = now(), taken_at = NULL, taken_until = NULL WHERE id = %s",
        (reason, job.id),
    )
    add_event(connection, "failed", job, reason)
    complete_run_if_ended(connection, job.run_id)


def complete_run_if_ended(
    connection: psycopg.Connection[TupleRow], run_id: UUID
) -> None:
    """Marks the run complete when none of its jobs is waiting or running."""
    # Locked before looking, so that two workers ending a run's last two jobs at
    # once do not each still see the other's job running, and both pass.
    connection.execute("SELECT 1 FROM runs WHERE id = %s FOR UPDATE", (run_id,))
    connection.execute(
        "UPDATE runs SET status = 'complete', finished_at = now()"
        " WHERE id = %s AND status = 'running' AND NOT EXISTS ("
        " SELECT 1 FROM jobs WHERE run_id = %s AND state IN ('queued', 'running'))",
        (run_id, run_id),
    )


def read_ended_jobs(
    connection: psycopg.Connection[TupleRow], run_id: UUID
) -> list[tuple[UUID, str, str]]:
    """Each ended job of a run, in the order they ended: job, file name, status."""
    rows = connection.execute(
        "SELECT jobs.id, documents.file_name, extractions.status FROM jobs"
        " JOIN documents ON documents.id = jobs.document_id"
        " JOIN extractions ON extractions.run_id = jobs.run_id"
        " AND extractions.document_id = jobs.document_id"
        " WHERE jobs.run_id = %s AND jobs.state IN ('succeeded', 'failed')"
        " ORDER BY jobs.finished_at",
        (run_id,),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def add_event(
    connection: psycopg.Connection[TupleRow],
    event: str,
    job: Job,
    reason: str | None,
) -> None:
    """Writes the audit row of a change to a job's state."""
    connection.execute(
        "INSERT INTO audit_events (event, job_id, run_id, document_id, attempt, reason)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (event, job.id, job.run_id, job.document_id, job.attempt, reason),
    )
