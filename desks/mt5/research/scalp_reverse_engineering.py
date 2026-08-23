"""Falsify the screenshot-style XAUUSD scalp on M1/M5/M15 broker bars.

The screenshots imply a mechanism (sweep/reclaim or displacement, several equal tickets, common
exit), not a complete strategy.  This study predefines a small family, selects on the first 60%
of time, and reports only untouched last-40% results.  Multiple tickets are one correlated basket.
The promotable implementation reserves four 0.25R risk slices and keeps the initial stop fixed;
the screenshot-like equal-lot recovery arm is diagnostic only because its loss grows with depth.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.validation.dsr import probabilistic_sharpe_ratio  # noqa: E402

DATA = DESK / "data" / "universe"
OUT = DESK / "reports" / "scalp_reverse_engineering.json"
VERSION = "screenshot-scalp-2026-08-22-a"
FUSION_COMMISSION_PRICE = 0.045  # $4.50 round turn / 100 oz XAUUSD contract


@dataclass(frozen=True)
class Config:
    family: str
    lookback: int
    displacement_atr: float
    stop_atr: float
    target_atr: float
    max_hold: int
    mode: str


def risk_sized_units(entry: float, stop: float, slice_r: float) -> float:
    """Units whose complete stop-out consumes exactly ``slice_r`` of basket risk."""
    distance = abs(entry - stop)
    if not math.isfinite(distance) or distance <= 0 or not 0 < slice_r <= 1:
        raise ValueError("entry/stop distance and risk slice must be positive")
    return slice_r / distance


def _signals(df: pd.DataFrame, cfg: Config) -> np.ndarray:
    high, low, opn, close = (df[c].to_numpy(float) for c in ("high", "low", "open", "close"))
    tr = pd.concat(
        [df.high - df.low, (df.high - df.close.shift()).abs(),
         (df.low - df.close.shift()).abs()], axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, min_periods=14).mean().to_numpy(float)
    prior_hi = df.high.shift(2).rolling(cfg.lookback).max().to_numpy(float)
    prior_lo = df.low.shift(2).rolling(cfg.lookback).min().to_numpy(float)
    prev_hi, prev_lo = np.roll(high, 1), np.roll(low, 1)
    prev_open, prev_close = np.roll(opn, 1), np.roll(close, 1)
    prev_atr = np.roll(atr, 1)
    sweep = np.zeros(len(df), dtype=np.int8)
    sweep[(prev_hi > prior_hi) & (prev_close < prior_hi)] = -1
    sweep[(prev_lo < prior_lo) & (prev_close > prior_lo)] = 1
    rng = prev_hi - prev_lo
    disp = np.zeros(len(df), dtype=np.int8)
    good = (rng >= cfg.displacement_atr * prev_atr) & (rng > 0)
    body_fraction = np.divide(
        prev_close - prev_open, rng, out=np.zeros_like(rng), where=rng > 0,
    )
    disp[good & (body_fraction > 0.5)] = 1
    disp[good & (body_fraction < -0.5)] = -1
    if cfg.family == "sweep_reclaim":
        return sweep
    if cfg.family == "displacement_continuation":
        return disp
    return np.where(sweep != 0, sweep, disp).astype(np.int8)


def _atr(df: pd.DataFrame) -> np.ndarray:
    tr = pd.concat(
        [df.high - df.low, (df.high - df.close.shift()).abs(),
         (df.low - df.close.shift()).abs()], axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / 14, min_periods=14).mean().to_numpy(float)


def simulate(
    df: pd.DataFrame,
    cfg: Config,
    *,
    cost: str = "fusion_zero",
    signal_override: np.ndarray | None = None,
    atr_override: np.ndarray | None = None,
    detailed: bool = False,
) -> np.ndarray | list[dict]:
    """Return non-overlapping basket R. Same-bar ambiguity is always stop-first."""
    sig = _signals(df, cfg) if signal_override is None else signal_override
    atr = _atr(df) if atr_override is None else atr_override
    if len(sig) != len(df) or len(atr) != len(df):
        raise ValueError("signal and ATR arrays must align exactly with bars")
    opn, high, low, close = (df[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    point = 0.01
    spreads = df.get("spread", pd.Series(0.0, index=df.index)).to_numpy(float) * point
    out: list[dict] = []
    i, n = max(40, cfg.lookback + 3), len(df) - 1
    event_indices = np.flatnonzero(sig != 0)
    event_pos = int(np.searchsorted(event_indices, i))
    while event_pos < len(event_indices):
        i = int(event_indices[event_pos])
        if i >= n:
            break
        direction = int(sig[i])
        a = float(atr[i])
        if not math.isfinite(a) or a <= 0:
            event_pos += 1
            continue
        first = float(opn[i])
        stop = first - direction * cfg.stop_atr * a
        # (entry, units in initial-risk currency). Four slices together can lose at most 1R.
        if cfg.mode == "single":
            entries = [(first, risk_sized_units(first, stop, 1.0))]
        else:
            entries = [(first, risk_sized_units(first, stop, 0.25))]
        cost_r = 0.0
        if cost != "frictionless":
            cost_r += entries[0][1] * (spreads[i] + FUSION_COMMISSION_PRICE)
        exit_price, j = float(close[i]), i
        for j in range(i + 1, min(n, i + cfg.max_hold) + 1):
            total_units = sum(u for _, u in entries)
            avg = sum(p * u for p, u in entries) / total_units
            target = avg + direction * cfg.target_atr * a
            if (direction > 0 and low[j] <= stop) or (direction < 0 and high[j] >= stop):
                exit_price = stop
                break
            if (direction > 0 and high[j] >= target) or (direction < 0 and low[j] <= target):
                exit_price = target
                break
            if cfg.mode == "bounded_structural" and len(entries) < 4 and sig[j] == direction:
                p = float(opn[j])
                distance = direction * (p - stop)
                if distance > 0:
                    units = risk_sized_units(p, stop, 0.25)
                    entries.append((p, units))
                    if cost != "frictionless":
                        cost_r += units * (spreads[j] + FUSION_COMMISSION_PRICE)
            exit_price = float(close[j])
        pnl_r = sum(u * direction * (exit_price - p) for p, u in entries) - cost_r
        out.append({
            "opened_at": df.index[i].isoformat(), "closed_at": df.index[j].isoformat(),
            "direction": direction, "depth": len(entries), "r": float(pnl_r),
            "risk_allocated_r": 1.0 if cfg.mode == "single" else 0.25 * len(entries),
        })
        event_pos = int(np.searchsorted(event_indices, j + 1))
    if detailed:
        return out
    return np.asarray([row["r"] for row in out], dtype=float)


def _stats(rs: np.ndarray) -> dict:
    if len(rs) == 0:
        return {"n": 0, "mean_r": None, "t_stat": None, "psr": None}
    sd = float(rs.std(ddof=1)) if len(rs) > 1 else 0.0
    return {
        "n": len(rs), "mean_r": round(float(rs.mean()), 5),
        "t_stat": round(float(rs.mean() / (sd / math.sqrt(len(rs)))), 3) if sd else 0.0,
        "psr": round(float(probabilistic_sharpe_ratio(rs, sr_benchmark=0.0)), 6)
        if len(rs) >= 3 and sd else 0.0,
        "win_rate": round(float((rs > 0).mean()), 4),
        "worst_r": round(float(rs.min()), 4), "total_r": round(float(rs.sum()), 2),
    }


def _configs(timeframe: str) -> list[Config]:
    holds = {"M1": (5, 15), "M5": (3, 9), "M15": (2, 6)}[timeframe]
    return [Config(*values) for values in itertools.product(
        ("sweep_reclaim", "displacement_continuation", "sweep_or_displacement"),
        (20,), (1.5,), (1.0, 1.5), (0.5, 1.0), holds,
        ("single", "bounded_structural"),
    )]


def run() -> dict:
    report: dict = {
        "version": VERSION, "evidence": "broker_native_bar_spread_plus_fusion_zero_commission",
        "fusion_cost": "$4.50/lot round turn plus each bar's recorded broker spread",
        "selection": "first 60% chronological; report/promote on untouched last 40%",
        "same_bar_policy": "stop_first", "timeframes": {},
    }
    promote: list[dict] = []
    for tf in ("M1", "M5", "M15"):
        path = DATA / f"XAUUSD_{tf}.parquet"
        if not path.exists():
            report["timeframes"][tf] = {"status": "UNMEASURED", "reason": "missing broker bars"}
            continue
        df = pd.read_parquet(path).sort_index()
        cut = int(len(df) * 0.60)
        train, test = df.iloc[:cut], df.iloc[cut:]
        configs = _configs(tf)
        ranked = []
        for cfg in configs:
            rs = simulate(train, cfg)
            ranked.append((float(rs.mean()) if len(rs) else -math.inf, cfg))
        # One winner per mechanism and implementation mode, not one cherry-picked global winner.
        selected = []
        for family in ("sweep_reclaim", "displacement_continuation", "sweep_or_displacement"):
            for mode in ("single", "bounded_structural"):
                eligible = [(score, cfg) for score, cfg in ranked
                            if cfg.family == family and cfg.mode == mode]
                _, winner = max(eligible, key=lambda row: row[0])
                oos = simulate(test, winner)
                zero = simulate(test, winner, cost="frictionless")
                stats, zero_stats = _stats(oos), _stats(zero)
                row = {"config": winner.__dict__, "oos": stats, "frictionless_ablation": zero_stats}
                # Existing original research screen: PSR >= .95 vs SR0=0. Shadow only.
                row["original_gate"] = bool(stats["n"] >= 30 and stats["psr"] >= 0.95)
                row["disposition"] = "SHADOW_CANDIDATE" if row["original_gate"] else "REJECT"
                selected.append(row)
                if row["original_gate"]:
                    promote.append({"timeframe": tf, **row})
        report["timeframes"][tf] = {
            "status": "MEASURED", "bars": len(df), "train_bars": len(train),
            "oos_bars": len(test), "configs_tried": len(configs), "selected": selected,
        }
    report["shadow_candidates"] = promote
    report["verdict"] = ("SHADOW_CANDIDATES" if promote else
                         "REJECTED: no costed untouched-OOS arm cleared the original gate")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), "utf-8")
    return report


def main() -> int:
    report = run()
    print(json.dumps({"verdict": report["verdict"],
                      "shadow_candidates": len(report["shadow_candidates"])}, indent=2))
    for tf, result in report["timeframes"].items():
        print(tf, result.get("status"), "bars=", result.get("bars", 0))
        for row in result.get("selected", []):
            print(" ", row["config"]["family"], row["config"]["mode"], row["oos"],
                  row["disposition"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
