"""Tests for comparing names and reading CUAD's document names."""

import pytest

from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.gold import AcceptedValues
from docintel.evaluation.names import (
    PART_BREAK,
    comparable_name,
    read_document_name_answer,
    same_name,
)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("SPONSORSHIP AGREEMENT", "Sponsorship Agreement"),
        ("CO-BRANDING", "Co Branding"),
        ("L.L.C.", "LLC"),
        ("SOFT WARE", "SOFTWARE"),
        (
            "FIRST AMENDMENT TO" + " " * 75 + "DISTRIBUTOR AGREEMENT",
            "First Amendment to Distributor Agreement",
        ),
        ("COLLABORATION AGREEMENT (“", "Collaboration Agreement"),
    ],
)
def test_only_letters_and_digits_are_compared(first: str, second: str) -> None:
    """Capitals, spacing, line breaks and punctuation do not matter."""
    assert same_name(first, second)


def test_accents_are_compared_as_they_are() -> None:
    """`Spôk` is not `Spok`."""
    assert not same_name("Spôk", "Spok")


def test_an_accent_written_as_a_separate_mark_is_still_an_accent() -> None:
    """`Spôk` is the same name however it is encoded, and still not `Spok`."""
    assert same_name("Spôk", "Spôk")
    assert not same_name("Spôk", "Spok")


def test_capitals_match_even_when_the_letter_changes_size() -> None:
    """`ß` is `SS` in capitals."""
    assert same_name("Straße GmbH", "STRASSE GMBH")


def test_a_mark_that_belongs_to_a_letter_is_kept() -> None:
    """The Hindi names Kumar and Kamar differ only by a vowel sign."""
    assert not same_name("कुमार", "कमर")


def test_the_whole_title_must_match() -> None:
    """A title that only contains the other is a different title."""
    assert not same_name(
        "FORM OF TRADEMARK LICENSE AGREEMENT", "Trademark License Agreement"
    )


def test_a_digit_is_part_of_the_name() -> None:
    """`Amendment No. 1` and `Amendment No. 2` are different documents."""
    assert comparable_name("AMENDMENT NO. 1") == "amendmentno1"
    assert not same_name("Amendment No. 1", "Amendment No. 2")


def test_a_title_is_kept_as_written_without_the_space_around_it() -> None:
    """The accepted title stays readable in an error report."""
    assert read_document_name_answer("  SPONSORSHIP AGREEMENT") == AcceptedValues(
        ("SPONSORSHIP AGREEMENT",)
    )


def test_a_title_in_parts_is_right_on_any_part_or_on_all_joined() -> None:
    """The amendment, the agreement it amends, and both in CUAD's order."""
    answer = "AMENDMENT NO. 1\n\nMANUFACTURING AGREEMENT"
    assert read_document_name_answer(answer) == AcceptedValues(
        (
            "AMENDMENT NO. 1",
            "MANUFACTURING AGREEMENT",
            "AMENDMENT NO. 1 MANUFACTURING AGREEMENT",
        )
    )


@pytest.mark.parametrize(
    ("answer", "title"),
    [
        (
            "AMENDMENT AND TERMINATION \n\nOF \n\nJOINT VENTURE AGREEMENT",
            "AMENDMENT AND TERMINATION OF JOINT VENTURE AGREEMENT",
        ),
        (
            "ADDENDUM TO \n\nZEBRA� PARTNERCONNECT DISTRIBUTOR AGREEMENT",
            "ADDENDUM TO ZEBRA� PARTNERCONNECT DISTRIBUTOR AGREEMENT",
        ),
    ],
)
def test_a_title_broken_over_lines_is_right_only_when_joined(
    answer: str, title: str
) -> None:
    """A part alone, such as `OF`, is not a title."""
    assert read_document_name_answer(answer) == AcceptedValues((title,))


def test_a_square_bracket_alone_is_not_a_redaction() -> None:
    """The version number in the title stays and the title is scored."""
    answer = "Software License Agreement [v.08.05.03]"
    assert read_document_name_answer(answer) == AcceptedValues((answer,))


@pytest.mark.parametrize("answer", ["", "[* * *]", "[]", "AMENDMENT\n\n"])
def test_an_answer_with_no_name_in_a_part_raises(answer: str) -> None:
    """The document name is never skipped, so this is a bug in the data."""
    with pytest.raises(ValueError):
        read_document_name_answer(answer)


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_has_the_published_shapes() -> None:
    """Every document name reads, with the shapes found by hand."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)
    raw_answers = [by_field["document_name"].answer for by_field in answers.values()]

    one_title = 0
    broken_over_lines = 0
    two_titles = 0
    for answer in raw_answers:
        gold = read_document_name_answer(answer)
        if PART_BREAK not in answer:
            assert len(gold.values) == 1, answer
            one_title += 1
        elif len(gold.values) == 1:
            broken_over_lines += 1
        else:
            # Each of the two titles, and both joined.
            assert len(gold.values) == 3, answer
            two_titles += 1
    assert (one_title, broken_over_lines, two_titles) == (496, 2, 12)

    assert len(set(raw_answers)) == 285
    assert len({comparable_name(answer) for answer in raw_answers}) == 243
