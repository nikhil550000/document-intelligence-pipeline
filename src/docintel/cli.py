"""The `docintel` command-line entry point."""

import subprocess
from collections import Counter
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
import typer

from docintel.config import Settings
from docintel.domain.fields import ALL_FIELDS, NON_CLAUSE_FIELDS
from docintel.evaluation.contracts import LEFT_OUT, PDF_FOLDER, find_contract_pdfs
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.cuad_gold import (
    CUAD_HAS_NOTHING,
    SCORED,
    count_scored_and_skipped,
    read_gold_answers,
)
from docintel.evaluation.dataset import ensure_dataset
from docintel.evaluation.gold import GoldAnswer, SkipRule
from docintel.evaluation.report import (
    ContractResult,
    compute_report,
    export_run,
    intervals_from_files,
    write_report,
)
from docintel.evaluation.splits import (
    DEV_SIZE,
    MIN_POSITIVES_IN_DEV,
    SMOKE_SIZE,
    SPLIT_SEED,
    count_positives,
    find_positive_contracts,
    read_list,
    split_contracts,
    write_lists,
)
from docintel.evaluation.stored_gold import (
    answers_of_record,
    gold_rows,
    read_gold_row,
    score_rows,
)
from docintel.extraction.budget import Budget
from docintel.extraction.client import ModelClient, make_sdk
from docintel.extraction.prices import PRICES_PATH, read_prices
from docintel.parsing.pdfium import PARSER_NAME, PARSER_VERSION
from docintel.pipeline import read_run_config, run_batch, store_contract
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations
from docintel.storage.objects import make_s3_client
from docintel.storage.runs import add_run, find_stored_text
from docintel.storage.scores import (
    read_extractions,
    read_gold_values,
    read_run,
    read_scores,
    replace_gold_values,
    replace_scores,
)

DATA_FOLDER = Path("data")
CONFIG_FOLDER = Path("configs")
REPORTS_FOLDER = Path("reports")

app = typer.Typer(help="Extract structured records from contracts.")
data_app = typer.Typer(help="Manage the CUAD dataset.")
app.add_typer(data_app, name="data")
database_app = typer.Typer(help="Manage the database.")
app.add_typer(database_app, name="db")


def echo_left_out() -> None:
    """Prints the answer rows left out of every list, each with its reason."""
    typer.echo(f"Left out of every list: {len(LEFT_OUT)}")
    for row_name, reason in LEFT_OUT.items():
        typer.echo(f"  {row_name}: {reason}")


@data_app.command("download")
def download() -> None:
    """Download the CUAD dataset into data/, check it and unpack it."""
    did_something = ensure_dataset(DATA_FOLDER)
    if did_something:
        typer.echo(f"Dataset is ready in {DATA_FOLDER}, MD5 checked.")
    else:
        typer.echo("Nothing to do: the dataset is already downloaded and unpacked.")


@data_app.command("split")
def split() -> None:
    """Write the dev, test and smoke lists to configs/ and show the positive counts."""
    answers = load_cuad_answers(MASTER_CLAUSES_PATH)
    positives_by_field = find_positive_contracts(answers)
    splits = split_contracts(
        list(answers),
        positives_by_field,
        SPLIT_SEED,
        DEV_SIZE,
        SMOKE_SIZE,
        MIN_POSITIVES_IN_DEV,
        set(LEFT_OUT),
    )
    write_lists(splits, CONFIG_FOLDER)
    typer.echo(
        f"Wrote {len(splits.dev)} dev, {len(splits.test)} test and "
        f"{len(splits.smoke)} smoke contracts to {CONFIG_FOLDER}."
    )
    echo_left_out()

    dev_counts = count_positives(positives_by_field, splits.dev)
    test_counts = count_positives(positives_by_field, splits.test)
    typer.echo("")
    typer.echo(f"{'Clause field':<45}{'dev':>5}{'test':>6}")
    for field_name, dev_count in dev_counts.items():
        typer.echo(f"{field_name:<45}{dev_count:>5}{test_counts[field_name]:>6}")

    fields_under_minimum = []
    for field_name, dev_count in dev_counts.items():
        if dev_count < MIN_POSITIVES_IN_DEV:
            fields_under_minimum.append(field_name)
    typer.echo("")
    if fields_under_minimum:
        typer.echo(
            f"Under {MIN_POSITIVES_IN_DEV} in dev: {', '.join(fields_under_minimum)}"
        )
    else:
        typer.echo(f"Every clause field has at least {MIN_POSITIVES_IN_DEV} in dev.")


@data_app.command("answers")
def answer_counts() -> None:
    """Show, per field, how many contracts are scored, skipped by rule, or empty."""
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))
    lists = {
        "all": list(gold_answers),
        "dev": read_list(CONFIG_FOLDER, "dev"),
        "test": read_list(CONFIG_FOLDER, "test"),
    }
    counts_by_list = {}
    for list_name, contracts in lists.items():
        counts_by_list[list_name] = count_scored_and_skipped(gold_answers, contracts)

    kinds_and_labels = [(SCORED, SCORED)]
    for rule in SkipRule:
        kinds_and_labels.append((rule.value, f"skipped: {rule.value}"))
    kinds_and_labels.append((CUAD_HAS_NOTHING, CUAD_HAS_NOTHING))

    left_out_count = len(lists["all"]) - len(lists["dev"]) - len(lists["test"])
    typer.echo(
        f"{len(lists['all'])} contracts: {len(lists['dev'])} in dev, "
        f"{len(lists['test'])} in test, {left_out_count} left out of both. "
        "Clause fields are never skipped."
    )
    typer.echo("")
    typer.echo(f"{'Field':<29}{'Answer':<35}{'all':>5}{'dev':>5}{'test':>6}")
    for field in NON_CLAUSE_FIELDS:
        for kind, label in kinds_and_labels:
            counts = []
            for list_name in lists:
                counts.append(counts_by_list[list_name][field.name][kind])
            # A row of zeros would only hide the rows that say something.
            if counts[0] == 0:
                continue
            all_count, dev_count, test_count = counts
            typer.echo(
                f"{field.name:<29}{label:<35}{all_count:>5}{dev_count:>5}"
                f"{test_count:>6}"
            )


@data_app.command("store")
def store() -> None:
    """Store each contract's PDF and its text, read page by page, with their rows."""
    settings = Settings()
    row_names = list(load_cuad_answers(MASTER_CLAUSES_PATH))
    # Every row must find its PDF before anything is stored.
    pdfs_by_row = find_contract_pdfs(PDF_FOLDER, row_names)
    typer.echo(f"All {len(row_names)} answer rows found their PDF.")
    echo_left_out()

    s3_client = make_s3_client(settings)
    stored = 0
    stored_before = 0
    pages = 0
    pages_without_text = 0
    database_url = settings.database_url.get_secret_value()
    with psycopg.connect(database_url, autocommit=True) as connection:
        for row_name, pdf_path in pdfs_by_row.items():
            if row_name in LEFT_OUT:
                continue
            parsed = store_contract(
                connection,
                s3_client,
                settings.s3_bucket,
                pdf_path.name,
                pdf_path.read_bytes(),
            )
            if parsed is None:
                stored_before += 1
                continue
            stored += 1
            pages += len(parsed.pages)
            # A blank page is a correct reading; a page that is only a picture is
            # text this parser cannot see. Both are listed for a person to judge.
            empty_page_numbers = []
            for page_number, text in enumerate(parsed.pages, start=1):
                if not text.strip():
                    empty_page_numbers.append(str(page_number))
            if empty_page_numbers:
                pages_without_text += len(empty_page_numbers)
                typer.echo(
                    f"  {pdf_path.name}, pages without text: "
                    f"{', '.join(empty_page_numbers)}"
                )

    typer.echo(
        f"Stored {stored} contracts: {pages:,} pages, {pages_without_text} of them "
        f"without text. {stored_before} were stored before."
    )


@database_app.command("migrate")
def migrate() -> None:
    """Apply the numbered SQL files that the database has not run yet."""
    settings = Settings()
    applied = apply_migrations(
        settings.database_url.get_secret_value(), MIGRATIONS_FOLDER
    )
    if not applied:
        typer.echo("Nothing to apply: the database is up to date.")
    for file_name in applied:
        typer.echo(f"Applied {file_name}.")


def committed_code() -> str:
    """Returns the commit the code is at, after checking nothing tracked has changed.

    Raises:
        typer.Exit: A tracked file differs from the commit, so the run could not
            be repeated from the commit alone.
    """
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if changed:
        typer.echo("Commit or undo these changes first, so the run can be repeated:")
        typer.echo(changed)
        raise typer.Exit(code=1)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


@app.command("run")
def run(
    config_path: Path,
    contracts: str = typer.Option(help="The list to run on: smoke, dev or test."),
    ceiling_usd: str = typer.Option(help="The most the run may spend, in dollars."),
) -> None:
    """Extract a record from each contract of a list, with one configuration."""
    settings = Settings()
    git_commit = committed_code()
    config, config_as_read = read_run_config(config_path)
    ceiling = Decimal(ceiling_usd)
    prices = read_prices(PRICES_PATH, config.model.model)
    row_names = read_list(CONFIG_FOLDER, contracts)
    pdfs_by_row = find_contract_pdfs(PDF_FOLDER, row_names)
    s3_client = make_s3_client(settings)
    client = ModelClient(make_sdk(settings, config.base_url), config.retry)
    budget = Budget(ceiling, prices)

    database_url = settings.database_url.get_secret_value()
    with psycopg.connect(database_url, autocommit=True) as connection:
        stored_texts = {}
        for row_name, pdf_path in pdfs_by_row.items():
            stored = find_stored_text(
                connection, pdf_path.name, PARSER_NAME, PARSER_VERSION
            )
            if stored is None:
                typer.echo(f"{pdf_path.name} is not stored. Run: docintel data store")
                raise typer.Exit(code=1)
            stored_texts[row_name] = stored
        run_id = add_run(
            connection,
            config_path.stem,
            config_as_read,
            git_commit,
            contracts,
            ceiling,
        )
        typer.echo(
            f"Run {run_id}: {len(stored_texts)} {contracts} contracts, "
            f"ceiling ${ceiling}, prices read on {prices.read_on}."
        )
        outcome = run_batch(
            connection,
            s3_client,
            settings.s3_bucket,
            run_id,
            config,
            stored_texts,
            client,
            budget,
            on_contract=lambda name, status: typer.echo(f"  {status:<13}{name}"),
        )

    counts = Counter(outcome.statuses.values())
    typer.echo(
        f"Run {outcome.status}: {len(outcome.statuses)} of {len(stored_texts)} "
        f"contracts ended ({dict(counts)}). Calls to the provider: {client.calls}. "
        f"Spent at most ${budget.spent_usd:.4f}."
    )
    if outcome.stop_reason is not None:
        typer.echo(outcome.stop_reason)


class RunNotReportableError(Exception):
    """The run does not exist, or did not finish, so it has no result to report."""


def report_run(
    connection: psycopg.Connection,
    run_id: UUID,
    gold_by_file_name: dict[str, dict[str, GoldAnswer]],
    reports_folder: Path,
) -> Path:
    """Scores a finished run, exports its results, and writes its report from them.

    Args:
        connection: The database the run is in.
        run_id: The run.
        gold_by_file_name: CUAD's answers in scoring form, by the PDF's file name.
        reports_folder: Where the run's folder of result files and report goes.

    Returns:
        The folder written.

    Raises:
        RunNotReportableError: There is no such run, or it is not complete.
    """
    run = read_run(connection, run_id)
    if run is None:
        raise RunNotReportableError(f"there is no run {run_id}")
    # A stopped or unfinished run lacks contracts, so its scores would mislead.
    if run.status != "complete":
        raise RunNotReportableError(f"run {run_id} is {run.status}, not complete")

    fields = {field.name: field for field in ALL_FIELDS}
    extractions = read_extractions(connection, run_id)
    gold_values = []
    for extraction in extractions:
        for gold_row in gold_rows(gold_by_file_name[extraction.file_name]):
            gold_values.append((extraction.document_id, *gold_row))
    document_ids = [extraction.document_id for extraction in extractions]
    score_values = []
    contracts = []
    # All of a run's scores are replaced together, or none are.
    with connection.transaction():
        replace_gold_values(connection, gold_values)
        # Scored from what the database holds, as any later run will be.
        stored_gold = read_gold_values(connection, document_ids)
        for extraction in extractions:
            gold_by_field = {}
            for field_name, kind, rule, values in stored_gold[extraction.document_id]:
                gold_by_field[field_name] = read_gold_row(
                    fields[field_name], kind, rule, values
                )
            answers = answers_of_record(extraction.record)
            for score_row in score_rows(gold_by_field, answers):
                score_values.append((extraction.extraction_id, *score_row))
            reason = None
            if extraction.record is None:
                reason = extraction.reason
            contracts.append(
                ContractResult(
                    contract=extraction.file_name,
                    status=extraction.status,
                    answered=extraction.record is not None,
                    reason=reason,
                    from_cache=extraction.from_cache,
                    input_tokens=extraction.input_tokens,
                    cached_input_tokens=extraction.cached_input_tokens,
                    output_tokens=extraction.output_tokens,
                    cost_usd=extraction.cost_usd,
                    total_seconds=extraction.total_seconds,
                )
            )
        replace_scores(connection, run_id, score_values)

    folder = reports_folder / f"{run.config_name}-{run.contract_list}-{run_id}"
    export_run(folder, read_scores(connection, run_id), contracts)
    report = compute_report(folder)
    intervals = intervals_from_files(folder)
    model = run.config["model"]["name"]
    about = [
        f"Run `{run_id}` of configuration `{run.config_name}` on the"
        f" `{run.contract_list}` list, at commit `{run.git_commit}`.",
        f"Model `{model}`, prompt version {run.config['prompt_version']},"
        f" parser `{run.config['parser']}`.",
        f"Started {run.started_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC, ceiling"
        f" ${run.cost_ceiling_usd:.2f}.",
    ]
    title = f"{run.config_name} on {run.contract_list}"
    write_report(folder, title, about, report, intervals)
    return folder


@app.command("report")
def report(run_id: str) -> None:
    """Score a finished run against CUAD and write its report into reports/."""
    settings = Settings()
    gold_answers = read_gold_answers(load_cuad_answers(MASTER_CLAUSES_PATH))
    pdfs_by_row = find_contract_pdfs(PDF_FOLDER, list(gold_answers))
    gold_by_file_name = {}
    for row_name, pdf_path in pdfs_by_row.items():
        gold_by_file_name[pdf_path.name] = gold_answers[row_name]
    database_url = settings.database_url.get_secret_value()
    with psycopg.connect(database_url, autocommit=True) as connection:
        try:
            folder = report_run(
                connection, UUID(run_id), gold_by_file_name, REPORTS_FOLDER
            )
        except RunNotReportableError as error:
            typer.echo(f"No report: {error}.")
            raise typer.Exit(code=1) from error
    typer.echo((folder / "report.md").read_text(encoding="utf-8"))
    typer.echo(f"Written to {folder}.")
