"""THE ROLLOVER RE-JUDGE TRIGGER: when the engine's swap instant moves, its verdicts are stale.

Desktop pass 2, row 6 (`rollover_stamp_midnight.patch`) moves the backtest's financing charge from
stamp 21:00 (`mt5desk/engine.py ROLLOVER_HOUR_UTC = 21`, a UTC hour applied to broker stamps) to
stamp midnight, the venue's true 17:00 New York rollover. A trade from 20:00 to 23:00 stamp was
charged a night it never paid; one from 22:00 to 20:00 next day, which did pay, was charged
nothing. So every verdict whose trades crossed stamp 21:00-24:00, or held for days, was priced by
the old instant and must be judged again under the new one.

WHAT THIS DOES, every run of the stage-1 leg (`research/stage1_judge.py` calls it first):

  1. FINGERPRINTS the engine's rollover: the constant's VALUE (`ROLLOVER_HOUR_UTC`,
     `TRIPLE_SWAP_WEEKDAY`) and a hash of `rollovers_between`'s source, recorded in the stage-1
     record's `meta`. First sight with the pre-pass-2 value (21) is the baseline and triggers
     nothing; first sight with any OTHER value means pass 2 landed before this ran, and it
     triggers against the known old value.
  2. On a change, QUEUES FOR PRIORITY RE-JUDGE:
       * every certified sleeve (every cell in `UNIVERSAL_SURVIVORS.canon.json`), unconditionally;
       * every sealed-judged docket cell whose MEASURED holding period spans the evening or the
         night: some trade's entry-to-exit crosses stamp 21:00-24:00, or lasts 24 h or more. The
         span is measured by replaying the cell once through the sealed builder and the engine,
         bounded per run and resumed the next hour; an unmeasured cell is PENDING, never "no".
  3. WRITES `data/hypotheses/priority_rollover_rejudge.json` ({"attestation", "cells", ...}).
     `research/stage1_record.PRIORITY_FILES` reads it, so these cells take tier 0 (named
     priority): after the v4 re-mint front (which the sealed sort puts first), level with the
     evicted re-judges, ahead of every stage-1 tier.

ORDER ONLY. Nothing is removed from any store; a queued cell is judged again, not un-judged.
"""
from __future__ import annotations

import contextlib
import hashlib
import inspect
import json
import os
import tempfile
import time
from collections.abc import Iterable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
HYP = DESK / "data" / "hypotheses"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
QUEUE = HYP / "priority_rollover_rejudge.json"
UNMEASURED = "UNMEASURED"
#: The engine's rollover hour before desktop pass 2 row 6. First sight of any other value is a
#: change that landed before this organ ever ran.
PRE_PASS2_ROLLOVER_HOUR = 21
#: The evening band on the stamp clock: the old charge instant up to the new one (midnight).
BAND_START_H = 21
BAND_END_H = 24
MULTI_DAY_H = 24.0
#: Share of the stage-1 leg's budget the span measurement may take while a change is pending.
BUDGET_SHARE = 0.25
META_FP = "engine_rollover_fp"
META_CHANGE = "engine_rollover_change"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rollover_span(
  cid TEXT PRIMARY KEY, span INTEGER, n_trades INTEGER, n_spanning INTEGER,
  measured_at TEXT, why TEXT
);
"""


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime | None = None) -> str:
    return (t or _now()).isoformat(timespec="seconds")


def fingerprint() -> dict[str, Any]:
    """The engine's rollover as it is in this tree: the values and a hash of the counter."""
    from mt5desk import engine as E
    try:
        src = inspect.getsource(E.rollovers_between)
    except (OSError, TypeError):
        src = ""
    h = hashlib.sha256(src.encode("utf-8")).hexdigest()[:12]
    hour = int(E.ROLLOVER_HOUR_UTC)
    tri = int(getattr(E, "TRIPLE_SWAP_WEEKDAY", -1))
    return {"rollover_hour": hour, "triple_swap_weekday": tri, "counter_sha": h,
            "fp": f"{hour}/{tri}/{h}"}


def detect_change(con, fp: dict[str, Any], *, now: datetime | None = None,
                  write: bool = True) -> dict[str, Any]:
    """The active change, or {"active": False}. Records the baseline on first sight."""
    from research import stage1_record as REC
    prev = REC.get_meta(con, META_FP)
    change = None
    raw = REC.get_meta(con, META_CHANGE)
    if raw:
        with contextlib.suppress(ValueError):
            change = json.loads(raw)
    if prev is None:
        if fp["rollover_hour"] != PRE_PASS2_ROLLOVER_HOUR:
            change = {"from": f"{PRE_PASS2_ROLLOVER_HOUR}/?/? (pre-pass-2 value, assumed: first "
                              "sight of the engine already changed)",
                      "to": fp["fp"], "at": _iso(now)}
    elif prev != fp["fp"]:
        change = {"from": prev, "to": fp["fp"], "at": _iso(now)}
    if write:
        REC.set_meta(con, META_FP, fp["fp"])
        if change is not None:
            REC.set_meta(con, META_CHANGE, json.dumps(change))
        con.commit()
    return {"active": change is not None, **(change or {})}


def spans_evening(entries: Iterable[Any], exits: Iterable[Any]) -> tuple[int, int]:
    """(trades, trades spanning): a trade spans when it lasts >= 24 h, or its (entry, exit]
    interval meets the stamp band [21:00, 24:00) of its entry day or the next day. Stamps are
    read as the venue's clock (tz labels dropped), which is the clock the engine charges on."""
    e = pd.DatetimeIndex(pd.to_datetime(list(entries)))
    x = pd.DatetimeIndex(pd.to_datetime(list(exits)))
    if len(e) == 0:
        return 0, 0
    if e.tz is not None:
        e = e.tz_localize(None)
    if x.tz is not None:
        x = x.tz_localize(None)
    ev, xv = e.values, x.values
    hours = (xv - ev) / np.timedelta64(1, "h")
    multi = hours >= MULTI_DAY_H
    d0 = e.normalize().values
    hit = np.zeros(len(e), dtype=bool)
    for k in (0, 1):
        lo = d0 + np.timedelta64(24 * k + BAND_START_H, "h")
        hi = d0 + np.timedelta64(24 * k + BAND_END_H, "h")
        hit |= (xv > lo) & (ev < hi)
    span = (multi | hit) & (xv > ev)
    return len(e), int(span.sum())


# --------------------------------------------------------------------------------------------
# the measurement: one replay per cell, in worker processes
# --------------------------------------------------------------------------------------------
_W: dict[str, Any] = {}


def _init_worker() -> None:
    import external_gauntlet as G
    try:
        meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        meta = {}
    _W.update(G=G, meta=meta if isinstance(meta, dict) else {})
    with contextlib.suppress(Exception):
        import psutil
        p = psutil.Process()
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(
            psutil, "BELOW_NORMAL_PRIORITY_CLASS") else 10)


def measure_one(spec: dict[str, Any]) -> dict[str, Any]:
    """{cid, span 1/0/None, n_trades, n_spanning, why}: the cell's full-history trades."""
    G, meta = _W["G"], _W["meta"]
    out: dict[str, Any] = {"cid": spec["cid"], "span": None, "n_trades": None,
                           "n_spanning": None, "why": ""}
    try:
        obj = G.build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if not obj:
            out["why"] = f"UNBUILDABLE: {str(G.LAST_BUILD_FAILURE or '')[:160]}"
            return out
        sigs = list(obj.get("sigs") or [])
        if not sigs:
            out.update(span=0, n_trades=0, n_spanning=0, why="no signals: holds nothing")
            return out
        res = G.run_backtest(obj["df"], sigs, obj["costs"])
        trades = list(res.trades)
        n, k = spans_evening([t.entry_time for t in trades], [t.exit_time for t in trades])
        out.update(span=int(k > 0), n_trades=n, n_spanning=k, why="measured")
    except Exception as exc:
        out["why"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    finally:
        with contextlib.suppress(Exception):
            obj["sigs"] = obj["df"] = None  # type: ignore[index]
    return out


def measure_batch(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [measure_one(sp) for sp in specs]


def _pool(specs: list[dict[str, Any]], workers: int, budget_s: float) -> list[dict[str, Any]]:
    """Measure within the wall budget; a batch still running at the deadline is killed."""
    started = time.monotonic()
    by: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sp in specs:
        by.setdefault((sp["sym"], sp.get("tf") or "H1"), []).append(sp)
    batches = [b[i:i + 16] for b in by.values() for i in range(0, len(b), 16)]
    out: list[dict[str, Any]] = []
    if not batches or budget_s <= 0:
        return out
    if workers <= 1:
        _init_worker()
        for b in batches:
            if time.monotonic() - started > budget_s:
                break
            out.extend(measure_batch(b))
        return out
    ex = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker)
    try:
        it = iter(batches)
        live: dict[Any, int] = {}
        for b in it:
            live[ex.submit(measure_batch, b)] = 1
            if len(live) >= 2 * workers:
                break
        while live:
            left = budget_s - (time.monotonic() - started)
            fin, _ = wait(list(live), timeout=max(1.0, left), return_when=FIRST_COMPLETED)
            if not fin:
                break
            for f in fin:
                with contextlib.suppress(Exception):
                    out.extend(f.result())
                if budget_s - (time.monotonic() - started) > 0:
                    nxt = next(it, None)
                    if nxt is not None:
                        live[ex.submit(measure_batch, nxt)] = 1
            live = {k: v for k, v in live.items() if k not in fin}
    finally:
        procs = list((getattr(ex, "_processes", None) or {}).values())
        ex.shutdown(wait=False, cancel_futures=True)
        for p in procs:
            with contextlib.suppress(Exception):
                p.terminate()
    return out


# --------------------------------------------------------------------------------------------
# population, queue, the run
# --------------------------------------------------------------------------------------------
def canon_cells(path: Path | None = None) -> list[str]:
    """Every certified sleeve's cell id (the canon's survivors)."""
    try:
        doc = json.loads(Path(path or CANON).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    sv = (doc or {}).get("survivors") if isinstance(doc, dict) else None
    rows = sv.values() if isinstance(sv, dict) else (sv or [])
    out = []
    for r in rows:
        if isinstance(r, dict) and r.get("cell"):
            out.append(str(r["cell"]))
    return sorted(set(out))


def _write_atomic(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def run(con, judged_specs: list[dict[str, Any]], *, workers: int, budget_s: float,
        queue_path: Path | None = None, canon_path: Path | None = None,
        now: datetime | None = None, dry_run: bool = False) -> dict[str, Any]:
    """One pass. `judged_specs` are sealed-judged docket cells ({cid, sym, family, params, tf}),
    collected by the stage-1 docket stream only while a change is active."""
    con.executescript(_SCHEMA)
    fp = fingerprint()
    change = detect_change(con, fp, now=now, write=not dry_run)
    doc: dict[str, Any] = {"fingerprint": fp, "change": change,
                           "queue_file": str(Path(queue_path or QUEUE).name)}
    if not change.get("active"):
        doc["status"] = "NO_CHANGE"
        return doc
    since = str(change.get("at") or "")
    measured = {r[0]: r[1] for r in con.execute(
        "SELECT cid, span FROM rollover_span WHERE measured_at >= ? AND span IS NOT NULL",
        (since,))}
    todo = [sp for sp in judged_specs if sp["cid"] not in measured]
    t0 = time.monotonic()
    got = _pool(todo, workers, budget_s)
    ts = _iso()
    if not dry_run:
        for r in got:
            con.execute("INSERT OR REPLACE INTO rollover_span(cid, span, n_trades, n_spanning, "
                        "measured_at, why) VALUES(?,?,?,?,?,?)",
                        (r["cid"], r["span"], r["n_trades"], r["n_spanning"], ts, r["why"]))
        con.commit()
    for r in got:
        if r["span"] is not None:
            measured[r["cid"]] = r["span"]
    canon = canon_cells(canon_path)
    spanning = sorted(c for c, s in measured.items() if s)
    cells = list(dict.fromkeys([*canon, *spanning]))
    population = {sp["cid"] for sp in judged_specs}
    pending = len([c for c in population if c not in measured])
    unmeasurable = sum(1 for r in got if r["span"] is None)
    qdoc = {"attestation": f"engine rollover {change.get('from')} -> {change.get('to')}",
            "reason": ("the backtest's swap instant moved (desktop pass 2 row 6); every "
                       "certified sleeve and every judged cell whose trades span stamp "
                       "21:00-24:00 or hold >= 24 h is re-judged under the new instant"),
            "at": ts, "cells": cells, "certified_sleeves": len(canon),
            "spanning_cells": len(spanning), "pending_measurement": pending}
    if not dry_run:
        _write_atomic(Path(queue_path or QUEUE), qdoc)
    doc.update(status="QUEUED", queued=len(cells), certified_sleeves=len(canon),
               spanning_cells=len(spanning),
               measured_not_spanning=sum(1 for s in measured.values() if not s),
               measured_this_run=len(got), unmeasurable_this_run=unmeasurable,
               pending_measurement=pending, population_judged_cells=len(population),
               measure_s=round(time.monotonic() - t0, 1),
               rule=("queued = canon cells (unconditional) + judged cells with a measured "
                     "span; a pending cell is measured on a later run, never read as 'no'"))
    return doc
