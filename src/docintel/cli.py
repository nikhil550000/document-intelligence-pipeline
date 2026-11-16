"""The `docintel` command-line entry point."""

from pathlib import Path

import typer

from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers
from docintel.evaluation.dataset import ensure_dataset
from docintel.evaluation.splits import (
    DEV_SIZE,
    MIN_POSITIVES_IN_DEV,
    SMOKE_SIZE,
    SPLIT_SEED,
    count_positives,
    find_positive_contracts,
    split_contracts,
    write_lists,
)

DATA_FOLDER = Path("data")
CONFIG_FOLDER = Path("configs")

app = typer.Typer(help="Extract structured records from contracts.")
data_app = typer.Typer(help="Manage the CUAD dataset.")
app.add_typer(data_app, name="data")


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
