"""Tests for the parts of the pipeline that need no services."""

from datetime import timedelta
from pathlib import Path

from docintel.pipeline import longest_job, read_run_config


def test_the_longest_job_counts_every_attempt_timing_out_and_every_wait() -> None:
    """Four attempts of 300 s, waits of 10, 20 and 40 s, and a minute to store."""
    config, _ = read_run_config(Path("configs") / "pdfium-deepseek-flash.toml")

    assert longest_job(config) == timedelta(seconds=4 * 300 + 10 + 20 + 40 + 60)
