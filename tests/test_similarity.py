"""Similarity primitives: known distances, boundaries, and symmetry."""

import pytest

from nearjoin.similarity import (
    alignment_ratio,
    dice_overlap,
    jaro,
    jaro_winkler,
    levenshtein,
    ratio,
    shared_and_unique,
    token_sort_ratio,
)


def test_levenshtein_known_values_and_empty_sides():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("flaw", "lawn") == 2
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3
    assert levenshtein("", "") == 0


def test_levenshtein_is_symmetric():
    assert levenshtein("northwind", "traders") == levenshtein("traders", "northwind")


def test_ratio_bounds_identity_and_partial_value():
    assert ratio("", "") == 1.0
    assert ratio("acme", "acme") == 1.0
    assert ratio("abc", "xyz") == 0.0
    # distance 1 over max length 4.
    assert ratio("acme", "acmé") == pytest.approx(0.75)


def test_jaro_identity_and_disjoint():
    assert jaro("acme", "acme") == 1.0
    assert jaro("abc", "xyz") == 0.0
    assert jaro("", "abc") == 0.0


def test_jaro_winkler_textbook_value():
    # The classic MARTHA/MARHTA example evaluates to 0.9611.
    assert jaro_winkler("martha", "marhta") == pytest.approx(0.9611, abs=1e-4)


def test_jaro_winkler_rewards_shared_prefix_within_bounds():
    plain = jaro("johnson", "johnsen")
    boosted = jaro_winkler("johnson", "johnsen")
    assert boosted > plain
    # Identical 10-char prefix must not boost the value out of [0, 1].
    assert jaro_winkler("abcdefghijX", "abcdefghijY") <= 1.0


def test_token_sort_ratio_ignores_word_order():
    assert token_sort_ratio(("sons", "smith"), ("smith", "sons")) == 1.0


def test_dice_overlap_values():
    assert dice_overlap(("a", "b"), ("a", "b")) == 1.0
    assert dice_overlap(("a", "b"), ("b", "c")) == pytest.approx(0.5)
    assert dice_overlap(("a",), ("b",)) == 0.0
    assert dice_overlap((), ()) == 1.0
    assert dice_overlap(("a",), ()) == 0.0


def test_alignment_ratio_perfect_and_empty():
    assert alignment_ratio(("acme", "corp"), ("corp", "acme")) == 1.0
    assert alignment_ratio((), ()) == 1.0
    assert alignment_ratio(("acme",), ()) == 0.0


def test_alignment_ratio_penalizes_extra_tokens_symmetrically():
    a_extra = alignment_ratio(("acme", "global", "widgets"), ("acme", "widgets"))
    b_extra = alignment_ratio(("acme", "widgets"), ("acme", "global", "widgets"))
    assert a_extra == pytest.approx(b_extra)
    assert a_extra < 1.0


def test_shared_and_unique_partitions_tokens():
    shared, only_a, only_b = shared_and_unique(("acme", "corp"), ("acme", "inc"))
    assert shared == ("acme",)
    assert only_a == ("corp",)
    assert only_b == ("inc",)
