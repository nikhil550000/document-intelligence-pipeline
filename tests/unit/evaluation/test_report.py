"""Tests for the result files and the report computed from them."""

import random
from decimal import Decimal
from pathlib import Path

import pytest

from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.evaluation.metrics import add_up_by_field, score_report
from docintel.evaluation.report import (
    ContractResult,
    compute_report,
    export_run,
    intervals_from_files,
    write_report,
)
from docintel.evaluation.scoring import Counts


def made_up_run(
    contracts: int, seed: int
) -> tuple[
    list[tuple[str, str, int, int, int, str | None]], dict[str, dict[str, Counts]]
]:
    """Counts for every field of some contracts: as score rows, and by contract."""
    generator = random.Random(seed)
    rows: list[tuple[str, str, int, int, int, str | None]] = []
    by_contract: dict[str, dict[str, Counts]] = {}
    for number in range(contracts):
        contract = f"contract_{number}.pdf"
        by_contract[contract] = {}
        for field in ALL_FIELDS:
            # A few fields are skipped, and some are never answered or never found.
            if generator.random() < 0.05:
                rows.append((contract, field.name, 0, 0, 0, "redacted"))
                continue
            counts = Counts(
                generator.choice([0, 0, 1, 1, 2]) if field.name != "insurance" else 0,
                generator.choice([0, 0, 0, 1]),
                generator.choice([0, 0, 1]) if field.name != "audit_rights" else 0,
            )
            rows.append(
                (
                    contract,
                    field.name,
                    counts.true_positives,
                    counts.false_positives,
                    counts.false_negatives,
                    None,
                )
            )
            by_contract[contract][field.name] = counts
    return rows, by_contract


def contract_results(names: list[str]) -> list[ContractResult]:
    """Every contract answered, but the first, which failed."""
    results = []
    for number, name in enumerate(names):
        results.append(
            ContractResult(
                contract=name,
                status="failed" if number == 0 else "valid",
                answered=number != 0,
                reason="timed out on the last of 4 attempts" if number == 0 else None,
                from_cache=number % 2 == 0,
                input_tokens=1000,
                cached_input_tokens=200,
                output_tokens=100,
                cost_usd=Decimal("0.0010"),
                total_seconds=float(number),
            )
        )
    return results


def test_the_sql_scores_equal_the_python_scores_on_the_same_counts(
    tmp_path: Path,
) -> None:
    """Two separate ways of computing the scores must agree to the last digit."""
    rows, by_contract = made_up_run(contracts=60, seed=7)
    export_run(tmp_path, rows, contract_results(list(by_contract)))

    sql = compute_report(tmp_path)
    python = score_report(add_up_by_field(list(by_contract.values())))

    assert [line.name for line in sql.by_field] == [field.name for field in ALL_FIELDS]
    for line in sql.by_field:
        assert line.scores == python.scores_by_field[line.name], line.name
    for line in sql.by_field_type:
        assert line.scores == python.scores_by_field_type[FieldType(line.name)]
    assert sql.micro.scores == python.micro
    assert sql.macro.precision == pytest.approx(python.macro.precision)
    assert sql.macro.recall == pytest.approx(python.macro.recall)
    assert sql.macro.f1 == pytest.approx(python.macro.f1)
    # A field never answered has no precision; one with nothing to find no recall.
    assert python.scores_by_field["insurance"].precision is not None
    assert python.scores_by_field["audit_rights"].recall is not None


def test_the_report_counts_contracts_skips_and_cost(tmp_path: Path) -> None:
    """Answered out of attempted, the failure's reason, the skips and the money."""
    rows, by_contract = made_up_run(contracts=10, seed=3)
    export_run(tmp_path, rows, contract_results(list(by_contract)))

    report = compute_report(tmp_path)

    assert (report.attempted, report.answered) == (10, 9)
    assert report.statuses == {"failed": 1, "valid": 9}
    assert report.unanswered == [
        ("contract_0.pdf", "failed", "timed out on the last of 4 attempts")
    ]
    skipped = 0
    for row in rows:
        if row[5] is not None:
            skipped += 1
    assert sum(count for _, _, count in report.skips) == skipped
    assert report.cost_usd == Decimal("0.0100")
    assert report.spent_usd == Decimal("0.0050")
    assert report.seconds_median == 4.5


def test_the_report_is_written_as_markdown_and_csv(tmp_path: Path) -> None:
    """Both files hold every field, with intervals, next to the result files."""
    rows, by_contract = made_up_run(contracts=20, seed=5)
    export_run(tmp_path, rows, contract_results(list(by_contract)))

    write_report(
        tmp_path,
        "a configuration on dev",
        ["Run of a made-up configuration."],
        compute_report(tmp_path),
        intervals_from_files(tmp_path),
    )

    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert markdown.startswith("# a configuration on dev\n")
    assert "Contracts answered: **19 of 20**" in markdown
    assert "timed out on the last of 4 attempts" in markdown
    for field in ALL_FIELDS:
        assert f"| `{field.name}` |" in markdown
    csv_lines = (tmp_path / "report.csv").read_text(encoding="utf-8").splitlines()
    # A header, 41 fields, 6 field types, micro and macro.
    assert len(csv_lines) == 1 + 41 + 6 + 2
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "contracts.parquet",
        "report.csv",
        "report.md",
        "scores.parquet",
    ]
