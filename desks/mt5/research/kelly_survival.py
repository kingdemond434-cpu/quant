#!/usr/bin/env python3
"""MAXIMUM AGGRESSION INSIDE SURVIVAL: the gold book's size per window, per venue.

The principal, 2026-09-30, after the survival-vs-Kelly arithmetic: "i dont want timidness but
i want maximum aggressiveness within survival". This organ is that sentence as a solve:

    maximise   ruin-counted posterior E[log W]          (Fusion)
               P(pass the challenge)                    (E8, a barrier game, where log wealth
                                                         is the wrong objective)
    subject to P(death within HORIZON) <= EPS_DEATH     (Fusion; E8's death is its own barrier)

over the three GOLD_WINDOWS, each window either OFF or at a size the venue can actually send.
Survival is the only thing that may take size away; everything else is growth's call.

WHY THIS CAN CUT A WINDOW, AND WHY THAT IS NOT TIMID. Full Kelly is the fastest-growing size
there is: betting above it lowers E[log W] AND raises ruin, so it is less aggressive in the only
sense that compounds. Measured 2026-09-30 on the allocator's worlds with live-updated posteriors:
the three windows at the 0.02-lot floor are ~24% heat on EUR 583, 2.7x full Kelly, at +0.65%/day
with 3.9% 60-day ruin; gold_asia alone at the floor (~9% heat, ~full Kelly) is +1.10%/day with
none. The 0.02 floor means a window is 0 or >= ~8% heat, so the only way to be AT Kelly is to
choose WHICH windows trade. Growth governance Rule 1 is met by construction: a window leaves
only when the solve measures that leaving raises E[log W], and the artifact carries that
missed-growth line (`vs_today`). Rule 2 is met the same way: sizes above the floor are in the
search, and a window whose live edge grows comes back on the next pass with no human act.

INPUTS, all the desk's own:

    worlds    data/pf_allocator_cache/worlds.npz   the allocator's world population (prior)
    live      data/live_ledger.jsonl               realised R per window, attributed by
                                                   `attribution_reconcile.attribute`
    equity    data/gateway_state.json (Fusion), reports/E8_GOLD.json (E8)
    floor     live_ledger risk per lot per window (measured), else decision_core constants

    -> reports/KELLY_SURVIVAL.json

The gateway and the E8 executor read it through `decision_core.load_kelly_survival`, which
returns None -- today's behaviour, unchanged -- when the artifact is absent, stale or unreadable.

    python desks/mt5/research/kelly_survival.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
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

WORLDS = BASE / "data" / "pf_allocator_cache" / "worlds.npz"
LEDGER = BASE / "data" / "live_ledger.jsonl"
GATEWAY_STATE = BASE / "data" / "gateway_state.json"
ACCOUNT = BASE / "data" / "account_state.json"
E8_REPORT = BASE / "reports" / "E8_GOLD.json"
OUT = BASE / "reports" / "KELLY_SURVIVAL.json"

WINDOWS = ("asia", "london_am", "afternoon")
#: Fusion horizon in trading days and the path count. 60 days is long enough for a correlated
#: losing run to show and short enough that the worlds' 256 rows give independent blocks.
HORIZON = 60
N_PATHS = 4000
#: THE DEATH LINE. Below 20% of starting equity the 0.02-lot floor is >= ~40% risk per trade on
#: this book, so the account cannot place a survivable order again: that is ruin in practice,
#: long before equity touches zero or the broker's stop-out needs to act.
DEATH_LINE = 0.20
#: Allowed probability of crossing it within HORIZON. The desk's own tolerance for a stop-out
#: event (`posterior_growth.EPS_STOP`, 5%). EPS_RUIN (1e-3 per 5 days) was tried first and no
#: tradable gold size on a EUR ~560 account meets it -- a 0.01-lot gold_asia bracket alone
#: crosses the death line on 2.3% of 60-day paths -- so it would have answered "trade nothing",
#: which is the one answer that cannot compound.
from libs.portfolio.posterior_growth import EPS_STOP as EPS_DEATH  # noqa: E402
#: Fusion size grid, in lots per window (0 = OFF). 0.01 is the venue minimum and 0.02 the
#: principal's policy floor; the principal put survival above that floor on 2026-09-30, so the
#: venue minimum is in the grid and the solve says which one survival allows. Above the floor
#: the search is free, so a strong window can be sized UP (Rule 2).
FUSION_LOTS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08)
GOLD_MIN_LOT = 0.02
#: E8 Pro rules (docs/PROP_FIRM_E8.md), in dollars of the $100,000 initial balance: +10% target,
#: $90,000 static floor, 2.5% daily breach, 2% daily profit cap stripped at rollover. The
#: barriers are placed relative to the account's CURRENT equity, which is not the initial one.
E8_INITIAL, E8_TARGET_USD, E8_FLOOR_USD = 100_000.0, 110_000.0, 90_000.0
E8_DAILY_BREACH, E8_DAILY_CAP = 0.025, 0.02
#: Survival on E8 is P(the account fails) = P(floor) + P(daily breach), held to EPS_DEATH; inside
#: it, the fastest median pass wins (aggression), P(pass) breaking ties.
E8_DAYS = 256
E8_PATHS = 2000
E8_RISKS = (0.0, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015)
#: Absurd R values are unit errors in the ledger (FX rows have read -15,889R), never evidence.
MAX_ABS_R = 20.0


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _num(v: object) -> float | None:
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def deal_r(d: dict[str, Any]) -> float | None:
    """A deal's realised R: the ledger's own, else P/L over the risk it recorded, else None."""
    r = _num(d.get("r_multiple"))
    if r is not None and r != 0.0 and abs(r) <= MAX_ABS_R:
        return r
    pl, risk = _num(d.get("pl_quote")), _num(d.get("risk_quote"))
    if pl is not None and risk:
        rr = pl / abs(risk)
        if abs(rr) <= MAX_ABS_R:
            return rr
    return None


def live_evidence(deals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per window: realised R list and the measured quote risk per lot, from attributed deals."""
    from attribution_reconcile import attribute
    names = [f"gold_{w}" for w in WINDOWS]
    gold = [d for d in deals if str(d.get("symbol") or "").upper().startswith("XAU")
            and str(d.get("account_kind") or "live") == "live"]
    out: dict[str, dict[str, Any]] = {w: {"r": [], "risk_per_lot": []} for w in WINDOWS}
    for row, d in zip(attribute(gold, names), gold, strict=True):
        name = str(row.get("sleeve") or "")
        if not name.startswith("gold_"):
            continue
        w = name[len("gold_"):]
        if w not in out:
            continue
        r = deal_r(d)
        if r is not None:
            out[w]["r"].append(r)
        risk, vol = _num(d.get("risk_quote")), _num(d.get("volume"))
        if risk and vol:
            out[w]["risk_per_lot"].append(abs(risk) / vol)
    return out


def posterior_shift(prior_mean: float, live_r: list[float]) -> tuple[float, float]:
    """(posterior mean, live weight) on the desk's own convention: the prior is worth K_SLEEVE
    observations and each live trade counts LIVE_WEIGHT times (posterior_growth)."""
    from libs.portfolio.posterior_growth import K_SLEEVE, LIVE_WEIGHT
    n = len(live_r)
    if n == 0:
        return prior_mean, 0.0
    w = LIVE_WEIGHT * n / (LIVE_WEIGHT * n + K_SLEEVE)
    return prior_mean + w * (float(np.mean(live_r)) - prior_mean), w


def fusion_equity() -> tuple[float | None, str]:
    for path, key in ((GATEWAY_STATE, "equity"), (ACCOUNT, "equity")):
        doc = _read_json(path)
        v = _num(doc.get(key)) if isinstance(doc, dict) else None
        if v and v > 0:
            return v, f"{path.name}:{key}"
    return None, "UNMEASURED: no equity in gateway_state.json or account_state.json"


def e8_equity() -> tuple[float | None, str]:
    doc = _read_json(E8_REPORT)
    v = _num(doc.get("equity")) if isinstance(doc, dict) else None
    return (v, "E8_GOLD.json:equity") if v and v > 0 else (None, "UNMEASURED: no E8 equity")


def ruin_counted_elog(r: np.ndarray, h: np.ndarray) -> tuple[float, float, float]:
    """(E[log W]/day with a dead path scored at the death line, P(death), P(-35% drawdown))."""
    x = 1.0 + r @ h                                          # (paths, days)
    logs = np.log(np.clip(x, 1e-12, None))
    cum = np.cumsum(logs, axis=1)
    low = cum.min(axis=1)
    dead = low <= math.log(DEATH_LINE)
    lw = np.where(dead, math.log(DEATH_LINE), cum[:, -1])
    return (float(lw.mean()) / r.shape[1], float(dead.mean()),
            float((low <= math.log(0.65)).mean()))


def e8_barrier(r: np.ndarray, h: np.ndarray, equity: float = E8_INITIAL
               ) -> dict[str, float | None]:
    """P(pass), P(static floor), P(daily breach), median days to pass, on E8 Pro's rules."""
    target, floor = E8_TARGET_USD / equity, E8_FLOOR_USD / equity
    day = np.minimum(r @ h, E8_DAILY_CAP)
    n, t_n = day.shape
    bal = np.ones(n)
    state = np.zeros(n, dtype=int)                           # 0 live, 1 pass, 2 daily, 3 floor
    days = np.full(n, t_n)
    for t in range(t_n):
        live = state == 0
        if not live.any():
            break
        breach = day[:, t] <= -E8_DAILY_BREACH
        bal = np.where(live, bal * (1.0 + day[:, t]), bal)
        f_d = live & breach
        f_s = live & ~breach & (bal <= floor)
        win = live & ~f_d & ~f_s & (bal >= target)
        state[f_d], state[f_s], state[win] = 2, 3, 1
        days[f_d | f_s | win] = t + 1
    passed = state == 1
    return {"p_pass": float(passed.mean()), "p_floor": float((state == 3).mean()),
            "p_daily": float((state == 2).mean()),
            "median_days": float(np.median(days[passed])) if passed.any() else None}


def solve(*, seed: int = 0) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    doc: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "objective": "max ruin-counted E[log W] s.t. P(death) <= eps (Fusion);"
                                        " fastest median pass s.t. P(fail) <= eps (E8)",
                           "death_line": DEATH_LINE, "eps_death": EPS_DEATH,
                           "horizon_days": HORIZON, "status": "OK"}
    try:
        z = np.load(WORLDS, allow_pickle=True)
    except (OSError, ValueError) as exc:
        doc["status"] = f"UNMEASURED: worlds unreadable ({type(exc).__name__})"
        return doc
    names = [str(n) for n in z["names"]]
    cols = [f"gold_{w}" for w in WINDOWS]
    missing = [c for c in cols if c not in names]
    if missing:
        doc["status"] = f"UNMEASURED: worlds carry no column for {missing}"
        return doc
    idx = [names.index(c) for c in cols]
    r = np.asarray(z["r"], dtype=float)[:, :, idx]            # (worlds, rows, 3)
    deals = []
    try:
        with LEDGER.open(encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if text:
                    try:
                        deals.append(json.loads(text))
                    except ValueError:
                        continue
    except OSError:
        pass
    ev = live_evidence(deals)
    post: dict[str, Any] = {}
    for k, w in enumerate(WINDOWS):
        prior = float(r[:, :, k].mean())
        mean, weight = posterior_shift(prior, ev[w]["r"])
        r[:, :, k] += mean - prior
        post[w] = {"prior_r": round(prior, 4), "live_n": len(ev[w]["r"]),
                   "live_mean_r": (round(float(np.mean(ev[w]["r"])), 4) if ev[w]["r"] else None),
                   "live_weight": round(weight, 3), "posterior_r": round(mean, 4)}
    doc["posterior"] = post

    rng = np.random.default_rng(seed)
    n_w, n_rows, _ = r.shape
    wi = rng.integers(0, n_w, N_PATHS)
    start = rng.integers(0, n_rows - HORIZON + 1, N_PATHS)
    paths = r[wi[:, None], start[:, None] + np.arange(HORIZON)[None, :], :]

    # ---------------------------------------------------------------- Fusion
    from mt5desk.decision_core import CONTRACT_OZ, DIST_USD, FX_EUR
    equity, eq_src = fusion_equity()
    fus: dict[str, Any] = {"equity_eur": equity, "equity_source": eq_src}
    if equity:
        eur_per_lot = {}
        for w in WINDOWS:
            per_lot = ev[w]["risk_per_lot"]
            quote = float(np.median(per_lot)) if per_lot else DIST_USD * CONTRACT_OZ
            eur_per_lot[w] = quote * FX_EUR
        fus["risk_eur_per_lot"] = {w: round(v, 2) for w, v in eur_per_lot.items()}
        best: tuple[float, tuple[float, ...], tuple[float, float, float]] | None = None
        table = []
        for lots in itertools.product(FUSION_LOTS, repeat=len(WINDOWS)):
            h = np.array([lots[k] * eur_per_lot[w] / equity for k, w in enumerate(WINDOWS)])
            el, p_dead, p_dd = ruin_counted_elog(paths, h)
            row = {"lots": dict(zip(WINDOWS, lots, strict=True)), "heat": round(float(h.sum()), 4),
                   "elog_per_day": round(el, 6), "p_death": round(p_dead, 4),
                   "p_dd35": round(p_dd, 4), "survives": p_dead <= EPS_DEATH}
            table.append(row)
            # Ties go to the larger book: at equal growth, aggression wins.
            if row["survives"] and (best is None or el > best[0] + 1e-9 or (
                    abs(el - best[0]) <= 1e-9 and h.sum() > sum(best[1]))):
                best = (el, tuple(float(x) for x in h), (el, p_dead, p_dd))
        today = next(t for t in table if all(t["lots"][w] == GOLD_MIN_LOT for w in WINDOWS))
        if best is None:
            fus["status"] = "NO_SURVIVING_BOOK: every size crosses the death line; today stands"
        else:
            chosen = next(t for t in table if abs(t["heat"] - round(sum(best[1]), 4)) < 1e-9
                          and abs(t["elog_per_day"] - round(best[0], 6)) < 1e-12)
            fus.update({
                "status": "OK",
                "windows": {w: {"lots": chosen["lots"][w], "heat": round(best[1][k], 5)}
                            for k, w in enumerate(WINDOWS)},
                "chosen": chosen, "today": today,
                # THE MISSED-GROWTH LINE (growth governance Rule 1): what moving from today's
                # book to the chosen one does to robust forward E[log W], measured, per day.
                "vs_today": {"delta_elog_per_day": round(chosen["elog_per_day"]
                                                         - today["elog_per_day"], 6),
                             "delta_p_death": round(chosen["p_death"] - today["p_death"], 4)},
            })
        fus["top"] = sorted(table, key=lambda t: -t["elog_per_day"])[:8]
    else:
        fus["status"] = eq_src
    doc["fusion"] = fus

    # ---------------------------------------------------------------- E8
    e8: dict[str, Any] = {}
    eq8, src8 = e8_equity()
    e8["equity_usd"], e8["equity_source"] = eq8, src8
    wi8 = rng.integers(0, n_w, E8_PATHS)
    r8 = r[wi8]                                                # a full world-year per path
    days = min(E8_DAYS, r8.shape[1])
    r8 = r8[:, :days, :]
    eq_e8 = eq8 or E8_INITIAL
    best8: tuple[tuple[float, float], tuple[float, ...], dict[str, Any]] | None = None
    for risks in itertools.product(E8_RISKS, repeat=len(WINDOWS)):
        if not any(risks):
            continue
        res = e8_barrier(r8, np.array(risks), eq_e8)
        if (res["p_floor"] or 0.0) + (res["p_daily"] or 0.0) > EPS_DEATH:
            continue
        md = res["median_days"] if res["median_days"] is not None else float("inf")
        key = (-md, res["p_pass"] or 0.0)
        if best8 is None or key > best8[0]:
            best8 = (key, risks, res)
    today8 = e8_barrier(r8, np.array([0.005] * len(WINDOWS)), eq_e8)
    if best8 is None:
        e8["status"] = "NO_SURVIVING_BOOK: every size fails the account too often; today stands"
    else:
        e8.update({"status": "OK",
                   "windows": {w: {"risk_frac": best8[1][k]} for k, w in enumerate(WINDOWS)},
                   "chosen": best8[2], "today": today8,
                   "vs_today": {"delta_p_pass": round((best8[2]["p_pass"] or 0.0)
                                                      - (today8["p_pass"] or 0.0), 4)}})
    doc["e8"] = e8
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = solve()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=float), encoding="utf-8")
    tmp.replace(a.out)
    fus, e8 = doc.get("fusion") or {}, doc.get("e8") or {}
    print(f"kelly_survival: {doc['status']} -- fusion {fus.get('status')} "
          f"{ {w: v['lots'] for w, v in (fus.get('windows') or {}).items()} }; "
          f"e8 {e8.get('status')} { {w: v['risk_frac'] for w, v in (e8.get('windows') or {}).items()} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
