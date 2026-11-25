"""Tests for the request and the prompt it carries."""

import json

from docintel.domain.fields import ALL_FIELDS
from docintel.domain.record import ContractRecord
from docintel.extraction.request import read_prompt


def test_the_prompt_defines_every_field_once() -> None:
    """Each field has one line of definition, so none is left to guessing."""
    prompt = read_prompt(1)

    for field in ALL_FIELDS:
        assert prompt.count(f"- `{field.name}`: ") == 1


def test_the_prompt_ends_with_the_schema_of_the_record() -> None:
    """The model reads the schema too, as the provider advises."""
    prompt = read_prompt(1)

    schema_text = prompt.split("# The schema\n\n")[1]
    assert json.loads(schema_text) == ContractRecord.model_json_schema()
