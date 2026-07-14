"""nearjoin — fuzzy-join two datasets on names or addresses, explainably.

Public API:

- :func:`normalize` / :class:`Normalized` — canonicalize a name or address
  with a recorded trace of every step.
- :func:`score_pair` / :class:`MatchScore` — score two strings 0-100 with
  weighted components and explicit penalties.
- :func:`join_values` / :class:`JoinResult` — the full pipeline: normalize,
  block, score, assign one-to-one.
- :func:`explain_short` / :func:`explain_long` — render a MatchScore as text.

Zero runtime dependencies; everything is deterministic and offline.
"""

from .blocking import BlockingStats, blocking_keys, candidate_pairs
from .errors import (
    ColumnNotFoundError,
    EmptyInputError,
    InvalidThresholdError,
    NearjoinError,
)
from .explain import explain_dict, explain_long, explain_short
from .joiner import (
    DEFAULT_ACCEPT,
    DEFAULT_REVIEW,
    JoinResult,
    Match,
    join_values,
)
from .normalize import KIND_ADDRESS, KIND_NAME, Normalized, detect_kind, normalize
from .scoring import Component, MatchScore, Penalty, score_pair

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BlockingStats",
    "blocking_keys",
    "candidate_pairs",
    "ColumnNotFoundError",
    "Component",
    "detect_kind",
    "DEFAULT_ACCEPT",
    "DEFAULT_REVIEW",
    "EmptyInputError",
    "explain_dict",
    "explain_long",
    "explain_short",
    "InvalidThresholdError",
    "join_values",
    "JoinResult",
    "KIND_ADDRESS",
    "KIND_NAME",
    "Match",
    "MatchScore",
    "NearjoinError",
    "normalize",
    "Normalized",
    "Penalty",
    "score_pair",
]
