"""Sends a request to a model, with a time limit and retries, and counts the calls."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import openai
from openai.types.chat import ChatCompletion
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from docintel.config import Settings
from docintel.extraction.budget import Budget
from docintel.extraction.prices import call_cost

tracer = trace.get_tracer(__name__)


class ModelCallError(Exception):
    """The model gave no answer: every attempt failed, or the request was refused."""


@dataclass(frozen=True)
class Completion:
    """What a response holds that the pipeline uses."""

    content: str
    # The model stopped at the length limit, so the content may end mid-way.
    cut_off: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


def read_completion(response: bytes) -> Completion:
    """Reads the answer and the token counts from a response as the provider sent it."""
    completion = ChatCompletion.model_validate_json(response)
    content = ""
    cut_off = False
    # No choice, or an empty message, is still an answer: one that is not a record.
    if completion.choices:
        content = completion.choices[0].message.content or ""
        cut_off = completion.choices[0].finish_reason == "length"
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    if completion.usage is not None:
        input_tokens = completion.usage.prompt_tokens
        output_tokens = completion.usage.completion_tokens
        details = completion.usage.prompt_tokens_details
        if details is not None and details.cached_tokens is not None:
            cached_input_tokens = details.cached_tokens
    return Completion(
        content, cut_off, input_tokens, cached_input_tokens, output_tokens
    )


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

    def complete(self, request: dict[str, Any], budget: Budget) -> bytes:
        """Sends the request and returns the provider's response as it came.

        Each attempt is paid for from the budget before it is sent, so neither
        the last call of a run nor its retries can go over the ceiling.

        Raises:
            CeilingReachedError: The budget cannot cover the next attempt.
            ModelCallError: The provider refused the request, or every attempt
                timed out, was rate limited, or met a server or network error.
        """
        wait = self.retry.first_wait_seconds
        attempt = 1
        while True:
            reserved = budget.reserve(request)
            self.calls += 1
            with tracer.start_as_current_span("model call") as span:
                span.set_attribute("docintel.attempt", attempt)
                span.set_attribute("docintel.cost.reserved_usd", float(reserved))
                try:
                    raw = self.sdk.chat.completions.with_raw_response.create(
                        **request, timeout=self.retry.timeout_seconds
                    )
                except (
                    openai.APIConnectionError,
                    openai.RateLimitError,
                    openai.InternalServerError,
                ) as error:
                    # A refusal for the rate is not charged. After a time-out or a
                    # server error the provider may have done the work, and billed it.
                    settled = reserved
                    if isinstance(error, openai.RateLimitError):
                        settled = Decimal(0)
                        budget.settle(reserved, settled)
                    mark_failed_call(span, describe(error), settled)
                    if attempt == self.retry.max_attempts:
                        raise ModelCallError(
                            f"{describe(error)} on the last of {attempt} attempts"
                        ) from error
                except openai.APIStatusError as error:
                    budget.settle(reserved, Decimal(0))
                    mark_failed_call(span, describe(error), Decimal(0))
                    # Sent again, it would be refused the same way.
                    raise ModelCallError(f"refused: {error}") from error
                else:
                    response = raw.http_response.content
                    completion = read_completion(response)
                    cost = call_cost(
                        budget.prices,
                        completion.input_tokens,
                        completion.cached_input_tokens,
                        completion.output_tokens,
                    )
                    budget.settle(reserved, cost)
                    span.set_attribute("docintel.outcome", "answered")
                    span.set_attribute("docintel.cost.settled_usd", float(cost))
                    return response
            self.sleep(wait)
            wait = wait * 2
            attempt += 1


def mark_failed_call(span: Span, outcome: str, settled_usd: Decimal) -> None:
    """Marks an attempt that got no answer, with what it stays counted at."""
    span.set_attribute("docintel.outcome", outcome)
    span.set_attribute("docintel.cost.settled_usd", float(settled_usd))
    span.set_status(Status(StatusCode.ERROR, outcome))


def describe(error: openai.APIError) -> str:
    """Names a passing failure in a few words, for the reason a contract failed."""
    if isinstance(error, openai.APITimeoutError):
        return "timed out"
    if isinstance(error, openai.APIStatusError):
        return f"error {error.status_code}"
    return "could not connect"
