"""MECHANISM FINGERPRINT -- the shared identity of an idea, used by #3 and #6 (HYPOTHESIS_MAX).

The spec defines one fingerprint and two consumers, so it lives in one place:

    fingerprint = feature family + signal transform + horizon bucket

  #3 TRIVIAL-VARIATION BLOCKER  two hypotheses with the same fingerprint are the SAME IDEA wearing
                                different parameters. Re-testing one is not new evidence, it is a
                                fresh multiplicity charge for a question already asked -- the
                                garden of forking paths with a lookback knob.
  #6 COLLAPSE DETECTOR          entropy over fingerprints across a generation batch. Collapse
                                shows as entropy falling while VOLUME HOLDS: the desk looks
                                productive and is asking one question repeatedly.

WHY THE BUCKETING IS COARSE ON PURPOSE. A 20-day and a 21-day lookback are the same hypothesis;
treating them as distinct is exactly the failure this exists to catch. Horizons therefore collapse
into log-spaced buckets (intraday / days / weeks / months / quarters), and continuous params are
dropped entirely -- they are the knob, never the idea. The cost of coarseness is occasionally
calling two genuinely different ideas the same; the cost of fineness is a desk that believes 400
reparameterisations of one mechanism are 400 tests. The second error is the one that has actually
happened here (420 candidates, 0 survivors), so the bucketing errs toward coarse.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

#: horizon in days -> bucket. Log-spaced, because the meaningful distinction between a 1-day and a
#: 5-day signal is large while 20 vs 21 days is noise.
_HORIZON_BUCKETS: tuple[tuple[float, str], ...] = (
    (1.0, "intraday"), (5.0, "days"), (21.0, "weeks"), (63.0, "months"),
    (252.0, "quarters"), (float("inf"), "annual+"),
)

#: signal transforms the desk actually uses, normalised to a canonical token.
_TRANSFORMS: dict[str, tuple[str, ...]] = {
    "zscore": ("zscore", "z-score", "standardi", "normali"),
    "rank": ("rank", "cross-section", "cross_section", "percentile", "decile", "quantile"),
    "momentum": ("momentum", "trend", "roc", "rate-of-change", "breakout"),
    "reversal": ("reversal", "mean-revert", "mean_revert", "contrarian", "fade"),
    "carry": ("carry", "funding", "basis", "roll", "yield"),
    "spread": ("spread", "divergence", "premium", "arb", "dislocation"),
    "level": ("level", "raw", "absolute", "threshold"),
    "vol": ("vol", "variance", "realized_vol", "garch", "dispersion"),
    "flow": ("flow", "netflow", "inflow", "outflow", "volume", "oi", "liquidation"),
}


def horizon_bucket(days: float | None) -> str:
    if days is None or days <= 0:
        return "unspecified"
    for upper, name in _HORIZON_BUCKETS:
        if float(days) <= upper:
            return name
    return "annual+"


def signal_transform(text: str) -> str:
    """The canonical transform named anywhere in the idea's text. First match wins, and the order
    of _TRANSFORMS is therefore meaningful -- specific mechanics before generic shapes."""
    low = (text or "").lower()
    for canon, needles in _TRANSFORMS.items():
        if any(n in low for n in needles):
            return canon
    return "unclassified"


def feature_family(hyp: Any) -> str:
    """The data axis an idea draws on. `family` when the model carries one, else the edge_source
    stem -- never the SYMBOL, because 40 symbols on one mechanism is one idea, not forty."""
    fam = getattr(hyp, "family", None)
    if fam is not None:
        return str(getattr(fam, "value", fam))
    src = str(getattr(hyp, "edge_source", "") or "")
    return src.split("/")[0].strip().lower() or "unknown"


def _horizon_of(hyp: Any) -> float | None:
    params = dict(getattr(hyp, "params", {}) or {})
    for key in ("horizon_days", "horizon", "lookback_days", "lookback", "window", "holding_days"):
        if key in params:
            try:
                return float(params[key])
            except (TypeError, ValueError):
                continue
    return None


def fingerprint(hyp: Any) -> str:
    """feature-family / signal-transform / horizon-bucket -- the idea, with the knobs removed."""
    text = " ".join(str(x) for x in (
        getattr(hyp, "subtype", ""), getattr(hyp, "edge_source", ""),
        getattr(getattr(hyp, "mechanism", None), "value", getattr(hyp, "mechanism", "")),
    ))
    return f"{feature_family(hyp)}/{signal_transform(text)}/{horizon_bucket(_horizon_of(hyp))}"


def fingerprint_hash(hyp: Any) -> str:
    return hashlib.sha256(fingerprint(hyp).encode("utf-8")).hexdigest()[:16]


_TOKEN = re.compile(r"[a-z0-9]+")
#: Words that carry no mechanism information. Without this the Jaccard proxy scores every pair as
#: similar on English scaffolding alone and the metric never moves.
_STOP = frozenset((
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are", "be", "as", "by",
    "with", "that", "this", "it", "its", "from", "at", "we", "our", "when", "than", "then",
    "signal", "strategy", "hypothesis", "returns", "return", "market", "price", "prices", "data",
))


def tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN.findall((text or "").lower())
                     if len(t) > 2 and t not in _STOP)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def describe(hyp: Any) -> str:
    """The text the semantic proxy compares. Excludes SYMBOL and raw numeric params -- the same
    mechanism on BTC and on ETH is one idea -- but INCLUDES the horizon bucket.

    THE BUG THAT REQUIRED THE HORIZON, caught by its own test: without it a 7-day and a 90-day
    carry signal produced identical token sets, so the near-duplicate check scored them at
    Jaccard 1.00 and BLOCKED the 90-day version -- despite their fingerprints differing
    (carry/carry/weeks vs carry/carry/quarters). The semantic proxy was overriding the structured
    dimension it is supposed to complement, and silently deleting a genuinely different question.
    That is precisely the over-tight-funnel failure this whole module warns about, produced by the
    module itself. The proxy must agree with the fingerprint, never fight it.
    """
    return " ".join(str(x) for x in (
        feature_family(hyp), getattr(hyp, "subtype", ""), getattr(hyp, "edge_source", ""),
        getattr(getattr(hyp, "mechanism", None), "value", ""),
        f"horizon_{horizon_bucket(_horizon_of(hyp))}",
        " ".join(getattr(hyp, "failure_modes", []) or []),
    ))
