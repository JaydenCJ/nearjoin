"""Normalization for names and addresses, with a human-readable trace.

The whole point of nearjoin is that every match is defensible, so
normalization never happens silently: ``normalize()`` returns a
:class:`Normalized` value that carries the original text, the canonical
form, and the ordered list of steps that changed something. The explanation
layer replays those steps back to the user verbatim.

Everything here is pure and deterministic — no locale calls, no network,
standard library only.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Sequence, Tuple

# Kinds understood by the scorer. "auto" is resolved by detect_kind() before
# normalization ever runs; normalize() itself only accepts the concrete two.
KIND_NAME = "name"
KIND_ADDRESS = "address"
KINDS = (KIND_NAME, KIND_ADDRESS)

_APOSTROPHES = "'’ʼ`´"
_WORD_RE = re.compile(r"[^0-9a-z\s]")
_WS_RE = re.compile(r"\s+")
_NUM_RE = re.compile(r"\d+")

# Trailing legal-form tokens dropped from company names. Keys are the surface
# forms seen after case folding; values are the canonical short form used in
# the trace ("dropped legal suffix 'inc'").
LEGAL_SUFFIXES = {
    "inc": "inc",
    "incorporated": "inc",
    "corp": "corp",
    "corporation": "corp",
    "co": "co",
    "company": "co",
    "ltd": "ltd",
    "limited": "ltd",
    "llc": "llc",
    "llp": "llp",
    "lp": "lp",
    "plc": "plc",
    "gmbh": "gmbh",
    "ag": "ag",
    "sa": "sa",
    "srl": "srl",
    "bv": "bv",
    "nv": "nv",
    "oy": "oy",
    "ab": "ab",
    "as": "as",
    "kk": "kk",
    "pty": "pty",
    "pte": "pte",
}

# Address vocabulary canonicalized to USPS-style short forms. Both long and
# short spellings map to the same canonical token so "Street" == "St.".
ADDRESS_ABBREVIATIONS = {
    "street": "st",
    "avenue": "ave",
    "av": "ave",
    "boulevard": "blvd",
    "road": "rd",
    "drive": "dr",
    "lane": "ln",
    "court": "ct",
    "place": "pl",
    "plaza": "plz",
    "square": "sq",
    "terrace": "ter",
    "parkway": "pkwy",
    "highway": "hwy",
    "circle": "cir",
    "crescent": "cres",
    "suite": "ste",
    "apartment": "apt",
    "building": "bldg",
    "floor": "fl",
    "room": "rm",
    "department": "dept",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northeast": "ne",
    "northwest": "nw",
    "southeast": "se",
    "southwest": "sw",
    "first": "1st",
    "second": "2nd",
    "third": "3rd",
    "fourth": "4th",
    "fifth": "5th",
    "sixth": "6th",
    "seventh": "7th",
    "eighth": "8th",
    "ninth": "9th",
    "tenth": "10th",
}

# Tokens that survive normalization but carry little identity on their own;
# blocking skips them when building prefix keys.
STOPWORDS = frozenset({"the", "and", "of", "de", "la", "le", "el", "di"})


@dataclass(frozen=True)
class Normalized:
    """A normalized value plus the trace of how it got that way."""

    raw: str
    text: str
    tokens: Tuple[str, ...]
    kind: str
    steps: Tuple[str, ...] = field(default=())
    numbers: Tuple[str, ...] = field(default=())

    def __bool__(self) -> bool:
        return bool(self.text)


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(value: str, kind: str = KIND_NAME) -> Normalized:
    """Normalize ``value`` for matching, recording every step that mattered.

    The pipeline is: accent stripping, case folding, apostrophe joining
    ("O'Brien" -> "obrien"), '&' -> 'and', punctuation-to-space, whitespace
    collapse, then kind-specific token rules (legal-suffix dropping for
    names, abbreviation canonicalization and leading-zero trimming for
    addresses).
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")

    steps: list = []
    text = value.strip()

    folded = _strip_accents(text)
    if folded != text:
        steps.append(f"stripped accents ({text!r} -> {folded!r})")
        text = folded

    lowered = text.casefold()
    if lowered != text:
        steps.append("case-folded")
        text = lowered

    without_apostrophes = "".join(ch for ch in text if ch not in _APOSTROPHES)
    if without_apostrophes != text:
        steps.append("joined apostrophes")
        text = without_apostrophes

    if "&" in text:
        text = text.replace("&", " and ")
        steps.append("expanded '&' to 'and'")

    depunctuated = _WORD_RE.sub(" ", text)
    if depunctuated != text:
        steps.append("removed punctuation")
        text = depunctuated

    collapsed = _WS_RE.sub(" ", text).strip()
    text = collapsed
    tokens = text.split(" ") if text else []

    if kind == KIND_NAME:
        tokens = _apply_name_rules(tokens, steps)
    else:
        tokens = _apply_address_rules(tokens, steps)

    text = " ".join(tokens)
    numbers = tuple(_NUM_RE.findall(text))
    return Normalized(
        raw=value,
        text=text,
        tokens=tuple(tokens),
        kind=kind,
        steps=tuple(steps),
        numbers=numbers,
    )


def _apply_name_rules(tokens: list, steps: list) -> list:
    tokens = list(tokens)
    # Drop trailing legal-form tokens, possibly several ("co ltd"), but never
    # empty the name: "Inc" alone stays "inc".
    while len(tokens) > 1 and tokens[-1] in LEGAL_SUFFIXES:
        dropped = tokens.pop()
        steps.append(f"dropped legal suffix {LEGAL_SUFFIXES[dropped]!r}")
    # "Tiffany & Co" -> "tiffany and" after the suffix drop; the dangling
    # conjunction carries no identity.
    while len(tokens) > 1 and tokens[-1] == "and":
        tokens.pop()
        steps.append("dropped trailing 'and'")
    if len(tokens) > 1 and tokens[0] == "the":
        tokens.pop(0)
        steps.append("dropped leading 'the'")
    return tokens


def _apply_address_rules(tokens: list, steps: list) -> list:
    out = []
    for token in tokens:
        canonical = ADDRESS_ABBREVIATIONS.get(token, token)
        if canonical != token:
            steps.append(f"canonicalized {token!r} -> {canonical!r}")
            token = canonical
        if token.isdigit() and len(token) > 1 and token[0] == "0":
            trimmed = token.lstrip("0") or "0"
            steps.append(f"trimmed leading zeros ({token!r} -> {trimmed!r})")
            token = trimmed
        out.append(token)
    return out


def detect_kind(values: Iterable[str], sample: int = 200) -> str:
    """Guess whether a column holds names or addresses.

    A value votes "address" when it contains a digit or a known address
    token; the column is an address column when at least half of the sampled
    non-empty values vote that way. Deterministic: the first ``sample``
    non-empty values decide.
    """
    votes = 0
    seen = 0
    vocabulary = set(ADDRESS_ABBREVIATIONS) | set(ADDRESS_ABBREVIATIONS.values())
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        seen += 1
        lowered = stripped.casefold()
        tokens = _WS_RE.split(_WORD_RE.sub(" ", lowered).strip())
        if any(ch.isdigit() for ch in lowered) or any(t in vocabulary for t in tokens):
            votes += 1
        if seen >= sample:
            break
    if seen == 0:
        return KIND_NAME
    return KIND_ADDRESS if votes * 2 >= seen else KIND_NAME


def significant_tokens(tokens: Sequence[str]) -> Tuple[str, ...]:
    """Tokens worth blocking on: everything that is not a stopword."""
    kept = tuple(t for t in tokens if t not in STOPWORDS)
    return kept if kept else tuple(tokens)
