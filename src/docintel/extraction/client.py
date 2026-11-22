"""Sends a request to a model, with a time limit and retries, and counts the calls."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import openai

from docintel.config import Settings


class ModelCallError(Exception):
    """The model gave no answer: every attempt failed, or the request was refused."""


@dataclass(frozen=True)
class RetrySettings:
    """How long one call may take, and how often a failed call is tried again."""

    timeout_seconds: float
    max_attempts: int
    # The wait before the second attempt. It doubles before each one after that.
    first_wait_seconds: float


def make_sdk(settings: Settings, base_url: str) -> openai.OpenAI:
    """Returns the OpenAI SDK pointed at a provider, with its own retries off.

    Raises:
        ModelCallError: No key for the provider is set.
    """
    key = ""
    if settings.fireworks_api_key is not None:
        key = settings.fireworks_api_key.get_secret_value()
    if not key:
        raise ModelCallError("No model key: set FIREWORKS_API_KEY in .env.")
    # Retries are done here, so that each attempt can be counted and paid for.
    return openai.OpenAI(base_url=base_url, api_key=key, max_retries=0)


class ModelClient:
    """Sends requests and keeps count of how many reached the provider."""

    def __init__(
        self,
        sdk: openai.OpenAI,
        retry: RetrySettings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Keeps the SDK and the retry settings; `sleep` is replaced in tests."""
        self.sdk = sdk
        self.retry = retry
        self.sleep = sleep
        self.calls = 0

    def complete(self, request: dict[str, Any]) -> bytes:
        """Sends the request and returns the provider's response as it came.

        Raises:
            ModelCallError: The provider refused the request, or every attempt
                timed out, was rate limited, or met a server or network error.
        """
        wait = self.retry.first_wait_seconds
        attempt = 1
        while True:
            self.calls += 1
            try:
                response = self.sdk.chat.completions.with_raw_response.create(
                    **request, timeout=self.retry.timeout_seconds
                )
                return response.http_response.content
            except (
                openai.APIConnectionError,
                openai.RateLimitError,
                openai.InternalServerError,
            ) as error:
                if attempt == self.retry.max_attempts:
                    raise ModelCallError(
                        f"{describe(error)} on the last of {attempt} attempts"
                    ) from error
            except openai.APIStatusError as error:
                # Sent again, it would be refused the same way.
                raise ModelCallError(f"refused: {error}") from error
            self.sleep(wait)
            wait = wait * 2
            attempt += 1


def describe(error: openai.APIError) -> str:
    """Names a passing failure in a few words, for the reason a contract failed."""
    if isinstance(error, openai.APITimeoutError):
        return "timed out"
    if isinstance(error, openai.APIStatusError):
        return f"error {error.status_code}"
    return "could not connect"
