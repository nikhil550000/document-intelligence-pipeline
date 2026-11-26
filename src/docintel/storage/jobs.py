"""The job queue: one row per contract to process, taken by one worker at a time.

Every time is the database's clock, so workers on machines whose clocks differ
still agree on when a job is ready or abandoned.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import psycopg
from psycopg.rows import TupleRow

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
    connection: psycopg.Connection[TupleRow], longest: timedelta
) -> Job | None:
    """Takes the oldest job that is ready, or returns None when there is none.

    Args:
        connection: The worker's connection.
        longest: The longest this worker can take over the job. Past it, the job
            is given up as abandoned.
    """
    with connection.transaction():
        # A row another worker is taking right now is skipped, not waited for.
        row = connection.execute(
            "SELECT id, run_id, document_id, attempt FROM jobs"
            " WHERE state = 'queued' AND available_at <= now()"
            " ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
        ).fetchone()
        if row is None:
            return None
        job = Job(id=row[0], run_id=row[1], document_id=row[2], attempt=row[3] + 1)
        connection.execute(
            "UPDATE jobs SET state = 'running', attempt = %s, taken_at = now(),"
            " taken_until = now() + %s WHERE id = %s",
            (job.attempt, longest, job.id),
        )
        add_event(connection, "started", job, None)
    return job


def mark_succeeded(connection: psycopg.Connection[TupleRow], job: Job) -> None:
    """Ends the job as done.

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


def give_up_abandoned(connection: psycopg.Connection[TupleRow]) -> list[Job]:
    """Ends every running job past its time, as a failed attempt, and returns them."""
    with connection.transaction():
        rows = connection.execute(
            "SELECT id, run_id, document_id, attempt FROM jobs"
            " WHERE state = 'running' AND taken_until < now()"
            " FOR UPDATE SKIP LOCKED"
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
    """Queues the job again after its wait, or fails it after its last attempt."""
    if job.attempt < MAX_ATTEMPTS:
        wait = WAITS_BETWEEN_ATTEMPTS[job.attempt - 1]
        connection.execute(
            "UPDATE jobs SET state = 'queued', available_at = now() + %s,"
            " taken_at = NULL, taken_until = NULL WHERE id = %s",
            (wait, job.id),
        )
        add_event(connection, "queued_again", job, reason)
    else:
        connection.execute(
            "UPDATE jobs SET state = 'failed', failure_reason = %s,"
            " finished_at = now(), taken_at = NULL, taken_until = NULL WHERE id = %s",
            (reason, job.id),
        )
        add_event(connection, "failed", job, reason)


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
