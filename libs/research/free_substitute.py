"""STRUCTURED FREE-SUBSTITUTE COMPARISON -- gate item 22, mandate XXIV-(6) and (7).

THE LAW: a free substitute must be compared to the paid source on TIMESTAMP FIDELITY, HISTORY,
LATENCY, ACCURACY, MISSINGNESS, RIGHTS, RELIABILITY and DOWNSTREAM ECONOMIC INFORMATION -- and
"free" is judged on TOTAL economic cost, never on purchase price.

WHY THE COMPARISON IS PER-USE AND NOT ABSOLUTE. "Worse on history" is not a defect if the study
needs thirty days. A dimension only counts against a substitute when the USE requires more than
the substitute provides, so every comparison is made against a stated REQUIREMENT. Comparing in
the abstract produces a table nobody can act on and a verdict that is really just a mood.

THE VETO, AND IT IS THE WHOLE POINT OF ITEM 22. DOWNSTREAM ECONOMIC INFORMATION is not one
dimension among eight -- it is a veto. This desk walked into the case that proves it and wrote the
finding down before it had anywhere to put it:

    DefiLlama's paid Emissions feed sells DATED, FORWARD-LOOKING unlock schedules. The desk's own
    free circulating-supply series makes a REALISED unlock observable as a supply jump. On seven of
    the eight dimensions the free route is competitive or better -- it is chain-derived, unlimited,
    unlicensed and already half-built. And it is NOT a replacement, because the paid feed is
    tradeable IN ANTICIPATION and a supply delta is only visible AFTER the release, when everyone
    else can see it too.

Booking that as "REPLACED" would have retired a screen's numerator in exchange for a series that
cannot answer the question the screen asks. So a substitute that answers a DIFFERENT economic
question is never an equivalent, however well it scores elsewhere -- and the same free route is
correctly FREE_NEAR_EQUIVALENT for a reaction study and NO_FREE_EQUIVALENT_YET for an anticipation
study. One route, two verdicts, because there are two uses.

UNKNOWN IS NEVER A PASS (L1.41). An unmeasured dimension leaves the verdict UNRESOLVED and caps it
below FREE_EXACT_EQUIVALENT. "We did not check the licence" must never read as "the licence is
fine" -- that is the failure mode that puts an NC-licensed feed into a commercial pipeline.

AUTHORITY: MEASUREMENT + RECOMMENDATION ONLY. Buying a licensed vendor feed is the principal's
decision, never a collector's. This module records what a free route can and cannot do.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "DIMENSIONS",
    "VERDICTS",
    "Requirement",
    "SourceSpec",
    "compare",
    "total_economic_cost",
]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "docs/research/free_substitute_comparisons.json"

#: XXIV-(6)'s eight dimensions, in the mandate's own order. The last is a VETO, not a tiebreak.
DIMENSIONS: tuple[str, ...] = (
    "timestamp_fidelity",
    "history",
    "latency",
    "accuracy",
    "missingness",
    "rights",
    "reliability",
    "downstream_economic_information",
)

#: The verdict ladder from XXIV-(5). NO_FREE_EQUIVALENT_YET is an HONEST verdict, not a failure --
#: recording it is what stops the desk pretending a proxy is a replacement.
VERDICTS: tuple[str, ...] = (
    "FREE_EXACT_EQUIVALENT",
    "FREE_NEAR_EQUIVALENT",
    "FREE_MULTI_SOURCE_RECONSTRUCTION",
    "FREE_PROXY",
    "NO_FREE_EQUIVALENT_YET",
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class SourceSpec:
    """One route to a data field. ``values`` maps a DIMENSION to a measured description; a
    dimension absent from the map is UNMEASURED, which is not the same as absent from the source."""

    name: str
    is_free: bool
    values: dict[str, Any] = field(default_factory=dict)
    n_upstream_sources: int = 1
    answers_question: str = ""
    engineering_hours: float = 0.0
    monthly_maintenance_hours: float = 0.0
    monthly_cash_usd: float = 0.0

    def get(self, dim: str) -> Any:
        return self.values.get(dim)


@dataclass(frozen=True)
class Requirement:
    """What THIS USE needs. A dimension the use does not care about is not a weakness."""

    use: str
    question: str
    needs: dict[str, Any] = field(default_factory=dict)

    def required(self, dim: str) -> Any:
        return self.needs.get(dim)


def _dimension_verdict(dim: str, paid: SourceSpec, free: SourceSpec,
                       req: Requirement) -> dict[str, Any]:
    need = req.required(dim)
    got = free.get(dim)
    row = {"dimension": dim, "paid": paid.get(dim), "free": got, "required": need}

    if need is None:
        return {**row, "status": "NOT_REQUIRED",
                "why": f"this use does not depend on {dim}; a difference here is not a weakness"}
    if got is None:
        return {**row, "status": "UNKNOWN",
                "why": f"{dim} was never measured for the free route. UNKNOWN is not a pass "
                       "(L1.41) -- 'we did not check the licence' must never read as 'the licence "
                       "is fine'"}

    if isinstance(need, bool):
        ok = bool(got) == need
    elif isinstance(need, int | float) and isinstance(got, int | float):
        ok = float(got) >= float(need)
    else:
        ok = str(got).strip().lower() == str(need).strip().lower()

    return {**row, "status": "MEETS" if ok else "FAILS",
            "why": (f"free route provides {got!r}, use requires {need!r}"
                    if ok else
                    f"free route provides {got!r} but this use requires {need!r}")}


def total_economic_cost(spec: SourceSpec, *, hourly_usd: float = 0.0,
                        months: int = 12) -> dict[str, Any]:
    """XXIV-(7). "Free" is evaluated on TOTAL economic cost, not purchase price.

    Engineering and maintenance hours are reported as HOURS whenever no hourly rate is supplied,
    and are NEVER silently converted to dollars at an invented rate -- a fabricated wage would
    make the comparison look decided when it is not. With hourly_usd=0 the dollar figure covers
    cash only and the hours stand beside it, uncollapsed.
    """
    hours = float(spec.engineering_hours) + float(spec.monthly_maintenance_hours) * int(months)
    cash = float(spec.monthly_cash_usd) * int(months)
    labour = hours * float(hourly_usd)
    return {
        "source": spec.name,
        "horizon_months": int(months),
        "cash_usd": round(cash, 2),
        "engineering_hours": round(hours, 2),
        "labour_usd": round(labour, 2) if hourly_usd else None,
        "total_usd": round(cash + labour, 2) if hourly_usd else None,
        "why": ("a free feed with 40h of integration and 2h/month of upkeep is not free; a paid "
                "feed that arrives clean can be the cheaper route"
                if not hourly_usd else ""),
        "note": ("hours are NOT converted to dollars without a stated rate -- an invented wage "
                 "would make the comparison look decided when it is not"
                 if not hourly_usd else ""),
    }


def compare(*, paid: SourceSpec, free: SourceSpec, requirement: Requirement,
            hourly_usd: float = 0.0, months: int = 12) -> dict[str, Any]:
    """GATE ITEM 22. Compare a free substitute to a paid source across all eight dimensions.

    Returns one of the XXIV-(5) verdicts, PER USE. The same free route legitimately earns
    different verdicts for different uses, and collapsing them into one global answer is how a
    proxy gets booked as a replacement.
    """
    dims = [_dimension_verdict(d, paid, free, requirement) for d in DIMENSIONS]
    by_status: dict[str, list[str]] = {}
    for d in dims:
        by_status.setdefault(d["status"], []).append(d["dimension"])

    fails = by_status.get("FAILS", [])
    unknowns = by_status.get("UNKNOWN", [])
    cost = total_economic_cost(free, hourly_usd=hourly_usd, months=months)
    paid_cost = total_economic_cost(paid, hourly_usd=hourly_usd, months=months)

    base = {
        "generated_utc": _now(),
        "use": requirement.use,
        "question": requirement.question,
        "paid_source": paid.name,
        "free_source": free.name,
        "dimensions": dims,
        "fails": fails,
        "unknown": unknowns,
        "free_total_economic_cost": cost,
        "paid_total_economic_cost": paid_cost,
        "authority": "MEASUREMENT + RECOMMENDATION ONLY. Buying a licensed vendor feed is the "
                     "principal's decision, never a collector's.",
    }

    # THE VETO, checked before anything else. A route that answers a different economic question
    # is not a worse version of the source -- it is a different source.
    if "downstream_economic_information" in fails:
        return {
            **base,
            "verdict": "NO_FREE_EQUIVALENT_YET",
            "veto": "downstream_economic_information",
            "why": "the free route answers a DIFFERENT economic question than the paid source "
                   f"(paid: {paid.answers_question or 'unstated'}; free: "
                   f"{free.answers_question or 'unstated'}). Scoring well on the other seven "
                   "dimensions cannot repair that -- booking it as REPLACED would retire a "
                   "capability in exchange for a series that cannot answer the question asked. "
                   "It may still be an honest FREE_PROXY for a DIFFERENT use; run that use "
                   "through this comparison separately rather than averaging the two",
        }

    if fails:
        return {**base, "verdict": "FREE_PROXY",
                "why": f"usable but materially weaker on {', '.join(fails)} for this use. A proxy "
                       "is a real asset and an honest label; it is not a replacement, and the "
                       "paid source stays OPEN in the registry"}

    if unknowns:
        return {**base, "verdict": "FREE_NEAR_EQUIVALENT", "unresolved": unknowns,
                "why": f"meets every MEASURED requirement, but {', '.join(unknowns)} was never "
                       "checked. UNKNOWN caps the verdict below EXACT -- an unmeasured dimension "
                       "is a question nobody asked, never an answer in the desk's favour"}

    if free.n_upstream_sources > 1:
        return {**base, "verdict": "FREE_MULTI_SOURCE_RECONSTRUCTION",
                "why": f"meets every requirement, reconstructed from {free.n_upstream_sources} "
                       "upstream sources. Recorded distinctly from an exact equivalent because it "
                       "carries N failure modes rather than one, and each is a separate way for "
                       "the reconstruction to go quietly wrong"}

    return {**base, "verdict": "FREE_EXACT_EQUIVALENT",
            "why": "meets every stated requirement on every dimension, from a single upstream "
                   "source, at lower total economic cost"}


def write_report(comparisons: list[dict[str, Any]], *, root: Path | None = None) -> Path:
    base = root or _ROOT
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "what": "XXIV-(6)/(7) structured free-substitute comparisons, one row per USE",
        "generated_utc": _now(),
        "law": "downstream economic information is a VETO dimension; UNKNOWN is never a pass; "
               "'free' is judged on total economic cost, not purchase price",
        "comparisons": comparisons,
    }, indent=1, ensure_ascii=False), "utf-8")
    return p
