"""Turn every CUAD answer into the form in which it is scored."""

from collections import Counter

from docintel.domain.fields import ALL_FIELDS, NON_CLAUSE_FIELDS, Field, FieldType
from docintel.evaluation.cuad import CuadAnswer
from docintel.evaluation.dates import read_date_answer
from docintel.evaluation.durations import read_duration_answer
from docintel.evaluation.gold import (
    AcceptedValues,
    GoldAnswer,
    NoAnswer,
    Skipped,
    SkipRule,
)
from docintel.evaluation.names import read_document_name_answer
from docintel.evaluation.parties import read_parties_answer
from docintel.evaluation.places import read_governing_law_answer

# CUAD writes an empty list as "[]", in answer cells as well as passage cells.
EMPTY_CELLS = ("", "[]")

# A skipped case is counted under the name of its rule, the other cases under these.
SCORED = "scored"
CUAD_HAS_NOTHING = "CUAD has nothing"


def read_gold_answer(field: Field, cuad_answer: CuadAnswer) -> GoldAnswer:
    """Turns CUAD's answer for one field of one contract into its scoring form.

    Raises:
        ValueError: A clause answer is neither `Yes` nor `No`, or the reader of
            the field's type finds a piece it cannot read.
    """
    if field.type == FieldType.CLAUSE:
        return read_clause_answer(cuad_answer.answer)

    if cuad_answer.answer in EMPTY_CELLS:
        if cuad_answer.passage in EMPTY_CELLS:
            return NoAnswer()
        # A person highlighted text and wrote no value, so there is nothing to compare.
        return Skipped(SkipRule.PASSAGE_ONLY)

    answer = cuad_answer.answer
    if field.type == FieldType.TEXT:
        return read_document_name_answer(answer)
    if field.type == FieldType.ENTITY_LIST:
        return read_parties_answer(answer)
    if field.type == FieldType.DATE:
        return read_date_answer(answer, field.name)
    if field.type == FieldType.DURATION:
        return read_duration_answer(answer)
    if field.type == FieldType.JURISDICTION:
        return read_governing_law_answer(answer)


def read_clause_answer(answer: str) -> AcceptedValues | NoAnswer:
    """Reads CUAD's `Yes` or `No` for a clause field.

    Raises:
        ValueError: The answer is neither `Yes` nor `No`.
    """
    if answer == "Yes":
        return AcceptedValues((True,))
    if answer == "No":
        # The contract has no such clause: a model that finds one is wrong, and a
        # model that finds none counts nothing.
        return NoAnswer()
    raise ValueError(f"a clause answer is Yes or No: {answer!r}")


def read_gold_answers(
    answers: dict[str, dict[str, CuadAnswer]],
) -> dict[str, dict[str, GoldAnswer]]:
    """Turns every field of every contract into its scoring form.

    Returns:
        For each contract file name, the scoring form for each of our field names.
    """
    gold_answers = {}
    for contract, answers_by_field in answers.items():
        gold_by_field = {}
        for field in ALL_FIELDS:
            gold_by_field[field.name] = read_gold_answer(
                field, answers_by_field[field.name]
            )
        gold_answers[contract] = gold_by_field
    return gold_answers


def count_scored_and_skipped(
    gold_answers: dict[str, dict[str, GoldAnswer]], contracts: list[str]
) -> dict[str, Counter[str]]:
    """Counts how each field that is not a clause is treated in the given contracts.

    Returns:
        For each of those fields, how many contracts are scored, how many are
        skipped under each skip rule, named by the rule, and how many have nothing.
    """
    counts: dict[str, Counter[str]] = {}
    for field in NON_CLAUSE_FIELDS:
        counts[field.name] = Counter()

    for contract in contracts:
        for field in NON_CLAUSE_FIELDS:
            gold = gold_answers[contract][field.name]
            if isinstance(gold, Skipped):
                counts[field.name][gold.rule.value] += 1
            elif isinstance(gold, NoAnswer):
                counts[field.name][CUAD_HAS_NOTHING] += 1
            else:
                counts[field.name][SCORED] += 1
    return counts
