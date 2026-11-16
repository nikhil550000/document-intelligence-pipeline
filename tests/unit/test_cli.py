"""Tests for the command-line entry point."""

import pytest
from typer.testing import CliRunner

from docintel import cli

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
