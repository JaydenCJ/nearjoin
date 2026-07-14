"""Pure string-similarity primitives: Levenshtein, Jaro-Winkler, token metrics.

All functions are deterministic, symmetric where mathematically expected, and
return floats in [0.0, 1.0] (except :func:`levenshtein`, which returns the raw
edit distance). No dependencies beyond the standard library.
"""

from __future__ import annotations

from typing import Sequence, Tuple


def levenshtein(a: str, b: str) -> int:
    """Classic edit distance (insert / delete / substitute, all cost 1)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        current = [i]
        for j, ch_b in enumerate(b, start=1):
            cost = 0 if ch_a == ch_b else 1
            current.append(
                min(
                    previous[j] + 1,      # deletion
                    current[j - 1] + 1,   # insertion
                    previous[j - 1] + cost,  # substitution
                )
            )
        previous = current
    return previous[-1]


def ratio(a: str, b: str) -> float:
    """Normalized Levenshtein similarity: 1 - distance / max_length."""
    if a == b:
        return 1.0
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1.0 - levenshtein(a, b) / longest


def jaro(a: str, b: str) -> float:
    """Jaro similarity; the base of Jaro-Winkler."""
    if a == b:
        return 1.0
    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0
    window = max(len_a, len_b) // 2 - 1
    if window < 0:
        window = 0
    matched_a = [False] * len_a
    matched_b = [False] * len_b
    matches = 0
    for i, ch in enumerate(a):
        lo = max(0, i - window)
        hi = min(len_b, i + window + 1)
        for j in range(lo, hi):
            if not matched_b[j] and b[j] == ch:
                matched_a[i] = True
                matched_b[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i in range(len_a):
        if matched_a[i]:
            while not matched_b[k]:
                k += 1
            if a[i] != b[k]:
                transpositions += 1
            k += 1
    transpositions //= 2
    return (
        matches / len_a + matches / len_b + (matches - transpositions) / matches
    ) / 3.0


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1, max_prefix: int = 4) -> float:
    """Jaro-Winkler: Jaro boosted for a shared prefix (names love prefixes)."""
    base = jaro(a, b)
    prefix = 0
    for ch_a, ch_b in zip(a, b):
        if ch_a != ch_b or prefix >= max_prefix:
            break
        prefix += 1
    return base + prefix * prefix_weight * (1.0 - base)


def token_sort_ratio(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Levenshtein ratio after sorting tokens, so word order is free."""
    return ratio(" ".join(sorted(tokens_a)), " ".join(sorted(tokens_b)))


def dice_overlap(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Sorensen-Dice coefficient over distinct tokens: 2|A∩B| / (|A|+|B|)."""
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return 2.0 * len(set_a & set_b) / (len(set_a) + len(set_b))


def alignment_ratio(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """Average best-token similarity, computed in both directions.

    Each token on one side is aligned with its most similar token on the
    other; the two directional means are averaged so extra tokens on either
    side pull the value down symmetrically.
    """
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    def directional(src: Sequence[str], dst: Sequence[str]) -> float:
        total = 0.0
        for token in src:
            total += max(ratio(token, other) for other in dst)
        return total / len(src)

    return (directional(tokens_a, tokens_b) + directional(tokens_b, tokens_a)) / 2.0


def shared_and_unique(
    tokens_a: Sequence[str], tokens_b: Sequence[str]
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    """(shared, only_a, only_b) as sorted tuples — used by explanations."""
    set_a, set_b = set(tokens_a), set(tokens_b)
    return (
        tuple(sorted(set_a & set_b)),
        tuple(sorted(set_a - set_b)),
        tuple(sorted(set_b - set_a)),
    )
