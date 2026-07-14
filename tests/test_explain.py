"""Explanation rendering: short lines, long breakdowns, JSON dicts."""

import json

from nearjoin.explain import explain_dict, explain_long, explain_short
from nearjoin.scoring import score_pair


def test_short_explanation_is_one_line_for_exact_and_fuzzy():
    exact = explain_short(score_pair("Acme, Inc.", "ACME Corporation"))
    assert exact == "exact after normalization ('acme')"
    fuzzy = explain_short(score_pair("Northwind Traders", "Northwind Trading"))
    assert "\n" not in fuzzy
    for name in ("token_sort=", "token_overlap=", "char=", "alignment="):
        assert name in fuzzy


def test_short_explanation_includes_penalty_reason():
    match = score_pair("123 Main St", "125 Main St", kind="address")
    line = explain_short(match)
    assert "numeric_mismatch -30" in line
    assert "left has {123}" in line


def test_long_explanation_shows_both_normalization_traces():
    match = score_pair("Smith & Sons Ltd.", "Smith and Sons Limited")
    text = explain_long(match)
    assert "'Smith & Sons Ltd.' -> 'smith and sons'" in text
    assert "dropped legal suffix 'ltd'" in text
    assert "expanded '&' to 'and'" in text
    assert text.startswith("score 100 / 100")


def test_long_explanation_lists_penalties_or_none():
    clean = explain_long(score_pair("Acme", "Acme Widgets"))
    assert "penalties: none" in clean
    dirty = explain_long(score_pair("12 Oak Ln", "14 Oak Ln", kind="address"))
    assert "numeric_mismatch" in dirty


def test_explain_dict_round_trips_through_json():
    match = score_pair("Pinewood Analytics LLC", "Pinewood Analytica")
    payload = json.loads(json.dumps(explain_dict(match)))
    assert payload["score"] == match.score
    assert payload["left"]["normalized"] == "pinewood analytics"
    assert payload["left"]["steps"] == ["case-folded", "dropped legal suffix 'llc'"]
    assert len(payload["components"]) == 4
    assert payload["penalties"] == []
