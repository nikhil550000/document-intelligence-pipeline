"""Smoke test that proves the test runner can import the package."""

from importlib.metadata import version

import docintel


def test_package_imports_and_reports_version() -> None:
    """The installed package imports and reports the version in pyproject.toml."""
    assert docintel.__doc__
    assert version("docintel") == "0.1.0"
