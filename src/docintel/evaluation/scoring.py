"""Score a model's answer for one field of one contract against CUAD's answer."""

from dataclasses import dataclass
from datetime import date

from docintel.domain.fields import ALL_FIELDS, Field, FieldType
from docintel.domain.values import Duration, Perpetual
from docintel.evaluation.durations import same_duration
from docintel.evaluation.gold import GoldAnswer, NoAnswer, PartyNames, Skipped
from docintel.evaluation.names import same_name
from docintel.evaluation.parties import comparable_party
from docintel.evaluation.places import same_place

# The model's answer for one field. None is null: the contract does not say.
type ModelAnswer = date | Perpetual | Duration | str | bool | list[str] | None


@dataclass(frozen=True)
class Counts:
    """True positives, false positives and false negatives.

    A case gets counts and not one label, because a contract can name several
    parties and each name is scored on its own.
    """

    true_positives: int
    false_positives: int
    false_negatives: int


def score_answer(
    field: Field, gold: GoldAnswer, model_answer: ModelAnswer
) -> Counts | None:
    """Scores the model's answer for one field of one contract.

    Returns:
        The counts, or None when CUAD's answer is skipped: then nothing is
        counted, whatever the model answers.

    Raises:
        TypeError: The answer for the parties is not a list of names.
    """
    if isinstance(gold, Skipped):
        return None
    if isinstance(gold, PartyNames):
        return score_party_names(gold.names, model_answer)
    if field.type == FieldType.ENTITY_LIST:
        # CUAD names no party here, so every name the model gives is wrong.
        return score_party_names((), model_answer)
    if field.type == FieldType.CLAUSE and model_answer is False:
        # Present is the one answer a clause has; absent means none was found.
        model_answer = None

    if isinstance(gold, NoAnswer):
        if model_answer is None:
            return Counts(true_positives=0, false_positives=0, false_negatives=0)
        return Counts(true_positives=0, false_positives=1, false_negatives=0)
    if model_answer is None:
        return Counts(true_positives=0, false_positives=0, false_negatives=1)
    for value in gold.values:
        if is_same_value(field.type, value, model_answer):
            return Counts(true_positives=1, false_positives=0, false_negatives=0)
    # Something wrong was given, and the right answer was missed.
    return Counts(true_positives=0, false_positives=1, false_negatives=1)


def is_same_value(
    field_type: FieldType,
    value: date | Perpetual | Duration | str | bool,
    model_answer: ModelAnswer,
) -> bool:
    """Tells whether the model's answer equals one accepted value of a field type.

    An answer of another type, such as a date given for a duration, is never
    the same.
    """
    if field_type == FieldType.DURATION:
        if isinstance(value, Duration) and isinstance(model_answer, Duration):
            return same_duration(value, model_answer)
        return False
    if field_type == FieldType.TEXT:
        if isinstance(value, str) and isinstance(model_answer, str):
            return same_name(value, model_answer)
        return False
    if field_type == FieldType.JURISDICTION:
        if isinstance(value, str) and isinstance(model_answer, str):
            return same_place(value, model_answer)
        return False
    # Two dates are the same on the same calendar day; perpetual and a clause's
    # true are equal only to themselves.
    return value == model_answer


def score_party_names(cuad_names: tuple[str, ...], model_answer: ModelAnswer) -> Counts:
    """Scores the parties name by name. A name given twice in either list counts once.

    Raises:
        TypeError: The model's answer is neither null nor a list of names.
    """
    model_names: list[str] = []
    if isinstance(model_answer, list):
        model_names = model_answer
    elif model_answer is not None:
        # Read as a list, a string would give one false party for each letter.
        raise TypeError(f"the parties answer is a list of names: {model_answer!r}")

    cuad_parties = set()
    for name in cuad_names:
        cuad_parties.add(comparable_party(name))
    model_parties = set()
    for name in model_names:
        model_parties.add(comparable_party(name))
    return Counts(
        true_positives=len(cuad_parties.intersection(model_parties)),
        false_positives=len(model_parties.difference(cuad_parties)),
        false_negatives=len(cuad_parties.difference(model_parties)),
    )


def score_contract(
    gold_by_field: dict[str, GoldAnswer], model_answers: dict[str, ModelAnswer]
) -> dict[str, Counts]:
    """Scores every field of one contract. A skipped field gets no counts.

    Args:
        gold_by_field: CUAD's answers in scoring form, by field name.
        model_answers: The model's answer for every field, by field name.

    Raises:
        KeyError: The model's answers leave out a field. Null is given as None.
    """
    counts_by_field = {}
    for field in ALL_FIELDS:
        counts = score_answer(
            field, gold_by_field[field.name], model_answers[field.name]
        )
        if counts is not None:
            counts_by_field[field.name] = counts
    return counts_by_field
