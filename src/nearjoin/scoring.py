"""The score model: weighted similarity components plus explicit penalties.

A score is a number in [0, 100] built from four transparent components and a
short list of penalties. Nothing is learned, nothing is opaque: every part of
the number is kept on the :class:`MatchScore` so it can be rendered back to a
stakeholder verbatim.

Score construction:

1. If the two normalized strings are identical -> 100 ("exact after
   normalization").
2. If the sorted token multisets are identical -> at least 95 ("same tokens,
   different order").
3. Otherwise a weighted blend of token_sort (30%), token_overlap (20%),
   char (25%, Jaro-Winkler) and alignment (25%), scaled to 100.
4. Penalties are subtracted last — numeric disagreement is the classic
   silent killer of address joins ("123 Main St" vs "125 Main St" look 95%
   similar and are different buildings), so it is called out and charged
   explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from .normalize import KIND_ADDRESS, KIND_NAME, Normalized, normalize
from .similarity import (
    alignment_ratio,
    dice_overlap,
    jaro_winkler,
    shared_and_unique,
    token_sort_ratio,
)

# Component weights; they sum to 1.0 and are part of the public contract
# (documented in docs/scoring.md and printed by `nearjoin score --json`).
WEIGHTS = {
    "token_sort": 0.30,
    "token_overlap": 0.20,
    "char": 0.25,
    "alignment": 0.25,
}

# Penalty points by kind. Addresses are punished harder for numeric drift
# because a house-number mismatch usually means a different premise, while a
# digit inside a company name ("7-Eleven") is weaker evidence.
NUMERIC_MISMATCH_PENALTY = {KIND_ADDRESS: 30.0, KIND_NAME: 12.0}
NUMERIC_MISSING_PENALTY = {KIND_ADDRESS: 10.0, KIND_NAME: 4.0}

# Floor applied when the token multisets are identical but order differs.
REORDERED_FLOOR = 95.0


@dataclass(frozen=True)
class Component:
    """One weighted ingredient of the score."""

    name: str
    value: float  # 0.0 - 1.0
    weight: float  # 0.0 - 1.0, fraction of the base score
    detail: str


@dataclass(frozen=True)
class Penalty:
    """Points subtracted after the weighted blend, with the reason."""

    name: str
    points: float
    detail: str


@dataclass(frozen=True)
class MatchScore:
    """A fully explained pair score."""

    left: Normalized
    right: Normalized
    kind: str
    score: float
    exact: bool
    components: Tuple[Component, ...] = field(default=())
    penalties: Tuple[Penalty, ...] = field(default=())


def score_pair(left: str, right: str, kind: str = KIND_NAME) -> MatchScore:
    """Score two raw strings; normalization happens inside."""
    return score_normalized(normalize(left, kind), normalize(right, kind))


def score_normalized(left: Normalized, right: Normalized) -> MatchScore:
    """Score two already-normalized values (the join pipeline's fast path)."""
    if left.kind != right.kind:
        raise ValueError(
            f"cannot score across kinds: {left.kind!r} vs {right.kind!r}"
        )
    kind = left.kind

    if not left.text or not right.text:
        detail = "one side normalized to an empty string; nothing to compare"
        return MatchScore(
            left=left,
            right=right,
            kind=kind,
            score=0.0,
            exact=False,
            components=(Component("empty", 0.0, 1.0, detail),),
        )

    if left.text == right.text:
        detail = f"both sides normalize to {left.text!r}"
        return MatchScore(
            left=left,
            right=right,
            kind=kind,
            score=100.0,
            exact=True,
            components=(Component("exact", 1.0, 1.0, detail),),
        )

    components = _build_components(left, right)
    base = sum(c.value * c.weight for c in components) * 100.0

    reordered = sorted(left.tokens) == sorted(right.tokens)
    if reordered and base < REORDERED_FLOOR:
        components = components + (
            Component(
                "reordered",
                1.0,
                0.0,
                f"same tokens in a different order; score floored at {REORDERED_FLOOR:g}",
            ),
        )
        base = REORDERED_FLOOR

    penalties = _build_penalties(left, right, kind)
    score = base - sum(p.points for p in penalties)
    score = max(0.0, min(100.0, score))
    return MatchScore(
        left=left,
        right=right,
        kind=kind,
        score=round(score, 1),
        exact=False,
        components=components,
        penalties=penalties,
    )


def _build_components(left: Normalized, right: Normalized) -> Tuple[Component, ...]:
    shared, only_left, only_right = shared_and_unique(left.tokens, right.tokens)

    sort_value = token_sort_ratio(left.tokens, right.tokens)
    overlap_value = dice_overlap(left.tokens, right.tokens)
    char_value = jaro_winkler(left.text, right.text)
    align_value = alignment_ratio(left.tokens, right.tokens)

    if shared:
        overlap_detail = f"shared tokens: {', '.join(shared)}"
    else:
        overlap_detail = "no tokens shared"
    extras = []
    if only_left:
        extras.append(f"only left: {', '.join(only_left)}")
    if only_right:
        extras.append(f"only right: {', '.join(only_right)}")
    if extras:
        overlap_detail += " (" + "; ".join(extras) + ")"

    return (
        Component(
            "token_sort",
            sort_value,
            WEIGHTS["token_sort"],
            "edit similarity after sorting tokens "
            f"({' '.join(sorted(left.tokens))!r} vs {' '.join(sorted(right.tokens))!r})",
        ),
        Component("token_overlap", overlap_value, WEIGHTS["token_overlap"], overlap_detail),
        Component(
            "char",
            char_value,
            WEIGHTS["char"],
            f"Jaro-Winkler over {left.text!r} vs {right.text!r}",
        ),
        Component(
            "alignment",
            align_value,
            WEIGHTS["alignment"],
            "average similarity of each token to its best counterpart",
        ),
    )


def _build_penalties(
    left: Normalized, right: Normalized, kind: str
) -> Tuple[Penalty, ...]:
    penalties = []
    left_nums, right_nums = set(left.numbers), set(right.numbers)
    if left_nums and right_nums and left_nums != right_nums:
        points = NUMERIC_MISMATCH_PENALTY[kind]
        penalties.append(
            Penalty(
                "numeric_mismatch",
                points,
                f"numbers disagree: left has {_fmt_nums(left_nums)}, "
                f"right has {_fmt_nums(right_nums)}",
            )
        )
    elif bool(left_nums) != bool(right_nums):
        points = NUMERIC_MISSING_PENALTY[kind]
        side = "left" if left_nums else "right"
        nums = left_nums or right_nums
        penalties.append(
            Penalty(
                "numeric_missing",
                points,
                f"only the {side} side carries numbers ({_fmt_nums(nums)})",
            )
        )
    return tuple(penalties)


def _fmt_nums(nums: set) -> str:
    return "{" + ", ".join(sorted(nums, key=lambda n: (len(n), n))) + "}"
