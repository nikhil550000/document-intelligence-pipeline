"""Tests for comparing party names and reading CUAD's parties answers."""

import pytest

from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.gold import PartyNames, Skipped, SkipRule
from docintel.evaluation.parties import (
    cut_parties_answer,
    read_parties_answer,
    same_party,
)


@pytest.mark.parametrize(
    ("answer", "names"),
    [
        (
            'Freeze Tag Inc. ("Company"); '
            'American Diabetes Association ("Association")',
            ("Freeze Tag Inc.", "American Diabetes Association"),
        ),
        (
            'Skype Communications, S.A. ("Skype"); '
            'TOM Online (BVI) limited("Online BVI")',
            ("Skype Communications, S.A.", "TOM Online (BVI) limited"),
        ),
        (
            'VERIZON ABS LLC ("Depositor"); Cellco Partnership d/b/a Verizon Wireless '
            '("Cellco", "Servicer", "Marketing Agent", "Custodian")',
            ("VERIZON ABS LLC", "Cellco Partnership"),
        ),
        (
            "Tate & Lyle PLC; Rubio's Fresh Mexican Grill",
            ("Tate & Lyle PLC", "Rubio's Fresh Mexican Grill"),
        ),
    ],
)
def test_the_name_is_the_text_in_front_of_the_alias(
    answer: str, names: tuple[str, ...]
) -> None:
    """The alias, a trading name and role words are dropped; a bare name is kept."""
    assert read_parties_answer(answer) == PartyNames(names)


def test_curly_quotation_marks_start_the_alias() -> None:
    """Some answers use curly quotation marks around the alias."""
    answer = "Leader Act Ltd (“LEADER”); EZJR, Inc. (“EZJR”);"
    assert read_parties_answer(answer) == PartyNames(("Leader Act Ltd", "EZJR, Inc."))


def test_one_extra_opening_bracket_is_dropped() -> None:
    """A bracket that is never closed is a slip of the highlight, not of the name."""
    answer = '(DGT Corp. ("DGT"); Dolphin Industries Limited ("Dolphin")'
    assert read_parties_answer(answer) == PartyNames(
        ("DGT Corp.", "Dolphin Industries Limited")
    )


@pytest.mark.parametrize(
    "answer",
    [
        'MiddleBrook Pharmaceuticals, Inc. ("MBRK"); (collectively "Parties")',
        'Howmedica Ostenonics Corp. ("Stryker"); Conformis, Inc. ("Conformis"); '
        "Stryker and Conformis (“Parties” and   individually as a “Party.”)",
        'Morgan Stanley & Co. Incorporated ("MS"); MSCI Inc. ("MSCI"); '
        'MS and MSCI individually as "Party" and collectively as the "Parties"',
        'XACCT Technologies, Inc. ("XACCT"); [] ("Licensee")',
        'B & C General Warehouse Corporation LLC ("Company"); '
        'XXXXXXXXXXXXXXXXXXXXX ("Distributor")',
    ],
)
def test_a_piece_that_names_no_party_is_dropped(answer: str) -> None:
    """The pieces after the first name the parties together, or leave a party blank."""
    gold = read_parties_answer(answer)
    assert isinstance(gold, PartyNames)
    assert len(gold.names) == len(cut_parties_answer(answer)) - 1


def test_pieces_with_only_an_alias_are_dropped() -> None:
    """Roles with no name in front name no party."""
    answer = (
        'Kiosk Concepts, Inc. ("Franchisor"); ("Master Franchisee"); ("Guarantors")'
    )
    assert read_parties_answer(answer) == PartyNames(("Kiosk Concepts, Inc.",))


def test_an_answer_with_only_blanks_is_skipped_as_redacted() -> None:
    """A form contract leaves every party blank, so there is no name to find."""
    answer = '[] ("Franchisee"); [] ("Member")'
    assert read_parties_answer(answer) == Skipped(SkipRule.REDACTED)


@pytest.mark.parametrize(
    "answer", ["", 'Corio Inc. ("CORIO");; Commerce One, Inc.', '("Master Franchisee")']
)
def test_an_answer_with_an_empty_piece_or_no_party_raises(answer: str) -> None:
    """No CUAD answer has one, so it is a bug in the data."""
    with pytest.raises(ValueError):
        read_parties_answer(answer)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("The John Hopkins University", "John Hopkins University"),
        ("Corio Inc", "Corio Inc."),
        ("Cellco Partnership d/b/a Verizon Wireless", "Cellco Partnership"),
        ("Pretzel Time, Inc. doing business as Pretzel Time", "Pretzel Time, Inc."),
        ("Cellco Partnership d/b/a Verizon\nWireless", "Cellco Partnership"),
    ],
)
def test_names_that_are_the_same_party(first: str, second: str) -> None:
    """A leading "The", punctuation and a trading name do not matter."""
    assert same_party(first, second)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Morgan Stanley & Co. Inc.", "Morgan Stanley & Co. Incorporated"),
        ("CLARUS IV-A, L.P.", "CLARUS IV-B, L.P."),
        ("Corio", "Corio Inc."),
    ],
)
def test_names_that_are_only_close_are_different_parties(
    first: str, second: str
) -> None:
    """One contract has four parties that differ by one letter."""
    assert not same_party(first, second)


def test_the_is_dropped_only_as_a_word() -> None:
    """A name that starts with the letters "The" keeps them."""
    assert not same_party("Theravance, Inc.", "ravance, Inc.")


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_has_the_published_pieces() -> None:
    """Every parties answer reads, and only the one with every party blank skips."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)

    answer_count = 0
    piece_count = 0
    skipped = []
    for answers_by_field in answers.values():
        answer = answers_by_field["parties"].answer
        if answer in ("", "[]"):
            continue
        answer_count += 1
        piece_count += len(cut_parties_answer(answer))
        if isinstance(read_parties_answer(answer), Skipped):
            skipped.append(answer)

    assert (answer_count, piece_count) == (509, 1391)
    assert skipped == ['[] ("Franchisee"); [] ("Member")']
