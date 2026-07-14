"""The join pipeline: assignment, verdicts, thresholds, determinism."""

import pytest

from nearjoin.errors import InvalidThresholdError
from nearjoin.joiner import VERDICT_MATCH, VERDICT_REVIEW, join_values


def test_basic_join_matches_the_obvious_pairs():
    result = join_values(
        ["Acme Inc", "Blue Bottle Coffee Co"],
        ["Blue Bottle Coffee", "ACME Corporation"],
        kind="name",
    )
    pairs = {(m.left_index, m.right_index) for m in result.matches}
    assert pairs == {(0, 1), (1, 0)}
    assert all(m.verdict == VERDICT_MATCH for m in result.matches)
    assert result.unmatched_left == ()
    assert result.unmatched_right == ()


def test_matches_are_sorted_by_left_index():
    result = join_values(
        ["Cafe Aurora", "Acme Inc", "Hilltop Bakery"],
        ["Hilltop Bakery", "Acme Inc", "Cafe Aurora"],
        kind="name",
    )
    assert [m.left_index for m in result.matches] == [0, 1, 2]


def test_review_band_between_thresholds():
    result = join_values(
        ["Northwind Traders"], ["Northwind Trading"], kind="name",
        accept_threshold=85.0, review_threshold=70.0,
    )
    assert len(result.matches) == 1
    assert result.matches[0].verdict == VERDICT_REVIEW
    assert result.match_count == 0
    assert result.review_count == 1


def test_below_review_threshold_stays_unmatched():
    result = join_values(
        ["Zenith Plumbing"], ["Zebra Products"], kind="name",
    )
    assert result.matches == ()
    assert result.unmatched_left == (0,)
    assert result.unmatched_right == (0,)


def test_one_to_one_gives_the_right_row_to_the_best_left():
    # Both lefts resemble the single right; the closer one must win it.
    result = join_values(
        ["Pinewood Analytics", "Pinewood Analytica LLC"],
        ["Pinewood Analytica"],
        kind="name",
        review_threshold=50.0,
    )
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.left_index == 1  # exact after normalization
    assert match.score.score == 100.0
    assert result.unmatched_left == (0,)


def test_many_mode_lets_one_right_serve_multiple_lefts():
    result = join_values(
        ["Acme Inc", "ACME Corp"], ["Acme"], kind="name", one_to_one=False,
    )
    assert {(m.left_index, m.right_index) for m in result.matches} == {(0, 0), (1, 0)}


def test_ties_break_by_row_order_for_determinism():
    # Two identical rights; the first one (lowest index) must be claimed.
    result = join_values(["Acme"], ["Acme", "Acme"], kind="name")
    assert result.matches[0].right_index == 0
    assert result.unmatched_right == (1,)


def test_join_is_reproducible():
    lefts = ["Acme Inc", "Hilltop Bakery", "Cafe Aurora", "Delta Freight"]
    rights = ["Delta Freight Lines", "The Hilltop Bakery", "ACME Corp"]
    first = join_values(lefts, rights, kind="name")
    second = join_values(lefts, rights, kind="name")
    assert [(m.left_index, m.right_index, m.score.score) for m in first.matches] == [
        (m.left_index, m.right_index, m.score.score) for m in second.matches
    ]


def test_auto_kind_resolves_from_the_data():
    addresses = join_values(["123 Main St"], ["123 Main Street"], kind="auto")
    assert addresses.kind == "address"
    names = join_values(["Acme Inc"], ["ACME Corp"], kind="auto")
    assert names.kind == "name"


def test_empty_values_never_match_each_other():
    # Two blank cells are not evidence of the same entity.
    result = join_values(["", "Acme"], ["", "Acme Inc"], kind="name")
    assert {(m.left_index, m.right_index) for m in result.matches} == {(1, 1)}
    assert result.unmatched_left == (0,)
    assert result.unmatched_right == (0,)


def test_invalid_thresholds_and_kind_rejected():
    with pytest.raises(InvalidThresholdError):
        join_values(["a"], ["a"], review_threshold=90.0, accept_threshold=80.0)
    with pytest.raises(InvalidThresholdError):
        join_values(["a"], ["a"], accept_threshold=120.0)
    with pytest.raises(ValueError):
        join_values(["a"], ["a"], kind="zipcode")


def test_blocking_stats_are_reported():
    result = join_values(
        ["Acme Inc", "Zenith Plumbing"], ["ACME Corp", "Bluebird Cafe"], kind="name",
    )
    assert result.blocking.pairs_possible == 4
    assert result.blocking.pairs_compared < 4
