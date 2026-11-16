"""Tests for the dev, test and smoke lists."""

from pathlib import Path

from docintel.domain.fields import ALL_FIELDS, CLAUSE_FIELD_NAMES
from docintel.evaluation.cuad import CuadAnswer
from docintel.evaluation.splits import (
    Splits,
    count_positives,
    find_positive_contracts,
    split_contracts,
    write_lists,
)

CONTRACTS = [f"contract_{number:02}.pdf" for number in range(30)]

# "rare" has 4 positives and "tiny" has 2, so only "tiny" cannot reach 3.
POSITIVES_BY_FIELD = {
    "common": set(CONTRACTS[:20]),
    "rare": {CONTRACTS[5], CONTRACTS[17], CONTRACTS[25], CONTRACTS[28]},
    "tiny": {CONTRACTS[3], CONTRACTS[11]},
}


def make_splits(seed: int = 2026) -> Splits:
    """Splits the made-up table into 10 dev, 20 test and 3 smoke contracts."""
    return split_contracts(
        CONTRACTS,
        POSITIVES_BY_FIELD,
        seed=seed,
        dev_size=10,
        smoke_size=3,
        min_positives_in_dev=3,
    )


def test_sizes_are_right() -> None:
    """Dev and test hold every contract between them, and smoke is part of dev."""
    splits = make_splits()

    assert len(splits.dev) == 10
    assert len(splits.test) == 20
    assert len(splits.smoke) == 3
    assert set(splits.smoke) <= set(splits.dev)


def test_no_contract_is_in_both_lists() -> None:
    """A contract used to choose settings must never be used to report them."""
    splits = make_splits()

    assert set(splits.dev).isdisjoint(splits.test)
    assert sorted(splits.dev + splits.test) == CONTRACTS


def test_every_field_reaches_the_minimum_where_it_can() -> None:
    """Fields with enough positives get 3 in dev; one with fewer gets all it has."""
    splits = make_splits()

    counts = count_positives(POSITIVES_BY_FIELD, splits.dev)

    assert counts["common"] >= 3
    assert counts["rare"] >= 3
    assert counts["tiny"] == 2


def test_same_seed_gives_the_same_lists() -> None:
    """Running the split again must not change the lists."""
    assert make_splits(seed=2026) == make_splits(seed=2026)


def test_a_different_seed_gives_different_lists() -> None:
    """The seed is really used."""
    assert make_splits(seed=2026).dev != make_splits(seed=7).dev


def test_lists_are_sorted() -> None:
    """Sorted lists give clean differences when they change."""
    splits = make_splits()

    assert splits.dev == sorted(splits.dev)
    assert splits.test == sorted(splits.test)
    assert splits.smoke == sorted(splits.smoke)


def test_positives_are_the_yes_answers_of_clause_fields() -> None:
    """Only a Yes counts, and only for clause fields."""
    answers = {}
    for contract, answer_text in [("yes.pdf", "Yes"), ("no.pdf", "No")]:
        answers[contract] = {
            field.name: CuadAnswer(passage="[]", answer=answer_text)
            for field in ALL_FIELDS
        }

    positives_by_field = find_positive_contracts(answers)

    assert list(positives_by_field) == list(CLAUSE_FIELD_NAMES)
    assert positives_by_field["non_compete"] == {"yes.pdf"}
    assert positives_by_field["insurance"] == {"yes.pdf"}


def test_count_positives_counts_only_the_given_contracts() -> None:
    """Counts are for the list asked about, not for all contracts."""
    counts = count_positives(POSITIVES_BY_FIELD, CONTRACTS[:10])

    assert counts == {"common": 10, "rare": 1, "tiny": 1}


def test_lists_are_written_one_name_per_line(tmp_path: Path) -> None:
    """Names with spaces and commas are kept whole, and line endings are always LF."""
    splits = Splits(
        dev=["Name, With Comma.pdf", "b.pdf"], test=["c.pdf"], smoke=["b.pdf"]
    )
    folder = tmp_path / "configs"

    write_lists(splits, folder)

    assert (folder / "dev.txt").read_bytes() == b"Name, With Comma.pdf\nb.pdf\n"
    assert (folder / "test.txt").read_bytes() == b"c.pdf\n"
    assert (folder / "smoke.txt").read_bytes() == b"b.pdf\n"
