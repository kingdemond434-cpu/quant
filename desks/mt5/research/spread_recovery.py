#!/usr/bin/env python3
"""SPREAD RECOVERY: the half-life of the bid-ask spread after three scheduled shocks, and the two
cell uses it buys -- an entry gate for gap fades and a FADE family of its own (P8-M2, 2026-10-14).

    python desks/mt5/research/spread_recovery.py --once --budget-s 480
    python desks/mt5/research/spread_recovery.py --once --dry-run      # measure, donate nothing

WHY. STYLE_NOVELTY read 0 novel certificates of 43: every certificate the desk holds projects onto
a textbook style. The spread is the one series every bar carries and no family reads as a STATE.
At the week open, at broker rollover and (for some crosses) at the Tokyo open the book thins, the
spread widens several-fold for a bounded time, and the price prints made inside that window are
concessions, not information. How long the hole takes to close is measurable per symbol, and it
is a timing input no certificate on the desk conditions on.

WHAT A PASS DOES
  1. MEASURE, per hypothesis-lane symbol x event (`sunday_open`, `tokyo_open`, `rollover`), the
     median excess-spread profile and its exponential half-life (`mt5desk.family_spread_recovery`
     .measure) on the finest data this host holds: the tick tape (per-minute spread) when it has
     at least TICK_MIN_DAYS days, else M15 bars, else H1. Published: half-life, excess at t0, n,
     the profile and the bars to recover within 1.25x / 1.5x. A bar size that cannot resolve the
     decay says BELOW_RESOLUTION with its upper bound -- never a fitted number it does not have.
  2. SEED two cell sets on the symbol's H1 bars, fixed before any result (PREREGISTERED below):
       spread_recovery_fade   FADE_GRID: 3 events x 2 recovery multiples x 2 displacement floors
                              x 2 holds = 24 points per symbol
       overnight_gap_decay    with the declared cell modifier `spread_recovery_wait` in
                              GATE_VALUES: the gap fade entered on the spread's recovery instead
                              of a fixed bar
     Firing is counted from signals only (`cross_sectional_breadth.firing`); a cell whose
     trade-day lower bound clears SEED_FLOOR is donated ONCE through `proposer_common.donate`.
  3. CHARGE THE WHOLE PREREGISTERED PLAN ONCE, AT ITS FIRST DONATION, keyed by lineage
     (`PLAN_LINEAGE`, a hash of the grids). That first donation's `tests_run` is every point of
     the plan over every hypothesis-lane symbol -- points that did not fire enough, were never
     measured or were cut by the budget included -- so no point waits on a later donation that
     may never come. A symbol that joins the lane later is charged at the next donation. The
     donation is two-phase (`proposer_common.donate_once`): the intent is written to the state
     before the door is called and the door's file is named by its id, so a crash between the
     door and the state write is settled from the file on the next pass and never charges or
     donates twice. One pass at a time (`proposer_common.run_lock`).
  4. BILL THE GATE. The gate moves entries both ways, so each move is priced: for every gap-fade
     signal, the net log return entered at the gated bar minus entered at the fixed one-bar wait,
     to the same exit, each charged the full spread paid at its own entry bar (points x
     tick_size / price). A symbol with no tick_size cannot have its spread priced, so it is left
     out of the line and named, never counted at zero cost. Summed per gate value into
     `missed_growth` lines (n, advanced, delayed, mean, t, log-wealth per day at unit notional,
     verdict, `cost_priced`) that `research/missed_growth.spread_recovery_wait_lines` carries
     into MISSED_GROWTH.json. The gate never drops a signal, so there is no veto to price.
  5. Write `reports/SPREAD_RECOVERY.json`.

UNMEASURED IS AN ANSWER (L1.28a): no spread column, no bars, or no occurrence with a baseline is
UNMEASURED with its reason, never a half-life of zero.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mt5desk import family_spread_recovery as fsr  # noqa: E402

SOURCE = "spread_recovery"
UNIVERSE = BASE / "data" / "universe"
GIT_BARS = BASE / "universe"
TICKS = BASE / "data" / "tape" / "ticks"
OUT = BASE / "reports" / "SPREAD_RECOVERY.json"
STATE = BASE / "data" / "spread_recovery" / "cells_state.json"
UNMEASURED = "UNMEASURED"
ACCRUING = "SERIES_ACCRUING"
SEED_FLOOR = 66
TICK_MIN_DAYS = 5
TICK_MAX_DAYS = 30

#: PREREGISTERED 2026-10-14, before any fade or gate result was read. Every point is a trial.
FADE_GRID: dict[str, list[Any]] = {"event": list(fsr.EVENTS), "k_mult": [1.25, 1.5],
                                   "min_disp_atr": [0.25, 0.5], "hold_bars": [4, 12]}
GATE_VALUES: tuple[str, ...] = ("k:1.25", "k:1.5", "hl:1", "hl:2")
GATE_FAMILY = "overnight_gap_decay"
FADE_FAMILY = "spread_recovery_fade"
#: The declared cell modifier the gate cells carry (`mt5desk.cell_modifiers.SPREAD_WAIT_KEY`).
GATE_KEY = "spread_recovery_wait"
#: The preregistered plan's lineage: the charge for it is made once, keyed by this id.
PLAN_LINEAGE = "srplan-" + hashlib.sha256(json.dumps(
    {"fade": FADE_GRID, "gate": list(GATE_VALUES), "families": [FADE_FAMILY, GATE_FAMILY],
     "gate_key": GATE_KEY, "preregistered": "2026-10-14"}, sort_keys=True).encode()
).hexdigest()[:10]
COST_MODEL = ("each entry charged the full spread at its own entry bar: spread points x "
              "tick_size / entry open; the common exit's cost cancels in the difference")
#: The fixed wait the gate replaces: the desk's `entry_timing=delayed` convention, one bar.
FIXED_WAIT = 1
MIN_N = 10

MECHANISM = {
    FADE_FAMILY: ("thin-book concession at a scheduled liquidity hole (week open / Tokyo open / "
                  "broker rollover): the move printed while the spread is wide is unwound once "
                  "liquidity providers return and the spread normalises"),
    GATE_FAMILY: ("overnight gap fade entered on the spread's measured recovery rather than a "
                  "fixed bar: the same fade without paying the rollover spread"),
}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    tmp.replace(path)


def _grid(spec: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


def _bars(path: Path) -> pd.DataFrame | None:
    try:
        d = pd.read_parquet(path)
    except Exception:
        return None
    if d.empty or "close" not in d.columns:
        return None
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index, utc=True, errors="coerce"))
    return d[~d.index.isna()].sort_index()


def symbols(universe: Path = UNIVERSE) -> list[str]:
    """Hypothesis-lane symbols with H1 bars here (registry asset class decides the lane)."""
    from research.universe_policy import may_hypothesise
    out = []
    for p in sorted(universe.glob("*_H1.parquet")):
        sym = p.name[:-len("_H1.parquet")]
        if may_hypothesise(sym, FADE_FAMILY):
            out.append(sym)
    return out


def tick_minutes(sym: str, tick_size: float | None, root: Path = TICKS) -> pd.DataFrame | None:
    """Per-minute median spread in POINTS from the tick tape (server-clock `time_msc`)."""
    d = root / sym
    if not d.is_dir() or not tick_size or tick_size <= 0:
        return None
    files = sorted(d.glob("*.parquet"))[-TICK_MAX_DAYS:]
    if len(files) < TICK_MIN_DAYS:
        return None
    parts = []
    for f in files:
        try:
            t = pd.read_parquet(f, columns=["time_msc", "bid", "ask"])
        except Exception:
            continue
        t = t[(t["bid"] > 0) & (t["ask"] >= t["bid"])]
        if t.empty:
            continue
        ts = pd.to_datetime(t["time_msc"].astype("int64"), unit="ms", utc=True)
        s = pd.Series(((t["ask"] - t["bid"]) / tick_size).to_numpy(), index=ts)
        parts.append(s.resample("1min").median().dropna())
    if not parts:
        return None
    sp = pd.concat(parts).sort_index()
    sp = sp[~sp.index.duplicated(keep="last")]
    return pd.DataFrame({"spread": sp})


def finest(sym: str, meta: dict[str, Any], universe: Path = UNIVERSE,
           git_bars: Path = GIT_BARS, ticks: Path = TICKS
           ) -> tuple[str, pd.DataFrame | None]:
    """(resolution, frame) -- ticks, then M15, then H1 -- the finest this host holds."""
    tk = tick_minutes(sym, (meta.get(sym) or {}).get("tick_size"), ticks)
    if tk is not None and len(tk) > 0:
        return "M1_ticks", tk
    for root in (universe, git_bars):
        p = root / f"{sym}_M15.parquet"
        if p.exists():
            d = _bars(p)
            if d is not None and "spread" in d.columns:
                return "M15", d
    for root in (universe, git_bars):
        p = root / f"{sym}_H1.parquet"
        if p.exists():
            d = _bars(p)
            if d is not None:
                return "H1", d
    return "none", None


# ==================================================================== the gate's missed growth
def gate_deltas(d: pd.DataFrame, gate: str, tick_size: float | None) -> dict[str, Any]:
    """Per gap-fade signal: net log return gated minus fixed-wait, same exit, own entry spread."""
    from mt5desk.families_orthogonal import family_overnight_gap_decay
    if "spread" not in d.columns:
        return {"n": 0, "why": "no spread column", "cost_priced": False}
    if not tick_size or float(tick_size) <= 0:
        # Without the point size the spread paid cannot be priced; a delta at zero cost would
        # bill the gate for a move whose whole point is the cost it avoids.
        return {"n": 0, "why": "no tick_size: the spread cost cannot be priced",
                "cost_priced": False}
    sigs = family_overnight_gap_decay(d)
    if not sigs:
        # Nothing to price is not unpriceable: the symbol joins the line with no deltas.
        return {"n": 0, "why": "the gap fade fired nothing on these bars", "cost_priced": True}
    idx = pd.DatetimeIndex(d.index)
    pos = {t: i for i, t in enumerate(idx)}
    ps = [pos[s.time] for s in sigs if s.time in pos]
    waits = fsr.gate_waits(d, ps, fsr.parse_gate(gate) or ("k", 1.5))
    o = d["open"].to_numpy(float)
    c = d["close"].to_numpy(float)
    sp = pd.to_numeric(d["spread"], errors="coerce").to_numpy(float)
    ts = float(tick_size)
    sides = {pos[s.time]: int(s.side) for s in sigs if s.time in pos}
    deltas: list[float] = []
    moves = Counter()
    n = len(o)
    for p, w in zip(ps, waits, strict=True):
        # The signal at p fills at the next open: the fixed wait enters at p + 1 + FIXED_WAIT,
        # the gate at p + 1 + w, and both close on one common bar after the later entry.
        ef, eg = p + 1 + FIXED_WAIT, p + 1 + w
        x = max(ef, eg) + 4
        if x >= n or eg >= n or ef >= n:
            continue
        side = sides[p]
        if not all(np.isfinite(sp[e]) and o[e] > 0 for e in (eg, ef)):
            continue          # an entry whose spread is unknown cannot be priced: not counted
        net = [side * math.log(c[x] / o[e]) - sp[e] * ts / o[e] for e in (eg, ef)]
        dlt = net[0] - net[1]
        if not np.isfinite(dlt):
            continue
        deltas.append(dlt)
        moves["advanced" if w < FIXED_WAIT else "delayed" if w > FIXED_WAIT else "same"] += 1
    days = max(1.0, (idx[-1] - idx[0]).total_seconds() / 86400.0)
    return {"n": len(deltas), "deltas": deltas, "moves": dict(moves), "days": days,
            "cost_priced": True}


def gate_lines(per_symbol: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """One missed-growth line per gate value, pooled over symbols. Two-sided by construction."""
    lines = []
    for gate in GATE_VALUES:
        ds: list[float] = []
        moves: Counter = Counter()
        rate = 0.0
        unpriced: list[str] = []
        for sym, g in sorted(per_symbol.items()):
            r = g.get(gate) or {}
            if not r.get("cost_priced"):
                unpriced.append(sym)
                continue
            ds.extend(r.get("deltas") or [])
            moves.update(r.get("moves") or {})
            if r.get("n"):
                rate += float(r["n"]) / float(r["days"])
        arr = np.asarray(ds, dtype=float)
        line: dict[str, Any] = {"gate": f"{GATE_KEY}={gate}", "family": GATE_FAMILY,
                                "direction": "two_sided", "n": int(arr.size),
                                "cost_priced": True, "cost_model": COST_MODEL,
                                "symbols_unpriced": unpriced,
                                "n_advanced": moves.get("advanced", 0),
                                "n_delayed": moves.get("delayed", 0),
                                "n_same": moves.get("same", 0),
                                "units": "log-wealth per day at unit notional per trade"}
        if arr.size < MIN_N:
            line.update({"verdict": UNMEASURED, "value": None,
                         "why": f"under {MIN_N} priced signals"})
        elif not moves.get("advanced") and not moves.get("delayed"):
            line.update({"verdict": "NOT_BINDING", "value": 0.0})
        else:
            se = float(arr.std(ddof=1) / math.sqrt(arr.size)) if arr.size > 1 else 0.0
            t = float(arr.mean() / se) if se > 0 else 0.0
            line.update({
                "mean_delta_logret": round(float(arr.mean()), 8), "t": round(t, 2),
                "value": round(float(arr.mean()) * rate, 10),
                "verdict": ("EARNS_ITS_PLACE" if t > 2.0 else "COSTS_GROWTH" if t < -2.0
                            else UNMEASURED)})
        lines.append(line)
    return lines


# ========================================================================= seeding the cells
def plan(syms: list[str]) -> list[dict[str, Any]]:
    cells = []
    for sym in syms:
        for p in _grid(FADE_GRID):
            cells.append({"family": FADE_FAMILY, "symbol": sym, "params": dict(p)})
        for g in GATE_VALUES:
            cells.append({"family": GATE_FAMILY, "symbol": sym,
                          "params": {GATE_KEY: g}})
    return cells


def _signals(fam: str, d: pd.DataFrame, params: dict[str, Any]) -> list[Any]:
    if fam == FADE_FAMILY:
        return fsr.family_spread_recovery_fade(d, **params)
    from mt5desk import cell_modifiers as cm
    from mt5desk.families_orthogonal import family_overnight_gap_decay
    kw, mods = cm.split(family_overnight_gap_decay, params)
    if cm.refusal(mods):
        return []
    return cm.apply(family_overnight_gap_decay(d, **kw), d, mods)


def seed(syms: list[str], bars: dict[str, pd.DataFrame | None], *, budget_s: float,
         dry_run: bool, state_path: Path = STATE, started: float | None = None,
         plan_syms: list[str] | None = None) -> dict[str, Any]:
    """One seeding pass under the organ's run lock (a dry run reads only and takes none)."""
    if dry_run:
        return _seed(syms, bars, budget_s=budget_s, dry_run=True, state_path=state_path,
                     started=started, plan_syms=plan_syms)
    from research import proposer_common as pc
    with pc.run_lock(state_path) as held:
        if not held:
            return {"stopped_because": "LOCKED: another spread_recovery pass holds the state",
                    "cells_planned": len(plan(plan_syms or syms)), "by_family": {},
                    "donation": {"status": "LOCKED"}, "errors": {}}
        return _seed(syms, bars, budget_s=budget_s, dry_run=False, state_path=state_path,
                     started=started, plan_syms=plan_syms)


def _seed(syms: list[str], bars: dict[str, pd.DataFrame | None], *, budget_s: float,
          dry_run: bool, state_path: Path, started: float | None,
          plan_syms: list[str] | None) -> dict[str, Any]:
    from research import proposer_common as pc
    from research.cross_sectional_breadth import firing, identity
    started = started if started is not None else time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    st = _read(state_path)
    state: dict[str, Any] = st if isinstance(st, dict) and isinstance(st.get("cells"), dict) \
        else {"cells": {}}
    cs: dict[str, Any] = state["cells"]
    charged_map: dict[str, Any] = state.setdefault("plan_charged", {})
    # A pre-lineage state recorded the charge per cell: carried over, never charged again.
    for k, v in cs.items():
        if isinstance(v, dict) and v.get("charged_at") and k not in charged_map:
            charged_map[k] = v["charged_at"]

    def settle(intent: dict[str, Any], at: str) -> None:
        for k in intent.get("cells") or []:
            if isinstance(cs.get(k), dict):
                cs[k]["donated_at"] = at
        for k in intent.get("charged") or []:
            charged_map.setdefault(k, at)

    recovered = ({"landed": 0, "dropped": 0} if dry_run
                 else pc.reconcile_donations(state, SOURCE, settle))
    # THE WHOLE PREREGISTERED PLAN, over every hypothesis-lane symbol: what gets charged.
    full_plan = plan(sorted(set(plan_syms or syms) | set(syms)))
    plan_ids = [identity(c["symbol"], c["family"], c["params"]) for c in full_plan]
    cells = plan(syms)
    by_family: dict[str, Counter] = {}
    cands: list[dict[str, Any]] = []
    errors: Counter = Counter()
    stopped = "grid exhausted"
    for cell in cells:
        if time.monotonic() - started > budget_s:
            stopped = f"time budget {budget_s:g}s reached; resumes next pass"
            break
        fam, sym, params = cell["family"], cell["symbol"], cell["params"]
        cnt = by_family.setdefault(fam, Counter())
        cnt["grid"] += 1
        ident = identity(sym, fam, params)
        prior = cs.get(ident) or {}
        if prior.get("day") != today:
            d = bars.get(sym)
            if d is None or "spread" not in d.columns:
                prior = {**prior, "day": today, "status": UNMEASURED,
                         "why": f"no H1 bars with a spread column for {sym} on this host"}
            else:
                try:
                    got = firing(list(_signals(fam, d, params) or []), d)
                except Exception as exc:
                    errors[f"{fam}: {type(exc).__name__}: {str(exc)[:60]}"] += 1
                    continue
                prior = {**prior, **got, "day": today, "why": None}
            prior.update({"family": fam, "symbol": sym, "params": params})
            cs[ident] = prior
            cnt["measured_this_pass"] += 1
        if prior.get("why"):
            status = UNMEASURED
        elif int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR:
            status = "DONATED" if prior.get("donated_at") else "CLEARS_FLOOR"
            if not prior.get("donated_at"):
                cands.append({"ident": ident, **cell})
        else:
            status = ACCRUING
        prior["status"] = status
        cnt[status.lower()] += 1
    # THE CHARGE: every point of the plan not yet charged, all of it on this donation.
    uncharged = [k for k in dict.fromkeys(plan_ids) if k not in charged_map]
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW",
                                "recovered": recovered}
    if cands and not dry_run:
        rows = []
        for c in cands:
            p = cs[c["ident"]]
            row = pc.candidate(SOURCE, c["symbol"], c["family"], dict(c["params"]),
                               f"{c['family']} on {c['symbol']}: {MECHANISM[c['family']]}",
                               f"{c['symbol']} {c['family']} {json.dumps(c['params'])}"[:120],
                               {"firing": {k: p.get(k) for k in ("signal_days",
                                                                 "trade_days_lb")},
                                "seed_floor": SEED_FLOOR, "plan_lineage": PLAN_LINEAGE,
                                "preregistered_grid": (FADE_GRID if c["family"] == FADE_FAMILY
                                                       else list(GATE_VALUES))})
            row["evidence"]["screen"] = ("input-only firing count (signals, never returns): no "
                                         "outcome screen; the whole preregistered plan charged "
                                         "once, at its first donation")
            row["declared_width"] = 1
            rows.append(row)
        path = pc.donate_once(
            state, lambda: _write_atomic(state_path, json.dumps(state, sort_keys=True,
                                                                default=str)),
            SOURCE, rows, len(uncharged), lineage=PLAN_LINEAGE,
            cells=[c["ident"] for c in cands], charged=uncharged, apply=settle)
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None,
                    "donated": counts.get("donated"),
                    "trials_charged": len(uncharged) if path else 0,
                    "lineage": PLAN_LINEAGE, "recovered": recovered,
                    "refused_wrong_lane": counts.get("refused_wrong_lane")}
    if not dry_run:
        _write_atomic(state_path, json.dumps(state, sort_keys=True, default=str))
    charged = sum(1 for k in dict.fromkeys(plan_ids) if k in charged_map)
    return {"stopped_because": stopped, "cells_planned": len(full_plan),
            "cells_seeded_this_host": len(cells), "plan_lineage": PLAN_LINEAGE,
            "seed_floor_trade_days": SEED_FLOOR,
            "by_family": {k: dict(v) for k, v in by_family.items()},
            "trials_charged_total": charged,
            "trials_pending_charge": len(set(plan_ids)) - charged,
            "donation": donation, "errors": dict(errors)}


def run(*, budget_s: float = 480.0, dry_run: bool = False, out: Path = OUT,
        universe: Path = UNIVERSE, git_bars: Path = GIT_BARS, ticks: Path = TICKS,
        state_path: Path = STATE) -> dict[str, Any]:
    started = time.monotonic()
    meta = _read(universe / "universe.json") or {}
    syms = symbols(universe)
    half_lives: list[dict[str, Any]] = []
    bars: dict[str, pd.DataFrame | None] = {}
    gates: dict[str, dict[str, dict[str, Any]]] = {}
    states: Counter = Counter()
    measure_budget = 0.5 * budget_s
    stopped = "all symbols measured"
    for sym in syms:
        if time.monotonic() - started > measure_budget:
            stopped = f"measurement budget {measure_budget:g}s reached"
            break
        res, frame = finest(sym, meta, universe, git_bars, ticks)
        h1 = _bars(universe / f"{sym}_H1.parquet")
        bars[sym] = h1
        for ev in fsr.EVENTS:
            m = (fsr.measure(frame, ev) if frame is not None
                 else {"state": UNMEASURED, "why": "no bars on this host", "n": 0})
            if res == "H1":
                m.pop("profile", None)
            states[str(m.get("state"))] += 1
            half_lives.append({"symbol": sym, "event": ev, "resolution": res, **m})
        if h1 is not None:
            ts = (meta.get(sym) or {}).get("tick_size")
            gates[sym] = {g: gate_deltas(h1, g, ts) for g in GATE_VALUES}
    lines = gate_lines(gates)
    seeded = seed([s for s in syms if s in bars], bars, budget_s=budget_s, dry_run=dry_run,
                  state_path=state_path, started=started, plan_syms=syms)
    rep = {"generated_at": _now(), "source": SOURCE, "dry_run": dry_run,
           "rule": ("half-life = ln2 / lambda of an exponential fit to the median excess-spread "
                    "profile; a bar size that cannot resolve it is BELOW_RESOLUTION with its "
                    "upper bound; the whole preregistered plan is charged once, at its "
                    "first donation, keyed by its lineage"),
           "events": {"sunday_open": "first bar after a > 30 h gap",
                      "rollover": "server midnight on the bars' own clock, week open excluded",
                      "tokyo_open": "00:00 UTC via session_clock.utc_to_server"},
           "n_symbols": len(syms), "measured_symbols": len(bars), "stopped_because": stopped,
           "states": dict(states), "half_lives": half_lives,
           "missed_growth": lines, "cells": seeded}
    if not dry_run:
        _write_atomic(out, json.dumps(rep, indent=1, sort_keys=True, default=str) + "\n")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's call)")
    ap.add_argument("--budget-s", type=float, default=480.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and report, write nothing")
    args = ap.parse_args(argv)
    rep = run(budget_s=args.budget_s, dry_run=args.dry_run)
    c = rep["cells"]
    print(f"spread_recovery: {rep['measured_symbols']}/{rep['n_symbols']} symbols "
          f"{rep['states']} cells planned={c['cells_planned']} "
          f"donation={c['donation'].get('status')} stopped={c['stopped_because']!r}")
    for ln in rep["missed_growth"]:
        print(f"  {ln['gate']}: n={ln['n']} adv={ln['n_advanced']} del={ln['n_delayed']} "
              f"t={ln.get('t')} {ln['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
