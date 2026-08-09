"""Automated report builders over the candidate ledger (pure, deterministic).

Feed the daily / weekly / monthly cadence. Honest by construction: every count comes from the
durable ``research_candidates`` table, survivors included or zero.
"""

from __future__ import annotations

from typing import Any

from libs.autodiscovery.memory import CandidateStore


def _rejection_histogram(store: CandidateStore) -> dict[str, int]:
    hist: dict[str, int] = {}
    # Full history on purpose: this tallies WHICH GATES KILL, a historical fact that a later
    # capacity retirement (status -> archived) must not shrink. Retired rows keep their original
    # rejection_reason untouched, so their gate history still counts here.
    for rec in store.all(include_retired=True):
        if rec.survived or not rec.rejection_reason:
            continue
        body = rec.rejection_reason.removeprefix("failed: ")
        for gate in (g.strip() for g in body.split(",") if g.strip()):
            hist[gate] = hist.get(gate, 0) + 1
    return hist


def research_report(store: CandidateStore) -> dict[str, Any]:
    return {
        "total_candidates": store.total(),
        "by_family": store.family_counts(),
        "by_status": store.status_counts(),
        "survivors": len(store.survivors()),
        "screen_survivors": len(store.screen_survivors()),
    }


def failure_analysis_report(store: CandidateStore) -> dict[str, Any]:
    return {"rejection_by_gate": _rejection_histogram(store)}


def survivor_report(store: CandidateStore) -> dict[str, Any]:
    return {
        "survivors": [
            {"id": r.id, "family": r.family, "subtype": r.subtype, "symbol": r.symbol,
             "annual_sharpe": r.metrics.annual_sharpe, "dsr": r.metrics.dsr}
            for r in store.survivors()
        ]
    }


def family_performance_report(store: CandidateStore) -> dict[str, Any]:
    counts = store.family_counts()
    survivors_by_family: dict[str, int] = {}
    for r in store.survivors():
        survivors_by_family[r.family] = survivors_by_family.get(r.family, 0) + 1
    return {
        "families": {
            fam: {"tested": n, "survivors": survivors_by_family.get(fam, 0),
                  "survivor_rate": survivors_by_family.get(fam, 0) / n if n else 0.0}
            for fam, n in counts.items()
        }
    }


def discovery_efficiency_report(store: CandidateStore) -> dict[str, Any]:
    total = store.total()
    survivors = len(store.survivors())
    return {
        "total_tested": total,
        "survivors": survivors,
        "survivor_rate": survivors / total if total else 0.0,
    }


def pipeline_health_report(store: CandidateStore) -> dict[str, Any]:
    return {"funnel": store.status_counts(), "total": store.total()}
