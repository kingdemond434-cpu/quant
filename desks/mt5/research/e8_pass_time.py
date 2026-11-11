#!/usr/bin/env python3
"""E8 PASS-TIME OPTIMISER: which risk per trade passes the E8 Pro challenge fastest without
raising the breach probability above today's (Hourly pass idea 591). REPORT ONLY.

It sizes nothing, arms nothing and writes no CERT_BOOK block. Nobody reads its artifact
(`consumer: null`); the principal reads it and the CERT_BOOK `e8` block stays the authority.

THE ARENA comes from `prop/e8_guard.py`, never re-typed here: START_BALANCE, PROFIT_TARGET,
STATIC_DRAWDOWN, DAILY_DRAWDOWN, DAILY_PROFIT_CAP, STAND_DOWN. The rules as simulated:

  * a day is one server day (00:00 server = 17:00 America/New_York, e8_guard's anchor); one
    world row is one server day, with gold_asia's two bracket legs ALREADY SUMMED into it: the
    losses-first ordering and STAND_DOWN act across sleeves, never inside the bracket (both legs
    rest at once, so a both-legs day cannot be truncated -- which matches the venue).
  * the walk STARTS at live E8 equity (E8_GOLD.json) when it reads, else at START_BALANCE (noted);
    the floor and target stay anchored to START_BALANCE.
  * DAILY LOSS counts floating P&L from day-start equity and is judged at the INTRADAY WORST
    point: within a day every losing leg is taken before any winning leg (losses ordered first).
  * STAND_DOWN is the desk's voluntary stop inside the 2.5%: once the day's running P&L reaches
    -STAND_DOWN, the legs that have not yet run that day are not taken.
  * profit above DAILY_PROFIT_CAP in a day is stripped at rollover -- it slows the pass, it is
    not a breach.
  * static floor at START_BALANCE * (1 - STATIC_DRAWDOWN), target at START_BALANCE *
    (1 + PROFIT_TARGET). Pro has no consistency rule, minimum days or time limit; the model
    stops at the target (the funded phase is out of scope).

GOLD_ASIA is a two-leg bracket: both legs can stop out on one day and a gap can stretch a stop
to GAP_R, so the worst day is 2 * GAP_R * risk (1.8% at the live 0.006). World rows below that
are clipped to it -- a bracket cannot lose more than its two stops gapped.

INPUTS (any missing -> UNMEASURED, never a number):
    worlds    data/pf_allocator_cache/worlds.npz        (kelly_survival.WORLDS)
    live      data/live_ledger.jsonl                    (posterior shift, kelly_survival)
    current   data/CERT_BOOK_LIVE.json  `e8`            (the live risk per sleeve)
    equity    reports/E8_GOLD.json                      (kelly_survival.e8_equity)
    -> reports/E8_PASS_TIME.json

    python desks/mt5/research/e8_pass_time.py
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(BASE / "prop"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop.e8_guard import (  # noqa: E402
    DAILY_DRAWDOWN,
    DAILY_PROFIT_CAP,
    PROFIT_TARGET,
    SERVER_ANCHOR_TZ,
    SERVER_MIDNIGHT_ET_HOUR,
    STAND_DOWN,
    START_BALANCE,
    STATIC_DRAWDOWN,
)

OUT = BASE / "reports" / "E8_PASS_TIME.json"
CERT_BOOK = BASE / "data" / "CERT_BOOK_LIVE.json"
#: A bracket's stop can gap to this many R; two legs can both stop on the same day.
GAP_R = 1.5
BRACKET_LEGS = 2
#: Risk-per-trade grid (fraction of equity), the live 0.006 included.
RISK_GRID = (0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.0075, 0.009, 0.01, 0.0125, 0.015)
N_PATHS = 2000
DAYS = 512
#: The edges-halved world takes this share off every positive mean (kelly_survival's haircut).
HALVE = 0.5


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def eligible_sleeves(book: dict[str, Any] | None, names: list[str]) -> dict[str, float]:
    """{sleeve: current live risk} for every positive CERT_BOOK `e8` row with a world column."""
    e8 = (book or {}).get("e8") or {}
    out: dict[str, float] = {}
    for k, v in e8.items():
        r = _num(v)
        if r and r > 0 and k in names:
            out[str(k)] = r
    return out


def simulate(paths_r: np.ndarray, risks: np.ndarray, *, start: float = START_BALANCE
             ) -> dict[str, Any]:
    """P(pass), P(breach) split daily/static, median and p90 server days to pass.

    paths_r: (n, days, sleeves) per-day R per sleeve; risks: (sleeves,) fraction of balance.
    Each day: legs ordered losses first; running P&L stops taking legs at -STAND_DOWN; the
    intraday low is checked against -DAILY_DRAWDOWN of day-start equity; the close is capped at
    +DAILY_PROFIT_CAP; then the static floor and the target are checked on the balance.
    """
    n, t_n, _ = paths_r.shape
    floor_r = -BRACKET_LEGS * GAP_R
    leg = np.maximum(paths_r, floor_r) * risks[None, None, :]       # fraction of day-start bal
    leg = np.sort(leg, axis=2)                                       # losses first
    cum = np.cumsum(leg, axis=2)
    # legs AFTER the one that took the day to the stand-down are not taken
    hit = cum <= -STAND_DOWN
    before = np.concatenate([np.zeros((n, t_n, 1), bool), np.cumsum(hit, axis=2)[..., :-1] > 0],
                            axis=2)
    taken = np.where(before, 0.0, leg)
    run = np.cumsum(taken, axis=2)
    low = np.minimum(run.min(axis=2), 0.0)
    close = np.minimum(run[..., -1], DAILY_PROFIT_CAP)

    target = start * (1.0 + PROFIT_TARGET)
    floor = start * (1.0 - STATIC_DRAWDOWN)
    bal = np.full(n, start)
    state = np.zeros(n, dtype=int)            # 0 live, 1 pass, 2 daily, 3 static
    days = np.full(n, t_n)
    for t in range(t_n):
        live = state == 0
        if not live.any():
            break
        f_d = live & (low[:, t] <= -DAILY_DRAWDOWN)
        f_s = live & ~f_d & (bal * (1.0 + low[:, t]) <= floor)
        bal = np.where(live & ~f_d & ~f_s, bal * (1.0 + close[:, t]), bal)
        win = live & ~f_d & ~f_s & (bal >= target)
        state[f_d], state[f_s], state[win] = 2, 3, 1
        days[f_d | f_s | win] = t + 1
    passed = state == 1
    d = days[passed]
    return {"p_pass": float(passed.mean()),
            "p_breach": float((state >= 2).mean()),
            "p_daily": float((state == 2).mean()),
            "p_static": float((state == 3).mean()),
            "p_unresolved": float((state == 0).mean()),
            "median_days": float(np.median(d)) if d.size else None,
            "p90_days": float(np.quantile(d, 0.9)) if d.size else None}


def optimise(paths_r: np.ndarray, current: np.ndarray, grid: tuple[float, ...] = RISK_GRID,
             start: float = START_BALANCE) -> dict[str, Any]:
    """Scale the live risk vector so its largest element is each grid value; pick the fastest
    median with P(breach) <= current's, and the max-P(pass) point."""
    base = simulate(paths_r, current, start=start)
    top = float(current.max())
    rows: list[dict[str, Any]] = []
    for g in grid:
        h = current * (g / top)
        rows.append({"risk": g, **simulate(paths_r, h, start=start)})
    ok = [r for r in rows if r["median_days"] is not None and r["p_breach"] <= base["p_breach"]]
    fastest = min(ok, key=lambda r: (r["median_days"], r["p_breach"])) if ok else None
    best_pass = max(rows, key=lambda r: (r["p_pass"], -(r["median_days"] or 1e9)))
    return {"current": {"risk": top, **base}, "grid": rows,
            "fastest_within_current_breach": fastest, "max_p_pass": best_pass}


def build(*, n_paths: int = N_PATHS, seed: int = 0, now: datetime | None = None) -> dict[str, Any]:
    import kelly_survival as ks
    from prop_challenge_allocator import draw_paths
    now = now or datetime.now(UTC)
    doc: dict[str, Any] = {
        "generated_at": now.isoformat(timespec="seconds"), "report_only": True, "consumer": None,
        "intended_consumer": "E8 risk-per-trade choice (future PR; report-only until then)",
        "authority": "REPORT ONLY: sizes nothing, arms nothing, writes no CERT_BOOK block",
        "rules": {"source": "desks/mt5/prop/e8_guard.py", "start_balance": START_BALANCE,
                  "profit_target": PROFIT_TARGET, "static_drawdown": STATIC_DRAWDOWN,
                  "daily_drawdown": DAILY_DRAWDOWN, "daily_profit_cap": DAILY_PROFIT_CAP,
                  "stand_down": STAND_DOWN, "day_anchor": f"{SERVER_ANCHOR_TZ} "
                  f"{SERVER_MIDNIGHT_ET_HOUR}:00", "bracket_legs": BRACKET_LEGS, "gap_r": GAP_R,
                  "intraday": "losses ordered first; floating loss judged at the worst point",
                  "scope": "challenge to +target only; funded phase out of scope"},
        "status": "OK"}
    book = _read_json(CERT_BOOK)
    if not isinstance(book, dict) or not isinstance(book.get("e8"), dict):
        doc["status"] = f"UNMEASURED: no readable e8 block in {CERT_BOOK.name}"
        return doc
    try:
        z = np.load(ks.WORLDS, allow_pickle=True)
        names = [str(x) for x in z["names"]]
        r_all = np.asarray(z["r"], dtype=float)
    except (OSError, ValueError, KeyError) as exc:
        doc["status"] = f"UNMEASURED: worlds unreadable ({type(exc).__name__})"
        return doc
    sleeves = eligible_sleeves(book, names)
    if not sleeves:
        doc["status"] = "UNMEASURED: no positive e8 risk with a world column"
        return doc
    cols = [names.index(s) for s in sleeves]
    r = r_all[:, :, cols].copy()
    # live posterior on gold_asia, the one sleeve the ledger attributes
    live_note: dict[str, Any] = {}
    try:
        with ks.LEDGER.open(encoding="utf-8") as fh:
            deals = [json.loads(t) for t in (ln.strip() for ln in fh) if t.startswith("{")]
        ev = ks.live_evidence(deals)
        for j, s in enumerate(sleeves):
            w = s[len("gold_"):] if s.startswith("gold_") else None
            lr = list((ev.get(w) or {}).get("r", [])) if w else []
            prior = float(r[:, :, j].mean())
            mean, wt = ks.posterior_shift(prior, lr)
            r[:, :, j] += mean - prior
            live_note[s] = {"prior_r": round(prior, 4), "posterior_r": round(mean, 4),
                            "live_n": len(lr), "live_weight": round(wt, 3)}
    except (OSError, ValueError, ImportError) as exc:
        live_note = {"status": f"UNMEASURED: live ledger unreadable ({type(exc).__name__}); "
                               "prior worlds only"}
    equity, eq_src = ks.e8_equity()
    doc["inputs"] = {"worlds": str(ks.WORLDS.name), "sleeves": sleeves, "posterior": live_note,
                     "e8_equity": equity, "e8_equity_source": eq_src}
    ok = isinstance(equity, (int, float)) and math.isfinite(equity) and equity > 0
    start = float(equity) if ok else float(START_BALANCE)
    doc["inputs"]["start_equity"] = start
    doc["inputs"]["start_source"] = "live_e8_equity" if ok else "START_BALANCE (live equity unread)"
    current = np.array(list(sleeves.values()))
    mu = r.mean(axis=(0, 1))
    worlds = {"as_estimated": r, "edges_halved": r - HALVE * np.maximum(mu, 0.0)}
    doc["worlds"] = {}
    for name, world in worlds.items():
        paths = draw_paths(world, n_paths, DAYS, seed)
        doc["worlds"][name] = optimise(paths, current, start=start)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--paths", type=int, default=N_PATHS)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    doc = build(n_paths=a.paths)
    if not a.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", encoding="utf-8")
        os.replace(tmp, OUT)
    for name, res in (doc.get("worlds") or {}).items():
        c, f, m = res["current"], res["fastest_within_current_breach"], res["max_p_pass"]
        print(f"  {name}: current {c['risk']} pass {c['p_pass']:.3f} median {c['median_days']}"
              f" unresolved {c['p_unresolved']:.3f}"
              f" | fastest {f and f['risk']} median {f and f['median_days']}"
              f" | max-pass {m['risk']} {m['p_pass']:.3f}")
    print(f"  e8_pass_time: {doc['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
