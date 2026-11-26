"""Gives each test its own empty database and bucket on the local services."""

import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

import psycopg
import pytest
from botocore.exceptions import BotoCoreError, ClientError
from psycopg import sql
from psycopg.conninfo import make_conninfo
from pydantic import ValidationError

from docintel.config import Settings
from docintel.storage.objects import make_s3_client

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

START_SERVICES = "Start them with: docker compose up -d --wait postgres objectstore"


@pytest.fixture(scope="session")
def settings() -> Settings:
    """The settings from the environment or `.env`."""
    try:
        return Settings()
    except ValidationError:
        pytest.skip("No settings found. Copy .env.example to .env.")


@pytest.fixture(scope="session")
def server_url(settings: Settings) -> str:
    """The address of the Postgres server, once it has answered."""
    url = settings.database_url.get_secret_value()
    try:
        with psycopg.connect(url, connect_timeout=3):
            pass
    except psycopg.OperationalError:
        pytest.skip(f"Postgres cannot be reached. {START_SERVICES}")
    return url


@pytest.fixture(scope="session")
def s3_client(settings: Settings) -> "S3Client":
    """A client for the object store, once it has answered."""
    client = make_s3_client(settings)
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except (BotoCoreError, ClientError):
        pytest.skip(f"The object store cannot be reached. {START_SERVICES}")
    return client


@pytest.fixture
def database_url(server_url: str) -> Iterator[str]:
    """An empty database for one test, dropped afterwards."""
    name = f"test_{uuid.uuid4().hex}"
    create = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
    drop = sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
    with psycopg.connect(server_url, autocommit=True) as connection:
        connection.execute(create)
    yield make_conninfo(server_url, dbname=name)
    with psycopg.connect(server_url, autocommit=True) as connection:
        connection.execute(drop)


@pytest.fixture
def bucket(s3_client: "S3Client") -> Iterator[str]:
    """An empty bucket for one test, emptied and removed afterwards."""
    name = f"test-{uuid.uuid4().hex}"
    s3_client.create_bucket(Bucket=name)
    yield name
    # A test stores a handful of objects, well under one listing page of 1,000.
    listing = s3_client.list_objects_v2(Bucket=name)
    for stored in listing.get("Contents", []):
        s3_client.delete_object(Bucket=name, Key=stored["Key"])
    s3_client.delete_bucket(Bucket=name)
