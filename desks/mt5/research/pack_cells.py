"""EVERY DATA PACK PRODUCES CELLS, or names the reason it cannot.

THE PRINCIPAL, 2026-09-23: *"every data pack must produce cells -- this is the whole point of the
global build and it currently produces almost none."*

MEASURED ON THE BOX THE MORNING THIS WAS WRITTEN. Of 85 registered sources: 39 never collected,
40 stopped at BYTES, 1 ingested, 5 credited with a cell, 0 with a judged cell. The break was never
coverage -- it was between BYTES and REPRESENTATION, and then between representation and the one
gauntlet. `source_drain` prices and repairs the first half and publishes the chain; it enqueues a
DISCOVERY for a represented source and stops there, eight per pass, because a discovery is not a
cell and the compiler decides its own clock. Nothing turned a stamped series into CELLS.

WHAT THIS ORGAN DOES, and every clause is a number it publishes per pack:

  1. READS THE CHAIN IT DOES NOT OWN. `source_drain.chain_state()` is the per-source stage; this
     organ never re-derives it and never edits that module. A pack the chain calls REPRESENTED is
     eligible; every other pack is published with the stage it stopped at, which IS its reason.

  2. TURNS A STAMPED SERIES INTO SIGNALS. The point-in-time envelope written by
     `asia_parser`/`libs.data.pit_stamp` is stripped off, and every remaining column that carries
     numbers is a candidate conditioner. A pack whose frame carries no numeric column is not a
     silent zero: `reason` says "the series carries no numeric column", which is a fact about the
     page, not about this organ.

  3. EMITS THROUGH THE ONE DOOR. `libs.moat.registry.record_discovery` for the pack (once, keyed
     by the pack) and `enqueue_candidate` for each (signal x transform x target symbol x chart)
     cell, carrying `source_id` so the credit is attributable and `discovery_id` so the lineage
     is. No store beside the registry, no second gauntlet, no judging here.

  4. REACHES EVERY PACK. The emission order is a ROUND ROBIN over eligible packs from a saved
     cursor, so a pack at the end of the alphabet is not starved behind a pack with four hundred
     columns -- the same anti-starvation rule `source_drain.drain` applies to fetching.

  5. PUBLISHES CELLS_EMITTED AND CELLS_JUDGED PER PACK. Emitted is counted in the registry, not
     in this organ's own bookkeeping. Judged is counted in `trials_ledger`, which is the one
     gauntlet's own record of having tested a candidate -- a pack at zero judged with cells
     emitted is waiting on the gauntlet's clock, and the report says exactly that.

NOTHING HERE IS A CAP. The per-pass budget is a wall clock, not a quota: a pack not reached this
pass leads the next one, nothing is refused, nothing is throttled, and no pack is ever removed
from the eligible set. It never judges, never sizes and never vetoes.

    python desks/mt5/research/pack_cells.py --once --budget-s 240
    python desks/mt5/research/pack_cells.py --once --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "data" / "asia_sources.json"
SERIES = DESK / "data" / "lake" / "series"
CURSOR = DESK / "data" / "pack_cells_cursor.json"
OUT = DESK / "reports" / "PACK_CELLS.json"

#: The point-in-time envelope. These columns are the stamp, never a signal.
STAMP_COLUMNS: frozenset[str] = frozenset({
    "event_time", "published_time", "available_time", "revision_time", "retrieval_time",
    "ingested_time", "source_id", "vintage_id"})

#: How a conditioner reads a column. Three shapes, all price-free and all computable from the
#: series alone, so the gauntlet is judging the PACK's information and not a modelling choice.
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")

#: The charts a macro conditioner is asked on. H4 and D1 because a published statistic moves a
#: market for longer than an hour; H1 because that is the chart the desk holds most bars for.
#: Never a filter -- this is the ORDER the cells are minted in.
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")

#: A column with fewer distinct values than this is a label, a flag or a key, not a series.
MIN_DISTINCT = 4
#: Signals taken per pack per pass. The cursor carries the offset, so the next pass takes the
#: next ones and every column of every pack is reached. Not a cap on what a pack may emit.
SIGNALS_PER_PACK_PER_PASS = 6


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def packs() -> list[dict[str, Any]]:
    """The registered data packs. One registry row is one pack; transports are not packs."""
    reg = _read(REGISTRY, {}) or {}
    rows = reg.get("sources") if isinstance(reg, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id")
            and str(r.get("role") or "mechanism") != "transport"]


def chain() -> dict[str, dict[str, Any]]:
    """The chain state `source_drain` publishes. Empty when that organ has not run here, which
    is UNMEASURED and reported as such -- never silently treated as "no pack is eligible"."""
    try:
        from research.source_drain import chain_state
        return chain_state()
    except Exception:
        return {}


def series_path(pack_id: str) -> Path | None:
    """The pack's canonical frame, written under its bare id by `asia_parser._canonicalise`."""
    for suffix in (".parquet", ".csv"):
        p = SERIES / f"{pack_id}{suffix}"
        if p.exists():
            return p
    return None


def signals_of(path: Path) -> tuple[list[str], int, str]:
    """(numeric signal columns, row count, why there are none).

    The stamp columns are stripped first; a column that is constant, or carries fewer than
    MIN_DISTINCT distinct values, is a key or a flag and not a conditioner.
    """
    try:
        import pandas as pd
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    except Exception as exc:
        return [], 0, f"series unreadable: {type(exc).__name__}: {str(exc)[:60]}"
    if df.empty:
        return [], 0, "the series frame is empty"
    import pandas as pd
    cols: list[str] = []
    for name in df.columns:
        if str(name) in STAMP_COLUMNS:
            continue
        col = pd.to_numeric(df[name], errors="coerce")
        if col.notna().mean() < 0.6:
            continue
        if int(col.nunique(dropna=True)) < MIN_DISTINCT:
            continue
        cols.append(str(name))
    if not cols:
        return [], len(df), ("the series carries no numeric column with "
                            f"{MIN_DISTINCT}+ distinct values: every column is a label, a key "
                            "or a constant")
    return cols, len(df), ""


def targets_of(pack: dict[str, Any]) -> list[str]:
    """The MT5 instruments this pack claims to condition, as the registry declares them."""
    raw = pack.get("targets") or []
    return [str(t) for t in raw if str(t).strip()][:8]


def _registry_counts() -> tuple[dict[str, dict[str, int]], str]:
    """Per source id: cells the registry holds, and cells the ONE gauntlet has judged.

    Emitted is counted in `research_candidates`, judged in `trials_ledger` -- the gauntlet's own
    append-only record that it tested a candidate. Neither number is this organ's bookkeeping.
    """
    try:
        from libs.moat.registry import connect
        conn = connect()
    except Exception as exc:
        return {}, f"registry unavailable: {type(exc).__name__}: {exc}"
    out: dict[str, dict[str, int]] = {}
    try:
        for sid, n in conn.execute("SELECT source_id, COUNT(*) FROM research_candidates "
                                   "WHERE source_id IS NOT NULL AND source_id != '' "
                                   "GROUP BY source_id"):
            out.setdefault(str(sid), {"emitted": 0, "judged": 0})["emitted"] = int(n)
        for sid, n in conn.execute(
                "SELECT c.source_id, COUNT(DISTINCT t.candidate_id) FROM research_candidates c "
                "JOIN trials_ledger t ON t.candidate_id = c.id "
                "WHERE c.source_id IS NOT NULL AND c.source_id != '' GROUP BY c.source_id"):
            out.setdefault(str(sid), {"emitted": 0, "judged": 0})["judged"] = int(n)
    except Exception as exc:
        return out, f"registry query failed: {type(exc).__name__}: {exc}"
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    return out, ""


def emit_for(pack: dict[str, Any], signals: list[str], targets: list[str], *,
             dry_run: bool = False, offset: int = 0) -> dict[str, Any]:
    """Every (signal x transform x target x chart) cell for one pack, through the one door."""
    pid = str(pack.get("id"))
    take = signals[offset % max(len(signals), 1):][:SIGNALS_PER_PACK_PER_PASS]
    if not take:
        take = signals[:SIGNALS_PER_PACK_PER_PASS]
    mech = (f"the {pid} release conditions {', '.join(targets)}: a move in its published series "
            "carries information about the instrument's next move that price alone does not")
    did = ""
    if not dry_run:
        try:
            from libs.moat.registry import record_discovery
            did, _created = record_discovery(
                source_id=pid, source_type="data_pack", mechanism=mech,
                origin="pack_cells", generator="pack_cells", assets=list(targets),
                exact_rule_if_known="", horizons=list(CHARTS),
                note="represented pack; cells minted per signal, transform, target and chart")
        except Exception as exc:
            return {"id": pid, "emitted": 0, "created": 0,
                    "error": f"record_discovery: {type(exc).__name__}: {str(exc)[:70]}"}
    made = created = 0
    errors: list[str] = []
    for sig in take:
        for tf in TRANSFORMS:
            for sym in targets:
                for chart in CHARTS:
                    made += 1
                    if dry_run:
                        continue
                    try:
                        from libs.moat.registry import enqueue_candidate
                        _cid, was_new = enqueue_candidate(
                            family="exogenous_conditioner", symbol=sym,
                            params={"source": pid, "signal": sig, "transform": tf},
                            origin="pack_cells", mechanism=mech, chart=chart,
                            horizon=chart, source_id=pid, discovery_id=did or None,
                            generator="pack_cells", department="information",
                            asset_class="", transformation="pack_signal",
                            required_data=[f"desks/mt5/data/lake/series/{pid}.parquet"],
                            pit_status="STAMPED",
                            causal_rationale=mech,
                            falsifier=(f"the {tf} of {pid}.{sig} has no measurable relation to "
                                       f"{sym} at {chart} out of sample"))
                        created += int(bool(was_new))
                    except Exception as exc:
                        errors.append(f"{sig}/{tf}/{sym}/{chart}: "
                                      f"{type(exc).__name__}: {str(exc)[:50]}")
    return {"id": pid, "discovery_id": did, "signals_used": take, "emitted": made,
            "created": created, "errors": errors[:5]}


def build(budget_s: float = 240.0, *, dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    rows_in = packs()
    st = chain()
    cursor = _read(CURSOR, {}) or {}
    offsets: dict[str, int] = dict(cursor.get("offsets") or {})
    start = int(cursor.get("next_pack") or 0)

    rows: list[dict[str, Any]] = []
    eligible: list[tuple[dict[str, Any], list[str], list[str], int]] = []
    for p in rows_in:
        pid = str(p.get("id"))
        stage = str((st.get(pid) or {}).get("stage_reached") or "unmeasured")
        targets = targets_of(p)
        row: dict[str, Any] = {"id": pid, "stage": stage, "targets": targets,
                               "cadence": p.get("cadence")}
        if not st:
            row["reason"] = ("UNMEASURED: source_drain has not published a chain state on this "
                             "host, so no pack's stage is known")
            rows.append(row)
            continue
        if stage not in ("represented", "cells_emitted", "cells_judged"):
            row["reason"] = str((st.get(pid) or {}).get("why")
                                or f"the chain stops at {stage}: no stamped series to read")
            rows.append(row)
            continue
        path = series_path(pid)
        if path is None:
            row["reason"] = ("the chain calls it represented and no canonical frame "
                             f"{pid}.parquet|.csv is on disk; asia_parser writes that alias")
            rows.append(row)
            continue
        sigs, n_rows, why = signals_of(path)
        row.update({"series": path.name, "n_rows": n_rows, "n_signals": len(sigs)})
        if not sigs:
            row["reason"] = why
            rows.append(row)
            continue
        if not targets:
            row["reason"] = ("the registry declares no MT5 target for this pack, so there is no "
                             "instrument to condition; add `targets` to its registry row")
            rows.append(row)
            continue
        eligible.append((p, sigs, targets, offsets.get(pid, 0)))
        rows.append(row)

    by_id = {r["id"]: r for r in rows}
    order = eligible[start % max(len(eligible), 1):] + eligible[:start % max(len(eligible), 1)] \
        if eligible else []
    emitted_this_pass = created_this_pass = 0
    reached: list[str] = []
    for p, sigs, targets, off in order:
        if time.monotonic() - t0 > budget_s:
            break
        res = emit_for(p, sigs, targets, dry_run=dry_run, offset=off)
        pid = res["id"]
        reached.append(pid)
        emitted_this_pass += int(res.get("emitted") or 0)
        created_this_pass += int(res.get("created") or 0)
        offsets[pid] = off + SIGNALS_PER_PACK_PER_PASS
        by_id[pid].update({k: res[k] for k in ("discovery_id", "signals_used", "emitted",
                                               "created", "errors") if k in res})
        if res.get("error"):
            by_id[pid]["reason"] = res["error"]

    if not dry_run:
        _write(CURSOR, {"at": now, "offsets": offsets,
                        "next_pack": (start + len(reached)) % max(len(eligible), 1),
                        "rule": ("a round robin over eligible packs and a per-pack signal "
                                 "offset, so every pack and every column is reached; a pack not "
                                 "reached this pass leads the next one")})

    counts, counts_why = _registry_counts()
    for r in rows:
        c = counts.get(r["id"]) or {}
        r["cells_emitted"] = int(c.get("emitted") or 0)
        r["cells_judged"] = int(c.get("judged") or 0)
        if r["cells_emitted"] > 0 and r["cells_judged"] == 0 and not r.get("reason"):
            r["reason"] = ("cells are in the registry and the one gauntlet has not reached them "
                           "yet; trials_ledger holds no trial for this pack's candidates")

    n_emit = sum(1 for r in rows if r["cells_emitted"] > 0)
    n_judged = sum(1 for r in rows if r["cells_judged"] > 0)
    zero = [{"id": r["id"], "stage": r["stage"], "reason": r.get("reason") or "unexplained"}
            for r in rows if r["cells_emitted"] <= 0]
    return {
        "at": now,
        "status": "OK" if rows else "UNMEASURED",
        "n_packs": len(rows),
        "n_eligible": len(eligible),
        "n_reached_this_pass": len(reached),
        "packs_with_cells": n_emit,
        "packs_with_a_judged_cell": n_judged,
        "cells_emitted_total": sum(int(r["cells_emitted"]) for r in rows),
        "cells_judged_total": sum(int(r["cells_judged"]) for r in rows),
        "cells_emitted_this_pass": emitted_this_pass,
        "cells_created_this_pass": created_this_pass,
        "counts_basis": (counts_why or "research_candidates.source_id for emitted; "
                         "trials_ledger.candidate_id for judged (the one gauntlet's own record)"),
        "packs_at_zero": zero,
        "rows": rows,
        "dry_run": bool(dry_run),
        "consumers": [
            "libs/moat/registry.py research_candidates -> the one gauntlet claims and judges "
            "these cells like any other; no second store and no second judge",
            "desks/mt5/reports/PACK_CELLS.json -> CELLS EMITTED and CELLS JUDGED per pack, and "
            "the named reason for every pack still at zero",
            "desks/mt5/research/source_drain.py -> reads the same registry credit, so its "
            "cells_emitted stage advances as this organ mints",
        ],
        "boundary": ("MINTS ONLY. Nothing here judges, sizes, vetoes or refuses a pack; the "
                     "per-pass budget is a wall clock and a pack not reached leads the next "
                     "pass."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="count the cells this pass would mint and write nothing")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"pack cells: could not write {OUT}: {exc}")
        return 1
    print(f"pack cells: {doc['n_packs']} pack(s), {doc['n_eligible']} eligible, "
          f"{doc['n_reached_this_pass']} reached this pass")
    print(f"  cells emitted this pass {doc['cells_emitted_this_pass']} "
          f"({doc['cells_created_this_pass']} new); registry total "
          f"{doc['cells_emitted_total']}, judged {doc['cells_judged_total']}")
    print(f"  packs with cells {doc['packs_with_cells']}/{doc['n_packs']}, "
          f"with a judged cell {doc['packs_with_a_judged_cell']}")
    for r in doc["packs_at_zero"][:8]:
        print(f"   ZERO {str(r['id'])[:28]:<28} stage={r['stage']:<14} {r['reason'][:58]}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
