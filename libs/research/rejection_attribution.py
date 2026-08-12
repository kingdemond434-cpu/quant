"""WHERE DID THE COHORT DIE? — per-gate rejection attribution over the REAL candidate set.

THE QUESTION NOTHING ON THIS DESK COULD ANSWER. The lab store holds ~1,673 candidates and every
one carries `survived = 0`. The forward-slot queue therefore reports 0 candidates against 10 free
slots, and alpha_output scores 0.8/10. Two very different worlds produce that same number:

    (a) SUPPLY IS GENUINELY WEAK -- the candidates are noise, the gauntlet is working, and the
        fix is upstream in discovery and mechanism supply;
    (b) ONE GATE IS BROKEN-CLOSED -- it rejects everything it sees, the gates behind it never
        run, and the desk's eight-stage validation is one stage wearing eight hats.

The desk already owns two instruments and NEITHER separates these. `audit_gate_power` measures
Type I/II per gate on SIMULATED cohorts, so it describes the gates' statistical behaviour on
synthetic data. `certify_gauntlet` runs known-good and known-null CONTROLS, so it answers "can a
real edge get through at all". Neither reads the actual 1,673 and asks which gate killed each one.

THE SIGNATURE THAT SEPARATES (a) FROM (b), and it is the reason first-failing-gate is not enough
on its own: in a healthy funnel, deaths SPREAD -- different candidates fail for different reasons,
because they are bad in different ways. A gate that kills a very high share of everything it sees
is doing one of two things, and the histogram alone cannot tell them apart. So this module also
computes, for each gate, how many candidates it would have rejected HAD THEY REACHED IT
(`would_reject_share`), which the first-failing histogram structurally cannot see: a gate late in
the order may be perfectly discriminating and simply never get a candidate to judge.

A GATE THAT HAS NEVER REJECTED ANYTHING is equally a finding, and the opposite one. It is either
redundant (the gates before it already caught everything it would catch) or unreachable (nothing
survives to it). Both are defects; neither is visible without counting.

WHAT THIS MODULE REFUSES TO DO. It does not loosen anything, propose loosening anything, or rank
gates by how many candidates they "cost". A gate that correctly rejects everything is doing its
job perfectly, and the desk's standing law is that no gate is ever loosened to manufacture
survivors. This is a MEASUREMENT that tells the principal where to look; the verdict on any gate
is a separate, evidenced decision.

UNMEASURED IS NOT ZERO. An absent or empty store returns UNMEASURED, never "0 rejections" -- the
store is 0 bytes on a non-research box, and reporting that as a clean funnel is the
read-without-writer failure (L1.40) this desk has already been bitten by twice.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CONCENTRATION_ALARM",
    "GateOutcome",
    "attribute",
    "concentration",
    "recoverable",
    "report",
]

_ROOT = Path(__file__).resolve().parents[2]
OUT = "docs/research/rejection_attribution.json"

#: A single gate killing at least this share of the whole cohort is FLAGGED FOR INVESTIGATION --
#: not condemned. It may be the desk's sharpest instrument or it may be broken-closed, and the
#: separator is whether the positive CONTROLS clear it (certify_gauntlet), which this report
#: names as the required follow-up rather than guessing.
CONCENTRATION_ALARM = 0.80


@dataclass(frozen=True)
class GateOutcome:
    """One candidate's journey: which gate killed it, and which others would have."""

    candidate_id: str
    first_failing_gate: str | None            # None => survived every gate
    failed_gates: tuple[str, ...] = ()        # every gate it fails, whether or not it reached one
    reached_gates: tuple[str, ...] = ()       # gates actually evaluated before it died
    family: str = ""


def attribute(outcomes: list[GateOutcome], *, gate_order: list[str]) -> dict[str, Any]:
    """Per-gate death counts over a REAL cohort, plus the counterfactual each histogram hides.

    Three numbers per gate, and the third is the one that changes conclusions:

      killed          candidates for which this gate was the FIRST failure -- what a naive
                      histogram shows.
      would_reject    candidates this gate would reject if every candidate reached it. A late
                      gate can be perfectly discriminating and show killed=0 purely because
                      nothing survives to it, which reads as "useless gate" and is not.
      never_reached   candidates that died before this gate ran. Large values mean this gate's
                      statistics are being drawn from a biased, tiny sample.
    """
    if not outcomes:
        return {"status": "UNMEASURED", "n": 0,
                "why": "no candidate outcomes supplied -- an absent or empty lab store is UNKNOWN, "
                       "never a clean funnel. Reporting 0 rejections from a 0-byte store is the "
                       "read-without-writer failure (L1.40)"}

    n = len(outcomes)
    survivors = [o for o in outcomes if o.first_failing_gate is None]
    rows: list[dict[str, Any]] = []
    for g in gate_order:
        killed = [o for o in outcomes if o.first_failing_gate == g]
        would = [o for o in outcomes if g in o.failed_gates]
        reached = [o for o in outcomes if g in o.reached_gates]
        rows.append({
            "gate": g,
            "killed": len(killed),
            "killed_share_of_cohort": round(len(killed) / n, 4),
            "would_reject": len(would),
            "would_reject_share": round(len(would) / n, 4),
            "reached": len(reached),
            "never_reached": n - len(reached),
            "killed_share_of_reached": (round(len(killed) / len(reached), 4) if reached else None),
        })
    return {
        "status": "MEASURED",
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_candidates": n,
        "n_survivors": len(survivors),
        "survival_rate": round(len(survivors) / n, 5),
        "gates": rows,
        "law": "MEASUREMENT ONLY. A gate that correctly rejects everything is doing its job "
               "perfectly; nothing here proposes loosening any gate, and no gate is ever loosened "
               "to manufacture survivors",
    }


def concentration(att: dict[str, Any]) -> dict[str, Any]:
    """Is the funnel actually multi-stage, or is it one gate wearing several hats?

    Reports the single most lethal gate, whether it trips the alarm, and -- separately -- the
    gates that have never killed anything. Both ends of the distribution are findings.
    """
    if att.get("status") != "MEASURED":
        return {"status": att.get("status", "UNMEASURED"),
                "why": "cannot judge concentration without a measured cohort"}
    gates = att["gates"]
    if not gates:
        return {"status": "UNMEASURED", "why": "no gates declared"}

    top = max(gates, key=lambda r: r["killed"])
    idle = [r["gate"] for r in gates if r["killed"] == 0]
    unreached = [r["gate"] for r in gates if r["reached"] == 0]
    alarm = top["killed_share_of_cohort"] >= CONCENTRATION_ALARM

    out = {
        "status": "MEASURED",
        "most_lethal_gate": top["gate"],
        "its_share_of_all_deaths": top["killed_share_of_cohort"],
        "concentration_alarm": alarm,
        "gates_that_never_killed": idle,
        "gates_never_reached": unreached,
        "effective_stages": sum(1 for r in gates if r["killed"] > 0),
        "declared_stages": len(gates),
    }
    if alarm:
        out["verdict"] = (
            f"CONCENTRATED: {top['gate']} is the first failure for "
            f"{top['killed_share_of_cohort']:.1%} of the cohort. This is NOT yet a defect -- it "
            "may be the desk's sharpest instrument. It becomes one only if the POSITIVE CONTROLS "
            "also fail it, which separates 'rejects everything because everything is noise' from "
            "'broken-closed'. REQUIRED NEXT STEP: scripts/certify_gauntlet.py, and read this "
            "gate's verdict on the known-GOOD control specifically")
    else:
        out["verdict"] = (
            f"SPREAD: deaths distribute across {out['effective_stages']} of "
            f"{out['declared_stages']} gates, which is the healthy shape -- candidates that are "
            "bad in different ways fail for different reasons")
    if unreached:
        out["unreached_note"] = (
            f"{len(unreached)} gate(s) evaluated NOTHING: {unreached}. Their statistics are not "
            "weak evidence, they are absent evidence -- and a gate nothing reaches cannot be "
            "said to be validating anything")
    if idle and not unreached:
        out["idle_note"] = (
            f"{len(idle)} gate(s) reached candidates and rejected none: {idle}. Either the gates "
            "before them already catch everything they would (redundant), or they are inert. "
            "Both are worth knowing; neither is visible without this count")
    return out


def recoverable(outcomes: list[GateOutcome], *,
                metrics: dict[str, dict[str, float]] | None = None,
                thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    """WHICH OF THE DEAD ARE RECOVERABLE -- delegated to libs.validation.near_miss, not rebuilt.

    THE DEFECT THIS CLOSES, and it is not a missing capability but an UNUSED one. The desk built
    a full near-miss triage in libs/validation/near_miss.py -- shortfall per gate, structural vs
    statistical failure, improvement hints, an append-only ledger, and a verdict whose __bool__ is
    hard-wired False so it can never be misread as a pass. It then wired it to NOTHING. Its only
    importer in the entire repo is its own test file, so every one of the ~1,673 candidates died
    as a bare PASS/FAIL and no near-miss was ever recorded.

    That is the L1.50 shape exactly: capability already paid for, returning zero. And it is the
    expensive one to leave unwired, because this desk's own accounting says 53% of refutations
    were MEASUREMENT failures rather than absent alpha -- so the discarded near-misses are
    disproportionately the FIXABLE half of the pile.

    IT CHANGES NO VERDICT. Every candidate reaching here has already failed. This adds a ranking
    over the dead -- how close, and which route back -- so a near-miss becomes a work item instead
    of a corpse. A re-test still costs a full search-accounting entry at the unchanged bar.
    """
    try:
        from libs.validation.near_miss import triage
    except ImportError as exc:
        return {"status": "UNAVAILABLE", "why": f"near-miss triage unimportable: {exc}"}
    if not outcomes:
        return {"status": "UNMEASURED",
                "why": "no outcomes -- nothing was triaged, which is not 'nothing is recoverable'"}
    if not metrics or not thresholds:
        return {"status": "UNMEASURED",
                "n_dead": sum(1 for o in outcomes if o.first_failing_gate),
                "why": "per-candidate METRICS and gate THRESHOLDS are required to measure how far "
                       "short each candidate fell. Without them the desk knows only THAT they "
                       "died, never HOW CLOSE -- and 'we did not measure the shortfall' must not "
                       "read as 'none was close' (L1.41)"}
    buckets: dict[str, list[str]] = {}
    verdicts = []
    for o in outcomes:
        if not o.first_failing_gate:
            continue
        m = metrics.get(o.candidate_id) or {}
        gates = {g: (g not in o.failed_gates) for g in o.reached_gates}
        v = triage(gates, m, thresholds, name=o.candidate_id)
        verdicts.append(v)
        buckets.setdefault(str(v.classification), []).append(o.candidate_id)
    return {
        "status": "MEASURED",
        "n_triaged": len(verdicts),
        "by_classification": {k: len(v) for k, v in buckets.items()},
        "near_miss_ids": buckets.get("NEAR_MISS", [])[:50],
        "verdicts": verdicts,
        "law": "changes no verdict -- every candidate here has already failed. A NEAR_MISS is a "
               "WORK ITEM, not a pass, and a re-test costs a full search-accounting entry at the "
               "unchanged bar (III-10: do not torture noise into alpha)",
    }


def report(outcomes: list[GateOutcome], *, gate_order: list[str],
           metrics: dict[str, dict[str, float]] | None = None,
           thresholds: dict[str, Any] | None = None,
           root: Path | None = None, write: bool = True) -> dict[str, Any]:
    """The full artifact: attribution + concentration + the action it implies."""
    att = attribute(outcomes, gate_order=gate_order)
    con = concentration(att)
    rec = recoverable(outcomes, metrics=metrics, thresholds=thresholds)
    doc = {
        "what": "per-gate rejection attribution over the REAL candidate cohort -- which gate "
                "killed each candidate, and which gates never got to judge one",
        "why": "the forward-slot queue reports 0 candidates against 10 free slots and "
               "alpha_output scores 0.8/10. That single number is produced equally by a weak "
               "supply and by one gate broken-closed, and the desk had no instrument separating "
               "them: audit_gate_power simulates cohorts, certify_gauntlet runs controls, and "
               "neither reads the actual cohort",
        "attribution": att,
        "concentration": con,
        "recoverable": rec,
        "authority": "MEASUREMENT ONLY -- proposes no threshold change and ranks no gate by the "
                     "candidates it costs.",
    }
    if write and att.get("status") == "MEASURED":
        p = (root or _ROOT) / OUT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1, ensure_ascii=False), "utf-8")
        doc["written_to"] = str(p)
    return doc


@dataclass
class StoreRead:
    """What a lab-store read produced, including the honest failure states."""

    status: str
    outcomes: list[GateOutcome] = field(default_factory=list)
    why: str = ""


def read_store(db_path: Path) -> StoreRead:
    """Load real candidate outcomes. Every failure mode is NAMED, never collapsed to empty.

    The distinction that matters on this desk: a 0-byte store on a non-research box and a store
    holding 1,673 rejected candidates both yield "no survivors", and only one of them is a
    finding about the funnel.
    """
    if not db_path.exists():
        return StoreRead("ABSENT", [], f"{db_path} does not exist -- this box is probably not the "
                                       "research box. UNMEASURED, not an empty funnel")
    if db_path.stat().st_size == 0:
        return StoreRead("EMPTY_FILE", [], f"{db_path} is 0 bytes -- the file exists and holds "
                                           "nothing. This is the read-without-writer signature, "
                                           "not a cohort with no survivors")
    try:
        from libs.autodiscovery.memory import CandidateStore
        from libs.store.connection import Database
        store = CandidateStore(Database(db_path, read_only=True))
        rows = list(store.all())
    except Exception as exc:
        return StoreRead("UNREADABLE", [], f"{type(exc).__name__}: {exc}")
    if not rows:
        return StoreRead("NO_ROWS", [], "store opened and holds zero candidates")

    outcomes = []
    for c in rows:
        gates = getattr(c, "gate_results", None) or {}
        failed = tuple(g for g, ok in dict(gates).items() if not ok)
        reached = tuple(dict(gates))
        first = next((g for g in reached if g in failed), None)
        outcomes.append(GateOutcome(
            candidate_id=str(getattr(c, "id", "?")), first_failing_gate=first,
            failed_gates=failed, reached_gates=reached,
            family=str(getattr(c, "family", ""))))
    return StoreRead("OK", outcomes, f"{len(outcomes)} candidate outcome(s) read")
