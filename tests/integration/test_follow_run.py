"""Tests for following a run from the command line, and for carrying one on."""

import threading
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
import typer

from docintel.cli import follow_run
from docintel.storage import jobs
from docintel.storage.jobs import add_jobs, claim_job, mark_failed
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.runs import add_run, finish_run, resume_run

CODE = "c" * 64
HOUR = timedelta(hours=1)


@pytest.fixture
def connection(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[psycopg.Connection]:
    """A connection to a database with every table; attempts follow with no wait."""
    monkeypatch.setattr(jobs, "WAITS_BETWEEN_ATTEMPTS", (timedelta(0), timedelta(0)))
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection


def queue_run(connection: psycopg.Connection, file_names: list[str]) -> UUID:
    """Writes a run with one job for a document of each file name."""
    config = {"model": {"name": "a-model"}, "prompt_version": 1}
    run_id = add_run(
        connection, "a-config", config, "b" * 40, CODE, "smoke", Decimal(1)
    )
    document_ids = []
    for file_name in file_names:
        row = connection.execute(
            "INSERT INTO documents (sha256, file_name, byte_size)"
            " VALUES (%s, %s, 1000) RETURNING id",
            (uuid.uuid4().hex * 2, file_name),
        ).fetchone()
        assert row is not None
        document_ids.append(row[0])
    add_jobs(connection, run_id, document_ids)
    return run_id


def end_next_job(connection: psycopg.Connection) -> None:
    """Fails the next job on every attempt, which ends it with a stored contract."""
    for _ in range(jobs.MAX_ATTEMPTS):
        job = claim_job(connection, HOUR, CODE)
        assert job is not None
        mark_failed(connection, job, "timed out")


def run_row(connection: psycopg.Connection, run_id: UUID) -> tuple:
    """The run's status, stop reason, ceiling and whether it has finished."""
    row = connection.execute(
        "SELECT status, stop_reason, cost_ceiling_usd, finished_at IS NOT NULL"
        " FROM runs WHERE id = %s",
        (run_id,),
    ).fetchone()
    assert row is not None
    return row


def test_a_complete_run_prints_each_contract_and_how_it_ended(
    connection: psycopg.Connection, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each contract once, with its status, then the counts."""
    run_id = queue_run(connection, ["Alpha.pdf", "Beta.pdf"])
    end_next_job(connection)
    end_next_job(connection)

    assert follow_run(connection, run_id) is True

    assert capsys.readouterr().out.splitlines() == [
        "  failed       Alpha.pdf",
        "  failed       Beta.pdf",
        "Run complete: 2 contracts ended ({'failed': 2}).",
    ]


def test_a_run_that_is_still_going_is_followed_until_its_last_contract_ends(
    connection: psycopg.Connection,
    database_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The second contract ends while the run is followed, and is printed too."""
    run_id = queue_run(connection, ["Alpha.pdf", "Beta.pdf"])
    end_next_job(connection)

    def end_later() -> None:
        time.sleep(0.3)
        with psycopg.connect(database_url, autocommit=True) as other:
            end_next_job(other)

    other_worker = threading.Thread(target=end_later)
    other_worker.start()
    complete = follow_run(connection, run_id)
    other_worker.join()

    assert complete is True
    output = capsys.readouterr().out
    # Looked at again every second, but each contract is printed once.
    assert output.count("Alpha.pdf") == 1
    assert "  failed       Beta.pdf" in output
    assert output.endswith("Run complete: 2 contracts ended ({'failed': 2}).\n")


def test_a_stopped_run_says_why_and_how_to_carry_it_on(
    connection: psycopg.Connection, capsys: pytest.CaptureFixture[str]
) -> None:
    """It returns at once, without waiting for the contract still queued."""
    run_id = queue_run(connection, ["Alpha.pdf", "Beta.pdf"])
    end_next_job(connection)
    finish_run(connection, run_id, "stopped", "the ceiling was reached")

    assert follow_run(connection, run_id) is False

    assert capsys.readouterr().out.splitlines() == [
        "  failed       Alpha.pdf",
        "Run stopped: 1 contracts ended ({'failed': 1}).",
        "the ceiling was reached.",
        f"To carry it on: docintel resume {run_id} --ceiling-usd <more>",
    ]


def test_following_a_run_that_does_not_exist_ends_the_command(
    connection: psycopg.Connection,
) -> None:
    """A mistyped run id is said plainly, not followed for ever."""
    with pytest.raises(typer.Exit):
        follow_run(connection, UUID(int=1))


def test_resuming_a_stopped_run_lets_it_go_on_with_the_new_ceiling(
    connection: psycopg.Connection,
) -> None:
    """Its jobs can be taken again; a complete run is left as it is."""
    stopped = queue_run(connection, ["Alpha.pdf"])
    finish_run(connection, stopped, "stopped", "the ceiling was reached")
    assert claim_job(connection, HOUR, CODE) is None

    resume_run(connection, stopped, Decimal(5))

    assert run_row(connection, stopped) == ("running", None, Decimal(5), False)
    assert claim_job(connection, HOUR, CODE) is not None

    complete = queue_run(connection, ["Beta.pdf"])
    end_next_job(connection)
    resume_run(connection, complete, Decimal(5))
    assert run_row(connection, complete)[:3] == ("complete", None, Decimal(1))
