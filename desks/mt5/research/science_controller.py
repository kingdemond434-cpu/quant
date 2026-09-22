"""THE ANYTIME-VALID SCIENCE CONTROLLER (LAWS 5k, 5m; Tier-1 U19): validation supremacy for a
research stream that never stops.

    python desks/mt5/research/science_controller.py --once [--budget-s 600] [--dry-run]

WHAT ONE PASS DOES, IN ORDER.
  1. Walks the registry's `research_candidates` and stamps every row with its research genome
     C = (M, D, R, G, S, H, E, F) (`libs.research.research_genome`) and the FAMILY the
     near-duplicate rule puts it in -- most of the tuple equal, whatever the parameters.
  2. Walks the trial stream -- the registry's `trials_ledger` (hash-chained, immutable) and the
     desk's `gate_verdict_ledger.jsonl` (every cell the external gauntlet judged, with the
     per-cell deflated-Sharpe probability joined from the gates report when it exists) -- maps
     each trial to its family, and prices the whole stream at N_effective through
     `libs.research.trial_ledger`: clones collapse, declared widths expand, and the raw count is
     published beside it so the size of the correction is visible.
  3. Replays online-FDR wealth (LORD++) per family in time order: every judged cell spends its
     grant; a cell whose p-value (1 - DSR when measured, the gate level when only pass/fail is
     known) is within the grant is a DISCOVERY and replenishes the lineage; a pass the grant
     could not afford is counted as such -- the sealed gate said yes at its level, the
     FDR-valid level said no, and both numbers are kept. Beside the per-cell replay, each
     family's pass/fail stream is scored by an anytime-valid e-process, so the family verdict
     (DISCOVERY / UNDECIDED) is the same whenever it is read.
  4. Keeps the quality-diversity archive over mechanism x data x region x asset x session x
     regime x horizon x execution: one elite per cell, the occupancy, and the empty cells one
     axis away from the strongest elites, valued with the registry's own empty-cell bonus.
  5. REFUSES launches an exhausted lineage cannot afford: every queued candidate whose family's
     next grant is below the floor is recorded BLOCKED with the reason, in the report and in
     the registry's `science_state` column. Nothing is dequeued and no gate is lowered; the
     consumer of that column is the next build and this report says so.

WHAT IT NEVER DOES. It moves no capital, changes no gate level, dequeues nothing, retires
nothing. The sealed fixed trial charge (gate_spec.yaml, principal 2026-08-26/28) stays exactly
what it is; N_effective is published beside it. Absent inputs are UNMEASURED by name, never
zero. Writes are atomic; `--dry-run` writes nothing at all, registry included.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import anytime_science as A  # noqa: E402
from libs.research import research_genome as G  # noqa: E402
from libs.research import trial_ledger as T  # noqa: E402

GATE_LEDGER = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
GATES_REPORT = BASE / "reports" / "universal_gates_external.json"
OUT_REPORT = BASE / "reports" / "SCIENCE_CONTROLLER.json"
MAX_LEDGER_LINES = 500_000
MAX_INPUT_BYTES = 64 * 1024 * 1024
TOP_FAMILIES = 200
TOP_ELITES = 100
TOP_BLOCKED = 300
EMPTY_CELLS = 25
#: A cell with more than this many UNMEASURED archive axes is a data gap, not a search target.
MAX_UNMEASURED_AXES = 2
UNMEASURED = "UNMEASURED"
#: The evidence rank an elite is seated on (axis_registry's STATES vocabulary, same order).
EVIDENCE_RANK = {"UNMEASURED": 0.0, "MEASURED_FAIL": 1.0, "CERTIFIED": 2.0, "FORWARD": 3.0,
                 "LIVE": 4.0}
RULE = ("the trial count follows the family; wealth is spent per launch and replenished per "
        "discovery; a verdict is the same whenever it is read; an exhausted lineage is refused "
        "and told why; no sealed gate moves")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _gate_level() -> tuple[float, str]:
    """1 - the sealed DSR threshold, read from the policy when it is importable."""
    try:
        from research.gate_policy import DSR_THRESHOLD
        return float(1.0 - float(DSR_THRESHOLD)), "research.gate_policy.DSR_THRESHOLD"
    except Exception as exc:  # the policy is an input; unreadable is a note, not a crash
        return 0.05, f"default 0.05 (policy unreadable: {type(exc).__name__})"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ------------------------------------------------------------------ inputs
def read_candidates(conn: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM research_candidates ORDER BY seq")]


def read_registry_trials(conn: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM trials_ledger ORDER BY seq")]


def read_gate_ledger(path: Path, note: dict[str, str]) -> list[dict[str, Any]]:
    """Every cell the external gauntlet judged, oldest first; absent is UNMEASURED."""
    if not path.exists():
        note["gate_ledger"] = f"absent: {path.name}"
        return []
    if path.stat().st_size > MAX_INPUT_BYTES:
        note["gate_ledger"] = f"{path.name} over {MAX_INPUT_BYTES} bytes; tail read only"
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("family"):
                rows.append(r)
            if len(rows) > MAX_LEDGER_LINES:
                rows = rows[-MAX_LEDGER_LINES:]
    rows.sort(key=lambda r: str(r.get("at") or ""))
    return rows


def read_cell_dsr(path: Path, note: dict[str, str]) -> dict[str, float]:
    """cell id -> deflated-Sharpe probability from the gates report, when a verdict carries
    one; a cell without it is priced at the gate level (pass) or 1.0 (fail) downstream."""
    if not path.exists():
        note["gates_report"] = f"absent: {path.name}; per-cell DSR unmeasured"
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        note["gates_report"] = f"unreadable: {type(exc).__name__}"
        return {}
    out: dict[str, float] = {}
    for v in doc.get("verdicts") or []:
        st = (v.get("stages") or {}).get("deflated_sharpe") if isinstance(v, dict) else None
        if isinstance(st, dict) and isinstance(st.get("dsr"), int | float):
            out[str(v.get("cell"))] = float(st["dsr"])
    return out


# ------------------------------------------------------------------ the pass
def _passed(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return True if s == "true" else False if s == "false" else None


def _evidence(row: dict[str, Any], judged: dict[str, bool]) -> tuple[str, float, str]:
    """(state, quality, basis) for one candidate: the gate ledger's verdict on its family x
    symbol when it has one, else the registry's priority score on an UNMEASURED base."""
    key = f"{row.get('family')}|{str(row.get('symbol') or '').upper()}"
    score = row.get("score")
    frac = min(0.999, float(score)) if isinstance(score, int | float) and score >= 0 else 0.0
    if key in judged:
        state = "CERTIFIED" if judged[key] else "MEASURED_FAIL"
        return state, EVIDENCE_RANK[state] + frac, f"gate_ledger:{state.lower()}"
    return UNMEASURED, frac, "registry:score" if frac > 0 else UNMEASURED


def build(*, registry_conn: Any | None = None, gate_ledger: Path | None = None,
          gates_report: Path | None = None, budget_s: float = 600.0,
          alpha: float = A.ALPHA, floor: float = A.ALPHA_FLOOR) -> dict[str, Any]:
    """One pass: read, stamp, price, replay, archive, refuse. Returns the report plus the
    private `_stamps` rows the writer applies to the registry. The input paths are resolved
    at call time (module globals), so a test that redirects them is honoured."""
    t0 = time.monotonic()
    note: dict[str, str] = {}
    gate_ledger = gate_ledger or GATE_LEDGER
    gates_report = gates_report or GATES_REPORT
    conn = registry_conn or R.connect()
    own = registry_conn is None
    try:
        rows = read_candidates(conn)
        reg_trials = read_registry_trials(conn)
    finally:
        if own:
            conn.close()
    gate_rows = read_gate_ledger(gate_ledger, note)
    dsr_by_cell = read_cell_dsr(gates_report, note)
    gate_level, gate_basis = _gate_level()
    if not rows:
        note["registry"] = "research_candidates is empty"
    if not reg_trials:
        note["trials_ledger"] = "registry trials_ledger holds no rows"

    # 1. genomes and families on every candidate
    genomes, fam_ids = G.stamp_all(rows)
    fam_of_key: dict[str, Counter[str]] = defaultdict(Counter)
    fam_names: dict[str, set[str]] = defaultdict(set)
    fam_mech: dict[str, str] = {}
    for g, fid in zip(genomes, fam_ids, strict=True):
        fam_of_key[f"{g.family}|{g.symbol}"][fid] += 1
        fam_of_key[g.family][fid] += 1
        fam_names[fid].add(g.family)
        fam_mech.setdefault(fid, g.mechanism)

    def family_for(family: str, symbol: str) -> str:
        c = fam_of_key.get(f"{family}|{str(symbol).upper()}") or fam_of_key.get(family)
        if c:
            return c.most_common(1)[0][0]
        g = G.genome_of({"family": family, "symbol": symbol})
        fid = f"fam_{g.exact_key()}"
        fam_names[fid].add(family)
        fam_mech.setdefault(fid, g.mechanism)
        return fid

    # 2. the trial stream, priced
    trials: list[T.Trial] = []
    events: list[dict[str, Any]] = []
    for i, r in enumerate(reg_trials):
        fid = family_for(str(r.get("family") or ""), str(r.get("symbol") or ""))
        g = G.genome_of({**r, "symbol": r.get("symbol") or ""})
        trials.append(T.Trial(str(r.get("id") or f"reg_{i}"), str(r.get("family") or ""),
                              g.descriptors(), g.params, 1, fid))
        verdict = r.get("passed")
        events.append({"at": str(r.get("created_at") or ""), "family_id": fid,
                       "passed": None if verdict is None else bool(verdict),
                       "p": None, "source": "trials_ledger"})
    judged: dict[str, bool] = {}
    for i, r in enumerate(gate_rows):
        fam, sym = str(r.get("family") or ""), str(r.get("sym") or r.get("symbol") or "")
        fid = family_for(fam, sym)
        g = G.genome_of({"family": fam, "symbol": sym})
        passed = _passed(r.get("passed"))
        cell = str(r.get("cell") or f"gate_{i}")
        trials.append(T.Trial(cell, fam, g.descriptors(), {"cell": cell}, 1, fid))
        if passed is not None:
            judged[f"{fam}|{sym.upper()}"] = judged.get(f"{fam}|{sym.upper()}", False) or passed
        dsr = dsr_by_cell.get(cell)
        p = (1.0 - dsr) if dsr is not None else (gate_level if passed else 1.0)
        events.append({"at": str(r.get("at") or ""), "family_id": fid, "passed": passed,
                       "p": None if passed is None else float(p), "source": "gate_ledger",
                       "dsr_measured": dsr is not None})
    census = T.census(trials)
    queue_trials = [T.Trial(g.candidate_id, g.family, g.descriptors(), g.params, 1, fid)
                    for g, fid in zip(genomes, fam_ids, strict=True)]
    queue_census = T.census(queue_trials)

    # 3. wealth replay, per lineage, in time order; the family e-process beside it
    ctrl = A.ScienceController(alpha=alpha, floor=floor)
    events.sort(key=lambda e: e["at"])
    per_fam: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "launches": 0, "judged": 0, "passes_at_gate": 0, "discoveries": 0,
        "passes_unaffordable": 0, "dsr_measured": 0, "stream": []})
    for e in events:
        fid = e["family_id"]
        st = per_fam[fid]
        launch = ctrl.launch(fid, 1.0)
        st["launches"] += 1
        if not launch.granted or e["passed"] is None:
            continue
        st["judged"] += 1
        st["stream"].append(bool(e["passed"]))
        if e.get("dsr_measured"):
            st["dsr_measured"] += 1
        if e["passed"]:
            st["passes_at_gate"] += 1
        p = e["p"] if e["p"] is not None else 1.0
        if ctrl.record(launch, p):
            st["discoveries"] += 1
        elif e["passed"]:
            st["passes_unaffordable"] += 1
    fam_rows: list[dict[str, Any]] = []
    members = Counter(fam_ids)
    queued = Counter(fid for fid, r in zip(fam_ids, rows, strict=True)
                     if str(r.get("status")) == "queued")
    all_fids = set(members) | set(per_fam)
    for fid in all_fids:
        st = per_fam.get(fid) or {"launches": 0, "judged": 0, "passes_at_gate": 0,
                                  "discoveries": 0, "passes_unaffordable": 0,
                                  "dsr_measured": 0, "stream": []}
        e_val = A.indicator_e_value(st["stream"], gate_level) if st["stream"] else 1.0
        fam_c = census.families.get(fid)
        wealth = ctrl.lineages[fid].to_dict() if fid in ctrl.lineages else None
        fam_rows.append({
            "family_id": fid, "families": sorted(fam_names.get(fid, ())),
            "mechanism": fam_mech.get(fid, UNMEASURED), "members": members.get(fid, 0),
            "queued": queued.get(fid, 0), "trials_raw": fam_c.n_raw if fam_c else 0,
            "n_effective": round(fam_c.n_effective, 3) if fam_c else 0.0,
            "launches": st["launches"], "judged": st["judged"],
            "passes_at_gate": st["passes_at_gate"], "discoveries": st["discoveries"],
            "passes_unaffordable": st["passes_unaffordable"],
            "dsr_measured": st["dsr_measured"],
            "e_value": round(e_val, 6),
            "anytime_p": round(min(1.0, 1.0 / e_val), 6) if e_val > 0 else 1.0,
            "verdict": (A.DISCOVERY if e_val >= 1.0 / alpha else
                        A.UNDECIDED if st["stream"] else UNMEASURED),
            "wealth": wealth["wealth"] if wealth else None,
            "next_alpha": wealth["next_alpha"] if wealth else None,
            "state": wealth["state"] if wealth else "OPEN",
        })
    fam_rows.sort(key=lambda r: (-int(r["members"]) - int(r["trials_raw"]), r["family_id"]))

    # 4. the archive
    archive = G.QDArchive(bonus=float(R.EMPTY_CELL_BONUS))
    state_counts: Counter[str] = Counter()
    for g, fid, row in zip(genomes, fam_ids, rows, strict=True):
        state, q, basis = _evidence(row, judged)
        state_counts[state] += 1
        archive.put(g.archive_cell(), g.candidate_id, q, basis, fid)
    unmeasured_cells = sum(1 for c in archive.cells
                           if c.split("|").count(UNMEASURED) > MAX_UNMEASURED_AXES)
    empty = [c for c in archive.empty_high_value(limit=EMPTY_CELLS * 8)
             if str(c["cell"]).split("|").count(UNMEASURED) <= MAX_UNMEASURED_AXES][:EMPTY_CELLS]

    # 5. refusals: queued members of exhausted lineages
    blocked: list[dict[str, Any]] = []
    stamps: list[tuple[str, str, str, str]] = []
    exhausted = {r["family_id"]: r for r in fam_rows if r["state"] == "EXHAUSTED"}
    for g, fid, row in zip(genomes, fam_ids, rows, strict=True):
        state = "OPEN"
        if str(row.get("status")) == "queued" and fid in exhausted:
            fr = exhausted[fid]
            reason = (f"EXHAUSTED lineage {fid}: next grant {fr['next_alpha']:.2e} below floor "
                      f"{floor:.0e} after {fr['launches']} launches and {fr['discoveries']} "
                      f"discoveries; {fr['passes_unaffordable']} gate pass(es) the grant could "
                      f"not afford")
            state = f"BLOCKED:{reason}"
            blocked.append({"candidate_id": g.candidate_id, "family_id": fid,
                            "family": g.family, "symbol": g.symbol, "reason": reason})
        stamps.append((json.dumps(g.to_dict(), sort_keys=True), fid, state, g.candidate_id))
    elapsed = time.monotonic() - t0
    report = {
        "at": _now(), "organ": "science_controller", "rule": RULE,
        "budget_s": budget_s, "elapsed_s": round(elapsed, 3),
        "budget_exhausted": elapsed > budget_s,
        "parameters": {"alpha": alpha, "w0": alpha / 2.0, "alpha_floor": floor,
                       "gate_level": gate_level, "gate_level_basis": gate_basis,
                       "near_duplicate_min_equal": G.NEAR_DUPLICATE_MIN_EQUAL,
                       "empty_cell_bonus": float(R.EMPTY_CELL_BONUS), "horizon": A.HORIZON},
        "inputs": {"registry": str(R.path()), "candidates": len(rows),
                   "registry_trials": len(reg_trials), "gate_ledger_rows": len(gate_rows),
                   "cells_with_dsr": len(dsr_by_cell),
                   "gate_level_affordable_by_a_fresh_lineage":
                       A.LineageWealth("fresh", alpha=alpha).alpha_at(1) >= gate_level,
                   "unmeasured": note},
        "families": {"count": len(all_fids), "with_queued": len(queued),
                     "exhausted": len(exhausted), "top": fam_rows[:TOP_FAMILIES]},
        "trials": {"stream": {"raw": census.n_raw, "effective": round(census.n_effective, 3),
                              "inflation": round(census.inflation, 4), "basis": census.basis},
                   "queue": {"raw": queue_census.n_raw,
                             "effective": round(queue_census.n_effective, 3),
                             "inflation": round(queue_census.inflation, 4)},
                   "sealed_charge_note": ("the external gauntlet's deflated-Sharpe charge is the"
                                          " sealed fixed campaign count (gate_spec.yaml); "
                                          "N_effective is published beside it and drives "
                                          "libs/validation/gauntlet.py's charge")},
        "wealth": ctrl.summary(),
        "archive": {**archive.occupancy(), "bonus": archive.bonus,
                    "unmeasured_cells": unmeasured_cells,
                    "evidence_states": dict(state_counts),
                    "elites": [e.to_dict() for e in sorted(
                        archive.cells.values(), key=lambda e: -e.quality)[:TOP_ELITES]]},
        "empty_high_value_cells": empty,
        "blocked": {"count": len(blocked), "families": len({b["family_id"] for b in blocked}),
                    "rows": blocked[:TOP_BLOCKED],
                    "consumer": "NONE yet: research_candidates.science_state carries the "
                                "verdict; claim_candidates does not read it (debt, named)"},
        "stamped": {"genomes": len(stamps), "families": len(set(fam_ids)),
                    "blocked_states": len(blocked), "written": False},
        "_stamps": stamps,
    }
    return report


def write(report: dict[str, Any], *, registry_conn: Any | None = None) -> Path:
    """Stamp the registry (genome_json, family_id, science_state) and write the report."""
    stamps = report.pop("_stamps", [])
    conn = registry_conn or R.connect()
    own = registry_conn is None
    try:
        conn.executemany(
            "UPDATE research_candidates SET genome_json=?, family_id=?, science_state=? "
            "WHERE id=?", stamps)
        conn.commit()
    finally:
        if own:
            conn.close()
    report["stamped"]["written"] = True
    _atomic_write(OUT_REPORT, json.dumps(report, indent=1, default=str))
    return OUT_REPORT


def summary(report: dict[str, Any], target: str) -> list[str]:
    f, t, w, a = report["families"], report["trials"], report["wealth"], report["archive"]
    inp = report["inputs"]
    top = f["top"][0] if f["top"] else {}
    return [
        f"SCIENCE CONTROLLER {report['at']}  candidates={inp['candidates']} "
        f"registry_trials={inp['registry_trials']} gate_ledger={inp['gate_ledger_rows']} "
        f"cells_with_dsr={inp['cells_with_dsr']}",
        f"  families {f['count']}  exhausted {f['exhausted']}  biggest "
        f"{top.get('family_id', 'none')} members={top.get('members', 0)} "
        f"n_eff={top.get('n_effective', 0)} state={top.get('state', UNMEASURED)}",
        f"  trials stream raw={t['stream']['raw']} effective={t['stream']['effective']} "
        f"(x{t['stream']['inflation']})  queue raw={t['queue']['raw']} "
        f"effective={t['queue']['effective']}",
        f"  wealth launches={w['launches']} discoveries={w['discoveries']} "
        f"spent={w['wealth_spent']} exhausted={w['exhausted']} refused={w['blocked']}  "
        f"gate level affordable by a fresh lineage: "
        f"{inp['gate_level_affordable_by_a_fresh_lineage']}",
        f"  archive cells_filled={a['cells_filled']} of {a['cells_possible']} "
        f"(unmeasured-heavy {a['unmeasured_cells']})  empty high-value "
        f"{len(report['empty_high_value_cells'])}",
        f"  BLOCKED {report['blocked']['count']} queued launches in "
        f"{report['blocked']['families']} families -> {target}",
        "  UNMEASURED  " + ("; ".join(f"{k}: {v}" for k, v in inp["unmeasured"].items())
                           or "nothing withheld"),
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="anytime-valid science controller")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args(argv)
    report = build(budget_s=args.budget_s)
    if args.dry_run:
        report.pop("_stamps", None)
        target = "DRY RUN (nothing written)"
    else:
        target = str(write(report))
    for line in summary(report, target):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
