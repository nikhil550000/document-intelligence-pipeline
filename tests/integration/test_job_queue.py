"""Tests for the job queue, on the real Postgres, with several connections."""

import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from docintel.storage.jobs import (
    ABANDONED,
    MAX_ATTEMPTS,
    Job,
    JobLostError,
    add_jobs,
    claim_job,
    extend_job,
    give_up_abandoned,
    mark_failed,
    mark_succeeded,
    return_job,
)
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations

HOUR = timedelta(hours=1)
# The code the test runs are made from, and the workers built from it.
CODE = "c" * 64


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to a database that has every table."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def queue_run(connection: psycopg.Connection, how_many: int) -> UUID:
    """Writes a run and that many documents, queues a job for each, returns the run."""
    run = connection.execute(
        "INSERT INTO runs (config_name, config, git_commit, code_sha256,"
        " contract_list, cost_ceiling_usd)"
        " VALUES ('a-config', %s, %s, %s, 'smoke', 1) RETURNING id",
        (Jsonb({"model": {"name": "a-model"}, "prompt_version": 1}), "b" * 40, CODE),
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


def run_status(connection: psycopg.Connection, run_id: UUID) -> str:
    """The run's status."""
    row = connection.execute("SELECT status FROM runs WHERE id = %s", (run_id,))
    found = row.fetchone()
    assert found is not None
    status: str = found[0]
    return status


def extraction_of(connection: psycopg.Connection, job: Job) -> tuple:
    """The job's contract as stored: status, reason, model, prompt, request."""
    row = connection.execute(
        "SELECT status, failure_reason, model, prompt_version, request_sha256"
        " FROM extractions WHERE run_id = %s AND document_id = %s",
        (job.run_id, job.document_id),
    ).fetchone()
    assert row is not None
    return row


def held_for(connection: psycopg.Connection, job: Job) -> timedelta:
    """How long after it was taken the job is held until."""
    row = connection.execute(
        "SELECT taken_until - taken_at FROM jobs WHERE id = %s", (job.id,)
    ).fetchone()
    assert row is not None
    held: timedelta = row[0]
    return held


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
                job = claim_job(own_connection, HOUR, CODE)
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
            first = claim_job(connection, HOUR, CODE)
            second = claim_job(other, HOUR, CODE)

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
        job = claim_job(connection, HOUR, CODE)
        assert job is not None
        claimed.append(job.id)

    assert claimed == [row[0] for row in queued]
    assert claim_job(connection, HOUR, CODE) is None


def test_a_worker_built_from_other_code_leaves_the_run_alone(
    connection: psycopg.Connection,
) -> None:
    """Its answers would not be the ones the run records, so it takes nothing."""
    queue_run(connection, 1)

    assert claim_job(connection, HOUR, "d" * 64) is None
    assert claim_job(connection, HOUR, CODE) is not None


def test_a_running_job_is_queued_again_only_once_past_its_time(
    connection: psycopg.Connection,
) -> None:
    """A job left running by a worker that died waits out its time, then runs again."""
    queue_run(connection, 1)
    job = claim_job(connection, HOUR, CODE)
    assert job is not None

    assert give_up_abandoned(connection) == []
    assert job_row(connection, job)[0] == "running"

    wait_passes(connection)
    assert give_up_abandoned(connection) == [job]
    assert job_row(connection, job)[:2] == ("queued", 1)

    # The first wait between attempts is a minute, so the job is not ready yet.
    assert claim_job(connection, HOUR, CODE) is None
    wait_passes(connection)
    second = claim_job(connection, HOUR, CODE)
    assert second is not None
    assert (second.id, second.attempt) == (job.id, 2)


def test_a_worker_that_lost_its_job_cannot_end_it(
    connection: psycopg.Connection,
) -> None:
    """A worker past its time, its job given to another, cannot mark that job."""
    queue_run(connection, 1)
    late = claim_job(connection, HOUR, CODE)
    assert late is not None
    wait_passes(connection)
    give_up_abandoned(connection)
    wait_passes(connection)
    current = claim_job(connection, HOUR, CODE)
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
        job = claim_job(connection, HOUR, CODE)
        assert job is not None
        assert job.attempt == attempt
        mark_failed(connection, job, f"timed out, attempt {attempt}")
        wait_passes(connection)

    assert job_row(connection, job) == ("failed", 3, "timed out, attempt 3")
    assert claim_job(connection, HOUR, CODE) is None
    # The contract is stored as failed, so the run's report still counts it.
    assert extraction_of(connection, job) == (
        "failed",
        "timed out, attempt 3",
        "a-model",
        "1",
        None,
    )
    assert run_status(connection, job.run_id) == "complete"


def test_a_job_given_up_on_its_last_attempt_is_stored_as_failed(
    connection: psycopg.Connection,
) -> None:
    """A contract that outlives its worker every time still ends, and is counted."""
    queue_run(connection, 1)
    for _ in range(MAX_ATTEMPTS):
        job = claim_job(connection, HOUR, CODE)
        assert job is not None
        wait_passes(connection)
        give_up_abandoned(connection)
        wait_passes(connection)

    assert job_row(connection, job) == ("failed", 3, ABANDONED)
    assert extraction_of(connection, job)[:2] == ("failed", ABANDONED)
    assert run_status(connection, job.run_id) == "complete"


def test_a_run_is_complete_once_its_last_job_has_ended(
    connection: psycopg.Connection,
) -> None:
    """One job ended leaves the run running; the second completes it."""
    run_id = queue_run(connection, 2)
    first = claim_job(connection, HOUR, CODE)
    second = claim_job(connection, HOUR, CODE)
    assert first is not None
    assert second is not None

    mark_succeeded(connection, first)
    assert run_status(connection, run_id) == "running"
    mark_succeeded(connection, second)
    assert run_status(connection, run_id) == "complete"


def test_two_workers_ending_the_last_two_jobs_at_once_complete_the_run(
    connection: psycopg.Connection, database_url: str
) -> None:
    """The second waits for the first to commit, so it sees both jobs ended."""
    run_id = queue_run(connection, 2)
    first = claim_job(connection, HOUR, CODE)
    second = claim_job(connection, HOUR, CODE)
    assert first is not None
    assert second is not None

    def end_second() -> None:
        with psycopg.connect(database_url, autocommit=True) as other:
            assert second is not None
            mark_succeeded(other, second)

    with connection.transaction():
        mark_succeeded(connection, first)
        other_worker = threading.Thread(target=end_second)
        other_worker.start()
        # Time for the other worker to look at the run while this one has not
        # committed; without the lock it would see the first job still running.
        time.sleep(0.5)
    other_worker.join()

    assert run_status(connection, run_id) == "complete"


def test_the_heartbeat_holds_a_job_but_never_past_its_longest_time(
    connection: psycopg.Connection,
) -> None:
    """Each heartbeat moves the time on, up to the cap; a lost job is not moved."""
    queue_run(connection, 1)
    job = claim_job(connection, timedelta(minutes=2), CODE)
    assert job is not None

    assert extend_job(connection, job, timedelta(minutes=2), HOUR)
    assert held_for(connection, job) > timedelta(minutes=1)
    assert extend_job(connection, job, timedelta(minutes=2), timedelta(seconds=30))
    assert held_for(connection, job) == timedelta(seconds=30)

    wait_passes(connection)
    give_up_abandoned(connection)
    assert not extend_job(connection, job, timedelta(minutes=2), HOUR)


def test_a_returned_job_keeps_its_attempts_and_a_stopped_run_is_not_taken(
    connection: psycopg.Connection,
) -> None:
    """A job its run's ceiling could not pay for waits, uncounted, for the run."""
    run_id = queue_run(connection, 1)
    job = claim_job(connection, HOUR, CODE)
    assert job is not None

    with connection.transaction():
        return_job(connection, job, "the ceiling was reached")
        connection.execute(
            "UPDATE runs SET status = 'stopped', stop_reason = 'ceiling' WHERE id = %s",
            (run_id,),
        )

    assert job_row(connection, job) == ("queued", 0, None)
    assert claim_job(connection, HOUR, CODE) is None
    connection.execute(
        "UPDATE runs SET status = 'running', stop_reason = NULL WHERE id = %s",
        (run_id,),
    )
    again = claim_job(connection, HOUR, CODE)
    assert again is not None
    assert (again.id, again.attempt) == (job.id, 1)
    assert events_of(connection, again)[2] == (
        "queued_again",
        1,
        "the ceiling was reached",
    )


def test_every_change_of_state_has_its_audit_row(
    connection: psycopg.Connection,
) -> None:
    """Queued, started, queued again, given up, started, succeeded: seven rows."""
    queue_run(connection, 1)
    first = claim_job(connection, HOUR, CODE)
    assert first is not None
    mark_failed(connection, first, "server error")
    wait_passes(connection)
    second = claim_job(connection, HOUR, CODE)
    assert second is not None
    wait_passes(connection)
    give_up_abandoned(connection)
    wait_passes(connection)
    third = claim_job(connection, HOUR, CODE)
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
