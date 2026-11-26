# One image for the code, started as a worker. It has no OCR and no machine
# learning libraries, which keeps it small.
FROM python:3.13.17-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /app
# Compiled once here, so a worker does not compile at every start.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# The dependencies first: they change less often than the code, so this layer
# is built again only when the lock file changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev

# A worker reads the model prices; the rest of a run's configuration is in
# the run's row.
COPY configs/prices.toml ./configs/prices.toml

ENV PATH="/app/.venv/bin:$PATH"
# Not root, so a library going wrong on a contract cannot change the installed code.
RUN useradd --no-create-home docintel
USER docintel
CMD ["docintel", "worker"]
