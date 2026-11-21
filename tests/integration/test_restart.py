"""Tests that stored data survives its service containers being replaced."""

import os
import subprocess
from typing import TYPE_CHECKING

import psycopg
import pytest

from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.objects import get_object, put_object

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

SERVICES = ["postgres", "objectstore"]


def container_ids() -> set[str]:
    """Returns the ids of the running service containers."""
    result = subprocess.run(
        ["docker", "compose", "ps", "--quiet", *SERVICES],
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.split())


# Replacing the containers takes a few seconds and interrupts anything else using
# them, so this runs only when asked for: pytest -m restart
@pytest.mark.restart
def test_a_stored_pdf_and_its_row_survive_recreated_containers(
    database_url: str, s3_client: "S3Client", bucket: str
) -> None:
    """Data is kept on the volumes, so it outlives the containers that wrote it."""
    apply_migrations(database_url, MIGRATIONS_FOLDER)
    # Storage never reads the content, so any bytes of a typical PDF's size will do.
    pdf = b"%PDF-1.7\n" + os.urandom(200_000)
    sha256 = put_object(s3_client, bucket, pdf)
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "INSERT INTO documents (sha256, file_name, byte_size)"
            " VALUES (%s, 'contract.pdf', %s) RETURNING id",
            (sha256, len(pdf)),
        ).fetchone()
    assert row is not None
    document_id = row[0]
    ids_before = container_ids()

    # Unnamed volumes are replaced too, so only the volumes the Compose file names
    # can carry the data over.
    subprocess.run(
        [
            "docker",
            "compose",
            "up",
            "--detach",
            "--force-recreate",
            "--renew-anon-volumes",
            "--wait",
        ],
        check=True,
    )

    # New containers, so what is read next can only have come from the volumes.
    ids_after = container_ids()
    assert len(ids_before) == 2
    assert ids_after.isdisjoint(ids_before)
    with psycopg.connect(database_url) as connection:
        stored = connection.execute(
            "SELECT sha256, file_name, byte_size FROM documents WHERE id = %s",
            (document_id,),
        ).fetchone()
    assert stored == (sha256, "contract.pdf", len(pdf))
    assert get_object(s3_client, bucket, sha256) == pdf
