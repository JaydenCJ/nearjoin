"""Exception hierarchy for nearjoin.

Every error raised on purpose by this package derives from NearjoinError so
callers (and the CLI) can catch one type and print a clean message instead of
a traceback.
"""

from __future__ import annotations


class NearjoinError(Exception):
    """Base class for all nearjoin errors."""


class ColumnNotFoundError(NearjoinError):
    """A join column named on the command line is missing from the file."""

    def __init__(self, column: str, available: list) -> None:
        self.column = column
        self.available = list(available)
        cols = ", ".join(repr(c) for c in self.available) or "(no columns)"
        super().__init__(f"column {column!r} not found; file has: {cols}")


class EmptyInputError(NearjoinError):
    """An input table contains a header but no data rows, or nothing at all."""


class InvalidThresholdError(NearjoinError):
    """Thresholds must satisfy 0 <= review <= accept <= 100."""
