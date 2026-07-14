"""Render MatchScore values as text a stakeholder can read.

Two renderers:

- :func:`explain_short` — one line, safe for a CSV cell, no newlines.
- :func:`explain_long` — a multi-line breakdown for the terminal, including
  the normalization trace of both sides.

Both work purely from the data already stored on the MatchScore; nothing is
recomputed, so what you read is exactly what was scored.
"""

from __future__ import annotations

from typing import List

from .scoring import MatchScore


def explain_short(match: MatchScore) -> str:
    """A single-line summary: components, then penalties if any."""
    if match.exact:
        return f"exact after normalization ({match.left.text!r})"
    parts = [
        f"{c.name}={c.value:.2f}" for c in match.components if c.weight > 0.0
    ]
    for component in match.components:
        if component.weight == 0.0:
            parts.append(component.name)
    for penalty in match.penalties:
        parts.append(f"{penalty.name} -{penalty.points:g} ({penalty.detail})")
    return "; ".join(parts)


def explain_long(match: MatchScore) -> str:
    """A multi-line, indented breakdown of the whole score."""
    lines: List[str] = []
    lines.append(f"score {match.score:g} / 100  [{match.kind}]")
    lines.append(f"  left : {match.left.raw!r} -> {match.left.text!r}")
    _append_steps(lines, match.left.steps)
    lines.append(f"  right: {match.right.raw!r} -> {match.right.text!r}")
    _append_steps(lines, match.right.steps)
    lines.append("  components:")
    for component in match.components:
        if component.weight > 0.0:
            lines.append(
                f"    {component.name:<13} {component.value:.3f} x {component.weight:.0%}"
                f"  {component.detail}"
            )
        else:
            lines.append(f"    {component.name:<13} {component.detail}")
    if match.penalties:
        lines.append("  penalties:")
        for penalty in match.penalties:
            lines.append(
                f"    {penalty.name:<16} -{penalty.points:g}  {penalty.detail}"
            )
    else:
        lines.append("  penalties: none")
    return "\n".join(lines)


def explain_dict(match: MatchScore) -> dict:
    """A JSON-friendly representation of the full explanation."""
    return {
        "score": match.score,
        "kind": match.kind,
        "exact": match.exact,
        "left": {
            "raw": match.left.raw,
            "normalized": match.left.text,
            "steps": list(match.left.steps),
        },
        "right": {
            "raw": match.right.raw,
            "normalized": match.right.text,
            "steps": list(match.right.steps),
        },
        "components": [
            {
                "name": c.name,
                "value": round(c.value, 4),
                "weight": c.weight,
                "detail": c.detail,
            }
            for c in match.components
        ],
        "penalties": [
            {"name": p.name, "points": p.points, "detail": p.detail}
            for p in match.penalties
        ],
    }


def _append_steps(lines: List[str], steps) -> None:
    if steps:
        for step in steps:
            lines.append(f"         - {step}")
