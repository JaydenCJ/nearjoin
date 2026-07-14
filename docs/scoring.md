# The nearjoin score model

Every number nearjoin prints can be reproduced by hand from this document.
That is the point: a reconciliation you cannot explain is a reconciliation
nobody signs off on.

## Pipeline

For each pair of values, in order:

1. **Normalize** both sides for the declared kind (`name` or `address`),
   recording every step that changed something (see below).
2. **Exact check** — identical normalized strings score **100** and stop here.
3. **Reorder check** — identical token multisets in a different order floor
   the score at **95** ("Sons & Smith" vs "Smith and Sons").
4. **Weighted blend** of four components, each in [0, 1], scaled to 100.
5. **Penalties** subtracted last, then clamp to [0, 100] and round to one
   decimal.

## Normalization steps

Common to both kinds: accent stripping (`Café` → `cafe`), case folding,
apostrophe joining (`O'Brien` → `obrien`), `&` → `and`, punctuation to
spaces, whitespace collapse.

| Kind | Extra rules |
| --- | --- |
| `name` | trailing legal suffixes dropped (`inc`, `llc`, `ltd`, `gmbh`, `corp`, `co`, …, long and short spellings); dangling trailing `and`; leading `the` |
| `address` | vocabulary canonicalized to short forms (`street` → `st`, `suite` → `ste`, `north` → `n`, `fifth` → `5th`, …); leading zeros trimmed from numbers |

A rule never empties a value: a company literally named "Inc" stays `inc`.

## Components

| Component | Weight | What it measures |
| --- | --- | --- |
| `token_sort` | 30% | Levenshtein ratio after sorting tokens — word order is free, typos are not |
| `token_overlap` | 20% | Sorensen–Dice coefficient over distinct tokens — shared vocabulary |
| `char` | 25% | Jaro–Winkler over the whole normalized strings — rewards shared prefixes |
| `alignment` | 25% | each token paired with its most similar counterpart, averaged in both directions — extra tokens cost both sides |

## Penalties

Numbers are treated as evidence, not as characters, because `123 Main St`
and `125 Main St` are 95% similar and 100% different buildings.

| Penalty | Address | Name | Trigger |
| --- | --- | --- | --- |
| `numeric_mismatch` | −30 | −12 | both sides contain numbers and the sets differ |
| `numeric_missing` | −10 | −4 | exactly one side contains numbers |

Names are charged less because a digit inside a company name ("Studio 54")
is weaker evidence of distinct entities than a house number is.

## Worked example

`nearjoin score "123 Main St" "125 Main St" --kind address`:

```text
score 56.6 / 100  [address]
  components:
    token_sort    0.909 x 30%   -> 27.3
    token_overlap 0.667 x 20%   -> 13.3
    char          0.952 x 25%   -> 23.8
    alignment     0.889 x 25%   -> 22.2
  blend                          = 86.6
  numeric_mismatch                -30.0
  score                          = 56.6
```

With the default review threshold of 70, this pair is not even offered for
review — which is exactly what you want for a house-number drift.

## Thresholds

`nearjoin join` sorts all candidate pairs by score and assigns them greedily,
one-to-one by default. Pairs scoring at or above `--threshold` (default 85)
become `match`; pairs in `[--review, --threshold)` (default 70) become
`review`; everything below stays unmatched. Ties break by row order, so the
same inputs always produce byte-identical output.
