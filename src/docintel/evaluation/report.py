"""A run's results as Parquet files, and its report computed from them in DuckDB."""

import csv
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import duckdb

from docintel.domain.fields import ALL_FIELDS, FieldType
from docintel.evaluation.intervals import (
    DRAWS,
    RESAMPLING_SEED,
    Interval,
    IntervalReport,
    ScoreIntervals,
    report_intervals,
)
from docintel.evaluation.metrics import LOW_SUPPORT_LIMIT, Scores
from docintel.evaluation.scoring import Counts

SCORES_FILE = "scores.parquet"
CONTRACTS_FILE = "contracts.parquet"


@dataclass(frozen=True)
class ContractResult:
    """How one contract of a run ended, and what it took."""

    contract: str
    status: str
    answered: bool
    # Why there is no record, or None when there is one.
    reason: str | None
    from_cache: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    total_seconds: float


@dataclass(frozen=True)
class Line:
    """One line of the report: what it is for, its counts and its scores."""

    name: str
    counts: Counts
    scores: Scores


@dataclass(frozen=True)
class SqlReport:
    """Everything the report's SQL computes from the result files."""

    by_field: list[Line]
    by_field_type: list[Line]
    micro: Line
    macro: Scores
    skips: list[tuple[str, str, int]]
    attempted: int
    answered: int
    statuses: dict[str, int]
    unanswered: list[tuple[str, str, str]]
    cost_usd: Decimal
    spent_usd: Decimal
    seconds_mean: float
    seconds_median: float
    seconds_95th: float


def export_run(
    folder: Path,
    scores: list[tuple[str, str, int, int, int, str | None]],
    contracts: list[ContractResult],
) -> None:
    """Writes the run's counts and contracts as Parquet files in the folder.

    Args:
        folder: Where the files go, next to the report made from them.
        scores: For each field of each contract: the contract, the field, the
            three counts and the skip rule, None when it was scored.
        contracts: How each contract of the run ended.
    """
    folder.mkdir(parents=True, exist_ok=True)
    positions = {}
    types = {}
    for position, field in enumerate(ALL_FIELDS):
        positions[field.name] = position
        types[field.name] = field.type.value
    score_rows = []
    for contract, field_name, true_pos, false_pos, false_neg, rule in scores:
        score_rows.append(
            (
                contract,
                positions[field_name],
                field_name,
                types[field_name],
                true_pos,
                false_pos,
                false_neg,
                rule,
            )
        )
    contract_rows = []
    for result in contracts:
        contract_rows.append(
            (
                result.contract,
                result.status,
                result.answered,
                result.reason,
                result.from_cache,
                result.input_tokens,
                result.cached_input_tokens,
                result.output_tokens,
                result.cost_usd,
                result.total_seconds,
            )
        )
    # DuckDB inserts Python rows one at a time; a CSV file it reads in one pass.
    with tempfile.TemporaryDirectory() as temporary, duckdb.connect() as database:
        tables = (
            (SCORES_FILE, SCORES_COLUMNS, score_rows),
            (CONTRACTS_FILE, CONTRACTS_COLUMNS, contract_rows),
        )
        for file_name, columns, rows in tables:
            csv_path = Path(temporary) / "rows.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as file:
                csv.writer(file).writerows(rows)
            # COPY takes no parameters; both paths are ours, so they are quoted here.
            source = csv_path.as_posix().replace("'", "''")
            target = (folder / file_name).as_posix().replace("'", "''")
            database.execute(
                f"COPY (SELECT * FROM read_csv('{source}', header = false,"
                f" columns = {columns}, nullstr = '')) TO '{target}' (FORMAT parquet)"
            )


SCORES_COLUMNS = {
    "contract": "VARCHAR",
    "field_position": "INTEGER",
    "field_name": "VARCHAR",
    "field_type": "VARCHAR",
    "true_positives": "INTEGER",
    "false_positives": "INTEGER",
    "false_negatives": "INTEGER",
    "skip_rule": "VARCHAR",
}

CONTRACTS_COLUMNS = {
    "contract": "VARCHAR",
    "status": "VARCHAR",
    "answered": "BOOLEAN",
    "reason": "VARCHAR",
    "from_cache": "BOOLEAN",
    "input_tokens": "INTEGER",
    "cached_input_tokens": "INTEGER",
    "output_tokens": "INTEGER",
    "cost_usd": "DECIMAL(12, 6)",
    "total_seconds": "DOUBLE",
}


# The three scores from summed counts, with nothing to divide by giving NULL.
SCORES_SQL = """
    CASE WHEN tp + fp > 0 THEN tp::DOUBLE / (tp + fp) END AS precision,
    CASE WHEN tp + fn > 0 THEN tp::DOUBLE / (tp + fn) END AS recall,
    CASE WHEN 2 * tp + fp + fn > 0 THEN 2 * tp::DOUBLE / (2 * tp + fp + fn) END
        AS f1
"""

FIELD_COUNTS_SQL = """
    SELECT field_position, field_name, field_type,
        sum(true_positives) AS tp, sum(false_positives) AS fp,
        sum(false_negatives) AS fn
    FROM read_parquet($scores)
    GROUP BY field_position, field_name, field_type
"""


def compute_report(folder: Path) -> SqlReport:
    """Computes the report's scores and counts with SQL over the result files."""
    # DuckDB refuses a parameter a query does not use, so each file has its own.
    scores_file = {"scores": (folder / SCORES_FILE).as_posix()}
    contracts_file = {"contracts": (folder / CONTRACTS_FILE).as_posix()}
    with duckdb.connect() as database:
        by_field = []
        for row in database.execute(
            f"SELECT field_name, tp, fp, fn, {SCORES_SQL}"
            f" FROM ({FIELD_COUNTS_SQL}) ORDER BY field_position",
            scores_file,
        ).fetchall():
            by_field.append(line_from_row(row))

        by_field_type = []
        rows = database.execute(
            f"SELECT field_type, tp, fp, fn, {SCORES_SQL} FROM ("
            "  SELECT field_type, sum(tp) AS tp, sum(fp) AS fp, sum(fn) AS fn"
            f"  FROM ({FIELD_COUNTS_SQL}) GROUP BY field_type)",
            scores_file,
        ).fetchall()
        lines_by_type = {}
        for row in rows:
            lines_by_type[row[0]] = line_from_row(row)
        for field_type in FieldType:
            by_field_type.append(lines_by_type[field_type.value])

        micro_row = database.execute(
            f"SELECT 'micro', tp, fp, fn, {SCORES_SQL} FROM ("
            "  SELECT sum(tp) AS tp, sum(fp) AS fp, sum(fn) AS fn"
            f"  FROM ({FIELD_COUNTS_SQL}))",
            scores_file,
        ).fetchone()
        # Plain means over the fields; AVG leaves out a NULL, a score with nothing
        # to divide by.
        macro_row = database.execute(
            "SELECT avg(precision), avg(recall), avg(f1) FROM ("
            f"  SELECT {SCORES_SQL} FROM ({FIELD_COUNTS_SQL}))",
            scores_file,
        ).fetchone()

        skips = database.execute(
            "SELECT field_name, skip_rule, count(*) FROM read_parquet($scores)"
            " WHERE skip_rule IS NOT NULL"
            " GROUP BY field_position, field_name, skip_rule"
            " ORDER BY field_position, skip_rule",
            scores_file,
        ).fetchall()

        summary = database.execute(
            "SELECT count(*), count(*) FILTER (WHERE answered),"
            " coalesce(sum(cost_usd), 0),"
            " coalesce(sum(cost_usd) FILTER (WHERE NOT from_cache), 0),"
            " avg(total_seconds), median(total_seconds),"
            " quantile_cont(total_seconds, 0.95)"
            " FROM read_parquet($contracts)",
            contracts_file,
        ).fetchone()
        statuses = dict(
            database.execute(
                "SELECT status, count(*) FROM read_parquet($contracts)"
                " GROUP BY status ORDER BY status",
                contracts_file,
            ).fetchall()
        )
        unanswered = database.execute(
            "SELECT contract, status, reason FROM read_parquet($contracts)"
            " WHERE NOT answered ORDER BY contract",
            contracts_file,
        ).fetchall()

    # An aggregate without GROUP BY always gives one row.
    assert micro_row is not None and macro_row is not None and summary is not None
    return SqlReport(
        by_field=by_field,
        by_field_type=by_field_type,
        micro=line_from_row(micro_row),
        macro=Scores(macro_row[0], macro_row[1], macro_row[2]),
        skips=[(row[0], row[1], row[2]) for row in skips],
        attempted=summary[0],
        answered=summary[1],
        statuses=statuses,
        unanswered=[(row[0], row[1], row[2]) for row in unanswered],
        cost_usd=summary[2],
        spent_usd=summary[3],
        seconds_mean=summary[4],
        seconds_median=summary[5],
        seconds_95th=summary[6],
    )


def line_from_row(row: tuple[object, ...]) -> Line:
    """Reads a row of name, three counts and three scores."""
    name, true_pos, false_pos, false_neg, precision, recall, f1 = row
    counts = Counts(int(str(true_pos)), int(str(false_pos)), int(str(false_neg)))
    return Line(
        str(name), counts, Scores(as_float(precision), as_float(recall), as_float(f1))
    )


def as_float(value: object) -> float | None:
    """Reads a score from SQL, where NULL means nothing to divide by."""
    if value is None:
        return None
    return float(str(value))


def intervals_from_files(folder: Path) -> IntervalReport:
    """Finds the 95% intervals by drawing the exported contracts again.

    Done in Python with the same code as every other interval, because drawing
    1,000 samples of contracts is awkward to say in SQL.
    """
    with duckdb.connect() as database:
        rows = database.execute(
            "SELECT contract, field_name, true_positives, false_positives,"
            " false_negatives FROM read_parquet($scores)"
            " WHERE skip_rule IS NULL",
            {"scores": (folder / SCORES_FILE).as_posix()},
        ).fetchall()
    counts_by_contract: dict[str, dict[str, Counts]] = {}
    for contract, field_name, true_pos, false_pos, false_neg in rows:
        counts_by_contract.setdefault(contract, {})[field_name] = Counts(
            true_pos, false_pos, false_neg
        )
    return report_intervals(counts_by_contract, RESAMPLING_SEED, DRAWS)


def percent(value: float | None) -> str:
    """Writes a score as a percentage with one decimal, or a dash without one."""
    if value is None:
        return "-"
    return f"{value * 100:.1f}"


def with_interval(value: float | None, interval: Interval | None) -> str:
    """Writes a score and its 95% interval, such as 81.2 (78.0 to 84.3)."""
    if interval is None:
        return percent(value)
    return f"{percent(value)} ({percent(interval.low)} to {percent(interval.high)})"


def score_cells(scores: Scores, intervals: ScoreIntervals) -> list[str]:
    """The precision, recall and F1 cells of one line."""
    return [
        with_interval(scores.precision, intervals.precision),
        with_interval(scores.recall, intervals.recall),
        with_interval(scores.f1, intervals.f1),
    ]


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Writes a Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def write_report(
    folder: Path,
    title: str,
    about: list[str],
    report: SqlReport,
    intervals: IntervalReport,
) -> None:
    """Writes report.md and report.csv into the folder of the result files."""
    lines = [f"# {title}", ""]
    for sentence in about:
        lines.append(f"- {sentence}")
    status_counts = []
    for status, count in report.statuses.items():
        status_counts.append(f"{count} {status}")
    lines.append(
        f"- Contracts answered: **{report.answered} of {report.attempted}** "
        f"({', '.join(status_counts)}). A contract without a record counts as null"
        " on every field, so what CUAD has in it is missed."
    )
    per_thousand = Decimal(0)
    if report.attempted:
        per_thousand = report.cost_usd / report.attempted * 1000
    lines.append(
        f"- Cost at list price: ${report.cost_usd:.4f}, ${per_thousand:.2f} per 1,000"
        f" contracts. Spent in this run: ${report.spent_usd:.4f}; the rest came from"
        " the cache."
    )
    lines.append(
        f"- Seconds per contract: mean {report.seconds_mean:.1f}, median"
        f" {report.seconds_median:.1f}, 95th percentile {report.seconds_95th:.1f}."
    )
    lines += ["", "Scores are percentages, each with its 95% interval.", ""]

    lines += ["## Overall", ""]
    lines += table(
        ["", "Precision", "Recall", "F1"],
        [
            ["Micro (counts of all fields added)"]
            + score_cells(report.micro.scores, intervals.micro),
            ["Macro (mean of the 41 fields)"]
            + score_cells(report.macro, intervals.macro),
        ],
    )

    lines += ["", "## By field type", ""]
    rows = []
    for line in report.by_field_type:
        field_type = FieldType(line.name)
        rows.append(
            [line.name, str(support_of(line))]
            + score_cells(line.scores, intervals.by_field_type[field_type])
        )
    lines += table(["Field type", "Support", "Precision", "Recall", "F1"], rows)

    lines += ["", "## By field", ""]
    lines.append(
        f"Support is the number of CUAD answers: contracts, or party names. Under"
        f" {LOW_SUPPORT_LIMIT} it is marked low, and the score is not to be read alone."
    )
    lines.append("")
    rows = []
    for line in report.by_field:
        support = str(support_of(line))
        if support_of(line) < LOW_SUPPORT_LIMIT:
            support += " (low)"
        rows.append(
            [
                f"`{line.name}`",
                support,
                str(line.counts.true_positives),
                str(line.counts.false_positives),
                str(line.counts.false_negatives),
            ]
            + score_cells(line.scores, intervals.by_field[line.name])
        )
    lines += table(
        ["Field", "Support", "TP", "FP", "FN", "Precision", "Recall", "F1"], rows
    )

    lines += ["", "## Cases skipped, by rule", ""]
    if report.skips:
        skip_rows = []
        for field_name, rule, count in report.skips:
            skip_rows.append([f"`{field_name}`", rule, str(count)])
        lines += table(["Field", "Rule", "Contracts"], skip_rows)
    else:
        lines.append("None.")

    lines += ["", "## Contracts without a record", ""]
    if report.unanswered:
        unanswered_rows = []
        for contract, status, reason in report.unanswered:
            unanswered_rows.append([contract, status, reason or "-"])
        lines += table(["Contract", "Status", "Why"], unanswered_rows)
    else:
        lines.append("None.")
    (folder / "report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )

    write_csv(folder, report, intervals)


def support_of(line: Line) -> int:
    """The number of CUAD answers behind a line: found plus missed."""
    return line.counts.true_positives + line.counts.false_negatives


def write_csv(folder: Path, report: SqlReport, intervals: IntervalReport) -> None:
    """Writes every line of the report with its counts, scores and intervals."""
    header = [
        "level",
        "name",
        "support",
        "true_positives",
        "false_positives",
        "false_negatives",
        "low_support",
    ]
    for score_name in ("precision", "recall", "f1"):
        header += [score_name, f"{score_name}_low", f"{score_name}_high"]
    rows = []
    for line in report.by_field:
        rows.append(csv_row("field", line, intervals.by_field[line.name]))
    for line in report.by_field_type:
        rows.append(
            csv_row("field_type", line, intervals.by_field_type[FieldType(line.name)])
        )
    rows.append(csv_row("overall", report.micro, intervals.micro))
    macro = Line("macro", Counts(0, 0, 0), report.macro)
    rows.append(csv_row("overall", macro, intervals.macro))
    with (folder / "report.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def csv_row(level: str, line: Line, intervals: ScoreIntervals) -> list[object]:
    """One CSV row; the macro line has no counts of its own, so they are empty."""
    has_counts = line.name != "macro"
    row: list[object] = [level, line.name]
    if has_counts:
        row += [
            support_of(line),
            line.counts.true_positives,
            line.counts.false_positives,
            line.counts.false_negatives,
            support_of(line) < LOW_SUPPORT_LIMIT,
        ]
    else:
        row += ["", "", "", "", ""]
    pairs = (
        (line.scores.precision, intervals.precision),
        (line.scores.recall, intervals.recall),
        (line.scores.f1, intervals.f1),
    )
    for value, interval in pairs:
        row.append("" if value is None else round(value, 6))
        if interval is None:
            row += ["", ""]
        else:
            row += [round(interval.low, 6), round(interval.high, 6)]
    return row
