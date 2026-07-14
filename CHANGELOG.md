# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-13

### Added

- Traced normalization for names and addresses: accent stripping, case
  folding, apostrophe joining, `&` → `and`, punctuation handling, legal-suffix
  dropping (`inc`/`llc`/`ltd`/`gmbh`/…, long and short spellings), USPS-style
  address canonicalization (`Street` → `st`, `Suite` → `ste`, `Fifth` → `5th`),
  and leading-zero trimming — every step recorded and replayed in
  explanations, never applied silently.
- Zero-dependency similarity primitives: Levenshtein distance and ratio,
  Jaro and Jaro–Winkler, token-sort ratio, Sorensen–Dice token overlap, and
  bidirectional best-token alignment.
- Transparent score model (documented in `docs/scoring.md`): exact-after-
  normalization = 100, reordered-tokens floor at 95, a four-component
  weighted blend, and explicit numeric penalties so `123 Main St` never
  silently matches `125 Main St`.
- Blocking with prefix, initials, and numeric keys plus measured stats
  (pairs compared vs the full cross product), so joins are not O(n×m).
- One-to-one greedy assignment with deterministic tie-breaking, an accept
  threshold, a human-review band, and `--many` to opt out of exclusivity.
- CLI: `join` (CSV or JSON output, `--unmatched-left/right` side files,
  `--kind auto|name|address` with auto-detection), `score` (full breakdown,
  `--json`), and `keys` (normalization trace + blocking keys).
- Library API re-exported from the package root: `normalize`, `score_pair`,
  `join_values`, `explain_short/long/dict`, and the result dataclasses.
- Bundled example customer lists from two fictional systems under
  `examples/`.
- 91 offline pytest tests and `scripts/smoke.sh` (prints `SMOKE OK`).

### Notes

- The repository ships no CI workflow; verification is local —
  `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/nearjoin/releases/tag/v0.1.0
