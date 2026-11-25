"""WHERE THE JUDGE'S TIME GOES, WHAT A VERDICT COSTS, AND THE FLOOR LADDER (owner, 2026-11-25).

    from research import judge_efficiency; judge_efficiency.publish()   # hourly, inside the
                                                                          # judging_throughput leg

THE OWNER'S TARGET. At least 100,000 first verdicts a day, then 200,000-300,000 judged cells a
day on a RATCHETING FLOOR LADDER: 100k, then 200k, raised again each time the measured rate
reaches the floor in force. Floors only ever go up. This organ publishes the ladder
(`floor_now`, `next_floor`, `measured_rate_24h`, `per_core`) and the breakdown behind it in
`reports/JUDGE_EFFICIENCY.json`; the ladder's own state is `data/judge_verdict_ladder.json`.

WHAT THE LADDER COUNTS: FIRST TERMINAL VERDICTS (`JUDGING_RATE.json`
`verdicts.first_terminal_counts.24h`) -- a cell ruled for the first time. A re-judge of a cell
already ruled cannot move it, so the floor can never be met by judging the same cells again.
The all-judged rate (re-judges included) is published beside it as `judged_cells_per_day`, with
its method, because the owner's second figure names judged cells.

EVERY NUMBER CARRIES ITS SOURCE, AND AN ABSENT INPUT IS UNMEASURED, NEVER ZERO (L1.28a). The
"after" figures are ESTIMATES and say so: each names the measured input it scales and the rule
it applies. Nothing here touches a gate, a trial charge, a cell or a verdict.

TWO HELPERS THE SEALED SWEEP'S SEAL_CLEAR PATCH CALLS (`prune_cache`, `reorder_keep`) live here
so the restatement in `judge_docket_order` and the tests read the same code the sweep would.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
REPORTS = DESK / "reports"
OUT = REPORTS / "JUDGE_EFFICIENCY.json"
LADDER = DESK / "data" / "judge_verdict_ladder.json"
UNMEASURED = "UNMEASURED"

#: The owner's ladder (2026-11-25): first rung, second rung, and the step after the last named one.
LADDER_RUNGS = (100_000, 200_000, 300_000)
LADDER_STEP_AFTER = 100_000
#: The owner's reserved floor and research cap, as `judge_elastic_cores` applies them.
FLOOR_CORES = 6
RESEARCH_CAP_SHARE = 0.75
#: The sealed prune's age (`external_gauntlet.main`: `> 3 * 86400`).
CACHE_PRUNE_AGE_S = 3 * 86400


# ---------------------------------------------------------------- helpers the sealed patch uses
def prune_cache(cache_dir: Path, max_age_s: float = CACHE_PRUNE_AGE_S,
                now: float | None = None, suffix: str = ".npz") -> dict[str, int]:
    """Delete `*{suffix}` files in `cache_dir` older than `max_age_s`: the sealed prune's rule.

    THE SAME FILES, A FRACTION OF THE SYSCALLS. The sealed prune is `CACHE_DIR.glob("*.npz")`
    then `f.stat()` per file. On Windows `Path.stat()` opens every file again
    (CreateFileW + GetFileInformationByHandle) after the directory listing already returned its
    times; `os.scandir`'s `DirEntry.stat()` is served from the FindNextFileW record with no
    further call. Measured on the box (JUDGE_RESIDENT.json wall profile, 2026-11-24): the plan
    phase ran 3,767 s, `cache_prune` 3,159 s of it, and 63.4% of the plan's samples sat in
    `stat` at external_gauntlet.py:3613 (7.1% in `unlink` at :3614).
    Never raises; an unreadable directory deletes nothing.
    """
    import time as _t

    now = _t.time() if now is None else now
    seen = removed = 0
    try:
        with os.scandir(cache_dir) as it:
            for e in it:
                if not e.name.endswith(suffix):
                    continue
                seen += 1
                try:
                    if now - e.stat().st_mtime > max_age_s:
                        os.unlink(e.path)
                        removed += 1
                except OSError:
                    continue
    except OSError:
        pass
    return {"seen": seen, "removed": removed}


def reorder_keep(before: list[dict], keep: list[dict]) -> list[dict]:
    """`keep` (allocate_by_yield's output) put back into the order `before` gave it. A PERMUTATION.

    `allocate_by_yield` builds `keep` one family block at a time, so the sweep's global order --
    never-judged first, intraday, CEO family, least-covered bucket, symbol rotation -- survives
    only INSIDE each family. The pre-warm and the shards then walk family blocks, and a
    never-judged cell of a late family waits behind every re-judge of the early ones, while the
    allocation's own docstring says the trim "leaves that ordering exactly as it is". This
    restores it: each kept spec takes the position it had in `before`; a spec `before` does not
    hold (none today) keeps its relative place after every one that it does. Same objects, same
    multiset, nothing added or dropped.
    """
    pos = {id(sp): i for i, sp in enumerate(before)}
    tail = len(pos)
    return [sp for _, sp in sorted(enumerate(keep),
                                   key=lambda t: (pos.get(id(t[1]), tail), t[0]))]


# ---------------------------------------------------------------- measurement
def _read(name: str, reports: Path | None = None) -> Any:
    try:
        return json.loads(((reports or REPORTS) / name).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _get(doc: Any, *path: str) -> Any:
    for k in path:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(k)
    return doc


def measure(reports: Path | None = None) -> dict[str, Any]:
    """The judge's measured breakdown, every figure with its source. Pure read."""
    res = _read("JUDGE_RESIDENT.json", reports)
    rate = _read("JUDGING_RATE.json", reports)
    thr = _read("JUDGING_THROUGHPUT.json", reports)
    stall = _read("JUDGE_STALL.json", reports)
    hb = _read("GAUNTLET_HEARTBEAT.json", reports)
    cov = _read("JUDGE_COVERAGE.json", reports)
    el = _read("JUDGE_ELASTIC_CORES.json", reports)

    first_24h = _num(_get(rate, "verdicts", "first_terminal_counts", "24h"))
    first_7d = _num(_get(rate, "verdicts", "first_terminal_counts", "7d"))
    changed_24h = _num(_get(rate, "verdicts", "counts", "24h"))
    created_24h = _num(_get(rate, "created", "counts", "24h"))
    created_7d = _num(_get(rate, "created", "counts", "7d"))
    sweep_s = _num(_get(res, "last_sweep_s"))
    judged_sweep = _num(_get(stall, "incidents", "zero_judged_sweep", "cells"))
    judged_per_day = (judged_sweep / sweep_s * 86400.0) if judged_sweep and sweep_s else None
    rejudge = (1.0 - first_24h / judged_per_day) if (first_24h is not None
                                                     and judged_per_day) else None
    box = _get(thr, "box") or {}
    n_cpus = _num(box.get("cores"))
    busy_j = [x for x in (_num(box.get("busy_judge_cores")),
                          _num(_get(stall, "incidents", "cores_idle", "busy_judge_cores")))
              if x is not None]
    busy_o = [x for x in (_num(box.get("busy_other_cores")),
                          _num(_get(stall, "incidents", "cores_idle", "busy_other_cores")))
              if x is not None]
    judge_cores = (sum(busy_j) / len(busy_j)) if busy_j else None
    other_cores = (sum(busy_o) / len(busy_o)) if busy_o else None
    idle_cores = (n_cpus - judge_cores - other_cores) if (n_cpus and judge_cores is not None
                                                          and other_cores is not None) else None
    sp = _get(res, "sweep_phase") or {}
    steps = sp.get("plan_steps") or {}
    plan_s = _num(_get(sp, "phases", "plan"))
    prune_s = _num(steps.get("cache_prune"))
    plan_prof = _get(sp, "wall_profile", "phases", "plan", "top") or []
    stat_share = sum(float(t.get("share") or 0) for t in plan_prof
                     if isinstance(t, dict) and ":stat:" in str(t.get("stack"))
                     and "external_gauntlet.py:main" in str(t.get("stack")))
    unlink_share = sum(float(t.get("share") or 0) for t in plan_prof
                       if isinstance(t, dict) and ":unlink:" in str(t.get("stack")))
    pre_prof = _get(sp, "wall_profile", "phases", "prewarm") or {}
    phase_now = _get(hb, "phase")
    phase_elapsed = _num(_get(hb, "phase_elapsed_s"))
    tree_cpu_s = _num(_get(hb, "tree", "cpu_s"))
    run_s = None
    try:
        t0 = datetime.fromisoformat(str(_get(hb, "started_utc")))
        t1 = datetime.fromisoformat(str(_get(hb, "beat_utc")))
        run_s = (t1 - t0).total_seconds()
    except (TypeError, ValueError):
        pass
    tree_cores = (tree_cpu_s / run_s) if (tree_cpu_s and run_s) else None
    reserved = len(_get(el, "cpus") or []) or (FLOOR_CORES if n_cpus and n_cpus >= 16 else None)
    totals = _get(cov, "totals") or {}

    def _per_core(v: float | None, c: float | None) -> float | None:
        return round(v / c, 1) if (v is not None and c) else None

    return {
        "first_verdicts_24h": first_24h,
        "first_verdicts_per_day_7d": round(first_7d / 7.0, 1) if first_7d is not None else None,
        "changed_verdicts_24h": changed_24h,
        "created_24h": created_24h,
        "created_per_day_7d": round(created_7d / 7.0, 1) if created_7d is not None else None,
        "judged_cells_last_sweep": judged_sweep,
        "last_sweep_s": sweep_s,
        "judged_cells_per_day": round(judged_per_day, 1) if judged_per_day else None,
        "judged_cells_per_day_method": ("JUDGE_STALL zero_judged_sweep.cells (n_judged of the last "
                                        "completed sweep) / JUDGE_RESIDENT last_sweep_s x 86400"),
        "rejudge_rate": round(rejudge, 4) if rejudge is not None else None,
        "rejudge_rate_method": "1 - first_verdicts_24h / judged_cells_per_day",
        "cores": {"n_cpus": n_cpus, "reserved": reserved,
                  "judge_busy_sampled": round(judge_cores, 2) if judge_cores is not None else None,
                  "others_busy_sampled": round(other_cores, 2) if other_cores is not None else None,
                  "idle_sampled": round(idle_cores, 2) if idle_cores is not None else None,
                  "judge_tree_avg_this_sweep": round(tree_cores, 2) if tree_cores else None,
                  "samples": ("JUDGING_THROUGHPUT.box and JUDGE_STALL.cores_idle: two 1-s "
                              "instants; judge_tree_avg = GAUNTLET_HEARTBEAT tree.cpu_s / run "
                              "wall")},
        "reservation_utilisation": (round(judge_cores / reserved, 3)
                                    if judge_cores is not None and reserved else None),
        "time_split": {
            "plan_s": plan_s, "cache_prune_s": prune_s,
            "cache_prune_share_of_plan": (round(prune_s / plan_s, 3)
                                          if prune_s and plan_s else None),
            "plan_stat_share": round(stat_share, 3), "plan_unlink_share": round(unlink_share, 3),
            "plan_steps": steps or None,
            "phase_now": phase_now, "phase_now_elapsed_s": phase_elapsed,
            "prewarm_main_thread_waiting_share": next(
                (float(t.get("share") or 0) for t in (pre_prof.get("top") or [])
                 if "_base.py:wait" in str(t.get("stack"))), None),
            "prewarm_write_bytes": _get(pre_prof, "process", "write_bytes"),
            "build_vs_evaluate": UNMEASURED,
            "build_vs_evaluate_why": ("the resident publishes only the CURRENT sweep's phases "
                                      "(plan done, prewarm running); the per-phase seconds of a "
                                      "COMPLETED sweep (build_shards / rule_shards / merge) are "
                                      "not in any report in the tree"),
        },
        "cache_hit_rate": UNMEASURED,
        "cache_hit_rate_why": ("the pre-warm summary (warmed / hit / unreached) is printed to the "
                               "sweep log only; no report carries it. Structural bound: the cache "
                               "key holds the last complete data-day AND the replay-code digest "
                               "(external_gauntlet._cache_key), so a sweep longer than a day "
                               "reads ~0 hits from the previous one"),
        "backlog": {"unjudged_total": totals.get("unjudged_total"),
                    "capacity_measured": totals.get("capacity_measured"),
                    "capacity_sustained_per_hour": totals.get("capacity_sustained_per_hour"),
                    "source": "JUDGE_COVERAGE.json totals"},
        "never_judged_in_sweep_docket": _num(_get(sp, "plan_counts", "never_judged")),
        "per_core": {
            "first_verdicts_per_day_per_reserved_core": _per_core(first_24h, reserved),
            "first_verdicts_per_day_per_busy_core": _per_core(first_24h, judge_cores),
            "judged_cells_per_day_per_reserved_core": _per_core(judged_per_day, reserved),
            "judged_cells_per_day_per_busy_core": _per_core(judged_per_day, judge_cores),
        },
        "elastic": {k: _get(el, k) for k in ("workers_now", "floor", "ceiling", "reason", "at")}
        if isinstance(el, dict) else UNMEASURED,
    }


def estimate_after(m: dict[str, Any]) -> dict[str, Any]:
    """The 'after' figures, each an ESTIMATE that names its measured input and its rule."""
    sweep_s, plan_s = m.get("last_sweep_s"), m["time_split"].get("plan_s")
    stat_share = m["time_split"].get("plan_stat_share") or 0.0
    cores = m["cores"]
    n, jb, ob = cores.get("n_cpus"), cores.get("judge_busy_sampled"), cores.get("others_busy_sampled")
    out: dict[str, Any] = {}
    if sweep_s and plan_s:
        saved = stat_share * plan_s
        out["prune_scandir"] = {
            "saved_s_per_sweep": round(saved, 0),
            "sweep_speedup": round(sweep_s / max(sweep_s - saved, 1.0), 4),
            "method": "plan_s x the plan's wall-profile share in external_gauntlet main's stat() "
                      "(the per-file stat DirEntry.stat removes; unlink stays)",
            "where": "SEAL_CLEAR patch (external_gauntlet.py is sealed)"}
    if n and jb is not None and ob is not None:
        ceiling = int(n * RESEARCH_CAP_SHARE)
        live_res = 2
        spare = max(0.0, n - live_res - ob)
        granted = max(FLOOR_CORES, min(ceiling, int(spare)))
        # The judge already fails to fill its reserved six (jb < 6); borrowing helps only in
        # proportion to the cores it can actually USE, so the gain is capped by its own fill.
        fill = (jb / FLOOR_CORES) if jb else 0.0
        usable = granted * fill
        out["elastic_cores"] = {
            "granted_cores_at_sample": granted, "usable_cores": round(usable, 2),
            "speedup": round(usable / jb, 3) if jb else None,
            "method": ("granted = clamp(n - 2 live reserve - others busy, 6, floor(0.75 n)); "
                       "usable = granted x measured reservation fill (judge busy / 6); speedup = "
                       "usable / judge busy, on the two sampled instants"),
            "full_borrow_speedup_bound": round(ceiling / FLOOR_CORES, 3)}
    sp = 1.0
    for k in ("prune_scandir", "elastic_cores"):
        v = out.get(k, {}).get("sweep_speedup" if k == "prune_scandir" else "speedup")
        if isinstance(v, (int, float)):
            sp *= float(v)
    jd = m.get("judged_cells_per_day")
    out["judged_cells_per_day_after"] = round(jd * sp, 0) if jd else None
    out["combined_speedup"] = round(sp, 3)
    # FIRST verdicts: a faster judge rules more cells, but a first verdict needs a never-judged
    # cell in the sweep's docket. The reorder (SEAL_CLEAR) puts them ahead of every re-judge; the
    # bound is the smaller of the sped-up reach and the never-judged supply.
    fv = m.get("first_verdicts_24h")
    out["first_verdicts_per_day_after"] = {
        "compute_bound": round(jd * sp, 0) if jd else None,
        "supply_bound_steady_state": m.get("created_24h"),
        "backlog_unjudged": (m.get("backlog") or {}).get("unjudged_total"),
        "estimate": (round(min(jd * sp, float(fv) * sp), 0) if (jd and fv is not None) else None),
        "method": ("without the reorder and with today's docket: measured first verdicts x the "
                   "combined speedup. With the reorder applied and a docket whose never-judged "
                   "tier is as deep as the sweep's reach, first verdicts approach the compute "
                   "bound until the coverage backlog drains, then the creation rate"),
    }
    return out


# ---------------------------------------------------------------- the ladder
def ladder_step(state: Any, measured_24h: float | None,
                now: datetime | None = None) -> dict[str, Any]:
    """Ratchet: when the measured 24h rate reaches `floor_now`, the next rung becomes the floor.

    Floors only go up: a state file holding a floor below the first rung, or a malformed one,
    reads as the first rung; a lower measured rate never lowers anything."""
    at = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    s = state if isinstance(state, dict) else {}
    fl = s.get("floor_now")
    floor_now = int(fl) if isinstance(fl, int) and not isinstance(fl, bool) else LADDER_RUNGS[0]
    floor_now = max(floor_now, LADDER_RUNGS[0])
    hist = list(s.get("history") or [])[-50:]

    def _next(f: int) -> int:
        higher = [r for r in LADDER_RUNGS if r > f]
        return higher[0] if higher else f + LADDER_STEP_AFTER

    raised = False
    if measured_24h is not None and measured_24h >= floor_now:
        hist.append({"at": at, "from": floor_now, "to": _next(floor_now),
                     "measured_24h": measured_24h})
        floor_now, raised = _next(floor_now), True
    return {"floor_now": floor_now, "next_floor": _next(floor_now), "raised_this_pass": raised,
            "met": bool(measured_24h is not None and measured_24h >= floor_now),
            "gap_per_day": (round(floor_now - measured_24h, 1)
                            if measured_24h is not None else UNMEASURED),
            "history": hist, "at": at}


def publish(*, reports: Path | None = None, ladder_path: Path | None = None,
            out: Path | None = None, write: bool = True,
            now: datetime | None = None) -> dict[str, Any]:
    """Measure, estimate, step the ladder, write JUDGE_EFFICIENCY.json. Never raises."""
    at = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    m = measure(reports)
    est = estimate_after(m)
    lp = ladder_path or LADDER
    try:
        prev = json.loads(lp.read_text("utf-8"))
    except (OSError, ValueError):
        prev = None
    rate = m.get("first_verdicts_24h")
    lad = ladder_step(prev, rate, now)
    cores = m["cores"]
    per_core_now = m["per_core"]
    n = cores.get("n_cpus")
    target_cores = int(n * RESEARCH_CAP_SHARE) if n else None
    doc = {
        "at": at,
        "ladder": {
            "counts": "first terminal verdicts (JUDGING_RATE verdicts.first_terminal_counts.24h)",
            "floor_now": lad["floor_now"], "next_floor": lad["next_floor"],
            "measured_rate_24h": rate if rate is not None else UNMEASURED,
            "per_core": per_core_now.get("first_verdicts_per_day_per_reserved_core"),
            "per_core_basis": "first verdicts / day / reserved judge core",
            "met": lad["met"], "raised_this_pass": lad["raised_this_pass"],
            "gap_per_day": lad["gap_per_day"],
            "judged_cells_per_day": m.get("judged_cells_per_day"),
            "required_per_hour": round(lad["floor_now"] / 24.0, 1),
            "required_per_hour_per_core_at_ceiling": (round(lad["floor_now"] / 24.0 / target_cores,
                                                            1) if target_cores else None),
            "rule": "floor_now rises to next_floor when measured_rate_24h >= floor_now; "
                    "100k -> 200k -> 300k -> +100k; floors never fall",
        },
        "before": m,
        "after_estimate": est,
        "rule": ("measured figures carry their source; after_estimate figures are estimates and "
                 "name their method; UNMEASURED is never zero; nothing here moves a gate, trial "
                 "charge, cell or verdict"),
    }
    if write:
        for path, body in ((lp, {k: lad[k] for k in ("floor_now", "next_floor", "history", "at")}),
                           (out or OUT, doc)):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
                tmp.write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
                os.replace(tmp, path)
            except OSError as exc:
                doc.setdefault("write_errors", []).append(f"{path.name}: {exc}")
    return doc


if __name__ == "__main__":
    import sys
    print(json.dumps(publish(write="--no-write" not in sys.argv)["ladder"], indent=1))
