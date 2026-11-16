"""Tests for the command-line entry point."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from docintel import cli
from docintel.domain.fields import ALL_FIELDS
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
