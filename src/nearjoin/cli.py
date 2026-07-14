"""Command-line interface: ``nearjoin join | score | keys``.

The CLI is a thin shell over the library modules — argument parsing, file
handling and printing live here; matching logic does not. Data output goes to
stdout (or ``--output``); the human-facing join summary goes to stderr so
``nearjoin join ... > matched.csv`` stays clean.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import Optional, Sequence

from . import __version__
from .blocking import blocking_keys
from .errors import NearjoinError
from .explain import explain_dict, explain_long
from .joiner import DEFAULT_ACCEPT, DEFAULT_REVIEW, join_values
from .normalize import normalize
from .scoring import score_pair
from .tabular import (
    column_values,
    matched_rows,
    read_rows,
    result_to_json,
    rows_to_csv_text,
    unmatched_table,
)

KIND_CHOICES = ("auto", "name", "address")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nearjoin",
        description=(
            "Fuzzy-join two datasets on names or addresses with explainable "
            "match scores."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"nearjoin {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_join = sub.add_parser(
        "join", help="fuzzy-join two CSV files on one column from each"
    )
    p_join.add_argument("left", help="left CSV file (the rows you want matched)")
    p_join.add_argument("right", help="right CSV file (the rows to match against)")
    p_join.add_argument(
        "--left-on", required=True, metavar="COL", help="join column in LEFT"
    )
    p_join.add_argument(
        "--right-on", metavar="COL", help="join column in RIGHT (default: same as --left-on)"
    )
    p_join.add_argument(
        "--kind", choices=KIND_CHOICES, default="auto",
        help="what the join column holds (default: auto-detect)",
    )
    p_join.add_argument(
        "--threshold", type=float, default=DEFAULT_ACCEPT, metavar="N",
        help=f"accept matches scoring >= N (default {DEFAULT_ACCEPT:g})",
    )
    p_join.add_argument(
        "--review", type=float, default=DEFAULT_REVIEW, metavar="N",
        help=f"flag pairs scoring in [N, threshold) for review (default {DEFAULT_REVIEW:g})",
    )
    p_join.add_argument(
        "--many", action="store_true",
        help="allow a right row to match multiple left rows (default: one-to-one)",
    )
    p_join.add_argument(
        "--format", choices=("csv", "json"), default="csv",
        help="output format (default csv; json includes full explanations)",
    )
    p_join.add_argument(
        "-o", "--output", metavar="FILE", help="write matches here instead of stdout"
    )
    p_join.add_argument(
        "--unmatched-left", metavar="FILE", help="write unmatched LEFT rows to FILE (CSV)"
    )
    p_join.add_argument(
        "--unmatched-right", metavar="FILE", help="write unmatched RIGHT rows to FILE (CSV)"
    )
    p_join.add_argument(
        "--no-explain", action="store_true",
        help="omit the match_explanation column from CSV output",
    )
    p_join.add_argument(
        "--quiet", action="store_true", help="suppress the summary on stderr"
    )
    p_join.set_defaults(func=cmd_join)

    p_score = sub.add_parser("score", help="score one pair of strings")
    p_score.add_argument("left_value", metavar="LEFT", help="left value to score")
    p_score.add_argument("right_value", metavar="RIGHT", help="right value to score")
    p_score.add_argument(
        "--kind", choices=("name", "address"), default="name",
        help="what the values hold (default: name)",
    )
    p_score.add_argument(
        "--json", action="store_true", help="emit the explanation as JSON"
    )
    p_score.set_defaults(func=cmd_score)

    p_keys = sub.add_parser(
        "keys", help="show how a value normalizes and which blocking keys it gets"
    )
    p_keys.add_argument("value", metavar="VALUE", help="the value to inspect")
    p_keys.add_argument(
        "--kind", choices=("name", "address"), default="name",
        help="what the value holds (default: name)",
    )
    p_keys.set_defaults(func=cmd_keys)

    return parser


def cmd_join(args: argparse.Namespace) -> int:
    right_on = args.right_on or args.left_on
    with open(args.left, newline="", encoding="utf-8") as handle:
        left_rows = read_rows(handle, source=args.left)
    with open(args.right, newline="", encoding="utf-8") as handle:
        right_rows = read_rows(handle, source=args.right)

    left_values = column_values(left_rows, args.left_on, source=args.left)
    right_values = column_values(right_rows, right_on, source=args.right)

    result = join_values(
        left_values,
        right_values,
        kind=args.kind,
        accept_threshold=args.threshold,
        review_threshold=args.review,
        one_to_one=not args.many,
    )

    if args.format == "json":
        text = result_to_json(result, left_rows, right_rows) + "\n"
    else:
        rows = matched_rows(
            result, left_rows, right_rows, include_explanation=not args.no_explain
        )
        text = rows_to_csv_text(rows)

    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)

    if args.unmatched_left:
        _write_unmatched(args.unmatched_left, left_rows, result.unmatched_left)
    if args.unmatched_right:
        _write_unmatched(args.unmatched_right, right_rows, result.unmatched_right)

    if not args.quiet:
        _print_summary(result, len(left_rows), len(right_rows))
    return 0


def _write_unmatched(path: str, rows, indices) -> None:
    table = unmatched_table(rows, indices)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        if table:
            handle.write(rows_to_csv_text(table))
        elif rows:
            # Keep the header so downstream tooling sees a valid, empty CSV.
            csv.writer(handle, lineterminator="\n").writerow(rows[0].keys())


def _plural(count: int, noun: str) -> str:
    """'1 left row' / '12 left rows' — summaries should never say '1 rows'."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _print_summary(result, left_total: int, right_total: int) -> None:
    blocking = result.blocking
    print(
        f"nearjoin: {_plural(left_total, 'left row')} x "
        f"{_plural(right_total, 'right row')} [kind={result.kind}]",
        file=sys.stderr,
    )
    print(
        f"  matched {result.match_count}, review {result.review_count}, "
        f"unmatched left {len(result.unmatched_left)}, "
        f"unmatched right {len(result.unmatched_right)}",
        file=sys.stderr,
    )
    print(
        f"  blocking compared {blocking.pairs_compared} of "
        f"{_plural(blocking.pairs_possible, 'possible pair')} "
        f"({blocking.reduction:.0%} skipped)",
        file=sys.stderr,
    )


def cmd_score(args: argparse.Namespace) -> int:
    match = score_pair(args.left_value, args.right_value, kind=args.kind)
    if args.json:
        print(json.dumps(explain_dict(match), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(explain_long(match))
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    norm = normalize(args.value, kind=args.kind)
    print(f"raw       : {norm.raw!r}")
    print(f"normalized: {norm.text!r}")
    if norm.steps:
        print("steps:")
        for step in norm.steps:
            print(f"  - {step}")
    else:
        print("steps: (none — already canonical)")
    keys = sorted(blocking_keys(norm))
    print("blocking keys:")
    for key in keys:
        print(f"  {key}")
    if not keys:
        print("  (none — value normalizes to nothing and can never match)")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except NearjoinError as exc:
        print(f"nearjoin: error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"nearjoin: error: {exc.filename}: no such file", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
