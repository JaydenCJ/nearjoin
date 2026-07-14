"""The score model: exactness, blending, floors, and penalties."""

import pytest

from nearjoin.scoring import WEIGHTS, score_pair


def test_exact_after_normalization_scores_100():
    match = score_pair("Acme, Inc.", "ACME Corporation")
    assert match.score == 100.0
    assert match.exact
    assert match.components[0].name == "exact"
    assert score_pair("Blue Bottle Coffee", "Blue Bottle Coffee").score == 100.0


def test_unrelated_names_score_low():
    match = score_pair("Zenith Plumbing", "Bluebird Cafe")
    assert match.score < 40.0
    assert not match.exact


def test_close_names_land_between_and_round_to_one_decimal():
    match = score_pair("Northwind Traders", "Northwind Trading")
    assert 60.0 < match.score < 95.0
    assert match.score == round(match.score, 1)


def test_reordered_tokens_floor_at_95():
    match = score_pair("Sons & Smith", "Smith and Sons")
    assert match.score >= 95.0
    assert any(c.name == "reordered" for c in match.components)


def test_score_is_symmetric():
    a = score_pair("Pinewood Analytics", "Pinewood Analytica")
    b = score_pair("Pinewood Analytica", "Pinewood Analytics")
    assert a.score == b.score


def test_four_weighted_components_whose_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)
    match = score_pair("Delta Freight Lines", "Delta Freight Line")
    names = [c.name for c in match.components if c.weight > 0]
    assert names == ["token_sort", "token_overlap", "char", "alignment"]
    for component in match.components:
        assert 0.0 <= component.value <= 1.0


def test_address_numeric_mismatch_is_heavily_penalized():
    same = score_pair("123 Main Street", "123 Main St", kind="address")
    drift = score_pair("123 Main Street", "125 Main St", kind="address")
    assert same.score == 100.0
    assert drift.score <= same.score - 30.0
    penalty = drift.penalties[0]
    assert penalty.name == "numeric_mismatch"
    assert "123" in penalty.detail and "125" in penalty.detail


def test_name_numeric_mismatch_penalty_is_milder():
    name_drift = score_pair("Studio 54", "Studio 55", kind="name")
    addr_drift = score_pair("Studio 54", "Studio 55", kind="address")
    assert name_drift.score > addr_drift.score


def test_missing_number_on_one_side_is_a_smaller_penalty():
    missing = score_pair("Elm Avenue", "45 Elm Avenue", kind="address")
    assert missing.penalties[0].name == "numeric_missing"
    mismatch = score_pair("44 Elm Avenue", "45 Elm Avenue", kind="address")
    assert missing.penalties[0].points < mismatch.penalties[0].points


def test_equal_numbers_incur_no_penalty():
    match = score_pair("123 Main St", "123 Main Street", kind="address")
    assert match.penalties == ()


def test_empty_side_scores_zero_with_reason():
    match = score_pair("", "Acme Inc")
    assert match.score == 0.0
    assert match.components[0].name == "empty"


def test_score_clamped_to_zero_not_negative():
    # Tiny overlap plus the address numeric penalty could go negative; it must clamp.
    match = score_pair("1 Z", "9 Q", kind="address")
    assert match.score == 0.0


def test_cross_kind_scoring_rejected():
    from nearjoin.normalize import normalize
    from nearjoin.scoring import score_normalized

    with pytest.raises(ValueError):
        score_normalized(normalize("a", "name"), normalize("a", "address"))
