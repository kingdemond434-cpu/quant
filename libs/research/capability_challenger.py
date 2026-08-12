"""ELITE RESEARCH-FACTORY CAPABILITY REPLICATION -- gate item 15, mandate V and V-C.

THE LAW. Treat High-Flyer and other elite quantitative organizations as sources of CAPABILITY
EVIDENCE, never as sources of strategy. For each capability walk:

    PUBLIC CAPABILITY -> EVIDENCE GRADE -> ECONOMIC MECHANISM -> CURRENT DESK ANALOGUE ->
    GAP -> SOLO-SCALE IMPLEMENTATION -> CONTROLLED TEST -> MARGINAL E[log W]

and adopt nothing without V-C's completion chain:

    PRODUCER -> STATE -> CONSUMER -> DECISION CONSEQUENCE -> CONTROLLED BENCHMARK -> RUNTIME
    EVIDENCE

THE FAILURE THIS EXISTS TO PREVENT is cargo-culting, and the mandate names it outright: "do not
hardcode TFT, PPO, LSTM, Transformer, RL, or other methods because somebody claims an elite fund
uses them." A capability adopted because a famous firm is said to have it is an expense justified
by gossip. So the benchmark ladder has a rung most benchmarks omit -- the SIMPLE BASELINE -- and a
candidate that beats the reigning champion but NOT the dumb baseline is rejected, because that
pattern means the champion is weak, not that the candidate is good.

THE SECOND FAILURE, subtler and more expensive: comparing a gain to a cost in different units. A
"30% faster" candidate against a "$40/mo" cost is not a comparison, it is two numbers next to each
other. adopt() refuses to net them and returns UNMEASURED rather than inventing a conversion.

EVIDENCE GRADE SETS THE PRIOR AND THE REQUIRED FALSIFICATION -- never the verdict. A rumour-graded
capability may still be replicated if the ECONOMIC MECHANISM stands on its own; what the grade
changes is how hard the desk must try to kill it first. Claims about named proprietary production
models, factor counts, latency, data rates and private risk architecture stay UNVERIFIED
regardless of how confidently they are repeated (mandate VI).

AUTHORITY: MEASUREMENT + RECOMMENDATION ONLY. This module never adopts anything by itself, never
touches a statistical gate, and never sizes a position.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "EVIDENCE_GRADES",
    "LEDGER",
    "VERDICTS",
    "Capability",
    "adopt",
    "chain_gaps",
    "record",
    "register",
    "rows",
]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "docs/research/capability_challengers.jsonl"

#: Descending strength. The grade sets the PRIOR and the falsification burden, never the verdict.
EVIDENCE_GRADES: tuple[str, ...] = (
    "FIRST_PARTY_TECHNICAL_DISCLOSURE",   # the org's own paper/code/filing, checkable
    "INDEPENDENT_REPRODUCTION",           # someone outside the org rebuilt and reported it
    "PEER_REPORTED",                      # a credible third party with access
    "CREDIBLE_PRESS_REPORT",              # journalism, no primary artifact
    "VENDOR_MARKETING_CLAIM",             # first-party marketing: a claim, not evidence
    "ANONYMOUS_RUMOR",                    # forum/anon: prior only, never belief
)

#: Mandate V-C's completion chain. A capability missing any link is INCOMPLETE by definition.
_CHAIN = ("producer", "state", "consumer", "decision_consequence",
          "controlled_benchmark", "runtime_evidence")

VERDICTS: tuple[str, ...] = (
    "ADOPT",                                  # beat baseline AND champion, net of total cost
    "PROVISIONAL_PENDING_RUNTIME_EVIDENCE",   # measured winner, not yet observed in production
    "REJECTED_NO_GAIN_OVER_SIMPLE_BASELINE",  # the anti-cargo-cult rung
    "REJECTED_CHAMPION_HOLDS",                # the desk already does this at least as well
    "REJECTED_COST_EXCEEDS_GAIN",             # real gain, not worth what it costs to hold
    "UNMEASURED",                             # missing input or incommensurable units -- not zero
)


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Capability:
    """One elite-factory capability, walked through the mandate's eight stations."""

    name: str
    public_capability: str
    evidence_grade: str
    economic_mechanism: str
    desk_analogue: str
    gap: str
    solo_scale_implementation: str
    controlled_test: str
    source: str = ""
    unverified_claims: tuple[str, ...] = ()
    chain: dict[str, str] = field(default_factory=dict)

    def missing_stations(self) -> list[str]:
        out = []
        for f in ("public_capability", "evidence_grade", "economic_mechanism", "desk_analogue",
                  "gap", "solo_scale_implementation", "controlled_test"):
            if not str(getattr(self, f, "")).strip():
                out.append(f)
        return out


def rows(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or _ROOT
    out: list[dict[str, Any]] = []
    try:
        text = (base / LEDGER).read_text("utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def register(cap: Capability) -> dict[str, Any]:
    """Validate one capability against the mandate's stations. Refuses silently-partial records.

    A capability registered with blank stations is worse than an unregistered one: it looks
    analysed. So an incomplete walk is INCOMPLETE and names which stations are empty, and an
    unrecognised evidence grade is refused rather than coerced to the weakest one -- coercion
    would let a typo quietly downgrade a first-party disclosure to a rumour.
    """
    missing = cap.missing_stations()
    if missing:
        return {"status": "INCOMPLETE", "capability": cap.name, "missing_stations": missing,
                "why": "mandate V requires all eight stations; a blank station is an unasked "
                       "question, not a negative answer"}
    if cap.evidence_grade not in EVIDENCE_GRADES:
        return {"status": "REFUSED", "capability": cap.name,
                "why": f"unknown evidence grade {cap.evidence_grade!r}; declare it in "
                       f"EVIDENCE_GRADES. Valid: {list(EVIDENCE_GRADES)}"}
    grade_rank = EVIDENCE_GRADES.index(cap.evidence_grade)
    return {
        "status": "REGISTERED",
        "capability": cap.name,
        "evidence_grade": cap.evidence_grade,
        "prior_strength": round(1.0 - grade_rank / (len(EVIDENCE_GRADES) - 1), 3),
        "falsification_burden": ("LOW" if grade_rank <= 1 else
                                 "MEDIUM" if grade_rank <= 3 else "HIGH"),
        "unverified_claims": list(cap.unverified_claims),
        "law": "evidence grade sets the PRIOR and the required falsification, never the verdict: "
               "a rumour-graded capability may still be replicated if its ECONOMIC MECHANISM "
               "stands on its own, and a disclosed one is still killed by a failed benchmark",
    }


def chain_gaps(cap: Capability) -> list[str]:
    """V-C: no capability is complete without every link. Returns the missing ones."""
    return [link for link in _CHAIN if not str(cap.chain.get(link, "")).strip()]


def adopt(*, name: str, metric: str, higher_is_better: bool,
          simple_baseline: float | None, current_champion: float | None,
          candidate: float | None,
          gain_unit: str = "", cost_unit: str = "",
          total_cost: float = 0.0,
          runtime_evidence: str = "",
          cost_breakdown: dict[str, float] | None = None) -> dict[str, Any]:
    """GATE ITEM 15's benchmark ladder: SIMPLE BASELINE -> CHAMPION -> CANDIDATE -> COST.

    The rung order is the whole argument. A candidate is tested against the DUMB baseline FIRST,
    because "beats the current champion" is satisfied equally by a good candidate and by a bad
    champion, and only the baseline separates those two cases. This is the rung that stops the
    desk hardcoding a method because an elite fund is said to use it.

    UNITS ARE CHECKED, NOT ASSUMED. Netting a gain against a cost requires both in one unit; if
    they differ the result is UNMEASURED, never a guess. `gain_unit`/`cost_unit` left blank means
    the caller has not stated them, which is itself unmeasured -- not permission to subtract.
    """
    if simple_baseline is None or current_champion is None or candidate is None:
        missing = [n for n, v in (("simple_baseline", simple_baseline),
                                  ("current_champion", current_champion),
                                  ("candidate", candidate)) if v is None]
        return {"verdict": "UNMEASURED", "capability": name, "metric": metric,
                "missing": missing,
                "why": f"cannot rank without {', '.join(missing)}. An unmeasured rung is UNKNOWN, "
                       "never a pass and never a zero (L1.41)"}

    def better(a: float, b: float) -> bool:
        return a > b if higher_is_better else a < b

    gain_vs_baseline = (candidate - simple_baseline) if higher_is_better else (
        simple_baseline - candidate)
    gain_vs_champion = (candidate - current_champion) if higher_is_better else (
        current_champion - candidate)

    base = {
        "capability": name, "metric": metric, "generated_utc": _now(),
        "simple_baseline": simple_baseline, "current_champion": current_champion,
        "candidate": candidate,
        "gain_vs_baseline": round(gain_vs_baseline, 6),
        "gain_vs_champion": round(gain_vs_champion, 6),
        "total_cost": total_cost, "cost_breakdown": dict(cost_breakdown or {}),
        "authority": "MEASUREMENT + RECOMMENDATION ONLY -- adopts nothing, sizes nothing, and "
                     "touches no statistical gate.",
    }

    if not better(candidate, simple_baseline):
        return {**base, "verdict": "REJECTED_NO_GAIN_OVER_SIMPLE_BASELINE",
                "why": "the candidate does not beat a DUMB baseline. Mandate V: do not adopt a "
                       "method because an elite fund is said to use it -- complexity that does "
                       "not beat the simplest thing is cost with a citation attached"}
    if not better(candidate, current_champion):
        return {**base, "verdict": "REJECTED_CHAMPION_HOLDS",
                "why": "the desk's existing analogue already does this at least as well; the "
                       "switching and maintenance cost buys nothing"}

    if total_cost:
        if not gain_unit or not cost_unit or gain_unit != cost_unit:
            return {**base, "verdict": "UNMEASURED",
                    "gain_unit": gain_unit, "cost_unit": cost_unit,
                    "why": f"gain is in {gain_unit or 'an unstated unit'} and cost in "
                           f"{cost_unit or 'an unstated unit'}. Netting incommensurable units is "
                           "arithmetic theatre; convert both to marginal E[log W] or to dollars "
                           "before comparing, or leave it UNMEASURED"}
        if gain_vs_champion <= total_cost:
            return {**base, "verdict": "REJECTED_COST_EXCEEDS_GAIN",
                    "net": round(gain_vs_champion - total_cost, 6),
                    "why": "a real but unprofitable gain. V-C: retain only where the "
                           "uncertainty-adjusted benefit exceeds compute, engineering, "
                           "complexity, maintenance, switching AND opportunity cost"}
        base["net"] = round(gain_vs_champion - total_cost, 6)

    if not str(runtime_evidence).strip():
        return {**base, "verdict": "PROVISIONAL_PENDING_RUNTIME_EVIDENCE",
                "why": "measured winner on a controlled benchmark, but V-C requires RUNTIME "
                       "EVIDENCE before a capability counts as complete. A bench win is a "
                       "prediction about production, not an observation of it"}

    return {**base, "verdict": "ADOPT", "runtime_evidence": str(runtime_evidence),
            "why": "beat the simple baseline AND the incumbent champion, survived total cost, "
                   "and has been observed working in production"}


def record(cap: Capability, verdict: dict[str, Any], *,
           root: Path | None = None) -> dict[str, Any]:
    """Append one challenger decision to the durable ledger, with its V-C chain gaps stated."""
    base = root or _ROOT
    row = {
        "ts": _now(),
        "capability": asdict(cap),
        "registration": register(cap),
        "benchmark": verdict,
        "chain_gaps": chain_gaps(cap),
        "complete": not chain_gaps(cap) and verdict.get("verdict") == "ADOPT",
    }
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row
