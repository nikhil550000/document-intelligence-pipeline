"""Object storage, where each object is kept under the SHA-256 of its content."""

import hashlib
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from docintel.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class CorruptObjectError(Exception):
    """An object's content does not match the hash it is stored under."""


def make_s3_client(settings: Settings) -> "S3Client":
    """Returns an S3 client for the configured endpoint and access key."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        # shortcut: a fixed region, which the local server ignores but signing
        # needs. Set from the settings when the store is a real AWS bucket.
        region_name="us-east-1",
        # A bucket name cannot go in front of a host such as localhost, so it goes
        # in the path.
        config=Config(s3={"addressing_style": "path"}),
    )


def put_object(client: "S3Client", bucket: str, content: bytes) -> str:
    """Stores the content under its SHA-256 and returns that hash."""
    sha256 = hashlib.sha256(content).hexdigest()
    client.put_object(Bucket=bucket, Key=sha256, Body=content)
    return sha256


def get_object(client: "S3Client", bucket: str, sha256: str) -> bytes:
    """Returns the content stored under the hash, after checking it against the hash.

    Raises:
        CorruptObjectError: The content does not hash to its key.
        botocore.exceptions.ClientError: Nothing is stored under the hash.
    """
    response = client.get_object(Bucket=bucket, Key=sha256)
    content = response["Body"].read()
    # The key promises the content, so a damaged object is caught here and not
    # passed on as a valid PDF or a valid model answer.
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != sha256:
        raise CorruptObjectError(
            f"Object {sha256} in bucket {bucket} has content with SHA-256 "
            f"{actual_sha256}."
        )
    return content
