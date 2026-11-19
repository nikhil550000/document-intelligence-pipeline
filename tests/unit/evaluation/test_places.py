"""Tests for comparing place names and reading CUAD's governing law answers."""

import pytest

from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.gold import AcceptedValues, Skipped, SkipRule
from docintel.evaluation.places import (
    comparable_place,
    read_governing_law_answer,
    same_place,
)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("State of New York", "New York"),
        ("New York, USA", "New York"),
        ("the State of New York", "New York"),
        ("Commonwealth of Massachusetts", "Massachusetts"),
        ("Province of Ontario, Canada", "Ontario"),
        ("Ontario, Canada", "Ontario"),
        ("British Columbia,Canada", "British Columbia"),
        ("Republic of South Africa", "South Africa"),
    ],
)
def test_words_around_the_place_are_dropped(first: str, second: str) -> None:
    """Words such as "State of" in front, and a country after a comma, do not matter."""
    assert same_place(first, second)


def test_district_of_columbia_is_untouched() -> None:
    """Only the listed words in front are dropped."""
    assert comparable_place("District of Columbia") == "districtofcolumbia"


@pytest.mark.parametrize(
    "spelling",
    [
        "England",
        "Wales",
        "England; Wales",
        "England, United Kingdom; Wales, United Kingdom",
        "England and Wales, UK",
    ],
)
def test_every_way_cuad_writes_england_and_wales_is_one_place(spelling: str) -> None:
    """England and Wales are one legal system."""
    assert same_place(spelling, "England and Wales")


@pytest.mark.parametrize(
    ("spelling", "place"),
    [
        ("PRC", "People's Republic of China"),
        ("China", "People's Republic of China"),
        ("Federal Republic of Germany", "Germany"),
        ("Republic of China", "Taiwan"),
        ("R.O.C.", "Taiwan"),
        ("United States of America", "United States"),
        ("Massachussets", "Massachusetts"),
    ],
)
def test_names_for_the_same_place_are_equal(spelling: str, place: str) -> None:
    """Each spelling was seen in CUAD's answers or in the passages behind them."""
    assert same_place(spelling, place)


def test_the_republic_of_china_is_not_china() -> None:
    """It is Taiwan, though dropping "Republic of" alone would give China."""
    assert not same_place("Republic of China", "China")
    assert not same_place("R.O.C.", "People's Republic of China")


def test_a_sentence_is_not_a_place_name() -> None:
    """Only the place is compared, so a model that answers with a sentence is wrong."""
    assert not same_place("the laws of the State of New York", "New York")


def test_one_place_is_kept_as_written() -> None:
    """The accepted place stays readable in an error report."""
    assert read_governing_law_answer("Beijing") == AcceptedValues(("Beijing",))


@pytest.mark.parametrize(
    ("answer", "places"),
    [
        ("Delaware, Illinois", ("Delaware", "Illinois")),
        ("Illinois; New York", ("Illinois", "New York")),
        ("Texas; Singapore; Belgium", ("Texas", "Singapore", "Belgium")),
        ("New York; Massachussets", ("New York", "Massachussets")),
    ],
)
def test_an_answer_with_several_places_is_right_on_any_one(
    answer: str, places: tuple[str, ...]
) -> None:
    """The answer is cut at each `;`, and at a comma no country follows."""
    assert read_governing_law_answer(answer) == AcceptedValues(places)


@pytest.mark.parametrize(
    "answer",
    [
        "Ontario, Canada",
        "England; Wales",
        "England, United Kingdom; Wales, United Kingdom",
    ],
)
def test_one_place_with_a_separator_in_it_is_not_cut(answer: str) -> None:
    """A country after a comma, or England and Wales in two pieces, is one place."""
    assert read_governing_law_answer(answer) == AcceptedValues((answer,))


def test_a_piece_that_is_not_a_place_is_dropped() -> None:
    """Only California is accepted."""
    answer = "California; the state in which the breach occurs"
    assert read_governing_law_answer(answer) == AcceptedValues(("California",))


def test_an_answer_with_no_named_place_is_skipped() -> None:
    """Neither piece names a place."""
    answer = (
        "THE STATE IN WHICH THE FRANCHISED RESTAURANT IS LOCATED;"
        " THE UNITED STATES TRADEMARK ACT OF 1946"
    )
    assert read_governing_law_answer(answer) == Skipped(SkipRule.NO_NAMED_PLACE)


def test_a_redacted_answer_is_skipped() -> None:
    """The place itself is blacked out."""
    assert read_governing_law_answer("[* * *]") == Skipped(SkipRule.REDACTED)


@pytest.mark.parametrize("answer", ["", "Delaware;;Illinois"])
def test_an_empty_piece_raises(answer: str) -> None:
    """No CUAD answer has one, so it is a bug in the data."""
    with pytest.raises(ValueError):
        read_governing_law_answer(answer)


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_has_the_published_shapes() -> None:
    """Every governing law answer reads, with the shapes found by hand."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)

    counts = {"one": 0, "several": 0, SkipRule.NO_NAMED_PLACE: 0, SkipRule.REDACTED: 0}
    england_and_wales = 0
    for answers_by_field in answers.values():
        answer = answers_by_field["governing_law"].answer
        if answer in ("", "[]"):
            continue
        gold = read_governing_law_answer(answer)
        if isinstance(gold, Skipped):
            counts[gold.rule] += 1
            continue
        if len(gold.values) == 1:
            counts["one"] += 1
        else:
            counts["several"] += 1
        if any(same_place(str(value), "England and Wales") for value in gold.values):
            england_and_wales += 1

    # 422 answers name one place and 9 name several. In 2 of the 9 a piece that is
    # not a place is dropped and one place is left, so 424 and 7 are read.
    assert tuple(counts.values()) == (424, 7, 1, 1)
    assert england_and_wales == 15
