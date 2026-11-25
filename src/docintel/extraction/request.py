"""The request that asks a model for the record of one contract."""

import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from docintel.domain.record import ContractRecord

PROMPT_FOLDER = Path(__file__).parent

# Fixed, so that the same request gives as near the same answer as the model allows.
TEMPERATURE = 0


@dataclass(frozen=True)
class ModelSettings:
    """Which model answers, and the limits it answers within."""

    model: str
    # The longest answer allowed, in tokens. An answer cut off here is flagged.
    max_tokens: int
    # Thinking is turned off: with a schema the provider would not return it.
    reasoning_effort: str


def read_prompt(version: int) -> str:
    """Returns the instructions of one prompt version, with the record's schema in."""
    template = (PROMPT_FOLDER / f"prompt_v{version}.md").read_text(encoding="utf-8")
    schema = json.dumps(ContractRecord.model_json_schema(), indent=1)
    return Template(template).substitute(schema=schema)


def build_request(
    settings: ModelSettings, prompt_version: int, pages: tuple[str, ...]
) -> dict[str, Any]:
    """Builds the request body for one contract, read page by page.

    The instructions come first and the contract last, so that the part every
    request shares is one prefix, which the provider can reuse.
    """
    return {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": read_prompt(prompt_version)},
            {"role": "user", "content": "\n\n".join(pages)},
        ],
        # The provider holds the output to this schema while it is written.
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ContractRecord",
                "schema": ContractRecord.model_json_schema(),
            },
        },
        "temperature": TEMPERATURE,
        "max_tokens": settings.max_tokens,
        "reasoning_effort": settings.reasoning_effort,
    }
