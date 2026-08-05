#!/usr/bin/env python3
"""PAPER-SLEEVE SPAWNER (R0102) -- Stage-A survivors become forward clocks, queued behind the cap.

WHAT THIS ORGAN DOES, once per day:
  1. reads the corrected screen verdicts (reports/axis_screens/*.json, `verdict_adjusted` --
     the artifact scripts/finalize_axis_screens.py writes; SCREEN-WEAK and NOT-A-CANDIDATE can
     never qualify);
  2. dedupes against every clock already standing (libs/research/slot_registry occupancy +
     on-disk *_shadow_state.json files + its own spawn ledger);
  3. spawns a PAPER sleeve per qualifying survivor while the Holm cohort has free slots, and
     QUEUES the rest by capacity runway, SHORTEST FIRST (L1.18a deployment race);
  4. maintains data/paper_sleeve_queue.json so the wait is visible, dated and ordered.

A SPAWN IS TWO WRITES, both idempotent: data/<sleeve>_shadow_state.json carrying `shadow_start`
(the same birth-certificate shape every standing clock uses -- an existing file is NEVER
overwritten, because rewriting shadow_start would reset a clock's forward evidence), and a row in
data/shadow_sleeves.json, the run roster slot_registry counts -- which is what makes the new clock
PAY ITS MULTIPLICITY from birth. A sleeve spawned without entering the cohort would understate m
and loosen every standing candidate's bar; that direction is forbidden, so if the roster is
unreadable the spawn REFUSES rather than risking an uncounted clock or erasing prior
registrations.

NEVER OVER CAP (the R0102 triage constraint): forward slots are 12/12 at the Holm cap today, and
each spawn tightens every standing clock's bar. Free slots come from the registry's own derived
cohort; an INCOMPLETE cohort (any unreadable source) spawns nothing, because m is then a lower
bound. The queue drains as retirements free slots -- this organ polls daily, which is the
information-arrival ceiling for ledgered retirement decisions.

ZERO PROMOTION AUTHORITY (L1.6): a paper sleeve accrues forward evidence and tests the execution
path at zero cost. It cannot touch capital; promotion stays with the forward-evidence bar.

REFUSAL PATHS: verdict store absent/uncorrected -> REFUSED-NO-INPUT, rc 2. Zero qualifying
survivors -> NO-CANDIDATES, rc 0 (the spawner being idle IS the correct state of an all-refuted
screen campaign -- today's real state). Cohort incomplete -> spawns 0, queues all, says why.

    python scripts/run_paper_sleeve_spawner.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.paper_sleeves import (  # noqa: E402
    Candidate,
    decide,
    parse_screen_verdicts,
    standing_names,
)

_REPORTS = "reports/axis_screens"
_QUEUE = "data/paper_sleeve_queue.json"
_ROSTER = "data/shadow_sleeves.json"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _load_queue(path: Path) -> dict[str, Any]:
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return {"queued": [], "spawned": []}
    return {"queued": [r for r in doc.get("queued", []) if isinstance(r, dict)],
            "spawned": [r for r in doc.get("spawned", []) if isinstance(r, dict)]}


def _spawn_one(root: Path, c: Candidate, reason: str) -> dict[str, Any]:
    """Create the sleeve's shadow-state file + roster row. Idempotent; refuses on a bad roster."""
    state_path = root / "data" / f"{c.name}_shadow_state.json"
    roster_path = root / _ROSTER
    roster_raw = _load_json(roster_path) if roster_path.exists() else []
    if not isinstance(roster_raw, list):
        # Rewriting a corrupt roster would ERASE prior registrations -> those clocks drop out of
        # the cohort, m shrinks and every bar LOOSENS. Refusing is the only safe direction.
        return {"name": c.name, "ts": _now(), "state": "REFUSED",
                "reason": f"{_ROSTER} unreadable/not-a-list -- writing would erase prior "
                          "registrations and shrink m (the forbidden direction)"}
    if not state_path.exists():
        # Birth certificate, same shape as every standing clock's (slot_registry _STANDING_STATES
        # reads `shadow_start`). Extra provenance keys are additive, like trend_regime's.
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({
            "shadow_start": _now(),
            "origin": "run_paper_sleeve_spawner (R0102): auto-spawned PAPER sleeve from a "
                      "corrected SCREEN-INTERESTING verdict; accrues forward evidence only, "
                      "never touches capital (L1.6)",
            "axis": c.axis, "trial": c.trial, "screen_report": f"{_REPORTS}/{c.source}",
            "screen_verdict": c.verdict,
            # THE BASELINE THE FORWARD CLOCK IS MEASURED AGAINST. Without it there is no way to
            # tell which rows arrived after birth, so "forward evidence" would silently mean
            # "in-sample evidence re-read" -- the exact confusion Stage B exists to prevent.
            "baseline": {"n_eff": c.n_eff, "ic": c.ic, "horizon_days": c.horizon_days,
                         "captured_at_spawn": True},
            "origin_artifact": c.origin_artifact, "origin_key": c.origin_key,
            "mechanism": c.mechanism,
        }, indent=1) + "\n", "utf-8")
    roster = sorted({*(str(x) for x in roster_raw if str(x).strip()), c.name})
    roster_path.write_text(json.dumps(roster, indent=1) + "\n", "utf-8")
    return {"name": c.name, "ts": _now(), "state": "SPAWNED", "reason": reason,
            "axis": c.axis, "trial": c.trial,
            # The verdict this clock was admitted under, ON THE LEDGER ROW. It was written into
            # the state file only, so the permanent spawn ledger recorded `verdict: None` for
            # every sleeve -- and the ledger is what survives a data reset, so the one durable
            # record of WHY a clock exists carried nothing.
            "verdict": c.verdict, "ic": c.ic, "horizon_days": c.horizon_days,
            "mechanism": c.mechanism,
            "state_file": f"data/{c.name}_shadow_state.json"}


def _repair_provenance(root: Path, candidates: list[Candidate]) -> list[dict[str, Any]]:
    """Top up a standing sleeve's state file with the provenance a forward runner needs.

    WHY A REPAIR PASS AND NOT A MIGRATION SCRIPT. `_spawn_one` never rewrites an existing state
    file -- rewriting one would reset `shadow_start` and erase a clock's forward evidence, which is
    the one thing that must never happen here. So a sleeve spawned before the state file carried
    `origin_artifact`/`origin_key`/`baseline` can never acquire them at spawn time, and the forward
    runner reports it UNRUNNABLE forever: standing, charging the cohort its multiplicity, and
    unable to accrue a single row. This pass adds ONLY the missing keys, on the sleeves whose
    hypothesis is still in the verdict store, and it is the reason the fix self-heals instead of
    needing a one-off script every time the shape grows.

    SHADOW_START IS NEVER TOUCHED, and neither is any key already present. The baseline is stamped
    `backfilled` rather than `captured_at_spawn`, because it was read after the clock started and
    claiming otherwise would overstate how much of the sample is genuinely out-of-sample.
    """
    repaired: list[dict[str, Any]] = []
    by_name = {c.name: c for c in candidates}
    data_dir = root / "data"
    if not data_dir.is_dir():
        return repaired
    for path in sorted(data_dir.glob("*_shadow_state.json")):
        name = path.name[: -len("_shadow_state.json")]
        c = by_name.get(name)
        if c is None:
            continue                            # not one of ours, or its hypothesis is gone
        doc = _load_json(path)
        if not isinstance(doc, dict) or not doc.get("shadow_start"):
            continue
        missing = [k for k in ("origin_artifact", "origin_key", "baseline") if not doc.get(k)]
        if not missing:
            continue
        if "origin_artifact" in missing:
            doc["origin_artifact"] = c.origin_artifact
        if "origin_key" in missing:
            doc["origin_key"] = c.origin_key
        if "baseline" in missing:
            doc["baseline"] = {
                "n_eff": c.n_eff, "ic": c.ic, "horizon_days": c.horizon_days,
                "captured_at_spawn": False,
                "backfilled_utc": _now(),
                "why": ("read AFTER the clock started, because this sleeve was spawned before "
                        "the state file carried a baseline. Rows already in the source at this "
                        "moment are therefore NOT proven out-of-sample; forward accrual is "
                        "measured from here, which understates nothing and overstates nothing."),
            }
        path.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")
        repaired.append({"name": name, "added": missing})
    return repaired


def run(root: Path, cohort: dict[str, Any] | None = None,
        book_usd: float | None = None) -> tuple[dict[str, Any], int]:
    """One spawner pass. `cohort` injectable for tests; None derives the live registry cohort."""
    if cohort is None:
        from libs.research.slot_registry import derive_slots
        cohort = derive_slots()

    parsed = parse_screen_verdicts(root / _REPORTS)
    queue_path = root / _QUEUE
    prior = _load_queue(queue_path)
    prior_queued = {str(r.get("name")): r for r in prior["queued"]}

    out: dict[str, Any] = {
        "updated": _now(),
        "law": "R0102/L1.6/L1.18a -- every corrected Stage-A survivor gets a costless paper "
               "sleeve; the cohort cap is never breached (queue behind retirements); the wait "
               "queue is ordered by capacity runway, shortest first",
        "verdict_store": {k: parsed[k] for k in parsed if k != "candidates"},
        "cohort": {k: cohort.get(k) for k in
                   ("m_concurrent", "cap", "complete", "over_cap", "idle_slots")},
        "spawned": prior["spawned"],
        "queued": [],
        "authority": "spawns PAPER clocks only; zero promotion authority, zero capital (L1.6)",
    }

    if parsed["status"] == "REFUSED-NO-INPUT":
        out["status"] = "REFUSED-NO-INPUT"
        out["why"] = parsed["why"]
        # The prior queue is PRESERVED, not dropped: a vanished verdict store must not silently
        # dissolve a wait that was lawfully entered.
        out["queued"] = prior["queued"]
        _write(queue_path, out)
        return out, 2

    out["provenance_repaired"] = _repair_provenance(root, parsed["candidates"])

    standing = standing_names(cohort, root / "data", prior)
    decision = decide(parsed["candidates"], standing, cohort, book_usd)
    out["free_slots"], out["why_free"] = decision["free_slots"], decision["why_free"]
    out["duplicates"] = decision["duplicates"]
    out["order_law"] = decision["order_law"]

    spawned_now = []
    for c in decision["spawn"]:
        reason = (f"corrected {c.verdict!r} from {c.source}; ic_t={c.ic_t}, "
                  f"sharpe_corrected={c.sharpe_corrected}; slot free at spawn time "
                  f"({decision['why_free']})")
        row = _spawn_one(root, c, reason)
        if row["state"] == "SPAWNED":
            out["spawned"] = [*out["spawned"], row]
            spawned_now.append(row["name"])
        else:
            # roster refusal: the candidate goes BACK to the queue, loudly
            decision["queue"].append(c)
            out["roster_refusal"] = row["reason"]

    for c in decision["queue"]:
        kept = prior_queued.get(c.name, {})
        out["queued"].append({
            "name": c.name, "axis": c.axis, "trial": c.trial,
            "ts": kept.get("ts", _now()),                      # first-seen stamp survives re-runs
            "reason": kept.get("reason",
                               f"corrected {c.verdict!r} from {c.source}; queued: "
                               f"{decision['why_free']}"),
            "capacity_usd": c.capacity_usd, "ic_t": c.ic_t,
        })

    dropped = sorted(set(prior_queued) - {q["name"] for q in out["queued"]}
                     - set(spawned_now)
                     - {d["name"] for d in decision["duplicates"]})
    if dropped:
        out["pruned"] = [{"name": n, "why": "no longer a qualifying survivor in the current "
                                            "verdict store (source of truth)"} for n in dropped]

    if spawned_now:
        out["status"] = f"SPAWNED {len(spawned_now)}" + (f", QUEUED {len(out['queued'])}"
                                                         if out["queued"] else "")
    elif out["queued"]:
        out["status"] = "QUEUED-AT-CAP" if decision["free_slots"] == 0 else "QUEUED"
    elif parsed["status"] == "NO-CANDIDATES":
        out["status"] = "NO-CANDIDATES"
        out["why"] = parsed["why"]
    else:
        out["status"] = "ALL-STANDING"
        out["why"] = "every qualifying survivor already has a clock -- nothing owed"
    _write(queue_path, out)
    return out, 0


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out, rc = run(_ROOT)
    if args.json:
        print(json.dumps(out, indent=1, default=str))
    else:
        print(f"paper-sleeve spawner (R0102): {out['status']} -- "
              f"cohort {out['cohort'].get('m_concurrent')}/{out['cohort'].get('cap')}, "
              f"{len(out.get('queued', []))} queued, "
              f"{len(out.get('spawned', []))} spawned all-time")
        if out.get("why"):
            print(f"  {out['why']}")
        for q in out.get("queued", [])[:6]:
            print(f"  QUEUED {q['name']} (since {str(q['ts'])[:10]}) -- {q['reason'][:90]}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
