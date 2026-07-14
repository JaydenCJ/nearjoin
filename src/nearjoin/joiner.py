"""The join pipeline: normalize, block, score, assign, explain.

This module turns two lists of rows into a :class:`JoinResult`:

1. Normalize the join column on both sides (once per row, not per pair).
2. Blocking proposes candidate pairs (see :mod:`nearjoin.blocking`).
3. Every candidate pair is scored (see :mod:`nearjoin.scoring`).
4. Assignment: pairs at or above the review threshold are sorted by score
   (descending, ties broken by row order so results are stable) and matched
   greedily. One-to-one by default — a right row can be claimed once —
   because duplicated right rows in a reconciliation are usually a bug you
   want surfaced, not silently absorbed.
5. Each match carries its verdict ("match" or "review") and the full
   MatchScore for explanation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .blocking import BlockingStats, candidate_pairs, stats_for
from .errors import InvalidThresholdError
from .normalize import KINDS, detect_kind, normalize
from .scoring import MatchScore, score_normalized

VERDICT_MATCH = "match"
VERDICT_REVIEW = "review"

DEFAULT_ACCEPT = 85.0
DEFAULT_REVIEW = 70.0


@dataclass(frozen=True)
class Match:
    """One accepted pairing between a left row and a right row."""

    left_index: int
    right_index: int
    score: MatchScore
    verdict: str


@dataclass(frozen=True)
class JoinResult:
    """Everything the CLI (or a library caller) needs to report a join."""

    kind: str
    matches: Tuple[Match, ...]
    unmatched_left: Tuple[int, ...]
    unmatched_right: Tuple[int, ...]
    blocking: BlockingStats
    accept_threshold: float
    review_threshold: float

    @property
    def match_count(self) -> int:
        return sum(1 for m in self.matches if m.verdict == VERDICT_MATCH)

    @property
    def review_count(self) -> int:
        return sum(1 for m in self.matches if m.verdict == VERDICT_REVIEW)


def join_values(
    left_values: Sequence[str],
    right_values: Sequence[str],
    kind: str = "auto",
    accept_threshold: float = DEFAULT_ACCEPT,
    review_threshold: float = DEFAULT_REVIEW,
    one_to_one: bool = True,
) -> JoinResult:
    """Fuzzy-join two lists of strings by index.

    ``kind`` may be "name", "address", or "auto" (detected from both columns
    together). Thresholds are on the 0-100 score scale: pairs scoring at or
    above ``accept_threshold`` are matches, pairs in
    [``review_threshold``, ``accept_threshold``) are flagged for human
    review, everything below is left unmatched.
    """
    if not (0.0 <= review_threshold <= accept_threshold <= 100.0):
        raise InvalidThresholdError(
            f"need 0 <= review ({review_threshold}) <= accept "
            f"({accept_threshold}) <= 100"
        )
    resolved_kind = _resolve_kind(kind, left_values, right_values)

    lefts = [normalize(v, resolved_kind) for v in left_values]
    rights = [normalize(v, resolved_kind) for v in right_values]

    candidates = candidate_pairs(lefts, rights)
    blocking = stats_for(lefts, rights, candidates)

    scored: List[Tuple[float, int, int, MatchScore]] = []
    for i, right_indices in candidates.items():
        for j in right_indices:
            match_score = score_normalized(lefts[i], rights[j])
            if match_score.score >= review_threshold:
                scored.append((match_score.score, i, j, match_score))

    # Highest score first; ties resolved by original row order on both sides
    # so the same inputs always produce byte-identical output.
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))

    matches: List[Match] = []
    taken_left: set = set()
    taken_right: set = set()
    for score_value, i, j, match_score in scored:
        if i in taken_left:
            continue
        if one_to_one and j in taken_right:
            continue
        verdict = VERDICT_MATCH if score_value >= accept_threshold else VERDICT_REVIEW
        matches.append(Match(i, j, match_score, verdict))
        taken_left.add(i)
        taken_right.add(j)

    matches.sort(key=lambda m: m.left_index)
    unmatched_left = tuple(i for i in range(len(lefts)) if i not in taken_left)
    unmatched_right = tuple(j for j in range(len(rights)) if j not in taken_right)

    return JoinResult(
        kind=resolved_kind,
        matches=tuple(matches),
        unmatched_left=unmatched_left,
        unmatched_right=unmatched_right,
        blocking=blocking,
        accept_threshold=accept_threshold,
        review_threshold=review_threshold,
    )


def _resolve_kind(
    kind: str, left_values: Sequence[str], right_values: Sequence[str]
) -> str:
    if kind in KINDS:
        return kind
    if kind != "auto":
        raise ValueError(f"unknown kind {kind!r}; expected 'auto' or one of {KINDS}")
    return detect_kind(list(left_values) + list(right_values))
