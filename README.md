# Document Intelligence Pipeline

A pipeline that turns contract PDFs into validated, structured JSON records. It is built for English commercial contracts in general, and its accuracy is measured field by field against the CUAD dataset. The project is a work in progress.

## Getting started

### Requirements

- Python 3.13 (installed on the machine, not only through uv)
- [uv](https://docs.astral.sh/uv/)
- About 500 MB of free disk space for the dataset

### Set up

```
git clone https://github.com/nikhil550000/document-intelligence-pipeline.git
cd document-intelligence-pipeline
uv sync
```

### Download the data

```
uv run docintel data download
```

This downloads the CUAD dataset (about 106 MB) from Zenodo into `data/`, checks its MD5 and unpacks it. Running it again does nothing if the data is already there and correct.

### Run the checks

```
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```
