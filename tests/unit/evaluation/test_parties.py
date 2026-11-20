"""Tests for comparing party names and reading CUAD's parties answers."""

from collections import Counter

import pytest

from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.gold import PartyNames, Skipped, SkipRule
from docintel.evaluation.parties import (
    comparable_party,
    cut_parties_answer,
    read_parties_answer,
    same_party,
)
from docintel.evaluation.parties_by_hand import PARTIES_BY_HAND


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


@pytest.mark.parametrize(
    ("answer", "names"),
    [
        (
            'Dundee Securities Ltd.("Lead Agent"); Kes 7 Capital Inc. and Bloom Burton '
            '& Co. Ltd. (collectively with the Lead Agent, "Agents" and each '
            'individually an "Agent"); Tribute Pharmaceuticals Canada Inc. '
            '("Corporation")',
            (
                "Dundee Securities Ltd.",
                "Kes 7 Capital Inc.",
                "Bloom Burton & Co. Ltd.",
                "Tribute Pharmaceuticals Canada Inc.",
            ),
        ),
        (
            'Sekisui Diagnostics, LLC and its Affiliates ("Sekisui"); '
            'Qualigen, Inc. and its Affiliates ("Qualigen")',
            ("Sekisui Diagnostics, LLC", "Qualigen, Inc."),
        ),
        (
            "Geno Auriemma (Auriemma); "
            'Berkshire Bank (Berkshire)("Party" or "Parties")',
            ("Geno Auriemma", "Berkshire Bank"),
        ),
        (
            'Bank of America, N.A. ("Bank of America"); Supplier ("Supplier")',
            ("Bank of America, N.A.",),
        ),
        (
            "Bank of America Corporatino, "
            "Banc of America Preferred Funding Corporation",
            (
                "Bank of America Corporatino",
                "Banc of America Preferred Funding Corporation",
            ),
        ),
    ],
)
def test_pieces_read_by_hand_give_the_names_they_hold(
    answer: str, names: tuple[str, ...]
) -> None:
    """Several parties, words that are not the name, a short name, a role word."""
    assert read_parties_answer(answer) == PartyNames(names)


def test_names_read_by_hand_are_copied_from_their_piece() -> None:
    """A name is never corrected, so CUAD's own misspellings stay as written."""
    for piece, names in PARTIES_BY_HAND.items():
        for name in names:
            assert name in piece


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
        ('"The John Hopkins University"', "John Hopkins University"),
        ("The DBA Group", "DBA Group"),
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


def test_a_name_that_starts_with_dba_is_kept() -> None:
    """With no name in front, "DBA" is part of the legal name."""
    assert not same_party("DBA Group", "DBA Corporation")
    answer = 'DBA Group, Inc. ("Company"); Beta Inc. ("Buyer")'
    assert read_parties_answer(answer) == PartyNames(("DBA Group, Inc.", "Beta Inc."))


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_names_add_up() -> None:
    """Every answer reads, every piece read by hand is in the file, the names add up."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)

    pieces = []
    skipped = []
    names_given = 0
    names_per_contract = []
    for answers_by_field in answers.values():
        answer = answers_by_field["parties"].answer
        if answer in ("", "[]"):
            continue
        pieces.extend(cut_parties_answer(answer))
        gold = read_parties_answer(answer)
        if isinstance(gold, Skipped):
            skipped.append(answer)
            continue
        names_given += len(gold.names)
        # A name given twice in one answer is one party.
        distinct_names = {comparable_party(name) for name in gold.names}
        names_per_contract.append(len(distinct_names))

    missing_from_file = [piece for piece in PARTIES_BY_HAND if piece not in pieces]
    assert missing_from_file == []

    by_hand = [piece for piece in pieces if piece in PARTIES_BY_HAND]
    names_by_hand = 0
    for piece in by_hand:
        names_by_hand += len(PARTIES_BY_HAND[piece])
    # Each piece the rules read gives one name or none.
    names_by_rule = names_given - names_by_hand
    dropped = len(pieces) - len(by_hand) - names_by_rule
    assert (len(pieces), names_by_rule, len(by_hand), dropped) == (1391, 1213, 76, 102)

    assert skipped == ['[] ("Franchisee"); [] ("Member")']
    assert (len(names_per_contract), sum(names_per_contract)) == (508, 1269)
    # Five names or more are counted together.
    contracts_by_name_count = Counter(min(count, 5) for count in names_per_contract)
    assert contracts_by_name_count == {1: 28, 2: 403, 3: 38, 4: 19, 5: 20}
