"""Normalization: canonical forms, the recorded trace, and kind detection."""

import pytest

from nearjoin.normalize import (
    KIND_ADDRESS,
    KIND_NAME,
    detect_kind,
    normalize,
    significant_tokens,
)


def test_case_folding_is_recorded_and_canonical_input_records_nothing():
    folded = normalize("ACME", KIND_NAME)
    assert folded.text == "acme"
    assert "case-folded" in folded.steps
    untouched = normalize("acme widgets", KIND_NAME)
    assert untouched.text == "acme widgets"
    assert untouched.steps == ()


def test_accents_are_stripped_and_traced():
    norm = normalize("Café Aurora", KIND_NAME)
    assert norm.text == "cafe aurora"
    assert any("stripped accents" in step for step in norm.steps)


def test_apostrophes_join_rather_than_split():
    # "O'Brien" must become "obrien", not "o brien" — otherwise it can never
    # match the apostrophe-less spelling common in exports.
    norm = normalize("O'Brien Consulting", KIND_NAME)
    assert norm.text == "obrien consulting"


def test_ampersand_expands_to_and():
    norm = normalize("Smith & Sons", KIND_NAME)
    assert norm.text == "smith and sons"
    assert "expanded '&' to 'and'" in norm.steps


def test_punctuation_becomes_token_separator():
    norm = normalize("Acme,Inc.", KIND_NAME)
    # The comma splits the tokens, then the legal suffix drops.
    assert norm.text == "acme"


def test_legal_suffix_dropped_and_named_in_trace():
    norm = normalize("Pinewood Analytics LLC", KIND_NAME)
    assert norm.text == "pinewood analytics"
    assert "dropped legal suffix 'llc'" in norm.steps


def test_stacked_legal_suffixes_all_drop_but_never_empty_the_name():
    norm = normalize("Kobayashi Trading Co Ltd", KIND_NAME)
    assert norm.text == "kobayashi trading"
    # A company literally named "Inc" must not normalize to nothing.
    assert normalize("Inc", KIND_NAME).text == "inc"


def test_trailing_and_dropped_after_suffix():
    # "Tiffany & Co" -> "tiffany and" after dropping "co"; the dangling
    # conjunction carries no identity and must go too.
    norm = normalize("Tiffany & Co", KIND_NAME)
    assert norm.text == "tiffany"


def test_leading_the_dropped_for_names():
    norm = normalize("The Home Improvement Depot", KIND_NAME)
    assert norm.tokens[0] == "home"
    assert "dropped leading 'the'" in norm.steps


def test_address_abbreviations_canonicalize_both_directions():
    long_form = normalize("123 Main Street, Suite 4", KIND_ADDRESS)
    short_form = normalize("123 Main St Ste 4", KIND_ADDRESS)
    assert long_form.text == short_form.text == "123 main st ste 4"


def test_ordinal_words_become_digit_ordinals():
    assert normalize("900 Fifth Avenue", KIND_ADDRESS).text == "900 5th ave"


def test_leading_zeros_trimmed_and_numbers_extracted_in_order():
    norm = normalize("007 Elm St", KIND_ADDRESS)
    assert norm.text == "7 elm st"
    assert norm.numbers == ("7",)
    multi = normalize("Unit 12, 300 Industrial Pkwy", KIND_ADDRESS)
    assert multi.numbers == ("12", "300")


def test_empty_and_whitespace_values_normalize_to_falsy():
    assert not normalize("", KIND_NAME)
    assert not normalize("   ", KIND_ADDRESS)


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        normalize("acme", "postcode")


def test_detect_kind_separates_address_and_name_columns():
    addresses = ["123 Main St", "45 Elm Avenue", "1 Harbor Blvd", "78 Oak Lane"]
    assert detect_kind(addresses) == KIND_ADDRESS
    names = ["Acme Inc", "Blue Bottle Coffee", "Smith & Sons", "Cafe Aurora"]
    assert detect_kind(names) == KIND_NAME


def test_detect_kind_empty_input_defaults_to_name():
    assert detect_kind([]) == KIND_NAME
    assert detect_kind(["", "  "]) == KIND_NAME


def test_significant_tokens_drop_stopwords_but_never_everything():
    assert significant_tokens(("bank", "of", "springfield")) == ("bank", "springfield")
    # All-stopword input falls back to the original tokens.
    assert significant_tokens(("the", "and")) == ("the", "and")
