"""CUAD's answers as database rows, and a stored record as the scorer's answers."""

import json
from datetime import date
from typing import Any

from docintel.domain.fields import ALL_FIELDS, Field, FieldType
from docintel.domain.record import (
    ClauseAnswer,
    ContractRecord,
    PartiesAnswer,
)
from docintel.domain.values import Duration, DurationUnit, Perpetual
from docintel.evaluation.gold import (
    AcceptedValues,
    GoldAnswer,
    NoAnswer,
    PartyNames,
    Skipped,
    SkipRule,
)
from docintel.evaluation.scoring import ModelAnswer, score_answer

# One field of one contract: its name, kind, skip rule and accepted values.
type GoldRow = tuple[str, str, str | None, list[Any] | None]


def gold_rows(gold_by_field: dict[str, GoldAnswer]) -> list[GoldRow]:
    """Turns one contract's answers in scoring form into rows, one per field."""
    rows: list[GoldRow] = []
    for field in ALL_FIELDS:
        gold = gold_by_field[field.name]
        if isinstance(gold, Skipped):
            rows.append((field.name, "skipped", gold.rule.value, None))
        elif isinstance(gold, NoAnswer):
            rows.append((field.name, "none", None, None))
        elif isinstance(gold, PartyNames):
            rows.append((field.name, "value", None, list(gold.names)))
        else:
            values = []
            for value in gold.values:
                values.append(value_as_json(value))
            rows.append((field.name, "value", None, values))
    return rows


def value_as_json(value: date | Perpetual | Duration | str | bool) -> Any:
    """Writes one accepted value in a form JSON can hold."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Perpetual):
        return value.value
    if isinstance(value, Duration):
        return {"amount": value.amount, "unit": value.unit.value}
    return value


def read_gold_row(
    field: Field, kind: str, skip_rule: str | None, accepted_values: list[Any] | None
) -> GoldAnswer:
    """Reads one row back into the scoring form it was made from.

    Raises:
        ValueError: The row's kind is not one the table allows.
    """
    if kind == "skipped" and skip_rule is not None:
        return Skipped(SkipRule(skip_rule))
    if kind == "none":
        return NoAnswer()
    if kind != "value" or accepted_values is None:
        raise ValueError(f"not a gold row: {kind!r} for {field.name}")
    if field.type == FieldType.ENTITY_LIST:
        return PartyNames(tuple(accepted_values))
    values = []
    for value in accepted_values:
        values.append(value_from_json(field.type, value))
    return AcceptedValues(tuple(values))


def value_from_json(
    field_type: FieldType, value: Any
) -> date | Perpetual | Duration | str | bool:
    """Reads one accepted value of a field type back from its JSON form."""
    if field_type == FieldType.DATE:
        if value == Perpetual.PERPETUAL.value:
            return Perpetual.PERPETUAL
        return date.fromisoformat(value)
    if field_type == FieldType.DURATION:
        return Duration(value["amount"], DurationUnit(value["unit"]))
    if isinstance(value, str | bool):
        return value
    raise ValueError(f"not a value of a {field_type.value} field: {value!r}")


def answers_of_record(record: dict[str, Any] | None) -> dict[str, ModelAnswer]:
    """Gives the scorer the model's answer for every field of a stored record.

    A contract with no record, because every call failed or the output did not
    load, answers null on every field: what CUAD has there counts as missed.
    """
    answers: dict[str, ModelAnswer] = {}
    if record is None:
        for field in ALL_FIELDS:
            answers[field.name] = None
        return answers

    # Read as JSON, the form it was stored in, so its dates are read as dates.
    read = ContractRecord.model_validate_json(json.dumps(record))
    for field in ALL_FIELDS:
        answer = getattr(read, field.name)
        if isinstance(answer, ClauseAnswer):
            answers[field.name] = answer.present
        elif isinstance(answer, PartiesAnswer):
            answers[field.name] = answer.names
        else:
            answers[field.name] = answer.value
    return answers


def score_rows(
    gold_by_field: dict[str, GoldAnswer], answers: dict[str, ModelAnswer]
) -> list[tuple[str, int, int, int, str | None]]:
    """Scores every field of one contract, as rows: field, the three counts, rule.

    A skipped field keeps a row with its rule and no counts, so the report can
    say how many cases each rule left out.
    """
    rows: list[tuple[str, int, int, int, str | None]] = []
    for field in ALL_FIELDS:
        gold = gold_by_field[field.name]
        if isinstance(gold, Skipped):
            rows.append((field.name, 0, 0, 0, gold.rule.value))
            continue
        counts = score_answer(field, gold, answers[field.name])
        # Only a skipped answer gets no counts, and it was handled above.
        assert counts is not None
        rows.append(
            (
                field.name,
                counts.true_positives,
                counts.false_positives,
                counts.false_negatives,
                None,
            )
        )
    return rows
