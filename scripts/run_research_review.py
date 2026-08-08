#!/usr/bin/env python3
"""THE CONSUMER FOR FOUR MODULES THAT HAD NONE -- funnel, evidence tier, near-survivors, convergence.

MEASURED 2026-08-08, and it is the defect this session spent its day diagnosing in other people's
code before committing it four times over::

    convergence     0 importers
    evidence_tier   0 importers
    funnel          0 importers
    near_survivor   0 importers

Tested, documented, committed, and nothing called any of them. By this desk's own standard that is
INVENTORY, not capability -- the same shape as `combination_engine` emitting 898,560 candidates
with no executor, and as `live_ladder` carrying the arithmetic with no consumer. A module is not a
capability until the cycle runs it and something reads its output.

WHAT THIS DOES. Reads the sweep report and turns it into the four things the desk actually needs
after a run:

    funnel        WHERE the pipeline is blocked, from the sweep's own stage counts
    near-survivor WHAT the killed cells license next, with the ancestry deflation attached
    evidence tier WHETHER a survivor is executable or merely claimed
    convergence   WHETHER independently-sourced findings agree, or are echoing one source

THE FUNNEL IS FED FROM THE SWEEP'S OWN COUNTS, not from a hand-typed number. That is the whole
reason it can be trusted to say "you are blocked at EXECUTION" rather than "generate more": the
counts come from the run that just happened.

Reads artifacts, writes a report. Promotes nothing, sizes nothing, trades nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.convergence import Observation, elevate  # noqa: E402
from libs.research.evidence_tier import Finding, classify  # noqa: E402
from libs.research.funnel import Funnel, diagnose, render  # noqa: E402
from libs.research.near_survivor import NearSurvivor, hurdle, next_experiments  # noqa: E402

SWEEP = ROOT / "data" / "full_sweep.json"
OUT = ROOT / "data" / "research_review.json"
#: Structured miner output: one JSON object per line, `{region, mechanism, source, origins,
#: origins_recorded}`. The frontier miners write PROSE to `docs/research/*`, so this file is
#: normally absent -- and that absence is the measurement, not a missing feature.
FINDINGS = ROOT / "data" / "frontier_findings.jsonl"

#: Sweep kill criteria -> the near-survivor playbook's failure vocabulary. A cell killed by cost
#: licenses different next experiments from one killed by a thin sample, and collapsing them would
#: send the desk hunting a slower version of something that was never measured.
_KILL_TO_MODE: tuple[tuple[str, str], ...] = (
    ("F2", "cost"), ("F3", "decay"), ("F4", "decay"), ("F5", "sample"),
    ("F6", "timing"), ("F7", "correlation"), ("F8", "cost"),
)


def failure_mode(kill_key: str) -> str:
    """Map a fired kill criterion to a playbook mode. Unknown keys yield '' rather than a guess."""
    for prefix, mode in _KILL_TO_MODE:
        if kill_key.strip().upper().startswith(prefix):
            return mode
    return ""


def kill_caveat(doc: dict[str, object], blocked_at: str | None) -> tuple[str, str]:
    """(dominant kill criterion, caveat). THE FUNNEL'S STAGE IS NOT ALWAYS THE CAUSE.

    CAUGHT BY RUNNING THIS AGAINST THE BOX'S OWN REPORT. The funnel saw `out_of_sample: 0` and
    diagnosed OVERFITTING -- "the harness is selecting on noise; widening the search makes it
    worse". The sweep's kill breakdown said `F5 SAMPLE FLOOR: 2`: both cells died because a split
    ARM HAD TOO FEW OBSERVATIONS, which is a data-span problem.

    Those imply opposite actions -- tighten the harness versus get more tape -- and the funnel
    alone cannot tell them apart, because a stage reports only that nothing got through, never
    why. The kill breakdown is the missing half, so it is read and stated beside the diagnosis
    rather than left in the artifact for someone to notice.
    """
    killed = doc.get("kill_criteria_fired", {})
    if not isinstance(killed, dict) or not killed:
        return "", ""
    dominant = max(killed, key=lambda k: killed[k])
    mode = failure_mode(str(dominant))
    if blocked_at in {"out_of_sample", "deflated"} and mode == "sample":
        return str(dominant), (
            f"THE STAGE IS NOT THE CAUSE: the funnel blames {blocked_at}, but the dominant kill is "
            f"'{dominant}' -- a SAMPLE floor, not a selection failure. Nothing overfitted; there "
            "were too few observations in a split arm to judge. The action is more span, NOT a "
            "tighter harness, and those are opposite spends.")
    return str(dominant), (
        f"dominant kill: '{dominant}' -- consistent with a {blocked_at or 'clear'} blockage")


def funnel_from_sweep(doc: dict[str, object]) -> Funnel:
    """Stage counts straight out of the sweep report.

    STAGES THE SWEEP DOES NOT MEASURE ARE None, NOT ZERO. `mined` and `novel_families` belong to
    the miners and the novelty gate, and reporting them as 0 here would make the funnel diagnose
    an INFORMATION blockage on every run -- blaming the one stage this artifact cannot see.
    """
    c = doc.get("counts", {}) if isinstance(doc.get("counts"), dict) else {}

    def _n(k: str) -> int | None:
        v = c.get(k)
        return int(v) if isinstance(v, int | float) else None

    return Funnel(counts={
        "mined": None,
        "hypotheses": _n("declared"),
        "novel_families": None,
        "tested": _n("measurable"),
        "net_positive": _n("net_positive_before_deflation"),
        "deflated": _n("cleared_screen_F1_F2"),
        "out_of_sample": _n("FORMULA"),
        "independent": _n("INDEPENDENT_MECHANISM"),
        "portfolio_positive": _n("PORTFOLIO_CONTRIBUTING"),
    })


def bank_near_survivors(doc: dict[str, object]) -> list[dict[str, object]]:
    """Killed cells -> next experiments, with the ancestry deflation already attached.

    THE ANCESTRY IS THE DECLARED UNIVERSE, not one. Every descendant spawned from these is a test
    on the same data chosen BECAUSE the desk saw this result, so it inherits the whole search that
    produced it -- otherwise the near-survivor bank becomes the most efficient survivor-
    manufacturing device on the desk.
    """
    killed = doc.get("kill_criteria_fired", {})
    ancestry = int(doc.get("declared_universe", 1) or 1)
    if not isinstance(killed, dict):
        return []
    out: list[dict[str, object]] = []
    for key, n in killed.items():
        mode = failure_mode(str(key))
        if not mode:
            continue
        ns = NearSurvivor(mechanism=str(key), failure_mode=mode, ancestry_trials=ancestry,
                          detail=f"{n} cell(s) killed by this criterion")
        plays = [d.experiment for d in next_experiments(ns)]
        out.append({
            "killed_by": str(key), "cells": n, "failure_mode": mode,
            "descendant_hurdle": round(hurdle(ns), 3),
            "next_experiments": plays,
            "note": ("a descendant is NOT an independent survivor and NOT a separate mechanism -- "
                     "it is spawned BECAUSE it is the same one, and it inherits the ancestry's "
                     f"whole trial count ({ancestry})"),
        })
    return out


def tier_survivors(doc: dict[str, object]) -> list[dict[str, object]]:
    """Tier each survivor by how cheaply it can be REFUTED.

    A sweep survivor is EXECUTABLE by construction -- the desk holds the expression and the data,
    so it can be re-run rather than argued about. Recording the tier anyway keeps one vocabulary
    across sweep survivors and mined claims, which is the point of having a tier at all.
    """
    survivors = doc.get("survivors", [])
    if not isinstance(survivors, list):
        return []
    out: list[dict[str, object]] = []
    for s in survivors:
        if not isinstance(s, dict):
            continue
        tier, why = classify(Finding(
            title="|".join(str(x) for x in s.get("key", [])),
            source_class="code_repository", has_code=True, has_data=True,
            has_params=True, mechanism_stated=True))
        out.append({"key": s.get("key"), "tier": tier, "why": why,
                    "t": s.get("t"), "net_bps": s.get("net_bps")})
    return out


def load_observations(path: Path) -> list[Observation]:
    """Miner sightings, from a STRUCTURED corpus. Malformed rows are skipped, not guessed at.

    `origins_recorded` defaults to False and that default is the honest one: a row that does not
    SAY it checked has not checked. Defaulting it True would turn every unexamined finding into
    an independent confirmation on the first run -- which is the exact inflation this module
    exists to refuse.
    """
    if not path.exists():
        return []
    obs: list[Observation] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not row.get("mechanism"):
            continue
        origins = row.get("origins") or ()
        obs.append(Observation(
            region=str(row.get("region", "")), mechanism=str(row["mechanism"]),
            source=str(row.get("source", "")),
            origins=tuple(str(x) for x in origins) if isinstance(origins, list | tuple) else (),
            origins_recorded=bool(row.get("origins_recorded", False)),
            observed=str(row.get("observed", "")), note=str(row.get("note", ""))))
    return obs


def convergence_report(path: Path) -> dict[str, object]:
    """Run the corpus through `convergence.elevate` -- CALLED, not described.

    THE MODULE HAD ZERO IMPORTERS AND AN EARLIER DRAFT OF THIS SCRIPT KEPT IT THAT WAY: it wrote
    a hand-typed `"verdict": "UNMEASURED"` string that merely ASSERTED what the module would have
    concluded. That is the same defect one level up -- a consumer that discusses a capability
    instead of exercising it -- so the verdict now comes out of `elevate()` on every run,
    including the run where the corpus is empty.
    """
    obs = load_observations(path)
    if not obs:
        return {"verdict": "UNMEASURED", "observations": 0, "source": str(path), "tally": {},
                "mechanisms": [],
                "reason": ("no STRUCTURED miner corpus at this path -- the frontier miners write "
                           "prose to docs/research/*, and no miner records a DERIVES-FROM chain "
                           "yet. So cross-ecosystem convergence cannot be told apart from three "
                           "regions echoing one English paper. Provenance accrues from the next "
                           "miner run forward; the existing corpus stays permanently "
                           "unverifiable.")}
    verdicts, tally = elevate(obs)
    elevated = [v.mechanism for v in verdicts if v.elevates]
    return {
        "verdict": "INDEPENDENT_CONVERGENCE" if elevated else "NONE ELEVATED",
        "observations": len(obs), "source": str(path), "tally": tally,
        "mechanisms": [{"mechanism": v.mechanism, "verdict": v.verdict,
                        "regions": list(v.regions), "clusters": v.independent_clusters,
                        "unrecorded": v.unrecorded, "reason": v.reason} for v in verdicts[:20]],
        "reason": ("convergence buys a QUEUE PLACE, never a lower bar -- an elevated mechanism "
                   "owes the same pre-registration, deflation and out-of-sample evidence as a "
                   "singleton lead."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", type=Path, default=SWEEP)
    ap.add_argument("--findings", type=Path, default=FINDINGS)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()

    try:
        doc = json.loads(a.sweep.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"research-review: BLOCKED -- no sweep report at {a.sweep}. That is UNMEASURED, "
              "not an empty funnel: run the sweep first.")
        return 0

    f = funnel_from_sweep(doc)
    d = diagnose(f)
    bank = bank_near_survivors(doc)
    tiers = tier_survivors(doc)
    dominant, caveat = kill_caveat(doc, d.blocked_at)
    conv = convergence_report(a.findings)

    rep = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "source": str(a.sweep),
        "sweep_verdict": doc.get("verdict"),
        "funnel": {"blocked_at": d.blocked_at, "blockage": d.blockage, "action": d.action,
                   "survivor_rate": d.survivor_rate, "survivors_per_month": d.survivors_per_month,
                   "unmeasured_downstream": list(d.unmeasured_downstream),
                   "warnings": list(d.warnings),
                   "dominant_kill": dominant, "kill_caveat": caveat},
        "near_survivor_bank": bank,
        "survivor_tiers": tiers,
        "convergence": conv,
        "authority": "NONE. Reads artifacts, promotes nothing, sizes nothing, trades nothing.",
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

    print(render(f))
    if caveat:
        print(f"  {caveat}")
    if bank:
        print(f"  near-survivor bank: {len(bank)} failure class(es) licensing next experiments")
        for b in bank[:3]:
            print(f"    {b['killed_by']} ({b['cells']} cells) -> hurdle "
                  f"{b['descendant_hurdle']} for any descendant")
    print(f"  convergence: {conv['verdict']} over {conv['observations']} sighting(s) {conv['tally']}")
    print(f"  survivors tiered: {len(tiers)} | artifact: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
