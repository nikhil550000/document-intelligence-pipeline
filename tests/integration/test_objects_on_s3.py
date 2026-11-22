"""Tests for storing and fetching objects by their hash on a real S3 server."""

import hashlib
from typing import TYPE_CHECKING

import pytest
from botocore.exceptions import ClientError

from docintel.storage.objects import CorruptObjectError, get_object, put_object

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def test_an_object_is_stored_under_its_sha256_and_comes_back_unchanged(
    s3_client: "S3Client", bucket: str
) -> None:
    """The key is the content's hash, so the same file is never stored twice."""
    content = b"%PDF-1.7 a few bytes"

    sha256 = put_object(s3_client, bucket, content)

    assert sha256 == hashlib.sha256(content).hexdigest()
    assert get_object(s3_client, bucket, sha256) == content


def test_an_object_that_does_not_match_its_hash_is_refused(
    s3_client: "S3Client", bucket: str
) -> None:
    """A damaged object is caught when read, and not passed on as a valid file."""
    wrong_key = hashlib.sha256(b"other content").hexdigest()
    s3_client.put_object(Bucket=bucket, Key=wrong_key, Body=b"damaged content")

    with pytest.raises(CorruptObjectError):
        get_object(s3_client, bucket, wrong_key)


def test_fetching_a_hash_that_was_never_stored_fails(
    s3_client: "S3Client", bucket: str
) -> None:
    """Asking for a file that was never stored is an error, not empty content."""
    with pytest.raises(ClientError):
        get_object(s3_client, bucket, "0" * 64)
