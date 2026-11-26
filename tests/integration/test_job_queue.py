"""Tests for the job queue, on the real Postgres, with several connections."""

import threading
from collections.abc import Iterator
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest

from docintel.storage.jobs import (
    MAX_ATTEMPTS,
    Job,
    JobLostError,
    add_jobs,
    claim_job,
    give_up_abandoned,
    mark_failed,
    mark_succeeded,
)
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations

HOUR = timedelta(hours=1)


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to a database that has every table."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def queue_run(connection: psycopg.Connection, how_many: int) -> UUID:
    """Writes a run and that many documents, queues a job for each, returns the run."""
    run = connection.execute(
        "INSERT INTO runs"
        " (config_name, config, git_commit, contract_list, cost_ceiling_usd)"
        " VALUES ('a-config', '{}', %s, 'smoke', 1) RETURNING id",
        ("b" * 40,),
    ).fetchone()
    assert run is not None
    documents = connection.execute(
        "INSERT INTO documents (sha256, file_name, byte_size)"
        " SELECT md5(n::text) || md5(n::text), n || '.pdf', 1000"
        " FROM generate_series(1, %s) AS n RETURNING id",
        (how_many,),
    ).fetchall()
    run_id: UUID = run[0]
    add_jobs(connection, run_id, [row[0] for row in documents])
    return run_id


def wait_passes(connection: psycopg.Connection) -> None:
    """Moves every wait and time limit an hour back, as if an hour went by."""
    connection.execute(
        "UPDATE jobs SET available_at = available_at - interval '1 hour',"
        " taken_at = taken_at - interval '1 hour',"
        " taken_until = taken_until - interval '1 hour'"
    )


def job_row(connection: psycopg.Connection, job: Job) -> tuple:
    """The job's state, attempt and failure reason."""
    row = connection.execute(
        "SELECT state, attempt, failure_reason FROM jobs WHERE id = %s", (job.id,)
    ).fetchone()
    assert row is not None
    return row


def events_of(connection: psycopg.Connection, job: Job) -> list[tuple]:
    """The job's audit rows in the order they were written: event, attempt, reason."""
    return connection.execute(
        "SELECT event, attempt, reason FROM audit_events WHERE job_id = %s ORDER BY id",
        (job.id,),
    ).fetchall()


def test_two_workers_claiming_at_once_take_every_job_exactly_once(
    connection: psycopg.Connection, database_url: str
) -> None:
    """Each of 200 jobs is taken by one of the two workers, and none by both."""
    queue_run(connection, 200)
    taken: dict[str, list[UUID]] = {"first": [], "second": []}
    start = threading.Barrier(2)

    def work(name: str) -> None:
        with psycopg.connect(database_url, autocommit=True) as own_connection:
            start.wait()
            while True:
                job = claim_job(own_connection, HOUR)
                if job is None:
                    return
                taken[name].append(job.id)

    workers = [threading.Thread(target=work, args=(name,)) for name in taken]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    every_job = taken["first"] + taken["second"]
    assert len(every_job) == 200
    assert len(set(every_job)) == 200
    # Both took part, so the jobs were really shared and not taken by one alone.
    assert taken["first"]
    assert taken["second"]


def test_a_job_being_taken_is_skipped_by_another_worker_and_not_waited_for(
    connection: psycopg.Connection, database_url: str
) -> None:
    """While one worker's transaction holds the oldest job, another takes the next."""
    queue_run(connection, 2)
    with psycopg.connect(database_url, autocommit=True) as other:
        # Waiting for the lock would fail at once instead of hanging the test.
        other.execute("SET lock_timeout = '100ms'")
        with connection.transaction():
            first = claim_job(connection, HOUR)
            second = claim_job(other, HOUR)

    assert first is not None
    assert second is not None
    assert first.id != second.id


def test_the_oldest_ready_job_is_taken_first(connection: psycopg.Connection) -> None:
    """Jobs come out in the order they were queued."""
    queue_run(connection, 3)
    queued = connection.execute(
        "SELECT job_id FROM audit_events WHERE event = 'queued' ORDER BY id"
    ).fetchall()

    claimed = []
    for _ in range(3):
        job = claim_job(connection, HOUR)
        assert job is not None
        claimed.append(job.id)

    assert claimed == [row[0] for row in queued]
    assert claim_job(connection, HOUR) is None


def test_a_running_job_is_queued_again_only_once_past_its_time(
    connection: psycopg.Connection,
) -> None:
    """A job left running by a worker that died waits out its time, then runs again."""
    queue_run(connection, 1)
    job = claim_job(connection, HOUR)
    assert job is not None

    assert give_up_abandoned(connection) == []
    assert job_row(connection, job)[0] == "running"

    wait_passes(connection)
    assert give_up_abandoned(connection) == [job]
    assert job_row(connection, job)[:2] == ("queued", 1)

    # The first wait between attempts is a minute, so the job is not ready yet.
    assert claim_job(connection, HOUR) is None
    wait_passes(connection)
    second = claim_job(connection, HOUR)
    assert second is not None
    assert (second.id, second.attempt) == (job.id, 2)


def test_a_worker_that_lost_its_job_cannot_end_it(
    connection: psycopg.Connection,
) -> None:
    """A worker past its time, its job given to another, cannot mark that job."""
    queue_run(connection, 1)
    late = claim_job(connection, HOUR)
    assert late is not None
    wait_passes(connection)
    give_up_abandoned(connection)
    wait_passes(connection)
    current = claim_job(connection, HOUR)
    assert current is not None

    with pytest.raises(JobLostError):
        mark_succeeded(connection, late)
    with pytest.raises(JobLostError):
        mark_failed(connection, late, "too late")
    assert job_row(connection, current)[:2] == ("running", 2)


def test_a_job_that_keeps_failing_ends_failed_with_its_reason(
    connection: psycopg.Connection,
) -> None:
    """After its last attempt the job is failed with the last reason, and not taken."""
    queue_run(connection, 1)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        job = claim_job(connection, HOUR)
        assert job is not None
        assert job.attempt == attempt
        mark_failed(connection, job, f"timed out, attempt {attempt}")
        wait_passes(connection)

    assert job_row(connection, job) == ("failed", 3, "timed out, attempt 3")
    assert claim_job(connection, HOUR) is None


def test_every_change_of_state_has_its_audit_row(
    connection: psycopg.Connection,
) -> None:
    """Queued, started, queued again, given up, started, succeeded: seven rows."""
    queue_run(connection, 1)
    first = claim_job(connection, HOUR)
    assert first is not None
    mark_failed(connection, first, "server error")
    wait_passes(connection)
    second = claim_job(connection, HOUR)
    assert second is not None
    wait_passes(connection)
    give_up_abandoned(connection)
    wait_passes(connection)
    third = claim_job(connection, HOUR)
    assert third is not None
    mark_succeeded(connection, third)

    assert events_of(connection, third) == [
        ("queued", 0, None),
        ("started", 1, None),
        ("queued_again", 1, "server error"),
        ("started", 2, None),
        ("queued_again", 2, "abandoned: still running when its time ran out"),
        ("started", 3, None),
        ("succeeded", 3, None),
    ]
    assert job_row(connection, third) == ("succeeded", 3, None)


def test_audit_rows_cannot_be_changed_or_removed(
    connection: psycopg.Connection,
) -> None:
    """The database itself refuses an update, a delete and emptying the table."""
    queue_run(connection, 1)

    for statement in (
        "UPDATE audit_events SET reason = 'changed'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ):
        with pytest.raises(psycopg.errors.RaiseException):
            connection.execute(statement)
    assert connection.execute("SELECT count(*) FROM audit_events").fetchone() == (1,)
