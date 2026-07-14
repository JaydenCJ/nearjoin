# Contributing to nearjoin

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/JaydenCJ/nearjoin
cd nearjoin
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest                 # 91 offline unit/CLI tests
bash scripts/smoke.sh  # end-to-end: name join, address join, score, keys, errors
```

Both must pass before a pull request is reviewed; the smoke script prints
`SMOKE OK` on success. Everything runs offline in well under a minute — no
API keys, no network, no data leaves your machine.

## Before you open a pull request

1. Format and lint if you have the tools (`ruff format` / `ruff check`); keep
   the style of the surrounding code either way.
2. `pytest` must pass.
3. `bash scripts/smoke.sh` must print `SMOKE OK`.
4. Add tests for behavior changes; keep logic in the pure modules
   (`normalize`, `similarity`, `blocking`, `scoring`, `joiner`) and out of
   `cli.py`.

## Ground rules

- **No new runtime dependencies.** The package is standard-library only;
  that is a feature. Test-only dependencies belong in the `dev` extra.
- **Every score must stay explainable.** A change that improves accuracy but
  cannot be rendered by `explain_long` in plain language will not be merged.
- **Determinism is part of the contract.** Same inputs, byte-identical
  output — no wall clock, no randomness, no locale-dependent behavior.
- **Keep the three READMEs aligned.** `README.md`, `README.zh.md`, and
  `README.ja.md` are line-for-line translations; update all three when you
  change one (English is the authoritative version).
- Code comments and doc comments are written in English.

## Reporting bugs

Please include `nearjoin --version`, the exact command line, and a minimal
pair of CSV snippets that reproduces the problem (a handful of rows is
usually enough — scrub anything sensitive first). For scoring disputes,
paste the output of `nearjoin score LEFT RIGHT --json`.

## Security

Please do not open public issues for security problems; use GitHub's
private vulnerability reporting on this repository instead.
