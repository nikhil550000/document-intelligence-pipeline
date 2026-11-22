# Document Intelligence Pipeline

A pipeline that turns contract PDFs into validated, structured JSON records. It is built for English commercial contracts in general, and its accuracy is measured field by field against the CUAD dataset. The project is a work in progress.

## Getting started

### Requirements

- Python 3.13 (installed on the machine, not only through uv)
- [uv](https://docs.astral.sh/uv/)
- Docker, with Docker Compose
- About 500 MB of free disk space for the dataset

### Set up

```
git clone https://github.com/<your-account>/document-intelligence-pipeline.git
cd document-intelligence-pipeline
uv sync
```

### Download the data

```
uv run docintel data download
```

This downloads the CUAD dataset (about 106 MB) from Zenodo into `data/`, checks its MD5 and unpacks it. Running it again does nothing if the data is already there and correct.

### Start the database and the object store

```
cp .env.example .env
docker compose up --detach --wait
uv run docintel db migrate
```

This starts Postgres (on port 5433, so a Postgres already installed can keep 5432) and an S3-compatible object store, [SeaweedFS](https://github.com/seaweedfs/seaweedfs), on port 8333. Their data is kept in Docker volumes, so it survives the containers being stopped or replaced. `db migrate` applies the numbered SQL files in `src/docintel/storage/sql/` that the database has not run yet; running it again applies nothing.

### Store the contracts

```
uv run docintel data store
```

This reads each contract's PDF page by page with [PDFium](https://pdfium.googlesource.com/pdfium/) and keeps the PDF and its text in the object store, each under the SHA-256 of its content, with a row for each in Postgres. It lists the pages that give no text: blank pages, and pages that are only a picture, since PDFium reads the text in the PDF and does no OCR. Running it again stores nothing new.

### Run the checks

```
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

The tests that need the database and the object store are skipped when the services are not running. One more test replaces the service containers to check that stored data survives, so it runs only when asked for:

```
uv run pytest -m restart
```
