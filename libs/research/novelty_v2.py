"""ONE novelty decision, over every dimension a clone can hide in.

WHY THIS EXISTS (principal, 2026-08-29: "Novelty V2 as one mandatory decision")

    EMA breakout
    Donchian breakout      -- four formulas
    ADX breakout           -- ONE alpha
    trend regression

The desk already owns pieces of this: `residual_novelty.branch_report` links on residual OR raw
correlation, the graveyard rejects on overlapping name tokens, the gauntlet measures correlation
to the book. None of them is THE novelty decision, so a candidate that fails one can still enter
through a door that checks a different one, and nothing ever combined them into a single verdict.
The result is measurable: n_eff ~5.5 across 23 certificates. The book has five and a half bets
wearing twenty-three name tags, and every one of them passed some novelty check.

SEVEN DIMENSIONS, BECAUSE A CLONE CAN HIDE IN ANY ONE OF THEM:

    name          cheapest, weakest -- and the only one previously enforced at intake
    semantic      same mechanism and coordinate, different words
    program       same computation, different spelling (AST shape)
    signal        same entries, different derivation
    trade overlap same fills at the same times
    gross pnl     same returns
    residual pnl  same returns AFTER removing what the book already earns -- the one that matters

RESIDUAL IS DECISIVE, RAW IS PROTECTIVE. A candidate can look novel on raw returns and be a clone
in residual space, which is the dangerous direction. It can also look like a clone on raw returns
purely through shared beta while carrying genuinely new residual -- valuable, and a residual-only
test would have kept it. So the verdict takes the MAXIMUM redundancy across dimensions: a
candidate must be novel on every axis, because being a duplicate on any one of them is enough to
make it worthless to the book.

THE FLOOR IS NOT A KILL. A duplicate returns REDUNDANT with the twin named, not "rejected" -- the
desk's own history has a case where a novelty rule discarded something that was actually the
better copy. Naming the twin lets the caller decide which survives.
"""
from __future__ import annotations

import ast
import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: Above this correlation on ANY dimension, two candidates are the same bet. 0.85 rather than
#: 0.95: by 0.95 two strategies are visually identical, and the pair that ruins a book's
#: independence sits at 0.85-0.92 looking like two ideas.
REDUNDANT_AT = 0.85

#: Minimum overlapping observations before a correlation means anything. Below this the estimate
#: is a rumour, and an unmeasurable correlation must never be READ AS NOVEL -- see `_verdict`.
MIN_OVERLAP = 20

#: Jaccard similarity of AST node-type multisets above this means the same computation.
PROGRAM_SAME_AT = 0.90

#: Dimensions that can actually establish novelty. Name and semantic similarity can only ever
#: CONVICT: a different name proves nothing, and two genuinely different mechanisms can share a
#: coordinate. Measured 2026-08-29: a candidate carrying nothing but a name was returned NOVEL,
#: because the name dimension was measurable and scored low -- letting a candidate earn novelty
#: by supplying LESS data than its rivals, which is the precise failure this module exists to
#: prevent. At least one of these must have been compared for a NOVEL verdict to mean anything.
STRONG_DIMENSIONS = frozenset({"program", "signal", "trade_overlap", "gross_pnl", "residual_pnl"})


@dataclass(frozen=True)
class NoveltyVerdict:
    novel: bool
    verdict: str                     # NOVEL | REDUNDANT | UNMEASURABLE
    worst_dimension: str
    worst_score: float
    nearest: str
    detail: dict[str, Any]

    def __bool__(self) -> bool:
        return self.novel


def _corr(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = min(len(a), len(b))
    if n < MIN_OVERLAP:
        return None
    a, b = list(a[:n]), list(b[:n])
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / math.sqrt(va * vb)


def ast_shape(source: str) -> Counter[str]:
    """Multiset of AST node types -- the computation's shape, independent of naming.

    Renaming every variable and reordering independent statements leaves this unchanged, which is
    exactly what a "new" candidate produced by mutating a formula's identifiers looks like.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return Counter()
    return Counter(type(n).__name__ for n in ast.walk(tree))


def program_similarity(src_a: str, src_b: str) -> float | None:
    a, b = ast_shape(src_a), ast_shape(src_b)
    if not a or not b:
        return None
    inter = sum((a & b).values())
    union = sum((a | b).values())
    return inter / union if union else None


def _name_similarity(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]{3,}", a.lower()))
    tb = set(re.findall(r"[a-z0-9]{3,}", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _trade_overlap(a: Sequence[Any], b: Sequence[Any]) -> float | None:
    """Jaccard over entry timestamps -- same fills at the same moments."""
    sa, sb = {str(x)[:16] for x in a}, {str(x)[:16] for x in b}
    if not sa or not sb:
        return None
    return len(sa & sb) / len(sa | sb)


def assess(candidate: dict[str, Any], incumbents: Sequence[dict[str, Any]]) -> NoveltyVerdict:
    """THE novelty decision. One call, every dimension, one verdict.

    Each dict may carry: `name`, `coordinate`, `mechanism`, `source`, `signal`, `entry_times`,
    `gross_pnl`, `residual_pnl`. Missing dimensions are SKIPPED, never scored as novel -- an
    absent measurement is not evidence of difference (LAWS L1.28a), and treating it as such would
    let a candidate earn novelty by supplying less data than its rivals.
    """
    worst_dim: str = ""
    worst_score: float = -1.0
    worst_twin: str = ""
    measured_any = False
    strong_measured: set[str] = set()
    per_incumbent: dict[str, dict[str, float]] = {}

    for inc in incumbents:
        twin = str(inc.get("name") or inc.get("artifact_id") or "?")
        scores: dict[str, float] = {}

        if candidate.get("name") and inc.get("name"):
            scores["name"] = _name_similarity(str(candidate["name"]), str(inc["name"]))

        # Semantic: identical coordinate AND mechanism is the same claim, whatever the words.
        if candidate.get("coordinate") and inc.get("coordinate"):
            same_coord = candidate["coordinate"] == inc["coordinate"]
            same_mech = (candidate.get("mechanism") or None) == (inc.get("mechanism") or object())
            scores["semantic"] = 1.0 if (same_coord and same_mech) else (0.6 if same_coord else 0.0)

        if candidate.get("source") and inc.get("source"):
            p = program_similarity(str(candidate["source"]), str(inc["source"]))
            if p is not None:
                scores["program"] = p

        for dim, key in (("signal", "signal"), ("gross_pnl", "gross_pnl"),
                         ("residual_pnl", "residual_pnl")):
            if candidate.get(key) and inc.get(key):
                c = _corr(candidate[key], inc[key])
                if c is not None:
                    scores[dim] = abs(c)

        if candidate.get("entry_times") and inc.get("entry_times"):
            o = _trade_overlap(candidate["entry_times"], inc["entry_times"])
            if o is not None:
                scores["trade_overlap"] = o

        if scores:
            measured_any = True
            strong_measured |= (set(scores) & STRONG_DIMENSIONS)
            per_incumbent[twin] = scores
            for dim, sc in scores.items():
                threshold = PROGRAM_SAME_AT if dim == "program" else REDUNDANT_AT
                # Normalise each dimension to "how close to its own duplicate threshold".
                normalised = sc / threshold
                if normalised > worst_score:
                    worst_dim, worst_score, worst_twin = dim, normalised, twin

    # UNMEASURABLE IS NOT NOVEL, and a NAME is not a measurement. A verdict resting only on weak
    # dimensions would let a candidate earn novelty by supplying less data than its rivals -- the
    # cheapest possible way past the one gate protecting the book's independence.
    if not measured_any or not strong_measured:
        redundant_on_weak = worst_score >= 1.0
        return NoveltyVerdict(
            False, "REDUNDANT" if redundant_on_weak else "UNMEASURABLE",
            worst_dim, round(max(worst_score, 0.0) * REDUNDANT_AT, 4), worst_twin,
            {"why": ("no STRONG dimension could be compared -- supply signal, pnl, entry times "
                     "or source. Name and coordinate similarity can CONVICT a duplicate but can "
                     "never establish novelty, and an unmeasured novelty claim is not a novelty "
                     "claim (LAWS L1.28a)."),
             "measured": sorted(strong_measured), "n_incumbents": len(incumbents)})

    dim = worst_dim
    raw = worst_score * (PROGRAM_SAME_AT if dim == "program" else REDUNDANT_AT)
    redundant = worst_score >= 1.0
    return NoveltyVerdict(
        not redundant,
        "REDUNDANT" if redundant else "NOVEL",
        dim, round(raw, 4), worst_twin,
        {"per_incumbent": per_incumbent,
         "rule": "max redundancy across dimensions -- a duplicate on ANY axis is worthless to "
                 "the book, however novel it looks on the others",
         "thresholds": {"correlation": REDUNDANT_AT, "program": PROGRAM_SAME_AT},
         "note": ("REDUNDANT names the twin rather than rejecting outright; which of the pair "
                  "survives is the caller's decision, not this module's")})


def fingerprint(candidate: dict[str, Any]) -> str:
    """Stable id over the novelty-bearing fields, for graveyard lookups."""
    payload = "|".join(str(candidate.get(k, "")) for k in
                       ("coordinate", "mechanism", "name"))
    shape = ast_shape(str(candidate.get("source", "")))
    payload += "|" + ",".join(f"{k}:{v}" for k, v in sorted(shape.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:20]
