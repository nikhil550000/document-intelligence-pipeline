"""Tests for reading CUAD's answer file."""

import csv
from pathlib import Path

import pytest

from docintel.domain.fields import ALL_FIELDS
from docintel.evaluation.cuad import (
    CUAD_COLUMN_NAMES,
    MASTER_CLAUSES_PATH,
    CuadAnswer,
    answer_column_name,
    load_cuad_answers,
)

# CUAD's header for the notice period answer has a space before "Answer".
NOTICE_PERIOD_ANSWER_COLUMN = "Notice Period To Terminate Renewal- Answer"


def write_master_clauses(path: Path, contracts: dict[str, dict[str, str]]) -> None:
    """Writes a CSV with CUAD's columns. `contracts` maps a file name to cell values.

    Any column not given a value is written empty.
    """
    header = ["Filename"]
    for passage_column_name in CUAD_COLUMN_NAMES.values():
        header.append(passage_column_name)
        header.append(answer_column_name(passage_column_name))

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=header, restval="")
        writer.writeheader()
        for file_name, cells in contracts.items():
            writer.writerow({"Filename": file_name, **cells})


def test_every_field_has_a_cuad_column() -> None:
    """The table covers exactly the 41 fields, so no field is read twice or missed."""
    assert set(CUAD_COLUMN_NAMES) == {field.name for field in ALL_FIELDS}


def test_answer_column_name_adds_the_suffix() -> None:
    """Most answer columns are the passage column's name plus "-Answer"."""
    assert answer_column_name("Governing Law") == "Governing Law-Answer"


def test_answer_column_name_follows_the_stray_space() -> None:
    """The notice period answer column is spelled differently from the others."""
    column = answer_column_name("Notice Period To Terminate Renewal")
    assert column == NOTICE_PERIOD_ANSWER_COLUMN


def test_passage_and_answer_are_returned_unchanged(tmp_path: Path) -> None:
    """Quotes, commas, brackets and blanks come back exactly as they were written."""
    path = tmp_path / "master_clauses.csv"
    write_master_clauses(
        path,
        {
            "first.pdf": {
                "Governing Law": "['laws of the State of Nevada, USA']",
                "Governing Law-Answer": "Nevada",
                "Non-Compete": "[]",
                "Non-Compete-Answer": "No",
                NOTICE_PERIOD_ANSWER_COLUMN: "60 days",
            },
            "second.pdf": {"Agreement Date": "['May 8, 2014']"},
        },
    )

    answers = load_cuad_answers(path)

    assert list(answers) == ["first.pdf", "second.pdf"]
    first = answers["first.pdf"]
    assert first["governing_law"] == CuadAnswer(
        passage="['laws of the State of Nevada, USA']", answer="Nevada"
    )
    assert first["non_compete"] == CuadAnswer(passage="[]", answer="No")
    assert first["notice_to_terminate_renewal"] == CuadAnswer(
        passage="", answer="60 days"
    )
    assert answers["second.pdf"]["agreement_date"] == CuadAnswer(
        passage="['May 8, 2014']", answer=""
    )
    assert len(first) == 41


# CI does not have the dataset, so this test only runs where it was downloaded.
@pytest.mark.skipif(
    not MASTER_CLAUSES_PATH.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_real_file_has_the_published_counts() -> None:
    """Counts of answers on the real file, as found by reading it by hand."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)
    assert len(answers) == 510

    def is_empty(text: str) -> bool:
        # CUAD writes an empty list as "[]", in answer cells as well as passage cells.
        return text in ("", "[]")

    # Field: (has an answer, passage only, neither).
    expected = {
        "document_name": (510, 0, 0),
        "parties": (509, 0, 1),
        "agreement_date": (465, 7, 38),
        "effective_date": (359, 34, 117),
        "expiration_date": (329, 86, 95),
        "renewal_term": (163, 16, 331),
        "notice_to_terminate_renewal": (100, 12, 398),
        "governing_law": (433, 7, 70),
    }
    for field_name, expected_counts in expected.items():
        has_answer = 0
        passage_only = 0
        neither = 0
        for answers_by_field in answers.values():
            cuad_answer = answers_by_field[field_name]
            if not is_empty(cuad_answer.answer):
                has_answer += 1
            elif not is_empty(cuad_answer.passage):
                passage_only += 1
            else:
                neither += 1
        assert (has_answer, passage_only, neither) == expected_counts, field_name
