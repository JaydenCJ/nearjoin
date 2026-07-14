"""Blocking: key construction, candidate recall, and the stats contract."""

from nearjoin.blocking import blocking_keys, candidate_pairs, stats_for
from nearjoin.normalize import KIND_ADDRESS, KIND_NAME, normalize


def keys(value, kind=KIND_NAME):
    return blocking_keys(normalize(value, kind))


def test_prefix_keys_from_significant_tokens():
    assert "p4:hill" in keys("Hilltop Bakery")
    assert "p4:bake" in keys("Hilltop Bakery")


def test_stopwords_get_no_prefix_key_but_count_in_initials():
    got = keys("Bank of Springfield")
    assert "p4:of" not in got
    # Initials cover all tokens including the stopword, sorted.
    assert "init:bos" in got


def test_numeric_tokens_become_num_keys_not_prefixes():
    got = keys("123 Main St", KIND_ADDRESS)
    assert "num:123" in got
    assert "p4:123" not in got


def test_identical_normal_forms_share_all_keys():
    assert keys("Smith & Sons Ltd") == keys("Smith and Sons Limited")


def test_typo_in_suffix_still_shares_a_prefix_key():
    assert keys("Johnson Freight") & keys("Johnsen Freight")


def test_reordered_words_share_the_initials_key():
    assert keys("Sons & Smith") & keys("Smith and Sons")


def test_empty_value_gets_no_keys():
    assert keys("") == frozenset()


def test_candidate_pairs_have_high_recall_and_skip_strangers():
    lefts = [normalize(v) for v in ("Acme Inc", "Zenith Plumbing", "")]
    rights = [normalize(v) for v in ("ACME Corporation", "Bluebird Cafe")]
    candidates = candidate_pairs(lefts, rights)
    assert candidates[0] == [0]      # acme finds acme
    assert candidates[1] == []       # zenith never meets bluebird
    assert candidates[2] == []       # empty value can never match
    stats = stats_for(lefts, rights, candidates)
    assert stats.pairs_compared == 1
    assert stats.pairs_possible == 6
    assert 0.0 < stats.reduction < 1.0
    # No rows -> no division by zero, reduction reads as 0.
    empty_stats = stats_for([], [], {})
    assert empty_stats.pairs_possible == 0
    assert empty_stats.reduction == 0.0
