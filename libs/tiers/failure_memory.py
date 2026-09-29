"""THE NEGATIVE-KNOWLEDGE CIVILIZATION AND SCIENTIFIC MEMORY COMPRESSION (Tier S layers 13, 45).

`desks/mt5/research/negative_knowledge.py` already trains P(survive) from the gate that killed
each cell, and the generators consult it. What it does not hold is WHY, as a typed cause, nor a
compressed statement a new researcher can read in one line. This adds both.

TYPED CAUSES. Every failure is mapped from its terminal gate (and any reason text) to one of:

    NO_SIGNAL, NO_CAUSAL_SUPPORT, SELECTION_ARTEFACT, UNSTABLE, COSTS_KILLED, OVERFIT_HOLDOUT,
    REGIME_SPECIFIC, CONDITIONAL_ONLY, DUPLICATED_EXPOSURE, CAPACITY_LIMITED,
    IMPLEMENTATION_IMPOSSIBLE, LIVE_DECAY, LOOKAHEAD, DATA_DEFECT, UNKNOWN

EQUIVALENCE CLASSES. Failures are grouped by (mechanism, asset class, selector/horizon). A class
with enough trials, no survivor and one dominant cause becomes a FAILURE THEOREM:

    "session_range_breakout on FX_MINOR in asia fails by COSTS_KILLED (57/61 trials, 0 survivors)"

with provenance: the evidence rows' hash and a sample of the cell ids, so a theorem can always be
walked back to raw verdicts. `neighbourhood()` retrieves the theorems relevant to a new candidate
("we have explored this conceptual neighbourhood 19,000 times") and the compression ratio says how
many raw rows each theorem stands for.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from libs.tiers.truth_kernel import canon, sha256

CAUSES: tuple[str, ...] = ("NO_SIGNAL", "NO_CAUSAL_SUPPORT", "SELECTION_ARTEFACT", "UNSTABLE",
                           "COSTS_KILLED", "OVERFIT_HOLDOUT", "REGIME_SPECIFIC",
                           "CONDITIONAL_ONLY", "DUPLICATED_EXPOSURE", "CAPACITY_LIMITED",
                           "IMPLEMENTATION_IMPOSSIBLE", "LIVE_DECAY", "LOOKAHEAD", "DATA_DEFECT",
                           "UNKNOWN")

GATE_CAUSE: dict[str, str] = {
    "in_sample_screen": "NO_SIGNAL", "screen": "NO_SIGNAL", "ic": "NO_SIGNAL",
    "economic_prior": "NO_CAUSAL_SUPPORT", "placebo": "NO_CAUSAL_SUPPORT",
    "deflated_sharpe": "SELECTION_ARTEFACT", "reality_check_spa": "SELECTION_ARTEFACT",
    "pbo": "SELECTION_ARTEFACT", "dsr": "SELECTION_ARTEFACT", "spa": "SELECTION_ARTEFACT",
    "walk_forward": "UNSTABLE", "cpcv": "UNSTABLE", "stability": "UNSTABLE",
    "stress_costs": "COSTS_KILLED", "expected_value": "COSTS_KILLED", "cost": "COSTS_KILLED",
    "lockbox": "OVERFIT_HOLDOUT", "regime": "REGIME_SPECIFIC", "state": "CONDITIONAL_ONLY",
    "novelty": "DUPLICATED_EXPOSURE", "duplicate": "DUPLICATED_EXPOSURE",
    "orthogonality": "DUPLICATED_EXPOSURE", "capacity": "CAPACITY_LIMITED",
    "untradeable": "IMPLEMENTATION_IMPOSSIBLE", "execution": "IMPLEMENTATION_IMPOSSIBLE",
    "forward": "LIVE_DECAY", "decay": "LIVE_DECAY", "lookahead": "LOOKAHEAD",
    "leak": "LOOKAHEAD", "data": "DATA_DEFECT", "bars": "DATA_DEFECT", "stale": "DATA_DEFECT",
}


def cause_of(gate: str | None, reason: str = "") -> str:
    g = (gate or "").lower()
    if g in GATE_CAUSE:
        return GATE_CAUSE[g]
    text = f"{g} {reason.lower()}"
    for key, cause in GATE_CAUSE.items():
        if key in text:
            return cause
    return "UNKNOWN"


def _cls(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("mechanism") or row.get("family") or "?"),
            str(row.get("asset_class") or row.get("sym") or "?"),
            str(row.get("selector") or row.get("horizon") or "?"))


def compress(rows: Iterable[Mapping[str, Any]], *, min_trials: int = 20,
             dominance: float = 0.8) -> dict[str, Any]:
    """rows: {family|mechanism, asset_class|sym, selector|horizon, passed, terminal_gate,
    reason?, cell?}. Returns theorems, rules and per-class cause histograms."""
    classes: dict[tuple[str, str, str], dict[str, Any]] = {}
    n_rows = 0
    for r in rows:
        n_rows += 1
        key = _cls(r)
        c = classes.setdefault(key, {"n": 0, "survivors": 0, "causes": Counter(), "cells": [],
                                     "hash": ""})
        c["n"] += 1
        if r.get("passed"):
            c["survivors"] += 1
        else:
            c["causes"][cause_of(r.get("terminal_gate"), str(r.get("reason") or ""))] += 1
        if len(c["cells"]) < 5 and r.get("cell"):
            c["cells"].append(str(r.get("cell")))
        c["hash"] = sha256(c["hash"] + canon(dict(r)))
    theorems: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    for (mech, ac, sel), c in classes.items():
        fails = c["n"] - c["survivors"]
        if not fails:
            continue
        top_cause, top_n = c["causes"].most_common(1)[0]
        share = top_n / fails
        stmt = (f"{mech} on {ac} in {sel} fails by {top_cause} ({top_n}/{c['n']} trials, "
                f"{c['survivors']} survivors)")
        rec = {"mechanism": mech, "asset_class": ac, "selector": sel, "n": c["n"],
               "survivors": c["survivors"], "cause": top_cause, "cause_share": round(share, 3),
               "statement": stmt, "provenance": {"evidence_hash": c["hash"],
                                                 "sample_cells": c["cells"]}}
        if c["n"] >= min_trials and c["survivors"] == 0 and share >= dominance:
            theorems.append({**rec, "kind": "FAILURE_THEOREM"})
        elif c["n"] >= min_trials and share >= dominance:
            rules.append({**rec, "kind": "DOMINANT_CAUSE_RULE"})
    theorems.sort(key=lambda t: -int(t["n"]))
    rules.sort(key=lambda t: -int(t["n"]))
    cause_totals: Counter[str] = Counter()
    for c in classes.values():
        cause_totals.update(c["causes"])
    stated = len(theorems) + len(rules)
    covered = sum(int(t["n"]) for t in theorems + rules)
    return {"n_rows": n_rows, "n_classes": len(classes), "theorems": theorems,
            "rules": rules, "cause_totals": dict(cause_totals.most_common()),
            "compression": {"statements": stated, "rows_covered": covered,
                            "rows_per_statement": round(covered / stated, 2) if stated else None,
                            "coverage_share": round(covered / n_rows, 4) if n_rows else None}}


def neighbourhood(desc: Mapping[str, Any], memory: Mapping[str, Any], min_match: int = 2
                  ) -> dict[str, Any]:
    key = _cls(desc)
    hits = []
    explored = 0
    for t in list(memory.get("theorems") or []) + list(memory.get("rules") or []):
        m = sum(1 for a, b in zip(key, (t["mechanism"], t["asset_class"], t["selector"]),
                                  strict=True) if a == b and a != "?")
        if m >= min_match:
            hits.append(t)
            explored += int(t["n"])
    return {"explored": explored, "relevant": hits[:10]}
