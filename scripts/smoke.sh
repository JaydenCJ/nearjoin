#!/usr/bin/env bash
# Smoke test for nearjoin: join the bundled example files on names and on
# addresses, check verdicts and unmatched handling, and exercise the score
# and keys subcommands. Self-contained: pure stdlib, no network, idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# The package has zero runtime dependencies, so running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/nearjoin-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

LEFT="$ROOT/examples/customers_crm.csv"
RIGHT="$ROOT/examples/customers_billing.csv"

# 1. Name join: matched pairs, review band, and unmatched files.
"$PYTHON" -m nearjoin join "$LEFT" "$RIGHT" \
  --left-on name --right-on customer --kind name \
  -o "$WORKDIR/matched.csv" \
  --unmatched-left "$WORKDIR/left_only.csv" \
  --unmatched-right "$WORKDIR/right_only.csv" \
  2> "$WORKDIR/summary.txt" || fail "name join exited non-zero"
sed 's/^/[join] /' "$WORKDIR/summary.txt"
grep -q "matched 9, review 1" "$WORKDIR/summary.txt" \
  || fail "summary did not report 9 matches and 1 review"
grep -q "exact after normalization ('acme')" "$WORKDIR/matched.csv" \
  || fail "Acme match lost its explanation"
grep -q "Northwind Traders.*review" "$WORKDIR/matched.csv" \
  || fail "Northwind pair was not flagged for review"
grep -q "Ironclad Security" "$WORKDIR/left_only.csv" \
  || fail "unmatched-left missing Ironclad Security"
grep -q "Kings Cross Hardware" "$WORKDIR/right_only.csv" \
  || fail "unmatched-right missing Kings Cross Hardware"
grep -q "Ironclad" "$WORKDIR/matched.csv" \
  && fail "unmatched row leaked into the match output"

# 2. Address join with auto-detection: the 45-vs-47 house-number drift must
#    NOT be silently matched.
"$PYTHON" -m nearjoin join "$LEFT" "$RIGHT" \
  --left-on address --right-on street_address \
  -o "$WORKDIR/addr.csv" 2> "$WORKDIR/addr_summary.txt" \
  || fail "address join exited non-zero"
grep -q "kind=address" "$WORKDIR/addr_summary.txt" \
  || fail "auto-detection did not pick kind=address"
grep -q "45 Elm Avenue" "$WORKDIR/addr.csv" \
  && fail "house-number drift 45 vs 47 was silently matched"
grep -q "123 Main Street.*123 Main St Ste 4" "$WORKDIR/addr.csv" \
  || fail "abbreviation-equivalent addresses did not match"

# 3. JSON output parses and carries full explanations.
"$PYTHON" -m nearjoin join "$LEFT" "$RIGHT" \
  --left-on name --right-on customer --quiet --format json \
  -o "$WORKDIR/result.json" || fail "json join exited non-zero"
"$PYTHON" - "$WORKDIR/result.json" <<'PY' || fail "json output invalid or incomplete"
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert len(payload["matches"]) == 10, "expected 10 kept pairs"
first = payload["matches"][0]["explanation"]
assert first["left"]["steps"], "explanation lost the normalization trace"
PY

# 4. score: penalty for numeric drift is spelled out.
score_out="$("$PYTHON" -m nearjoin score "123 Main St" "125 Main St" --kind address)"
echo "$score_out" | sed 's/^/[score] /'
echo "$score_out" | grep -q "numeric_mismatch" || fail "score missing numeric penalty"
echo "$score_out" | grep -q "left has {123}" || fail "score missing penalty detail"

# 5. keys: normalization trace and blocking keys are shown.
keys_out="$("$PYTHON" -m nearjoin keys "The Hilltop Bakery Inc.")"
echo "$keys_out" | grep -q "normalized: 'hilltop bakery'" || fail "keys missing normal form"
echo "$keys_out" | grep -q "dropped legal suffix 'inc'" || fail "keys missing trace step"
echo "$keys_out" | grep -q "p4:hill" || fail "keys missing prefix key"

# 6. Clean errors: bad column exits 2 without a traceback.
set +e
err_out="$("$PYTHON" -m nearjoin join "$LEFT" "$RIGHT" --left-on company 2>&1)"
err_rc=$?
set -e
[ "$err_rc" -eq 2 ] || fail "bad column should exit 2, got $err_rc"
echo "$err_out" | grep -q "column 'company' not found" || fail "bad-column error unhelpful"
echo "$err_out" | grep -q "Traceback" && fail "bad column printed a traceback"

# 7. --version agrees with the package.
version_out="$("$PYTHON" -m nearjoin --version)"
pkg_version="$("$PYTHON" -c 'import nearjoin; print(nearjoin.__version__)')"
[ "$version_out" = "nearjoin $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"

echo "SMOKE OK"
