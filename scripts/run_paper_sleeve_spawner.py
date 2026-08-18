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
    build_incumbent_series,
    decide,
    parse_full_sweep_candidates,
    parse_screen_verdicts,
    resolve_pnl_series,
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
            "origin": (
                "run_paper_sleeve_spawner (R0102): auto-spawned PAPER sleeve from "
                f"{c.source_kind}; accrues forward evidence only, never touches capital (L1.6)"),
            "axis": c.axis, "trial": c.trial,
            "screen_report": (
                f"{_REPORTS}/{c.source}" if c.source_kind == "axis_screen"
                else c.origin_artifact),
            "screen_verdict": c.verdict,
            "source_kind": c.source_kind,
            "pnl_artifact": (
                "data/full_sweep_survivor_pnl.npz"
                if c.source_kind == "full_sweep_npz" else ""),
            "pnl_key": c.pnl_key,
            "baseline_window_end": c.baseline_window_end,
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
        missing = [k for k in (
            "origin_artifact", "origin_key", "baseline", "source_kind",
        ) if not doc.get(k)]
        if c.source_kind == "full_sweep_npz":
            missing.extend(k for k in ("pnl_artifact", "pnl_key", "baseline_window_end")
                           if not doc.get(k))
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
        if "source_kind" in missing:
            doc["source_kind"] = c.source_kind
        if "pnl_artifact" in missing:
            doc["pnl_artifact"] = "data/full_sweep_survivor_pnl.npz"
        if "pnl_key" in missing:
            doc["pnl_key"] = c.pnl_key
        if "baseline_window_end" in missing:
            doc["baseline_window_end"] = c.baseline_window_end
        path.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")
        repaired.append({"name": name, "added": missing})
    return repaired


def _axis_slot_is_reclaimable(root: Path, name: str) -> bool:
    """True only when an explicit axis row can be retired without deleting evidence."""
    doc = _load_json(root / "data" / "axis_shadow_state.json")
    rows = doc.get("axes") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return False
    return any(isinstance(r, dict) and str(r.get("axis")) == name
               and str(r.get("verdict", "")).upper() != "RETIRED"
               for r in rows)


def _retire_axis_slot(root: Path, name: str, challenger: str, why: str) -> dict[str, Any]:
    """Ledger an instrument-failed axis retirement atomically; never delete its history.

    The replacement is written first, so a crash before this step can only make the cohort
    temporarily over-cap (a tighter bar, the safe direction). A failed retirement is reported and
    leaves that over-cap state visible; it never pretends the one-out/one-in swap completed.
    """
    path = root / "data" / "axis_shadow_state.json"
    doc = _load_json(path)
    rows = doc.get("axes") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return {"slot": name, "state": "REFUSED",
                "why": "axis_shadow_state missing/unreadable; evidence cannot be retired safely"}
    target = next((r for r in rows if isinstance(r, dict) and str(r.get("axis")) == name), None)
    if target is None:
        return {"slot": name, "state": "REFUSED", "why": "axis row vanished before retirement"}
    if str(target.get("verdict", "")).upper() == "RETIRED":
        return {"slot": name, "state": "ALREADY-RETIRED"}
    target.update({
        "verdict": "RETIRED",
        "retired_at": _now(),
        "retired_for": challenger,
        "retirement_reason": why,
        "retirement_authority": (
            "slot_displacement: zero observations/instrument fault only; outgoing hypothesis "
            "requeues as UNTESTED, never refuted"),
    })
    if isinstance(doc, dict):
        doc["updated"] = _now()
        payload = doc
    else:
        payload = rows
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    tmp.replace(path)
    return {"slot": name, "state": "RETIRED", "challenger": challenger, "why": why}


def run(root: Path, cohort: dict[str, Any] | None = None,
        book_usd: float | None = None) -> tuple[dict[str, Any], int]:
    """One spawner pass. `cohort` injectable for tests; None derives the live registry cohort."""
    if cohort is None:
        from libs.research.slot_registry import derive_slots
        cohort = derive_slots()

    axis_parsed = parse_screen_verdicts(root / _REPORTS)
    sweep_parsed = parse_full_sweep_candidates(root / "data" / "full_sweep.json")
    candidates = [*axis_parsed.get("candidates", []), *sweep_parsed.get("candidates", [])]
    if candidates:
        combined_status = "OK"
        combined_why = ""
    elif (axis_parsed.get("status") == "REFUSED-NO-INPUT"
          and sweep_parsed.get("status") == "REFUSED-NO-INPUT"):
        combined_status = "REFUSED-NO-INPUT"
        combined_why = (f"axis: {axis_parsed.get('why', '')}; "
                        f"full_sweep: {sweep_parsed.get('why', '')}")
    else:
        combined_status = "NO-CANDIDATES"
        combined_why = (f"axis: {axis_parsed.get('why', '')}; "
                        f"full_sweep: {sweep_parsed.get('why', '')}")
    parsed = {"status": combined_status, "why": combined_why, "candidates": candidates}
    queue_path = root / _QUEUE
    prior = _load_queue(queue_path)
    prior_queued = {str(r.get("name")): r for r in prior["queued"]}

    out: dict[str, Any] = {
        "updated": _now(),
        "law": "R0102/L1.6/L1.18a -- every corrected Stage-A survivor gets a costless paper "
               "sleeve; the cohort cap is never breached (queue behind retirements); the wait "
               "queue is ordered by capacity runway, shortest first",
        "verdict_store": {
            "axis": {k: axis_parsed[k] for k in axis_parsed if k != "candidates"},
            "full_sweep": {k: sweep_parsed[k] for k in sweep_parsed if k != "candidates"},
            "combined_candidates": len(candidates),
        },
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

    # Reclaim only clocks the shared displacement law proves cannot resolve. The plan includes
    # idle seats first, then count-neutral swaps. Only explicit axis rows are actionable here:
    # fixed standing clocks and built-in derivative clocks require their owning lifecycle to
    # retire them, and guessing would destroy irreplaceable forward evidence.
    from libs.research.slot_displacement import plan_displacement
    plan = plan_displacement(
        list(cohort.get("slots") or []),
        [c.as_rank_row(book_usd) for c in parsed["candidates"]],
        cap=int(cohort.get("cap") or 12))
    by_candidate = {d.challenger: d for d in plan.displaced
                    if _axis_slot_is_reclaimable(root, d.slot)}
    virtual = dict(cohort)
    if by_candidate:
        retiring = {d.slot for d in by_candidate.values()}
        virtual["slots"] = [s for s in list(cohort.get("slots") or [])
                            if str(s.get("name")) not in retiring]
        for key in ("m_concurrent", "m_upper"):
            if isinstance(cohort.get(key), (int, float)):
                virtual[key] = max(0, int(cohort[key]) - len(retiring))
        virtual["idle_slots"] = max(
            0, int(virtual.get("cap") or 12) - int(
                virtual.get("m_upper") if isinstance(virtual.get("m_upper"), (int, float))
                else virtual.get("m_concurrent") or 0))

    # R0480: the marginal-contribution gate needs every candidate's and every standing clock's
    # return series. The incumbent map is built from the REAL cohort's slots; the virtual pass
    # looks up its (reduced) slot set in the same map, so a retiring clock lawfully leaves the
    # matrix while a slot the map cannot resolve stays in it as UNMEASURED and fails closed.
    inc_series = build_incumbent_series(root, cohort)

    def _series(c: Candidate):
        return resolve_pnl_series(root, source_kind=c.source_kind, pnl_key=c.pnl_key)

    decision = decide(parsed["candidates"], standing, virtual, book_usd,
                      series_of=_series, incumbent_series=inc_series)
    # A virtual displacement may only fund ITS OWN challenger. Otherwise a higher-ranked,
    # unrelated candidate can consume the virtual seat while the outgoing clock remains live.
    actual = decide(parsed["candidates"], standing, cohort, book_usd,
                    series_of=_series, incumbent_series=inc_series)
    real_free = int(actual["free_slots"])
    lawful_spawn = []
    for candidate in decision["spawn"]:
        if real_free > 0:
            lawful_spawn.append(candidate)
            real_free -= 1
        elif candidate.name in by_candidate:
            lawful_spawn.append(candidate)
        else:
            decision["queue"].append(candidate)
    decision["spawn"] = lawful_spawn
    out["free_slots"], out["why_free"] = decision["free_slots"], decision["why_free"]
    out["duplicates"] = decision["duplicates"]
    out["order_law"] = decision["order_law"]
    out["displacement_plan"] = {
        "planned": [{"slot": d.slot, "challenger": d.challenger, "why": d.why}
                    for d in plan.displaced],
        "actionable_axis_swaps": list(by_candidate),
        "blocked": list(plan.blocked),
        "protected": list(plan.protected),
        "waiting": list(plan.waiting),
        "count_neutral": plan.count_neutral,
        "notes": list(plan.notes),
    }

    spawned_now = []
    retirements: list[dict[str, Any]] = []
    for c in decision["spawn"]:
        reason = (f"corrected {c.verdict!r} from {c.source}; ic_t={c.ic_t}, "
                  f"sharpe_corrected={c.sharpe_corrected}; slot free at spawn time "
                  f"({decision['why_free']})")
        row = _spawn_one(root, c, reason)
        # R0480(4): the Admission verdict this clock was spawned under, ON the durable spawn row
        # -- the decision is auditable at the moment it was taken, not reconstructed later.
        row["marginal_admission"] = decision["admissions"].get(c.name)
        if row["state"] == "SPAWNED":
            out["spawned"] = [*out["spawned"], row]
            spawned_now.append(row["name"])
            displacement = by_candidate.get(c.name)
            if displacement is not None:
                retirements.append(_retire_axis_slot(
                    root, displacement.slot, c.name, displacement.why))
        else:
            # roster refusal: the candidate goes BACK to the queue, loudly
            decision["queue"].append(c)
            out["roster_refusal"] = row["reason"]

    for c in decision["queue"]:
        kept = prior_queued.get(c.name, {})
        qrow: dict[str, Any] = {
            "name": c.name, "axis": c.axis, "trial": c.trial,
            "ts": kept.get("ts", _now()),                      # first-seen stamp survives re-runs
            "reason": kept.get("reason",
                               f"corrected {c.verdict!r} from {c.source}; queued: "
                               f"{decision['why_free']}"),
            "capacity_usd": c.capacity_usd, "ic_t": c.ic_t,
        }
        # R0480: a candidate the marginal gate REFUSED queues with its verdict visible -- the
        # refusal is a measurement of the current book, not a permanent kill, and it must be
        # readable on the queue row it produced.
        if c.name in decision["admissions"]:
            qrow["marginal_admission"] = decision["admissions"][c.name]
        out["queued"].append(qrow)

    out["retirements"] = retirements
    if any(r.get("state") == "REFUSED" for r in retirements):
        out["safe_over_cap_warning"] = (
            "replacement was registered but outgoing axis retirement failed. The cohort may be "
            "temporarily over cap, which tightens the bar (safe direction); repair before any "
            "promotion decision.")

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
    try:
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
    except BrokenPipeError:
        # Pipe closed (e.g., `head`, `less`) - exit cleanly
        sys.exit(0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
