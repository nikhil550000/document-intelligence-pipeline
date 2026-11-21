"""The `docintel` command-line entry point."""

from pathlib import Path

import typer

from docintel.config import Settings
from docintel.domain.fields import NON_CLAUSE_FIELDS
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.cuad_gold import (
    CUAD_HAS_NOTHING,
    SCORED,
    count_scored_and_skipped,
    read_gold_answers,
)
from docintel.evaluation.dataset import ensure_dataset
from docintel.evaluation.gold import SkipRule
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
from docintel.storage.migrations import MIGRATIONS_FOLDER, apply_migrations

DATA_FOLDER = Path("data")
CONFIG_FOLDER = Path("configs")

app = typer.Typer(help="Extract structured records from contracts.")
data_app = typer.Typer(help="Manage the CUAD dataset.")
app.add_typer(data_app, name="data")
database_app = typer.Typer(help="Manage the database.")
app.add_typer(database_app, name="db")


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
    )
    write_lists(splits, CONFIG_FOLDER)
    typer.echo(
        f"Wrote {len(splits.dev)} dev, {len(splits.test)} test and "
        f"{len(splits.smoke)} smoke contracts to {CONFIG_FOLDER}."
    )

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

    typer.echo(
        f"{len(lists['all'])} contracts: {len(lists['dev'])} in dev, "
        f"{len(lists['test'])} in test. Clause fields are never skipped."
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
