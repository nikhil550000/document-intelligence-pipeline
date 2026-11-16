"""The `docintel` command-line entry point."""

from pathlib import Path

import typer

from docintel.evaluation.dataset import ensure_dataset

DATA_FOLDER = Path("data")

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
