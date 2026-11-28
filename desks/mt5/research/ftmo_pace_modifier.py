#!/usr/bin/env python3
"""FTMO PACE MODIFIER -- the book-risk multiplier that maximises P(pass) from where the account is.

Idea 625, consumer half. `prop_pacing.py` (#1010) publishes how far the FTMO challenge is from its
target, how much room is left to the daily and maximum loss limits, and the allocator's plan
(median days and P(pass) from the phase start). This module reads that report and answers one
question: given the distance to target NOW and the room NOW, which multiplier m on the book's
risk maximises P(pass), with E[log W] as the tiebreak?

THE WALK (re-implemented small, after #946's e8_pass_time.py; nothing imported from that branch):
the book's day at m = 1 is Normal(mu, sigma) as a fraction of the initial balance, CALIBRATED to
the allocator's own plan -- mu = target / days_median, and sigma solved so that the walk
under the FTMO limits from the phase start passes with the plan's P(pass). P(pass) is read
by the plan's own deadline (its p90 days, less the weekdays spent), since without one a smaller m
always passes more often and speed would count for nothing. A day at m is
m times that draw. FTMO 2-Step rules from `prop_challenge_allocator.FTMO_2STEP` (10% target in
phase 1, 5% daily from the day's start, 10% static maximum, 4 minimum trading days): a day losing
more than the daily room fails, equity under the floor fails, and the target counts only once the
minimum days are traded. Day one uses the daily room the account has left today. The day's close
stands in for its intraday low, which is the walk's stated simplification.

TWO-SIDED (growth governance Rule 2): ahead and near the target m may fall below 1; behind it may
rise above 1. The only cap is SURVIVAL: the 1-in-100 worst day at m must stay inside today's
daily room. No other ceiling or floor beyond the grid's own [0.5, 2.0].

REPORT ONLY. It writes `reports/FTMO_PACE_MODIFIER.json` with report_only true and consumer null;
its intended consumer is the FTMO allocator. It never changes any live size. An absent pacing
report, a missing plan, or a funded phase is UNMEASURED with multiplier 1.0, never a guess.

    python desks/mt5/research/ftmo_pace_modifier.py --once
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
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PACING = BASE / "reports" / "FTMO_PACING.json"
OUT = BASE / "reports" / "FTMO_PACE_MODIFIER.json"
SCHEMA = "ftmo-pace-modifier/1"
UNMEASURED = "UNMEASURED"
INTENDED_CONSUMER = "research/prop_challenge_allocator.py (FTMO allocator)"

GRID: tuple[float, ...] = tuple(round(0.5 + 0.1 * i, 2) for i in range(16))   # 0.5 .. 2.0
N_PATHS = 4000
HORIZON_DAYS = 60
#: The calibration walk runs without a practical deadline: FTMO's trading period is unlimited.
CALIBRATION_DAYS = 250
#: P(pass) within this of the best is a tie, broken by E[log W].
TIE_EPS = 0.005
#: The survival cap's worst day: the 1-in-100 day at m.
WORST_Z = 2.326


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def calibrate(days_median: float, p_pass: float, target: float, rules: Any, *,
              n_paths: int = 2000, seed: int = 1) -> tuple[float, float] | None:
    """(mu, sigma) per day as a fraction of the initial balance, from the allocator's plan:
    mu = target / days_median, sigma bisected so the walk at m = 1 from the phase start (no
    deadline) passes with the plan's P(pass). P(pass) falls as sigma rises at fixed mu."""
    if not (days_median > 0 and 0.0 < p_pass < 1.0 and target > 0):
        return None
    mu = target / days_median

    def p_at(sig: float) -> float:
        return walk(1.0, mu=mu, sigma=sig, gain=0.0, target=target, floor_gap=rules.max_loss,
                    daily_limit=rules.daily_loss, room_today=rules.daily_loss,
                    min_days_left=rules.min_days, n_paths=n_paths, horizon=CALIBRATION_DAYS,
                    seed=seed)["p_pass"]

    lo, hi = 1e-4, 0.08
    if p_at(lo) < p_pass or p_at(hi) > p_pass:
        return None
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        if p_at(mid) > p_pass:
            lo = mid
        else:
            hi = mid
    return mu, 0.5 * (lo + hi)


def walk(m: float, *, mu: float, sigma: float, gain: float, target: float, floor_gap: float,
         daily_limit: float, room_today: float, min_days_left: int, n_paths: int = N_PATHS,
         horizon: int = HORIZON_DAYS, seed: int = 0) -> dict[str, float]:
    """FTMO walk in fractions of the initial balance. `gain` is equity - initial; `floor_gap`
    is equity - floor; `room_today` is the daily room left today."""
    rng = np.random.default_rng(seed)
    draws = m * (mu + sigma * rng.standard_normal((n_paths, horizon)))
    eq = np.full(n_paths, gain)
    floor = gain - floor_gap
    state = np.zeros(n_paths, dtype=int)      # 0 live, 1 pass, 2 daily fail, 3 max fail
    days = np.full(n_paths, horizon, dtype=float)
    for d in range(horizon):
        live = state == 0
        if not live.any():
            break
        x = draws[:, d]
        room = room_today if d == 0 else daily_limit
        daily = live & (x < -room)
        eq = np.where(live, eq + x, eq)
        maxf = live & ~daily & (eq < floor)
        hit = live & ~daily & ~maxf & (eq >= target) & (d + 1 >= min_days_left)
        state[daily], state[maxf], state[hit] = 2, 3, 1
        days[hit] = d + 1
    start_w = 1.0 + gain
    end_w = np.maximum(1.0 + eq, 1e-9)
    passed = state == 1
    return {"p_pass": float(passed.mean()), "p_fail_daily": float((state == 2).mean()),
            "p_fail_max": float((state == 3).mean()),
            "p_open": float((state == 0).mean()),
            "days_median_pass": (float(np.median(days[passed])) if passed.any() else None),
            "elog_w": float(np.mean(np.log(end_w / start_w)))}


def solve(pacing: Any, *, n_paths: int = N_PATHS, seed: int = 0) -> dict[str, Any]:
    """The modifier from a FTMO_PACING.json document. Pure."""
    from prop_challenge_allocator import FTMO_2STEP as rules
    out: dict[str, Any] = {"multiplier": 1.0, "status": UNMEASURED, "rules": rules.name,
                           "grid": list(GRID)}
    if not isinstance(pacing, dict):
        out["why"] = "reports/FTMO_PACING.json is absent or unreadable"
        return out
    prog, days = pacing.get("progress") or {}, pacing.get("days") or {}
    plan, room = pacing.get("plan") or {}, pacing.get("room") or {}
    target_usd = _f(prog.get("target_usd"))
    gained = _f(prog.get("gained_equity_usd"))
    if gained is None:
        gained = _f(prog.get("gained_usd"))
    target_frac = _f(prog.get("target_frac"))
    initial = (target_usd / target_frac if target_usd and target_frac else None)
    if initial is None and target_usd:
        initial = target_usd / rules.targets.get(str(pacing.get("phase") or "phase1"), 0.10)
    daily_room, max_room = _f(room.get("daily_room_usd")), _f(room.get("max_room_usd"))
    dm, pp = _f(plan.get("days_median")), _f(plan.get("p_pass"))
    missing = [k for k, v in (("progress.target_usd", target_usd), ("progress.gained_usd", gained),
                              ("room.daily_room_usd", daily_room), ("room.max_room_usd", max_room),
                              ("plan.days_median", dm), ("plan.p_pass", pp)) if v is None]
    if pacing.get("status") not in (None, "OK"):
        missing.append(f"pacing status {pacing.get('status')}")
    if missing or not initial:
        out["why"] = "inputs absent: " + ", ".join(missing or ["initial balance"])
        return out
    assert target_usd is not None and gained is not None and daily_room is not None
    assert max_room is not None and dm is not None and pp is not None
    target, gain = target_usd / initial, gained / initial
    daily_limit = rules.daily_loss
    room_today, floor_gap = max(daily_room, 0.0) / initial, max(max_room, 0.0) / initial
    cal = calibrate(dm, pp, target, rules)
    if cal is None:
        out["why"] = f"plan (days_median {dm}, p_pass {pp}) does not calibrate a daily walk"
        return out
    mu, sigma = cal
    min_left = int(_f(days.get("min_days_left")) or 0)
    # THE DEADLINE THAT MAKES SPEED COUNT. With no deadline a positive-drift walk always passes
    # more often at a smaller m, so P(pass) is read by the plan's own horizon: its p90 days (or
    # twice the median), less the weekdays already spent. Behind that clock m rises; ahead, falls.
    p90 = _f(plan.get("days_p90"))
    plan_h = p90 if p90 and p90 > 0 else 2.0 * dm
    spent = max(int(_f(days.get("weekdays_elapsed")) or 1) - 1, 0)
    horizon = max(int(math.ceil(plan_h)) - spent, min_left, 1)
    rows, admissible = [], []
    for m in GRID:
        worst = m * (WORST_Z * sigma - mu)            # 1-in-100 day's loss, fraction
        ok = worst <= room_today
        r = {"m": m, "worst_day_usd": round(worst * initial, 2), "survives": ok,
             **walk(m, mu=mu, sigma=sigma, gain=gain, target=target, floor_gap=floor_gap,
                    daily_limit=daily_limit, room_today=room_today, min_days_left=min_left,
                    horizon=horizon, n_paths=n_paths, seed=seed)}
        rows.append(r)
        if ok:
            admissible.append(r)
    base = next(r for r in rows if r["m"] == 1.0)
    if not admissible:
        # Survival binds below the grid: the grid's floor is reported, with the bound that binds.
        out.update({"status": "SURVIVAL_BELOW_GRID", "multiplier": GRID[0], "direction": "DOWN",
                    "why": f"even m={GRID[0]}'s 1-in-100 day exceeds today's daily room",
                    "survival_cap": {"worst_day_z": WORST_Z, "max_m": None},
                    "calibration": {"mu": mu, "sigma": sigma}, "table": rows})
        return out
    best_p = max(r["p_pass"] for r in admissible)
    tied = [r for r in admissible if r["p_pass"] >= best_p - TIE_EPS]
    pick = max(tied, key=lambda r: (r["elog_w"], -abs(r["m"] - 1.0)))
    m = float(pick["m"])
    out.update({
        "status": "OK", "multiplier": m,
        "direction": "UP" if m > 1.0 else ("DOWN" if m < 1.0 else "NEUTRAL"),
        "why": None,
        "state": {"initial_usd": round(initial, 2), "gain_usd": round(gained, 2),
                  "target_usd": round(target_usd, 2), "left_usd": round(target_usd - gained, 2),
                  "daily_room_usd": round(daily_room, 2), "max_room_usd": round(max_room, 2),
                  "min_days_left": min_left, "horizon_days": horizon, "pace_verdict": (pacing.get("pace") or {}
                                                              ).get("verdict")},
        "calibration": {"mu_frac_per_day": round(mu, 6), "sigma_frac_per_day": round(sigma, 6),
                        "from_plan": {"days_median": dm, "p_pass": pp},
                        "model": "Normal day, mu=target/days_median, sigma so the FTMO walk at "
                                 "m=1 from the phase start passes with the plan's p_pass"},
        "survival_cap": {"worst_day_z": WORST_Z,
                         "max_m": max(r["m"] for r in admissible)},
        "at_m": {"p_pass": round(pick["p_pass"], 4), "elog_w": round(pick["elog_w"], 6)},
        "at_1": {"p_pass": round(base["p_pass"], 4), "elog_w": round(base["elog_w"], 6)},
        "p_pass_gain": round(pick["p_pass"] - base["p_pass"], 4),
        "missed_growth": {
            "elog_w_forgone_at_1": round(pick["elog_w"] - base["elog_w"], 6),
            "p_pass_forgone_at_1": round(pick["p_pass"] - base["p_pass"], 4),
            "why": "the book trades at 1.0 while this is report-only; this is what that costs"},
        "table": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
                  for r in rows]})
    return out


def build(pacing: Any = None, *, now: datetime | None = None, n_paths: int = N_PATHS
          ) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {"schema": SCHEMA, "generated_at": now.isoformat(timespec="seconds"),
                           "report_only": True, "consumer": None,
                           "intended_consumer": INTENDED_CONSUMER,
                           "source": "reports/FTMO_PACING.json",
                           "source_generated_at": (pacing or {}).get("generated_at")
                           if isinstance(pacing, dict) else None}
    try:
        doc.update(solve(pacing, n_paths=n_paths))
    except Exception as exc:                    # never raises; neutral on a fault
        doc.update({"status": UNMEASURED, "multiplier": 1.0,
                    "why": f"{type(exc).__name__}: {exc}"[:300]})
    return doc


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = build(_read_json(PACING))
    write(doc)
    print(json.dumps({k: doc.get(k) for k in ("status", "multiplier", "direction", "why")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
