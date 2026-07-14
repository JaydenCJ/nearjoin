"""Reading and writing tables: CSV in, CSV or JSON out. Standard library only.

Input is any CSV with a header row (read with ``csv.DictReader``). Output
rows for a join carry the left columns prefixed ``left_``, the right columns
prefixed ``right_``, then ``match_score``, ``match_verdict`` and (optionally)
``match_explanation``. Prefixing sidesteps column-name collisions between the
two files without inventing a merge policy.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Dict, List, Sequence, TextIO

from .errors import ColumnNotFoundError, EmptyInputError
from .explain import explain_dict, explain_short
from .joiner import JoinResult


def read_rows(handle: TextIO, source: str = "<input>") -> List[Dict[str, str]]:
    """Read a CSV with a header into a list of dicts; empty input is an error."""
    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
        raise EmptyInputError(f"{source}: file is empty (no header row)")
    rows = [dict(row) for row in reader]
    if not rows:
        raise EmptyInputError(f"{source}: no data rows after the header")
    return rows


def column_values(
    rows: Sequence[Dict[str, str]], column: str, source: str = "<input>"
) -> List[str]:
    """Extract one column, raising a helpful error if it does not exist."""
    if not rows:
        raise EmptyInputError(f"{source}: no rows")
    fieldnames = list(rows[0].keys())
    if column not in fieldnames:
        raise ColumnNotFoundError(column, fieldnames)
    return [(row.get(column) or "") for row in rows]


def matched_rows(
    result: JoinResult,
    left_rows: Sequence[Dict[str, str]],
    right_rows: Sequence[Dict[str, str]],
    include_explanation: bool = True,
) -> List[Dict[str, str]]:
    """Flatten a JoinResult into prefixed output rows."""
    out: List[Dict[str, str]] = []
    for match in result.matches:
        row: Dict[str, str] = {}
        for key, value in left_rows[match.left_index].items():
            row[f"left_{key}"] = value
        for key, value in right_rows[match.right_index].items():
            row[f"right_{key}"] = value
        row["match_score"] = f"{match.score.score:g}"
        row["match_verdict"] = match.verdict
        if include_explanation:
            row["match_explanation"] = explain_short(match.score)
        out.append(row)
    return out


def write_csv(rows: Sequence[Dict[str, str]], handle: TextIO) -> None:
    """Write dict rows as CSV; the union of keys (first-seen order) is the header."""
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def rows_to_csv_text(rows: Sequence[Dict[str, str]]) -> str:
    buffer = io.StringIO()
    write_csv(rows, buffer)
    return buffer.getvalue()


def result_to_json(
    result: JoinResult,
    left_rows: Sequence[Dict[str, str]],
    right_rows: Sequence[Dict[str, str]],
) -> str:
    """The full join as pretty JSON: matches with explanations, plus leftovers."""
    payload = {
        "kind": result.kind,
        "accept_threshold": result.accept_threshold,
        "review_threshold": result.review_threshold,
        "matches": [
            {
                "left": left_rows[m.left_index],
                "right": right_rows[m.right_index],
                "verdict": m.verdict,
                "explanation": explain_dict(m.score),
            }
            for m in result.matches
        ],
        "unmatched_left": [left_rows[i] for i in result.unmatched_left],
        "unmatched_right": [right_rows[j] for j in result.unmatched_right],
        "blocking": {
            "pairs_compared": result.blocking.pairs_compared,
            "pairs_possible": result.blocking.pairs_possible,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def unmatched_table(
    rows: Sequence[Dict[str, str]], indices: Sequence[int]
) -> List[Dict[str, str]]:
    return [dict(rows[i]) for i in indices]
