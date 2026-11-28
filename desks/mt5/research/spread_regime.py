#!/usr/bin/env python3
"""SPREAD REGIME: each symbol's spread as a time-of-day-normed liquidity-stress state, hourly.

    spread_z = (spread_pts - median[symbol, broker hour]) / scale[symbol, broker hour]

THE NORM IS THE HOUR'S OWN. A spread is wide or tight only against what that symbol pays at that
hour: USDZAR at 01:00 broker time routinely pays ten times its London spread (cost_surface.py
measured 6x on its own fill bars), so a pooled z would flag every Asian-session quote as stress
and miss a real London blow-out. The norm is built per (symbol, broker hour) from the data the
desk already holds and nothing is fetched:

    ticks   the tick tape (mt5desk.tape, data/tape/ticks/<SYM>/<day>.parquet), the newest
            TICK_DAYS day files, every quoted spread zeros INCLUDED (on this raw-FX account a
            zero spread is a real quote -- tape.py measured it over 204M ticks). Trading box only.
    bars    the H1 bars' own `spread` column (data/universe/<SYM>_H1.parquet), the newest
            BAR_DAYS days, where the tape holds nothing for the symbol. Zero-spread bars are
            dropped there as absence (cost_surface.py's splice finding).

Median and a ROBUST scale per hour, scale = max(1.4826 * MAD, (p90 - p50) / 1.2816, a floor of
one point or a tenth of the median), so an administered flat spread (MAD 0) still has a finite,
honest scale. An hour with fewer than MIN_TICKS / MIN_BARS observations is UNMEASURED and carries
no number; the gate does nothing there (L1.28a: absence is never a clean verdict).

THREE JOBS, ONE HOURLY LEG (`hourly_cycle:spread_regime`):

1. STATE   reports/SPREAD_REGIME.json: per symbol, the per-hour norm, the latest quote's spread_z
           and its regime (STRESS >= 3, WIDE >= 2, TIGHT <= -1, else NORMAL). The entry gate
           (mt5desk/spread_gate.py) reads the norm; anything else may read the state.
2. SCORE   every entry the gate recorded in data/spread_gate_ledger.jsonl is scored. A SHADOW
           `would_defer` row against the tick tape: walk the ticks after the decision and take the
           first one at which the gate would have RELEASED (spread_z under Z_RELEASE, the defer
           horizon reached, or the quote DRIFT_RELEASE_FRAC of the stop against the entry), and
           compare its side quote with the side quote the order actually took -- both net of spread
           because both are the side the order pays. A LIVE `release` row carries its realised
           improvement already. Improvement is in R (price units over the stop distance).
3. PROMOTE reports/SPREAD_GATE.json, and data/SPREAD_GATE_MODE.json written LIVE when the mean
           minus TWO standard errors of the improvement is above zero over at least N_MIN scored
           deferrals (the newest WINDOW), SHADOW when the mean plus one SE is below
           zero, and HOLDS in between (a dead band, so noise cannot thrash it). Shadow rows are
           scored at the gateway's pass cadence, not per tick. No human step either way; a
           switch file carrying `"pinned": true` is left alone (the human revert path).

THE GATE'S MISSED-GROWTH LINE (Rule 1). A veto has to prove it raises robust forward E[log W],
so SPREAD_GATE.json publishes a `missed_growth` line every hour -- the improvement per deferral in
R and, where the sleeve's risk fraction is known, in log-wealth -- and research/missed_growth.py
carries it into MISSED_GROWTH.json beside the registered rails (the rail register,
libs/portfolio/rails.py, is a sealed immutable-evaluator file, so the gate registers no rail).

    python desks/mt5/research/spread_regime.py [--budget-s 600] [--no-write]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import spread_gate as gate  # noqa: E402

UNIVERSE = BASE / "data" / "universe"
SLEEVES = BASE / "data" / "sleeves.json"
OUT_STATE = BASE / "reports" / "SPREAD_REGIME.json"
OUT_GATE = BASE / "reports" / "SPREAD_GATE.json"
SCHEMA = "spread-regime-1"

TICK_DAYS = 5
BAR_DAYS = 90
MIN_TICKS = 200
MIN_BARS = 20
#: Promotion reads the newest WINDOW scored deferrals, so a gate that stops earning reverts.
WINDOW = 200
REGIMES = (("STRESS", 3.0), ("WIDE", 2.0))
TIGHT_Z = -1.0
EARNS, COSTS, UNMEASURED = "EARNS_ITS_PLACE", "COSTS_GROWTH", "UNMEASURED"


# ----------------------------------------------------------------------------- the norm
def norm_from_counts(counts: Counter[float], min_n: int) -> dict[str, Any]:
    """Median and robust scale of a spread distribution held as {points: count}."""
    n = int(sum(counts.values()))
    if n < min_n:
        return {"status": "UNMEASURED", "n": n}
    vals = np.array(sorted(counts), dtype=float)
    w = np.array([counts[v] for v in sorted(counts)], dtype=float)
    cum = np.cumsum(w) / w.sum()

    def q(p: float) -> float:
        return float(vals[min(int(np.searchsorted(cum, p)), len(vals) - 1)])
    med = q(0.5)
    dev = Counter[float]()
    for v, c in counts.items():
        dev[abs(v - med)] += c
    dv = np.array(sorted(dev), dtype=float)
    dw = np.cumsum([dev[v] for v in sorted(dev)]) / n
    mad = float(dv[min(int(np.searchsorted(dw, 0.5)), len(dv) - 1)])
    p90, p99 = q(0.90), q(0.99)
    scale = max(1.4826 * mad, (p90 - med) / 1.2816, 1.0, 0.1 * med)
    return {"status": "MEASURED", "n": n, "median": round(med, 3), "scale": round(scale, 4),
            "p90": round(p90, 3), "p99": round(p99, 3), "mad": round(mad, 3)}


def regime_of(z: float | None) -> str:
    if z is None:
        return UNMEASURED
    for name, lo in REGIMES:
        if z >= lo:
            return name
    return "TIGHT" if z <= TIGHT_Z else "NORMAL"


def _registry() -> dict[str, Any]:
    try:
        reg = json.loads((UNIVERSE / "universe.json").read_text("utf-8"))
        return reg if isinstance(reg, dict) else {}
    except (OSError, ValueError):
        return {}


def point_of(row: dict[str, Any] | None) -> float | None:
    if not isinstance(row, dict):
        return None
    d = row.get("digits")
    if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 10:
        return 10.0 ** -d
    ts = row.get("tick_size")
    return float(ts) if isinstance(ts, (int, float)) and ts > 0 else None


def tick_norm(symbol: str, point: float, root: Path | None = None,
              days: int = TICK_DAYS) -> dict[str, Any] | None:
    """Per broker hour from the newest `days` tape files, one file in memory at a time."""
    from mt5desk.tape import day_files
    files = day_files(symbol, root)[-days:]
    if not files:
        return None
    by_hour: dict[int, Counter[float]] = {h: Counter() for h in range(24)}
    latest: tuple[int, float] | None = None
    used = []
    for day, f in files:
        try:
            t = pd.read_parquet(f, columns=["time_msc", "bid", "ask"])
        except (OSError, ValueError, KeyError, ImportError):
            continue
        t = t[(t["bid"] > 0) & (t["ask"] >= t["bid"])]
        if t.empty:
            continue
        used.append(day)
        pts = ((t["ask"].astype(float) - t["bid"].astype(float)) / point).round(1)
        ms = t["time_msc"].astype("int64")
        hour = (ms // 3_600_000) % 24
        vc = pd.DataFrame({"h": hour.to_numpy(), "p": pts.to_numpy()}).value_counts()
        for (h, p), c in vc.items():
            by_hour[int(h)][float(p)] += int(c)
        i = int(ms.to_numpy().argmax())
        cand = (int(ms.iloc[i]), float(pts.iloc[i]))
        if latest is None or cand[0] > latest[0]:
            latest = cand
    if not used:
        return None
    hours = {str(h): norm_from_counts(c, MIN_TICKS) for h, c in by_hour.items() if c}
    out: dict[str, Any] = {"basis": "ticks", "days": used, "hours": hours}
    if latest is not None:
        out["latest"] = {"broker_ms": latest[0], "hour": (latest[0] // 3_600_000) % 24,
                         "spread_pts": latest[1]}
    return out


def bar_norm(symbol: str, days: int = BAR_DAYS) -> dict[str, Any] | None:
    f = UNIVERSE / f"{symbol}_H1.parquet"
    try:
        df = pd.read_parquet(f, columns=["spread"])
    except (OSError, ValueError, KeyError, ImportError):
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    sp = pd.to_numeric(df["spread"], errors="coerce")
    # ON BARS A ZERO SPREAD IS ABSENCE, not a free quote (cost_surface.py: the D1/H1 splice
    # carries spread == 0 on 99.9% of its bars). The tick basis keeps its zeros; this does not.
    ok = (~idx.isna()) & sp.notna().to_numpy() & (sp.to_numpy() > 0)
    sp, idx = sp[ok], idx[ok]
    if sp.empty:
        return None
    keep = idx >= idx.max() - pd.Timedelta(days=days)
    sp, idx = sp[keep], idx[keep]
    hours = {}
    for h in range(24):
        cell = sp[idx.hour == h]
        if cell.size:
            hours[str(h)] = norm_from_counts(Counter(cell.astype(float).round(1).tolist()),
                                             MIN_BARS)
    return {"basis": "bars", "days": days, "hours": hours,
            "latest": {"broker_ms": int(idx[-1].timestamp() * 1000), "hour": int(idx[-1].hour),
                       "spread_pts": float(sp.iloc[-1])}}


def _roster_symbols() -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return sorted({str(r.get("symbol")) for r in rows or [] if isinstance(r, dict)
                   and r.get("symbol")})


def build_state(budget_s: float = 600.0, tape_root: Path | None = None) -> dict[str, Any]:
    reg = _registry()
    symbols = sorted(f.name[: -len("_H1.parquet")] for f in UNIVERSE.glob("*_H1.parquet"))
    roster = [s for s in _roster_symbols() if s in set(symbols) or s in reg]
    order = roster + [s for s in symbols if s not in set(roster)]
    t0 = time.monotonic()
    out: dict[str, Any] = {}
    n_tick = n_bar = n_none = 0
    budget_hit = False
    for sym in order:
        point = point_of(reg.get(sym))
        norm = None
        if point and not budget_hit:
            try:
                norm = tick_norm(sym, point, tape_root)
            except Exception:
                norm = None
            budget_hit = time.monotonic() - t0 > budget_s
        if norm is None:
            norm = bar_norm(sym)
        if norm is None:
            n_none += 1
            continue
        n_tick += norm["basis"] == "ticks"
        n_bar += norm["basis"] == "bars"
        lt = norm.get("latest") or {}
        z = None
        if lt:
            z, _ = gate.spread_z(norm, int(lt["hour"]), float(lt["spread_pts"]))
        norm["point"] = point
        norm["latest"] = {**lt, "z": None if z is None else round(z, 4), "regime": regime_of(z)}
        norm["n_hours_measured"] = sum(1 for c in norm["hours"].values()
                                       if c.get("status") == "MEASURED")
        out[sym] = norm
    regimes = Counter(v["latest"]["regime"] for v in out.values())
    return {"schema": SCHEMA, "generated_at": datetime.now(tz=UTC).isoformat(),
            "z_defer": gate.Z_DEFER, "z_release": gate.Z_RELEASE,
            "n_symbols": len(out), "n_tick_basis": n_tick, "n_bar_basis": n_bar,
            "n_no_spread_data": n_none, "tick_budget_hit": budget_hit,
            "regimes": dict(sorted(regimes.items())),
            "stressed": sorted(k for k, v in out.items() if v["latest"]["regime"] == "STRESS"),
            "symbols": out}


# ----------------------------------------------------------------------------- the scorer
def _ledger(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    rows = []
    for ln in text.splitlines():
        try:
            r = json.loads(ln) if ln.strip() else None
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def score_would_defer(row: dict[str, Any], ticks: pd.DataFrame | None,
                      point: float | None, pass_s: float = gate.PASS_S) -> dict[str, Any] | None:
    """The counterfactual for one SHADOW row, AT THE GATEWAY'S CADENCE.

    A LIVE deferral is re-checked once per gateway pass, not on every tick, so the scorer does
    the same: at each `pass_s` step after the decision (plus the row's measured pass latency,
    `pass_latency_s`, when the gateway recorded one -- it does not today, so the step is the
    loop's nominal 60 s) it reads the first tick AT OR AFTER that instant, and releases there if
    the gate would (spread_z under Z_RELEASE, the quote DRIFT_RELEASE_FRAC of the stop against
    the entry, or the horizon reached). The improvement is that tick's side quote against the
    side quote taken, both net of spread. None when the tape does not yet cover the last check.
    """
    t0, side = row.get("broker_ms"), int(row.get("side") or 0)
    q0, dist = row.get("quote"), row.get("dist")
    med, sc = row.get("median"), row.get("scale")
    horizon_s = float(row.get("max_defer_s") or 0.0)
    if ticks is None or ticks.empty or not point or side not in (1, -1) or not all(
            isinstance(v, (int, float)) for v in (t0, q0, dist, med, sc)) or not dist or not sc \
            or horizon_s <= 0:
        return None
    lat = row.get("pass_latency_s")
    lat_s = float(lat) if isinstance(lat, (int, float)) and lat >= 0 else 0.0
    t0f = float(t0)  # type: ignore[arg-type]
    times = ticks["time_msc"].astype("int64").to_numpy()
    bid = ticks["bid"].astype(float).to_numpy()
    ask = ticks["ask"].astype(float).to_numpy()
    k = 1
    while True:
        step_s = k * pass_s
        at_ms = t0f + (step_s + lat_s) * 1000.0
        j = int(np.searchsorted(times, at_ms, side="left"))
        if j >= times.size:
            return None                 # the tape has not reached this check yet
        quote = ask[j] if side == 1 else bid[j]
        z = ((ask[j] - bid[j]) / point - float(med)) / float(sc)
        adverse = side * (quote - float(q0)) / float(dist)  # type: ignore[arg-type]
        reason = ("spread_normal" if z < gate.Z_RELEASE
                  else "horizon" if step_s >= horizon_s
                  else "drift" if adverse >= gate.DRIFT_RELEASE_FRAC else None)
        if reason is not None:
            return {"key": row.get("key"), "symbol": row.get("symbol"), "at": row.get("at"),
                    "mode": "SHADOW", "reason": reason, "risk_frac": row.get("risk_frac"),
                    "checks": k, "elapsed_s": round((float(times[j]) - t0f) / 1000.0, 1),
                    "improvement_r": round(float(-adverse), 6)}
        k += 1


def _tape_window(symbol: str, t0_ms: float, root: Path | None) -> pd.DataFrame | None:
    """The ticks around one decision, from the day files on EITHER side of its broker date.

    HOW THE FILES ARE DATED, measured in mt5desk/tape.py: the desk's own writer names a file by
    `pd.to_datetime(time_msc, unit="ms", utc=True).date`, i.e. the broker-clock date read as
    if it were UTC -- the same mapping this uses -- but `moat/moat_silver.py`'s YYYYMMDD files
    take the date of the recorder's bronze file name, whose clock this module cannot prove. So
    it does not trust either convention: it reads the files for the date before, the date of and
    the date after the decision, and the caller selects the ticks by `time_msc` alone. A day
    boundary on any clock offset under 24 h therefore cannot drop the deferral's window.
    """
    from mt5desk.tape import day_files
    day = datetime.fromtimestamp(t0_ms / 1000.0, tz=UTC).date()
    want = {(day + timedelta(days=d)).isoformat() for d in (-1, 0, 1)}
    frames = []
    for d, f in day_files(symbol, root):
        if d in want:
            try:
                frames.append(pd.read_parquet(f, columns=["time_msc", "bid", "ask"]))
            except (OSError, ValueError, KeyError, ImportError):
                continue
    if not frames:
        return None
    t = pd.concat(frames, ignore_index=True).drop_duplicates()
    t = t[(t["bid"] > 0) & (t["ask"] >= t["bid"])]
    return t[t["time_msc"] >= t0_ms].sort_values("time_msc", kind="stable")


def lost_keys(ledger: list[dict[str, Any]]) -> list[str]:
    """Deferrals expired with no release: out of the proof, so counted apart. Once per key (the
    hourly leg and the gateway may both ledger one), and never a key that WAS released after the
    leg's ledger-only sweep: that one is scored as a release instead."""
    released = {str(r.get("key")) for r in ledger if r.get("kind") == "release"}
    return sorted({str(r.get("key")) for r in ledger if r.get("kind") == "expired"} - released)


def score(ledger: list[dict[str, Any]], state: dict[str, Any],
          tape_root: Path | None = None) -> tuple[list[dict[str, Any]], int]:
    scored: list[dict[str, Any]] = []
    unscored = 0
    cache: dict[tuple[str, str], pd.DataFrame | None] = {}
    for r in ledger:
        if r.get("kind") == "release":
            if isinstance(r.get("improvement_r"), (int, float)):
                scored.append({"key": r.get("key"), "symbol": r.get("symbol"), "at": r.get("at"),
                               "mode": "LIVE", "reason": r.get("reason"),
                               "risk_frac": r.get("risk_frac"), "elapsed_s": r.get("elapsed_s"),
                               "lot0": r.get("lot0"), "lot_sent": r.get("lot_sent"),
                               "improvement_r": float(r["improvement_r"])})
            else:
                unscored += 1
            continue
        if r.get("kind") != "would_defer":
            continue
        sym, t0 = str(r.get("symbol") or ""), r.get("broker_ms")
        point = (state.get("symbols", {}).get(sym) or {}).get("point")
        got = None
        if isinstance(t0, (int, float)):
            ck = (sym, str(int(float(t0))))
            if ck not in cache:
                try:
                    cache[ck] = _tape_window(sym, float(t0), tape_root)
                except Exception:
                    cache[ck] = None
            got = score_would_defer(r, cache[ck], point)
        if got is None:
            unscored += 1
        else:
            scored.append(got)
    return scored, unscored


#: THE DEAD BAND (audit MF1). One bar for both directions made every pass that did not promote
#: write SHADOW, so the mode thrashed on noise. Promote only past a strict bar, demote only past
#: a looser one in the other direction, and hold in between. One-sided normal levels published.
PROMOTE_SE = 2.0
DEMOTE_SE = 1.0


def _one_sided_level(k: float) -> float:
    return round(0.5 * (1.0 + math.erf(k / math.sqrt(2.0))), 4)


def stats(scored: list[dict[str, Any]]) -> tuple[dict[str, Any], float | None, float | None]:
    """The published block, the mean and the SE of the newest WINDOW scored deferrals."""
    recent = scored[-WINDOW:]
    imp = np.array([float(x["improvement_r"]) for x in recent], dtype=float)
    n = int(imp.size)
    out: dict[str, Any] = {"n_scored": len(scored), "n_window": n, "n_min": gate.N_MIN}
    if n == 0:
        return out, None, None
    mean = float(imp.mean())
    se = float(imp.std(ddof=1) / math.sqrt(n)) if n > 1 else math.inf
    risk = [float(x["risk_frac"]) * float(x["improvement_r"]) for x in recent
            if isinstance(x.get("risk_frac"), (int, float)) and x["risk_frac"] > 0]
    fin = not math.isinf(se)
    out.update(mean_improvement_r=round(mean, 6), se_r=round(se, 6) if fin else None,
               lcb_r=round(mean - se, 6) if fin else None,
               promote_bar_r=round(mean - PROMOTE_SE * se, 6) if fin else None,
               demote_bar_r=round(mean + DEMOTE_SE * se, 6) if fin else None,
               logw_per_deferral=(round(float(np.mean([math.log1p(v) for v in risk])), 8)
                                  if risk else None),
               n_with_risk_frac=len(risk))
    return out, mean, se


def verdict(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """PROMOTE when mean - 2 SE > 0, DEMOTE when mean + 1 SE < 0, HOLD otherwise (and below
    N_MIN). The LIVE-only rows are judged on their own as well, so a LIVE gate can be demoted on
    what it actually did, not on a shadow history that may flatter it."""
    out, mean, se = stats(scored)
    live, lmean, lse = stats([x for x in scored if x.get("mode") == "LIVE"])
    out["bars"] = {"promote": f"mean - {PROMOTE_SE:g} SE > 0",
                   "promote_one_sided_level": _one_sided_level(PROMOTE_SE),
                   "demote": f"mean + {DEMOTE_SE:g} SE < 0",
                   "demote_one_sided_level": _one_sided_level(DEMOTE_SE),
                   "between": "hold the current mode"}
    out["live_only"] = live
    n = int(out["n_window"])
    if mean is None or se is None or n < gate.N_MIN:
        return {**out, "verdict": UNMEASURED, "action": "HOLD", "promote": False,
                "demote": False, "why": f"{n} scored deferrals, under the {gate.N_MIN} needed"}
    up = mean - PROMOTE_SE * se > 0
    down = mean + DEMOTE_SE * se < 0 or (
        lmean is not None and lse is not None and live["n_window"] >= gate.N_MIN
        and lmean + DEMOTE_SE * lse < 0)
    if down:
        return {**out, "verdict": COSTS, "action": "DEMOTE", "promote": False, "demote": True,
                "why": "mean + 1 SE of the improvement (all rows, or LIVE rows alone) is below "
                       "zero: deferring cost the entry"}
    if up:
        return {**out, "verdict": EARNS, "action": "PROMOTE", "promote": True, "demote": False,
                "why": "mean - 2 SE of the improvement is above zero: deferring raised the "
                       "entry's value"}
    return {**out, "verdict": UNMEASURED, "action": "HOLD", "promote": False, "demote": False,
            "why": "inside the dead band (mean - 2 SE <= 0 <= mean + 1 SE): mode held"}


MODE_RULE = ("SHADOW records only. research/spread_regime.py writes LIVE when mean - 2 SE of the "
             "scored improvement (R) > 0 over >= 30 scored deferrals (newest 200), SHADOW when "
             "mean + 1 SE < 0 (all rows, or LIVE rows alone), and leaves the mode alone in "
             "between. pinned=true freezes the mode; OFF stops the shadow record too.")


def promote(v: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    """Move the switch only across a bar; hold inside the dead band. Pinned and OFF are left
    alone."""
    p = gate.paths(BASE)["mode"]
    try:
        cur_doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        cur_doc = {}
    cur_doc = cur_doc if isinstance(cur_doc, dict) else {}
    cur = gate.read_mode(BASE)
    if cur_doc.get("pinned") or cur == "OFF":
        return {"mode": cur, "changed": False, "why": "pinned by the switch file; left alone"}
    want = ("LIVE" if v.get("promote") and cur != "LIVE"
            else "SHADOW" if v.get("demote") and cur == "LIVE" else cur)
    if want == cur:
        return {"mode": cur, "changed": False, "action": v.get("action", "HOLD")}
    if write:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "mode": want, "set_by": "research/spread_regime.py",
            "at": datetime.now(tz=UTC).isoformat(), "rule": MODE_RULE,
            "evidence": {k: v.get(k) for k in ("n_window", "mean_improvement_r", "se_r",
                                               "promote_bar_r", "demote_bar_r", "verdict",
                                               "action")}}, indent=1), "utf-8")
    return {"mode": want, "changed": True, "from": cur, "action": v.get("action")}


def run(write: bool = True, budget_s: float = 600.0,
        tape_root: Path | None = None) -> dict[str, Any]:
    state = build_state(budget_s, tape_root)
    n_swept = gate.sweep_expired(BASE) if write else 0
    ledger = _ledger(gate.paths(BASE)["ledger"])
    lost = lost_keys(ledger)
    scored, unscored = score(ledger, state, tape_root)
    v = verdict(scored)
    mode = promote(v, write=write)
    now = datetime.now(tz=UTC).isoformat()
    line = {"gate": "spread_regime_entry_gate", "at": now, "mode": mode["mode"],
            "binding": mode["mode"] == "LIVE", "n_unscored": unscored, "n_lost": len(lost),
            **{k: v.get(k) for k in ("verdict", "action", "n_window", "mean_improvement_r",
                                     "se_r", "promote_bar_r", "demote_bar_r",
                                     "logw_per_deferral")},
            "live_only": {k: v["live_only"].get(k) for k in ("n_window", "mean_improvement_r",
                                                             "se_r", "demote_bar_r")},
            "why": ("improvement per deferral, in R, of the side quote at release over the side "
                    "quote taken (both net of spread); positive means deferring paid. In SHADOW "
                    "it is what the gate WOULD have earned or cost; nothing was deferred. "
                    "n_lost deferrals expired with no release and are UNMEASURED, outside "
                    "the mean.")}
    gate_doc = {"schema": "spread-gate-1", "generated_at": now, "mode": mode, "verdict": v,
                "n_ledger_rows": len(ledger), "n_scored": len(scored), "n_unscored": unscored,
                "n_lost": len(lost), "lost_recent": lost[-50:], "n_swept_this_pass": n_swept,
                "scored_recent": scored[-50:], "missed_growth": [line],
                "rule": {"z_defer": gate.Z_DEFER, "z_release": gate.Z_RELEASE,
                         "max_defer_min": gate.MAX_DEFER_MIN,
                         "drift_release_frac": gate.DRIFT_RELEASE_FRAC, "n_min": gate.N_MIN,
                         "window": WINDOW, "pass_s": gate.PASS_S, "bars": v["bars"],
                         "mode_rule": MODE_RULE}}
    if write:
        OUT_STATE.parent.mkdir(parents=True, exist_ok=True)
        OUT_STATE.write_text(json.dumps(state, indent=1, default=str), "utf-8")
        OUT_GATE.write_text(json.dumps(gate_doc, indent=1, default=str), "utf-8")
    return {"state": state, "gate": gate_doc}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    d = run(write=not a.no_write, budget_s=a.budget_s)
    st, g = d["state"], d["gate"]
    print(f"SPREAD REGIME  {st['n_symbols']} symbols (ticks {st['n_tick_basis']}, bars "
          f"{st['n_bar_basis']})  regimes={st['regimes']}  stressed={st['stressed'][:10]}")
    print(f"SPREAD GATE    mode={g['mode']['mode']}  scored={g['n_scored']} "
          f"unscored={g['n_unscored']}  verdict={g['verdict']['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
