#!/usr/bin/env python3
"""FILL THE positioning_flow CLUSTER: CFTC positioning-CHANGE cells per FX pair and metal.

    python desks/mt5/research/cot_positioning_flow.py --once            # the scheduled form
    python desks/mt5/research/cot_positioning_flow.py --once --dry-run  # measure only

WHY (completion audit 2026-10-06, repair #3). Measured on the trading box: 9 of 15 alpha clusters
occupied and `positioning_flow` empty, while three CFTC report families sat in git -- legacy,
Traders in Financial Futures and disaggregated, under `data/cot*/`. The one COT family the
sealed gauntlet can build, `cot_positioning`, read a single gitignored column (legacy
non-commercial z) and traded only its LEVEL; the four `families.cot_*` change constructions take
a COT argument `build_cell` never loads (`gauntlet_buildability`: INPUT_NOT_SUPPLIED), so no
positioning-change hypothesis on any trader class could ever be judged. `empty_cluster_forcer`
names this cluster PROPOSER_OWNED; this is that proposer.

WHAT A PASS DOES:
  1. For every MT5 symbol with a CFTC contract (`mt5desk.cot_frames.SOURCES`: the seven USD
     majors and gold/silver) and every trader-class column the reports carry for it, form the
     cell `cot_positioning(series=<column>, transform="change", mode=fade|follow)` -- the weekly
     net change at an extreme, faded (crowding) and followed (flow).
  2. Build the cell's signals with the SAME frame the sealed gauntlet hands the family
     (`orthogonal_sweep._cot_frame`, point-in-time: a Tuesday report is first usable on the
     Monday after its Friday 15:30 ET release, or after its TRUE release when a holiday or a
     shutdown delayed it -- `mt5desk.cot_frames.release_schedule`) and count its firing. A
     cell under SEED_FLOOR trade days is HELD BACK and counted -- the gauntlet would drop it
     under 60 days as UNKNOWN.
  3. Donate the rest through `proposer_common.donate` (two-lane filter, point-in-time stamp,
     preregistration, canonical registry) into `data/intelligence/cot_positioning_flow/`, which
     `miner_candidate_compiler` compiles as EXACT_RECIPE into the docket the gauntlet judges.
     `tests_run` is the whole grid, so the screen's own looks are charged, not only survivors.
  4. Write `reports/COT_POSITIONING_FLOW.json`: cells per symbol and column, held back, donated,
     and the gauntlet's verdicts on them (UNMEASURED with the reason until it has judged one).

ADDITIVE ONLY: no other miner is capped, reordered or slowed. A cell is measured at most once per
day and donated once (the state file carries both).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "cot_positioning_flow"
FAMILY = "cot_positioning"
CLUSTER = "positioning_flow"
OUT = BASE / "reports" / "COT_POSITIONING_FLOW.json"
STATE = BASE / "data" / "cot_positioning_flow_state.json"
SEAT = BASE / "data" / "intelligence" / SOURCE
VERDICTS = BASE / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
#: The sealed run_gauntlet's reproduction-mode verdicts on these cells, judged off the box on
#: 2026-10-06 (no certificate, no ledger row). Reported beside the box's verdicts, never as them.
OFFBOX = BASE / "data" / "cot_positioning_flow_offbox_judge.json"
UNMEASURED = "UNMEASURED"

#: The construction, fixed BEFORE any verdict and identical for every symbol and class, so the
#: grid's width is the trial count and nothing is tuned per market. A weekly report on an H1
#: chart: an extreme is the top/bottom 20% of the last three years of weekly changes (40% of
#: weeks fire, enough independent entries for the gauntlet's 60-day floor on 2018+ bars), and the
#: hold is one trading week of H1 bars less a session, so a position closes before the next
#: report it would otherwise straddle.
PARAMS: dict[str, Any] = {"transform": "change", "change_weeks": 1, "lookback_weeks": 156,
                          "extreme_pct": 0.80, "ttl_bars": 110, "stop_atr": 3.0, "rr": 2.0,
                          "input_source": "cot_point_in_time"}
MODES = ("fade", "follow")
#: The sealed gauntlet drops a daily series under 60 days before any gate.
FIRE_FLOOR = 60
#: Ten percent above it, as `cross_sectional_breadth` holds: the lockbox carve and the cost model
#: both remove days the count here assumed.
SEED_FLOOR = 66
VERDICT_TAIL_BYTES = 64 * 1024 * 1024
#: Seconds the refetch step may spend on the network before the measuring pass (the hourly cap on
#: this leg covers both).
REFETCH_BUDGET_S = 150.0

MECHANISM = {
    "fade": ("{cls} moved its {sym} net position by an extreme amount in one week; a class that "
             "has just done that much of its buying or selling is closer to done than not, so the "
             "price move it forced is faded"),
    "follow": ("{cls} moved its {sym} net position by an extreme amount in one week; a class "
               "re-positioning that hard is acting on information or a mandate that does not "
               "finish in a week, so the flow is followed"),
}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def identity(symbol: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": FAMILY, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


def grid() -> list[tuple[str, dict[str, Any]]]:
    """(symbol, params) for every cell: symbol x trader-class column on disk x mode."""
    from mt5desk import cot_frames
    out: list[tuple[str, dict[str, Any]]] = []
    for sym in sorted(cot_frames.SOURCES):
        for col in cot_frames.available(sym):
            for mode in MODES:
                out.append((sym, {**PARAMS, "series": col, "mode": mode}))
    return out


def _seat_donated() -> dict[str, str]:
    """{identity: generated_at} for every cell already in this organ's seat files.

    THE SEAT IS THE RECORD OF WHAT WAS DONATED, not only the state file. A donation committed
    from one tree reaches the other as an origin-only input while the state file may not, and a
    proposer that trusted its state alone would donate the same cells again on the box."""
    out: dict[str, str] = {}
    for path in sorted(SEAT.glob("discoveries_*.json")):
        doc = _read(path)
        if not isinstance(doc, dict):
            continue
        at = str(doc.get("generated_at") or path.stem)
        for row in doc.get("discoveries") or []:
            if isinstance(row, dict) and row.get("family") == FAMILY and row.get("symbol"):
                out.setdefault(identity(str(row["symbol"]), dict(row.get("params") or {})), at)
    return out


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    state = (doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict)
             else {"cells": {}})
    for ident, at in _seat_donated().items():
        row = state["cells"].setdefault(ident, {})
        row.setdefault("donated_at", at)
    return state


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1), "utf-8")
    tmp.replace(STATE)


def _build(sym: str, params: dict[str, Any], bars_cache: dict[str, Any]) -> list:
    """The family's signals on the gauntlet's own inputs: its COT frame, these H1 bars."""
    from mt5desk import families_orthogonal as fo

    from research import orthogonal_sweep as inputs
    from research.proposer_common import bars
    if sym not in bars_cache:
        bars_cache[sym] = bars(sym)
    d = bars_cache[sym]
    cot = inputs._cot_frame(sym)
    if d is None or cot is None:
        return []
    call = {k: v for k, v in params.items() if k != "input_source"}
    return list(fo.family_cot_positioning(d, cot=cot, **call) or [])


def seed(*, budget_s: float = 300.0, dry_run: bool = False) -> dict[str, Any]:
    from mt5desk import cot_frames

    from research.cross_sectional_breadth import firing
    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    state = _load_state()
    cells_state: dict[str, Any] = state["cells"]
    plan = grid()
    bars_cache: dict[str, Any] = {}
    cands: list[dict[str, Any]] = []
    by_symbol: dict[str, Counter] = {}
    by_series: dict[str, Counter] = {}
    errors: Counter = Counter()
    measured = 0
    stopped = "grid exhausted"
    for sym, params in plan:
        if time.monotonic() - started > budget_s:
            stopped = f"time budget {budget_s:g}s reached; resumes next pass"
            break
        ident = identity(sym, params)
        prior = cells_state.get(ident) or {}
        srow = by_symbol.setdefault(sym, Counter())
        crow = by_series.setdefault(str(params["series"]), Counter())
        srow["grid"] += 1
        crow["grid"] += 1
        if prior.get("day") != today:
            try:
                sigs = _build(sym, params, bars_cache)
                d = bars_cache.get(sym)
                got = firing(sigs, d) if d is not None else {"signal_days": 0,
                                                             "trade_days_lb": 0}
            except Exception as exc:
                errors[f"{sym}.{params['series']}: {type(exc).__name__}"] += 1
                continue
            prior = {**prior, **got, "day": today, "symbol": sym, "params": params}
            cells_state[ident] = prior
            measured += 1
        ok = int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR
        tag = "clears_floor" if ok else "held_back_under_floor"
        srow[tag] += 1
        crow[tag] += 1
        if ok and not prior.get("donated_at"):
            cands.append({"ident": ident, "symbol": sym, "params": params,
                          "firing": {k: prior.get(k) for k in ("signal_days", "trade_days_lb")}})

    donated = 0
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        from research import proposer_common as pc
        rows = []
        for c in cands:
            col = str(c["params"]["series"])
            report, cls = cot_frames.COLUMNS.get(col, ("?", col))
            rows.append(pc.candidate(
                SOURCE, c["symbol"], FAMILY, c["params"],
                MECHANISM[str(c["params"]["mode"])].format(cls=cls, sym=c["symbol"]),
                f"{c['symbol']} COT {report} {col} weekly change, {c['params']['mode']}",
                # No "gauntlet_floor" key: the Tier S blinding door strips any gate-named field
                # as a read of gate outcomes and withholds the seat's passes for it.
                {"firing": c["firing"], "seed_floor": SEED_FLOOR, "target_cluster": CLUSTER,
                 "cot_report": report, "trader_class": cls,
                 "release_clock": ("report usable from the later of the Monday after its "
                                   "nominal Friday release and the first hour after its TRUE "
                                   "release (holiday and shutdown delays: "
                                   "mt5desk.cot_frames.release_schedule)")}))
        path = pc.donate(SOURCE, rows, len(plan))
        counts = pc.donation_counts()
        donated = int(counts.get("donated") or 0)
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None,
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "refused_unstamped": counts.get("refused_unstamped"),
                    "registry_error": counts.get("registry_error")}
        if path:
            at = _now()
            for c in cands:
                cells_state[c["ident"]]["donated_at"] = at
    if not dry_run:
        _save_state(state)
    donated_total = sum(1 for v in cells_state.values() if v.get("donated_at"))
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2),
        "grid_cells": len(plan), "measured_this_pass": measured,
        "seed_floor_trade_days": SEED_FLOOR, "gauntlet_floor_days": FIRE_FLOOR,
        "construction": PARAMS, "modes": list(MODES),
        "cells_by_symbol": {k: dict(v) for k, v in sorted(by_symbol.items())},
        "cells_by_series": {k: dict(v) for k, v in sorted(by_series.items())},
        "candidates_this_pass": len(cands), "donated_this_pass": donated,
        "donated_total": donated_total, "donation": donation,
        "held_back": sorted(f"{v.get('symbol')}.{(v.get('params') or {}).get('series')}."
                            f"{(v.get('params') or {}).get('mode')}"
                            f" ({v.get('trade_days_lb')}d)"
                            for v in cells_state.values()
                            if int(v.get("trade_days_lb") or 0) < SEED_FLOOR),
        "errors": dict(errors),
    }


def donated_keys() -> dict[str, dict[str, str]]:
    """{key kind: {key: donated cell label}} for every cell this organ donated.

    THE JOIN KEYS THE DONATION AND THE BOX'S VERDICT LEDGER SHARE (traced 2026-10-07). The
    compiler keeps a donated row's params EXACTLY (`miner_candidate_compiler.compile_row`,
    EXACT_RECIPE), and `external_gauntlet` writes each verdict row with
      * `cell`     = `frontier_identity.cell_id({sym, family, params})` -- `<SYM>.cot_positioning.
                     p=<sha256(params)[:16]>`, the name the off-box judge also printed;
      * `graph_id` = `hypothesis_graph.node_id_for_spec(...)` of the same spec;
      * `prereg_hash` -- when that sweep stamped the verdict: the content hash of the registered
                     card (`preregistration.row_hash`), so the SAME spec registered by this
                     proposer and by the docket carries the same hash.
    The join tries `prereg_hash` first (the one key that names the pre-registered card itself),
    then `cell`, then `graph_id`, so a verdict the sweep did not stamp is still read.
    The reader used to look for the literal '"transform": "change"' inside `cell`, a string no
    real cell name contains, so it read UNMEASURED forever whatever the box had judged."""
    from libs.research.hypothesis_graph import node_id_for_spec
    from research.frontier_identity import cell_id
    out: dict[str, dict[str, str]] = {"cell": {}, "graph_id": {}, "prereg_hash": {}}
    for path in sorted(SEAT.glob("discoveries_*.json")):
        doc = _read(path)
        if not isinstance(doc, dict):
            continue
        for row in doc.get("discoveries") or []:
            if not (isinstance(row, dict) and row.get("family") == FAMILY and row.get("symbol")):
                continue
            params = dict(row.get("params") or {})
            spec = {"sym": str(row["symbol"]), "family": FAMILY, "params": params}
            label = cell_id(spec)
            out["cell"][label] = label
            out["graph_id"][node_id_for_spec(spec)] = label
            if row.get("prereg_hash"):
                out["prereg_hash"][str(row["prereg_hash"])] = label
    return out


def verdicts() -> dict[str, Any]:
    """The gauntlet's recorded verdicts on the cells this organ donated (latest per cell)."""
    keys = donated_keys()
    if not keys["cell"]:
        return {"status": UNMEASURED, "why": "this organ has donated no cell yet, so there is "
                                             "nothing whose verdict could be read"}
    try:
        size = VERDICTS.stat().st_size
        with VERDICTS.open("rb") as fh:
            if size > VERDICT_TAIL_BYTES:
                fh.seek(size - VERDICT_TAIL_BYTES)
                fh.readline()
            blob = fh.read()
    except OSError as exc:
        return {"status": UNMEASURED,
                "why": f"{type(exc).__name__} reading {VERDICTS.name}: the gauntlet's verdict "
                       "ledger is not on this tree, so no verdict can be read here"}
    latest: dict[str, dict[str, Any]] = {}
    joined_by: Counter = Counter()
    needle = FAMILY.encode()
    for line in blob.splitlines():
        if needle not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("family") != FAMILY:
            continue
        for kind in ("prereg_hash", "cell", "graph_id"):
            label = keys[kind].get(str(row.get(kind) or ""))
            if label:
                latest[label] = row
                joined_by[kind] += 1
                break
    if not latest:
        return {"status": UNMEASURED, "cells_donated": len(keys["cell"]),
                "why": ("the gauntlet's ledger holds no verdict on any donated positioning-change "
                        "cell yet (joined on prereg hash, cell id and graph id)")}
    gates = Counter(str(r.get("terminal_gate") or "?") for r in latest.values())
    return {"status": "MEASURED", "cells_donated": len(keys["cell"]),
            "cells_judged": len(latest), "joined_by": dict(joined_by),
            "by_terminal_gate": dict(gates),
            "passed": sorted(c for c, r in latest.items() if r.get("passed"))}


def _offbox() -> dict[str, Any]:
    doc = _read(OFFBOX)
    if not isinstance(doc, dict):
        return {"status": UNMEASURED, "why": f"{OFFBOX.name} absent"}
    return {"status": "REPRODUCTION_ONLY", "path": str(OFFBOX.relative_to(ROOT)),
            **{k: doc.get(k) for k in ("judged_at", "n_cells_submitted", "n_judged",
                                       "n_unmeasured", "survivors_passing_all", "gate_fails")}}


def report(seeded: dict[str, Any]) -> dict[str, Any]:
    from libs.research.alpha_clusters import classify_family
    try:
        from research.gauntlet_buildability import family_verdict
        build = list(family_verdict(FAMILY))
    except Exception as exc:
        build = [UNMEASURED, f"buildability probe failed: {type(exc).__name__}"]
    return {
        "at": _now(), "organ": "desks/mt5/research/cot_positioning_flow.py",
        "family": FAMILY, "classified_cluster": classify_family(FAMILY),
        "target_cluster": CLUSTER, "sealed_gauntlet_buildability": build,
        "rule": ("one construction for every symbol and trader class, fixed before any verdict; "
                 f"a cell is donated once its lower-bound trade days clear {SEED_FLOOR} (the "
                 f"sealed gauntlet drops a series under {FIRE_FLOOR} days as UNKNOWN); the whole "
                 "grid is the donation's tests_run. Additive: no other miner is touched"),
        "seeding": seeded,
        "verdicts": verdicts(),
        "offbox_reproduction": _offbox(),
        "consumer": ("data/intelligence/cot_positioning_flow/ -> "
                     "research/miner_candidate_compiler.py (EXACT_RECIPE) -> the docket -> "
                     "scripts/external_gauntlet.py build_cell (sealed; its cot_positioning branch "
                     "loads orthogonal_sweep._cot_frame, which now carries every in-git column)"),
    }


def refetch(*, budget_s: float, dry_run: bool) -> dict[str, Any]:
    """THE REFETCH STEP (2026-10-07): bring the in-git CFTC files up to the newest RELEASED
    report before measuring. Every file had stopped at the 2026-08-11 report because nothing ran
    a fetcher after the first hand run; `mt5desk.fetch_cot_latest` fetches only a report family
    that is behind the release schedule, at most once per its retry window, and never writes
    less than the stored file holds. A failure is recorded in the report, never raised."""
    if dry_run:
        return {"status": "SKIPPED_DRY_RUN"}
    try:
        from mt5desk import fetch_cot_latest
        return {"status": "RAN", **fetch_cot_latest.run(budget_s=budget_s)}
    except Exception as exc:
        return {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"[:300]}


def run(*, budget_s: float = 300.0, dry_run: bool = False, out: Path | None = None
        ) -> dict[str, Any]:
    fetched = refetch(budget_s=REFETCH_BUDGET_S, dry_run=dry_run)
    doc = report(seed(budget_s=budget_s, dry_run=dry_run))
    doc["refetch"] = fetched
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and report, donate nothing")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run, out=args.out)
    s = doc["seeding"]
    print(f"cot_positioning_flow: grid={s.get('grid_cells')} measured={s.get('measured_this_pass')}"
          f" candidates={s.get('candidates_this_pass')} donated={s.get('donated_this_pass')} "
          f"(total {s.get('donated_total')}) held_back={len(s.get('held_back') or [])} "
          f"verdicts={doc['verdicts'].get('status')} -> {args.out or OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
