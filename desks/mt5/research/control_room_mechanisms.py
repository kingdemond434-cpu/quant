#!/usr/bin/env python3
"""REVERSE-ENGINEERED CONTROL-ROOM MECHANISMS, screened on the desk's own bars.

    python desks/mt5/research/control_room_mechanisms.py [--out PATH]

Three practices the principal cited (2026-09-30), taken down to a rule a bar file can falsify.
Each is a SCREEN: it says whether the mechanism is worth a certificate, it never is one. A screen
that passes is routed to the gauntlet like any other hypothesis; a screen that fails is a lesson.

1. REGIME-FIRST GATING (the seven-strategy operator: "the most important thing is to pay
   attention to the market regime"; his book includes a gap strategy). The desk already trades
   `overnight_gap_decay`. The operator's claim, made testable: the same weekend-gap trade earns
   more when the instrument's regime agrees with it -- fade the gap when the instrument RANGES,
   follow it ("gap and go") when it TRENDS. Arms: fade always, follow always, regime-gated. The
   regime is `libs.regime.control_room`'s label on the Friday before the gap (causal).

2. INDEX / VOLATILITY DIVERGENCE (Scherman, 491% World Cup: S&P 500 vs VIX, disclosed 75.3% hit
   rate and 3.16 profit factor, traded 2006-2018). The rule as disclosed in outline: when the
   index makes a new N-day high but the VIX does NOT make a matching N-day low, the rally is
   unconfirmed (short bias); when the index makes a new N-day low but the VIX does not make a
   new high, the selloff is unconfirmed (long bias). Held H days. Needs the index AND its vol
   index on one clock: runs wherever `US500`-like and `VIX`-like bars exist (the box), and says
   UNMEASURED -- never zero -- where they do not.

3. KOREAN AXES -- regime re-weighting trend vs range strategies under a geometric solve -- is the
   subject of `regime_allocation_contract.py`, which scores it against the live solver; this file
   does not repeat it.

Every arm is counted in `trials`; t-statistics are raw, the deflation belongs to the gauntlet.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.regime import control_room as cr  # noqa: E402

OUT = ROOT / "desks" / "mt5" / "reports" / "CONTROL_ROOM_MECHANISMS.json"
GAP_ASSETS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY",
              "GBPJPY", "AUDJPY", "XAUUSD", "XAGUSD")
#: A weekend gap smaller than this many H1 ATRs is noise, not a gap.
GAP_MIN_ATR = 0.25
#: Hours the gap trade is held from the first Monday bar.
GAP_HOLD_H = 8
INDEX_NAMES = ("US500", "US500.cash", "SPX500", "SP500", "US500Roll", "USA500")
VIX_NAMES = ("VIX", "VIX.cash", "VIXX", "VOLX", "USVIX")
DIV_N, DIV_H = 20, 5
COST_R = 0.05


def _stats(r: list[float]) -> dict[str, Any]:
    a = np.asarray(r, dtype=float)
    if a.size < 2:
        return {"n": int(a.size), "status": "INSUFFICIENT"}
    sd = float(a.std(ddof=1))
    wins, losses = a[a > 0].sum(), -a[a < 0].sum()
    return {"n": int(a.size), "mean_r": round(float(a.mean()), 4),
            "t": round(float(a.mean()) / sd * math.sqrt(a.size), 3) if sd > 0 else 0.0,
            "hit_rate": round(float((a > 0).mean()), 4),
            "profit_factor": round(float(wins / losses), 3) if losses > 0 else None}


def gap_trades(symbol: str) -> dict[str, list[float]] | None:
    """Weekend-gap trades in R (1R = one H1 ATR(20) at the gap), three arms."""
    p = cr.bar_path(symbol)
    if p is None:
        return None
    h1 = pd.read_parquet(p)
    labels = cr.label_days(cr.daily_frame(h1))
    close, high, low, opn = (h1[c].to_numpy(float) for c in ("close", "high", "low", "open"))
    tr = np.maximum(high - low, np.abs(high - np.r_[close[0], close[:-1]]))
    atr = pd.Series(tr).rolling(20).mean().to_numpy()
    idx = h1.index
    gaps = np.where(np.diff(idx.as_unit("ns").asi8) > 36 * 3600 * 10**9)[0] + 1   # first bar after a weekend
    arms: dict[str, list[float]] = {"fade": [], "follow": [], "regime_gated": [],
                                    "fade_in_range_only": [], "fade_in_trend_only": []}
    lab_days = labels.index.to_numpy(dtype=str)
    for i in gaps:
        if i + GAP_HOLD_H >= close.size or not math.isfinite(atr[i - 1]) or atr[i - 1] <= 0:
            continue
        gap = opn[i] - close[i - 1]
        if abs(gap) < GAP_MIN_ATR * atr[i - 1]:
            continue
        move = (close[i + GAP_HOLD_H - 1] - opn[i]) / atr[i - 1]
        follow = float(np.sign(gap) * move) - COST_R
        fade = float(-np.sign(gap) * move) - COST_R
        arms["fade"].append(fade)
        arms["follow"].append(follow)
        day = str(idx[i - 1])[:10]
        k = np.searchsorted(lab_days, day, side="right") - 1
        if k < 0 or labels["trend"].iloc[k] == "":
            continue
        trending = labels["trend"].iloc[k] == "trend"
        arms["regime_gated"].append(follow if trending else fade)
        arms["fade_in_trend_only" if trending else "fade_in_range_only"].append(fade)
    return arms


def screen_gap() -> dict[str, Any]:
    pooled: dict[str, list[float]] = {"fade": [], "follow": [], "regime_gated": [],
                                      "fade_in_range_only": [], "fade_in_trend_only": []}
    per: dict[str, Any] = {}
    for s in GAP_ASSETS:
        arms = gap_trades(s)
        if arms is None:
            continue
        per[s] = {a: _stats(v) for a, v in arms.items()}
        for a, v in arms.items():
            pooled[a].extend(v)
    out = {a: _stats(v) for a, v in pooled.items()}
    g, f = np.asarray(pooled["regime_gated"]), np.asarray(pooled["fade"])
    verdict = "UNMEASURED"
    rng_, trd = np.asarray(pooled["fade_in_range_only"]), np.asarray(pooled["fade_in_trend_only"])
    tilt: dict[str, Any] = {}
    if rng_.size >= 30 and trd.size >= 30:
        d = float(rng_.mean() - trd.mean())
        se = math.sqrt(rng_.var(ddof=1) / rng_.size + trd.var(ddof=1) / trd.size)
        tilt = {"range_minus_trend_r": round(d, 4), "welch_t": round(d / se, 3) if se else 0.0}
    if g.size >= 30:
        better = g.mean() > max(f.mean(), np.mean(pooled["follow"]))
        if better and out["regime_gated"].get("t", 0) >= 2.0:
            verdict = "PASS_TO_GAUNTLET"
        elif tilt and abs(tilt["welch_t"]) >= 2.0 and rng_.mean() > 0 and trd.mean() > 0:
            # Both regimes pay; one pays more. That is a SIZE tilt, which is exactly what the
            # control-room kernel does through the allocator -- never a gate that forgoes the
            # other regime's positive expectancy (Rule 2: a gate costs growth).
            verdict = "SOFT_TILT_NOT_GATE"
        else:
            verdict = "GATE_LOSES_KEEP_UNGATED"
    return {"mechanism": "regime_first_gap", "verdict": verdict, "pooled": out, "tilt": tilt,
            "per_symbol": per, "trials": 5 * max(len(per), 1),
            "rule": ("regime-gated = follow the weekend gap when the instrument's Friday "
                     "control-room label is TREND, fade it when RANGE; passes only if it beats "
                     "BOTH ungated arms pooled and its raw t >= 2")}


def _find(names: tuple[str, ...]) -> tuple[str, Path] | None:
    for n in names:
        p = cr.bar_path(n)
        if p is not None:
            return n, p
    return None


def screen_vix_divergence() -> dict[str, Any]:
    base = {"mechanism": "index_vol_divergence", "trials": 2,
            "rule": (f"short when the index makes a new {DIV_N}-day high and its vol index does "
                     f"not make a new {DIV_N}-day low; long on the mirror; hold {DIV_H} days; "
                     "1R = the index's 20-day daily sigma")}
    ix, vx = _find(INDEX_NAMES), _find(VIX_NAMES)
    if ix is None or vx is None:
        return {**base, "verdict": "UNMEASURED",
                "why": (f"no bars for {'the index' if ix is None else ''}"
                        f"{' and ' if ix is None and vx is None else ''}"
                        f"{'its vol index' if vx is None else ''} on this host; looked for "
                        f"{list(INDEX_NAMES)} / {list(VIX_NAMES)} in {[str(d) for d in cr.BAR_DIRS]}")}
    a = cr.daily_frame(pd.read_parquet(ix[1]))["close"]
    v = cr.daily_frame(pd.read_parquet(vx[1]))["close"]
    df = pd.concat({"ix": a, "vx": v}, axis=1).dropna()
    lr = np.log(df["ix"]).diff()
    sig = lr.rolling(20).std()
    hi = df["ix"] >= df["ix"].rolling(DIV_N).max()
    lo = df["ix"] <= df["ix"].rolling(DIV_N).min()
    vlo = df["vx"] <= df["vx"].rolling(DIV_N).min()
    vhi = df["vx"] >= df["vx"].rolling(DIV_N).max()
    fwd = np.log(df["ix"]).shift(-DIV_H) - np.log(df["ix"])
    arms: dict[str, list[float]] = {"short_unconfirmed_high": [], "long_unconfirmed_low": []}
    last = -DIV_H
    for t in range(DIV_N, len(df) - DIV_H):
        if t - last < DIV_H or not math.isfinite(sig.iloc[t]) or sig.iloc[t] <= 0:
            continue
        if hi.iloc[t] and not vlo.iloc[t]:
            arms["short_unconfirmed_high"].append(float(-fwd.iloc[t] / sig.iloc[t]) - COST_R)
            last = t
        elif lo.iloc[t] and not vhi.iloc[t]:
            arms["long_unconfirmed_low"].append(float(fwd.iloc[t] / sig.iloc[t]) - COST_R)
            last = t
    both = arms["short_unconfirmed_high"] + arms["long_unconfirmed_low"]
    st = _stats(both)
    verdict = ("PASS_TO_GAUNTLET" if st.get("n", 0) >= 30 and st.get("t", 0) >= 2.0
               else "NO_EDGE" if st.get("n", 0) >= 30 else "INSUFFICIENT")
    return {**base, "verdict": verdict, "index": ix[0], "vol_index": vx[0],
            "days": int(len(df)), "pooled": st, "arms": {k: _stats(x) for k, x in arms.items()}}


def run() -> dict[str, Any]:
    screens = [screen_gap(), screen_vix_divergence()]
    return {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "screens": {s["mechanism"]: s for s in screens},
            "trials": sum(int(s.get("trials", 0)) for s in screens),
            "note": ("screens, not certificates: a PASS is routed to the gauntlet, whose "
                     "deflation charges these trials; the Korean trend/range re-weighting is "
                     "scored in REGIME_ALLOCATION_CONTRACT.json")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = run()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({k: {"verdict": v["verdict"], "pooled": v.get("pooled")}
                      for k, v in doc["screens"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
