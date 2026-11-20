"""Split the contracts into the dev, test and smoke lists."""

import random
from dataclasses import dataclass
from pathlib import Path

from docintel.domain.fields import CLAUSE_FIELD_NAMES
from docintel.evaluation.cuad import CuadAnswer

# Fixed before the split was ever run, so it could not be chosen after seeing it.
SPLIT_SEED = 2026
DEV_SIZE = 100
SMOKE_SIZE = 5
MIN_POSITIVES_IN_DEV = 3


@dataclass(frozen=True)
class Splits:
    """The three lists of contract file names, each sorted."""

    dev: list[str]
    test: list[str]
    smoke: list[str]


def find_positive_contracts(
    answers: dict[str, dict[str, CuadAnswer]],
) -> dict[str, set[str]]:
    """Returns, for each clause field, the contracts where CUAD's answer is Yes."""
    positives_by_field: dict[str, set[str]] = {}
    for field_name in CLAUSE_FIELD_NAMES:
        positives_by_field[field_name] = set()

    for contract, answers_by_field in answers.items():
        for field_name in CLAUSE_FIELD_NAMES:
            if answers_by_field[field_name].answer == "Yes":
                positives_by_field[field_name].add(contract)
    return positives_by_field


def split_contracts(
    contracts: list[str],
    positives_by_field: dict[str, set[str]],
    seed: int,
    dev_size: int,
    smoke_size: int,
    min_positives_in_dev: int,
) -> Splits:
    """Picks the dev contracts so that every clause field has enough positives.

    Args:
        contracts: Every contract file name.
        positives_by_field: For each clause field, the contracts that are positive.
        seed: Seed for the shuffle.
        dev_size: How many contracts `dev` has when it is complete.
        smoke_size: How many contracts `smoke` has, taken from `dev`.
        min_positives_in_dev: The positives each field gets in `dev`, where the
            contracts have enough of them.
    """
    shuffled = sorted(contracts)
    random.Random(seed).shuffle(shuffled)

    # Rarest field first, so the contracts added for it also count for the
    # commoner fields. Fields with the same count go in alphabetical order.
    counts_and_names = []
    for field_name, positives in positives_by_field.items():
        counts_and_names.append((len(positives), field_name))
    counts_and_names.sort()

    dev: list[str] = []
    for _, field_name in counts_and_names:
        positives = positives_by_field[field_name]
        positives_in_dev = len(positives.intersection(dev))
        for contract in shuffled:
            if positives_in_dev >= min_positives_in_dev:
                break
            if contract in positives and contract not in dev:
                dev.append(contract)
                positives_in_dev += 1

    for contract in shuffled:
        if len(dev) >= dev_size:
            break
        if contract not in dev:
            dev.append(contract)

    # A seeded random sample of dev, not only the contracts added for rare fields.
    smoke: list[str] = []
    for contract in shuffled:
        if len(smoke) >= smoke_size:
            break
        if contract in dev:
            smoke.append(contract)

    test = sorted(set(contracts).difference(dev))
    return Splits(dev=sorted(dev), test=test, smoke=sorted(smoke))


def count_positives(
    positives_by_field: dict[str, set[str]], contracts: list[str]
) -> dict[str, int]:
    """Returns, for each clause field, how many of the given contracts are positive."""
    counts: dict[str, int] = {}
    for field_name, positives in positives_by_field.items():
        counts[field_name] = len(positives.intersection(contracts))
    return counts


def write_lists(splits: Splits, folder: Path) -> None:
    """Writes dev.txt, test.txt and smoke.txt, one contract file name per line."""
    folder.mkdir(exist_ok=True)
    lists = {"dev": splits.dev, "test": splits.test, "smoke": splits.smoke}
    for list_name, file_names in lists.items():
        text = "\n".join(file_names) + "\n"
        # The file is committed, so line endings must not depend on the machine.
        (folder / f"{list_name}.txt").write_text(text, encoding="utf-8", newline="\n")


def read_list(folder: Path, list_name: str) -> list[str]:
    """Reads back one list written by `write_lists`, such as "dev"."""
    # Git may check the file out with CRLF line endings; splitting on lines drops them.
    text = (folder / f"{list_name}.txt").read_text(encoding="utf-8")
    return text.splitlines()
