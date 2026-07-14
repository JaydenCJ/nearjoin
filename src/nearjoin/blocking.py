"""Blocking: cheap candidate generation so the join is not O(n x m).

Scoring every left row against every right row is quadratic and pointless —
"Acme" will never match "Zenith Plumbing". Blocking assigns each normalized
value a small set of keys; only pairs that share at least one key are scored.

Key families (all derived from the normalized tokens, so two values that
normalize identically always share every key):

- ``p4:<prefix>``  — the first 4 characters of each significant token,
  which survives suffix typos ("Johnson" / "Johnsen" -> ``p4:john``).
- ``init:<chars>`` — the sorted first letters of all tokens, which survives
  word reordering ("Sons & Smith" / "Smith and Sons").
- ``num:<n>``      — each numeric token; for addresses the house number is
  by far the strongest cheap signal.

The trade-off is explicit and measured: :class:`BlockingStats` reports how
many pairs were actually compared versus the full cross product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Sequence, Set

from .normalize import Normalized, significant_tokens


@dataclass(frozen=True)
class BlockingStats:
    """How much work blocking saved, for the join summary."""

    left_count: int
    right_count: int
    pairs_compared: int

    @property
    def pairs_possible(self) -> int:
        return self.left_count * self.right_count

    @property
    def reduction(self) -> float:
        """Fraction of the cross product that was skipped (0.0 - 1.0)."""
        if self.pairs_possible == 0:
            return 0.0
        return 1.0 - self.pairs_compared / self.pairs_possible


def blocking_keys(norm: Normalized) -> FrozenSet[str]:
    """The set of blocking keys for one normalized value."""
    keys: Set[str] = set()
    tokens = significant_tokens(norm.tokens)
    for token in tokens:
        if len(token) >= 2 and not token.isdigit():
            keys.add("p4:" + token[:4])
    if norm.tokens:
        initials = "".join(sorted(token[0] for token in norm.tokens))
        keys.add("init:" + initials)
    for number in norm.numbers:
        keys.add("num:" + number)
    return frozenset(keys)


def candidate_pairs(
    lefts: Sequence[Normalized], rights: Sequence[Normalized]
) -> Dict[int, List[int]]:
    """Map each left index to the sorted right indices sharing a key.

    Left values that normalize to nothing get no candidates (there is nothing
    to match on); they surface as unmatched with an empty-value note.
    """
    index: Dict[str, List[int]] = {}
    for j, right in enumerate(rights):
        for key in blocking_keys(right):
            index.setdefault(key, []).append(j)

    candidates: Dict[int, List[int]] = {}
    for i, left in enumerate(lefts):
        seen: Set[int] = set()
        for key in blocking_keys(left):
            seen.update(index.get(key, ()))
        candidates[i] = sorted(seen)
    return candidates


def stats_for(
    lefts: Sequence[Normalized],
    rights: Sequence[Normalized],
    candidates: Dict[int, List[int]],
) -> BlockingStats:
    compared = sum(len(v) for v in candidates.values())
    return BlockingStats(
        left_count=len(lefts), right_count=len(rights), pairs_compared=compared
    )
