"""Shared fixtures: paths to the bundled examples and a tiny CSV writer."""

from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def crm_csv() -> Path:
    return EXAMPLES / "customers_crm.csv"


@pytest.fixture
def billing_csv() -> Path:
    return EXAMPLES / "customers_billing.csv"


@pytest.fixture
def write_csv(tmp_path):
    """Write a CSV file from a header line and rows; returns the path."""

    counter = {"n": 0}

    def _write(header: str, *rows: str) -> Path:
        counter["n"] += 1
        path = tmp_path / f"table_{counter['n']}.csv"
        path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
        return path

    return _write
