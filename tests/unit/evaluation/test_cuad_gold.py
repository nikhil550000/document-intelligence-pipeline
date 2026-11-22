"""Tests for turning CUAD's answers into the form in which they are scored."""

from datetime import date
from pathlib import Path

import pytest

from docintel.domain.fields import ALL_FIELDS, CLAUSE_FIELDS, FieldType
from docintel.domain.values import Duration, DurationUnit, Perpetual
from docintel.evaluation.contracts import LEFT_OUT
from docintel.evaluation.cuad import (
    MASTER_CLAUSES_PATH,
    CuadAnswer,
    load_cuad_answers,
)
from docintel.evaluation.cuad_gold import (
    CUAD_HAS_NOTHING,
    SCORED,
    count_scored_and_skipped,
    read_gold_answer,
    read_gold_answers,
)
from docintel.evaluation.gold import (
    AcceptedValues,
    GoldAnswer,
    NoAnswer,
    PartyNames,
    Skipped,
    SkipRule,
)
from docintel.evaluation.parties import comparable_party
from docintel.evaluation.splits import read_list

FIELDS = {field.name: field for field in ALL_FIELDS}
PASSAGE = "['the text a person highlighted']"


def made_up_contract(**cells: CuadAnswer) -> dict[str, CuadAnswer]:
    """CUAD's cells for one made-up contract: no clause and no other answer."""
    answers_by_field = {}
    for field in ALL_FIELDS:
        if field.type == FieldType.CLAUSE:
            answers_by_field[field.name] = CuadAnswer("[]", "No")
        else:
            answers_by_field[field.name] = CuadAnswer("[]", "")
    answers_by_field.update(cells)
    return answers_by_field


def test_a_written_answer_gives_the_values_that_count_as_right() -> None:
    """The model is right when it gives the date CUAD wrote."""
    gold = read_gold_answer(
        FIELDS["agreement_date"], CuadAnswer("['May 8, 2014']", "5/8/14")
    )
    assert gold == AcceptedValues((date(2014, 5, 8),))


def test_a_written_answer_that_is_redacted_is_skipped() -> None:
    """The contract leaves the day and month blank, so there is no date to find."""
    gold = read_gold_answer(
        FIELDS["agreement_date"],
        CuadAnswer("['_____ day of __________________, 2020']", "[]/[]/2020"),
    )
    assert gold == Skipped(SkipRule.REDACTED)


@pytest.mark.parametrize("answer", ["", "[]"])
@pytest.mark.parametrize("passage", ["", "[]"])
def test_no_answer_and_no_passage_is_cuad_has_nothing(
    answer: str, passage: str
) -> None:
    """Nothing was highlighted, so a value from the model is something wrong."""
    gold = read_gold_answer(FIELDS["expiration_date"], CuadAnswer(passage, answer))
    assert gold == NoAnswer()


@pytest.mark.parametrize("answer", ["", "[]"])
def test_a_passage_with_no_answer_is_skipped(answer: str) -> None:
    """A person highlighted text and wrote no value, so there is nothing to compare."""
    passage = "['until the date of expiration of the last to expire patent']"
    gold = read_gold_answer(FIELDS["expiration_date"], CuadAnswer(passage, answer))
    assert gold == Skipped(SkipRule.PASSAGE_ONLY)


@pytest.mark.parametrize(
    ("field_name", "answer", "expected"),
    [
        (
            "document_name",
            "SPONSORSHIP AGREEMENT",
            AcceptedValues(("SPONSORSHIP AGREEMENT",)),
        ),
        (
            "parties",
            'Corio Inc. ("CORIO"); Commerce One, Inc. ("COMMERCE ONE")',
            PartyNames(("Corio Inc.", "Commerce One, Inc.")),
        ),
        ("expiration_date", "Perpetual", AcceptedValues((Perpetual.PERPETUAL,))),
        (
            "renewal_term",
            "successive 1 year",
            AcceptedValues((Duration(1, DurationUnit.YEARS),)),
        ),
        (
            "notice_to_terminate_renewal",
            "60) days",
            AcceptedValues((Duration(60, DurationUnit.DAYS),)),
        ),
        (
            "governing_law",
            "Illinois; New York",
            AcceptedValues(("Illinois", "New York")),
        ),
        ("parties", '[] ("Franchisee"); [] ("Member")', Skipped(SkipRule.REDACTED)),
        ("renewal_term", "perpetual", Skipped(SkipRule.PERPETUAL_RENEWAL)),
        (
            "renewal_term",
            "7/22/2019; 7/22/2022",
            Skipped(SkipRule.DATE_IN_A_DURATION_FIELD),
        ),
        (
            "governing_law",
            "THE STATE IN WHICH THE FRANCHISED RESTAURANT IS LOCATED; "
            "THE UNITED STATES TRADEMARK ACT OF 1946",
            Skipped(SkipRule.NO_NAMED_PLACE),
        ),
    ],
)
def test_each_answer_is_read_by_the_reader_of_its_field_type(
    field_name: str, answer: str, expected: GoldAnswer
) -> None:
    """Each reader knows how CUAD wrote one kind of value; its skips come through."""
    assert read_gold_answer(FIELDS[field_name], CuadAnswer(PASSAGE, answer)) == expected


def test_a_clause_yes_is_the_one_value_that_counts_as_right() -> None:
    """The model is right when it says the clause is present."""
    gold = read_gold_answer(FIELDS["non_compete"], CuadAnswer(PASSAGE, "Yes"))
    assert gold == AcceptedValues((True,))


def test_a_clause_no_is_cuad_has_nothing() -> None:
    """No such clause: finding one is wrong, and finding none counts nothing."""
    gold = read_gold_answer(FIELDS["non_compete"], CuadAnswer("[]", "No"))
    assert gold == NoAnswer()


@pytest.mark.parametrize("answer", ["", "[]", "yes", "N/A"])
def test_a_clause_answer_that_is_neither_yes_nor_no_raises(answer: str) -> None:
    """A clause is never skipped, so an answer that is not Yes or No is a fault."""
    with pytest.raises(ValueError):
        read_gold_answer(FIELDS["non_compete"], CuadAnswer(PASSAGE, answer))


def test_every_field_of_every_contract_is_read() -> None:
    """Each contract gets an answer in scoring form for each of the fields, in order."""
    answers = {
        "first.pdf": made_up_contract(),
        "second.pdf": made_up_contract(
            agreement_date=CuadAnswer("['May 8, 2014']", "5/8/14")
        ),
    }

    gold_answers = read_gold_answers(answers)

    assert list(gold_answers) == ["first.pdf", "second.pdf"]
    assert list(gold_answers["first.pdf"]) == [field.name for field in ALL_FIELDS]
    assert gold_answers["first.pdf"]["agreement_date"] == NoAnswer()
    assert gold_answers["second.pdf"]["agreement_date"] == AcceptedValues(
        (date(2014, 5, 8),)
    )


def test_counts_are_for_the_given_contracts_only() -> None:
    """A field is counted as scored, under its skip rule, or as CUAD has nothing."""
    gold_answers = read_gold_answers(
        {
            "scored.pdf": made_up_contract(
                agreement_date=CuadAnswer("['May 8, 2014']", "5/8/14")
            ),
            "redacted.pdf": made_up_contract(
                agreement_date=CuadAnswer("['____, 2020']", "[]/[]/2020")
            ),
            "passage only.pdf": made_up_contract(
                agreement_date=CuadAnswer("['the date of the Closing']", "")
            ),
        }
    )

    counts = count_scored_and_skipped(gold_answers, ["scored.pdf", "redacted.pdf"])

    assert list(counts) == [
        "document_name",
        "parties",
        "agreement_date",
        "effective_date",
        "expiration_date",
        "renewal_term",
        "notice_to_terminate_renewal",
        "governing_law",
    ]
    assert counts["agreement_date"] == {SCORED: 1, "redacted": 1}
    assert counts["expiration_date"] == {CUAD_HAS_NOTHING: 2}


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_is_scored_and_skipped_as_counted_by_hand() -> None:
    """Every answer reads, and each list has the counts found by reading the file."""
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))
    dev = read_list(Path("configs"), "dev")
    test = read_list(Path("configs"), "test")
    # A row is in one list, or left out of both with its reason.
    assert sorted(dev + test + list(LEFT_OUT)) == sorted(gold_answers)

    kinds = [SCORED]
    for rule in SkipRule:
        kinds.append(rule.value)
    kinds.append(CUAD_HAS_NOTHING)
    # Scored; skipped as redacted, passage only, perpetual renewal, date in a
    # duration field, no named place; CUAD has nothing.
    expected_dev = {
        "document_name": (96, 0, 0, 0, 0, 0, 0),
        "parties": (96, 0, 0, 0, 0, 0, 0),
        "agreement_date": (74, 11, 1, 0, 0, 0, 10),
        "effective_date": (57, 9, 8, 0, 0, 0, 22),
        "expiration_date": (53, 5, 19, 0, 0, 0, 19),
        "renewal_term": (29, 0, 3, 0, 0, 0, 64),
        "notice_to_terminate_renewal": (18, 0, 3, 0, 0, 0, 75),
        "governing_law": (85, 0, 0, 0, 0, 0, 11),
    }
    expected_test = {
        "document_name": (410, 0, 0, 0, 0, 0, 0),
        "parties": (408, 1, 0, 0, 0, 0, 1),
        "agreement_date": (340, 37, 6, 0, 0, 0, 27),
        "effective_date": (265, 25, 26, 0, 0, 0, 94),
        "expiration_date": (253, 16, 67, 0, 0, 0, 74),
        "renewal_term": (121, 2, 13, 10, 1, 0, 263),
        "notice_to_terminate_renewal": (82, 0, 9, 0, 0, 0, 319),
        "governing_law": (344, 1, 7, 0, 0, 1, 57),
    }
    skipped = 0
    for contracts, expected in [(dev, expected_dev), (test, expected_test)]:
        counts = count_scored_and_skipped(gold_answers, contracts)
        for field_name, expected_counts in expected.items():
            found = []
            for kind in kinds:
                found.append(counts[field_name][kind])
            assert tuple(found) == expected_counts, field_name
            skipped += sum(found[1:-1])
    assert skipped == 281

    clause_answers = []
    for gold_by_field in gold_answers.values():
        for field in CLAUSE_FIELDS:
            clause_answers.append(gold_by_field[field.name])
    yes_count = clause_answers.count(AcceptedValues((True,)))
    no_count = clause_answers.count(NoAnswer())
    assert (yes_count, no_count) == (3688, 13142)

    # A name given twice in one answer is one party.
    names = {"dev": 0, "test": 0}
    for list_name, contracts in [("dev", dev), ("test", test)]:
        for contract in contracts:
            gold = gold_answers[contract]["parties"]
            if isinstance(gold, PartyNames):
                distinct_names = {comparable_party(name) for name in gold.names}
                names[list_name] += len(distinct_names)
    assert names == {"dev": 273, "test": 986}
