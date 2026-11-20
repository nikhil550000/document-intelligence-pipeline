"""Tests for the command-line entry point."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from docintel import cli
from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.evaluation.cuad import CuadAnswer

runner = CliRunner()


@pytest.mark.parametrize(
    ("did_something", "expected_text"),
    [(True, "Dataset is ready"), (False, "Nothing to do")],
)
def test_data_download_reports_what_happened(
    monkeypatch: pytest.MonkeyPatch, did_something: bool, expected_text: str
) -> None:
    """The command prints a different message when the download function did nothing."""
    monkeypatch.setattr(cli, "ensure_dataset", lambda data_folder: did_something)

    result = runner.invoke(cli.app, ["data", "download"])

    assert result.exit_code == 0
    assert expected_text in result.output


def test_data_split_writes_the_lists_and_prints_the_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The command writes the three lists and names the fields it shows counts for."""
    answers = {}
    for number in range(120):
        answers[f"contract_{number:03}.pdf"] = {
            field.name: CuadAnswer(passage="[]", answer="No") for field in ALL_FIELDS
        }
    for number in range(10):
        answers[f"contract_{number:03}.pdf"]["non_compete"] = CuadAnswer("[]", "Yes")
    monkeypatch.setattr(cli, "load_cuad_answers", lambda path: answers)
    monkeypatch.setattr(cli, "CONFIG_FOLDER", tmp_path)

    result = runner.invoke(cli.app, ["data", "split"])

    assert result.exit_code == 0
    assert "Wrote 100 dev, 20 test and 5 smoke contracts" in result.output
    assert "non_compete" in result.output
    # Every other clause field has no positives, so the command must name them.
    assert "Under 3 in dev:" in result.output
    assert len((tmp_path / "dev.txt").read_text(encoding="utf-8").splitlines()) == 100


def counts_in_row(output: str, field_name: str, kind: str) -> list[str]:
    """Gives the all, dev and test counts in the row of a field and kind."""
    for line in output.splitlines():
        if line.startswith(field_name + " ") and kind in line:
            return line.split()[-3:]
    raise AssertionError(f"no row for {field_name}, {kind}")


def test_data_answers_prints_the_counts_for_all_dev_and_test(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Each field and kind that occurs gets a row, and a kind that never occurs none."""
    answers = {}
    for file_name in ["a.pdf", "b.pdf", "c.pdf"]:
        answers_by_field = {}
        for field in ALL_FIELDS:
            if field.type == FieldType.CLAUSE:
                answers_by_field[field.name] = CuadAnswer("[]", "No")
            else:
                answers_by_field[field.name] = CuadAnswer("[]", "")
        answers[file_name] = answers_by_field
    answers["a.pdf"]["agreement_date"] = CuadAnswer("['May 8, 2014']", "5/8/14")
    answers["b.pdf"]["agreement_date"] = CuadAnswer("['____, 2020']", "[]/[]/2020")
    answers["c.pdf"]["agreement_date"] = CuadAnswer("['the date of the Closing']", "")
    monkeypatch.setattr(cli, "load_cuad_answers", lambda path: answers)
    monkeypatch.setattr(cli, "CONFIG_FOLDER", tmp_path)
    (tmp_path / "dev.txt").write_text("a.pdf\n", encoding="utf-8")
    (tmp_path / "test.txt").write_text("b.pdf\nc.pdf\n", encoding="utf-8")

    result = runner.invoke(cli.app, ["data", "answers"])

    assert result.exit_code == 0
    assert counts_in_row(result.output, "agreement_date", "scored") == ["1", "1", "0"]
    redacted = counts_in_row(result.output, "agreement_date", "skipped: redacted")
    assert redacted == ["1", "0", "1"]
    passage_only = counts_in_row(
        result.output, "agreement_date", "skipped: passage only"
    )
    assert passage_only == ["1", "0", "1"]
    nothing = counts_in_row(result.output, "document_name", "CUAD has nothing")
    assert nothing == ["3", "1", "2"]
    assert "perpetual renewal" not in result.output
