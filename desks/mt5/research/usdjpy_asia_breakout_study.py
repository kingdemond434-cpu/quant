"""USDJPY session_range_breakout (asia): why the forward is flat, and five costed variants.

REPORT-ONLY. Pre-registered in docs/research/USDJPY_ASIA_BREAKOUT_PREREGISTRATION.md, which was
committed before this script first ran. It writes one JSON report wherever `--out` points
(default reports/USDJPY_ASIA_BREAKOUT_STUDY.json, the hourly leg's artifact) and nothing else: no
certificate, no clock, no sleeve, no book, no registry. The report names input files
repo-relative and refusals by exception type only.

What it does, in the pre-registered order:

  1. Builds each variant through the canonical `external_gauntlet.build_cell` (the cell the
     certifier and the forward clock both build), on the local Fusion H1 bars.
  2. Re-prices every trade under five cost arms (ZERO .. STRESS) with the one sanctioned
     constructor, `engine.Costs.from_symbol(..., spread_pts=X)`. Zero is never the default arm;
     it is there only to reproduce the uncosted certificate.
  3. Splits in-sample (selection) / holdout / local post-start windows and reports per-trade and
     daily statistics, including the Tier S bar: the canonical deflated Sharpe at N = 5 with the
     per-cell null variance 1/(T-1). A bare t is reported for context, never as the bar.
  4. Applies the pre-registered selection rule on in-sample PRIMARY Sharpe only.
  5. Noise: the 95% band for a mean of n forward trades implied by V0's own holdout distribution.
  6. Regime: ATR and asia-range descriptors per window (the box forward window is UNMEASURED
     here: local bars end 2026-09-16).
  7. Optionally (`--gauntlet`) runs `external_gauntlet.run_gauntlet` on the five cells and keeps
     its gate verdicts. That call returns a dict; nothing it returns is persisted as authority.

Run (any box, read-only):
    python desks/mt5/research/usdjpy_asia_breakout_study.py [--out <path.json>] [--gauntlet]
On the trading box, `--bars` can point at a fresher USDJPY_H1.parquet to cover the forward
window, and `--forward-ledger` at reports/shadow/ledger_USDJPY_asia.json to read forward trades.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `usdjpy_asia_breakout_study` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import usdjpy_asia_breakout_study as M; M.main()"
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SYMBOL = "USDJPY"
FAMILY = "session_range_breakout"
BARS = DESK / "data" / "universe" / "USDJPY_H1.parquet"
OUT = DESK / "reports" / "USDJPY_ASIA_BREAKOUT_STUDY.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"

#: Pre-registered variants (see the pre-registration). Five trials; N = 5 is the bar's fixed N.
VARIANTS: dict[str, dict[str, Any]] = {
    "V0": {"rr": 2.0, "wait_bars": 12},
    "V1": {"rr": 2.0, "wait_bars": 12, "spread_gate": True},
    "V2": {"rr": 2.0, "wait_bars": 8},
    "V3": {"rr": 2.0, "wait_bars": 12, "vol_filter": "high"},
    "V4": {"rr": 2.5, "wait_bars": 12},
}

#: Cost arms: (spread points per round trip, extra adverse slip points). PRIMARY selects.
ARMS: dict[str, tuple[float, float]] = {
    "ZERO": (0.0, 0.0),
    "BENCH": (5.4, 0.0),
    "PRIMARY": (13.0, 0.0),
    "PRIMARY+SLIP": (13.0, 5.0),
    "STRESS": (26.0, 5.0),
}

START = pd.Timestamp("2018-01-01", tz="UTC")
IS_END = pd.Timestamp("2024-01-01", tz="UTC")          # exclusive
SHADOW_START = pd.Timestamp("2026-08-17", tz="UTC")    # exclusive end of the backtest
WINDOWS = {
    "in_sample": (START, IS_END),
    "holdout": (IS_END, SHADOW_START),
    "full": (START, SHADOW_START),
    "post_start_local": (SHADOW_START, pd.Timestamp("2026-12-31", tz="UTC")),
}

BAR_N = 5
DSR_BAR = 0.95
COMMISSION_PER_SIDE = 2.00
FWD_N: int = 20
FWD_MEAN: float = -0.095
REPORTED_FORWARD: dict[str, Any] = {"n": FWD_N, "mean_r": FWD_MEAN,
                                    "source": "brief (E8 forward)"}


def tier_s_dsr(r: np.ndarray) -> dict[str, Any]:
    """Canonical Tier S DSR: N = 5, null variance 1/(T-1). UNMEASURED below 3 observations."""
    from libs.validation.dsr import deflated_sharpe_ratio

    r = np.asarray(r, dtype=float)
    t = len(r)
    if t < 3 or float(np.std(r, ddof=1)) == 0.0:
        return {"status": "UNMEASURED", "T": t}
    res = deflated_sharpe_ratio(r, n_trials=BAR_N, variance_of_sharpes=1.0 / (t - 1),
                                threshold=DSR_BAR)
    return {"status": "MEASURED", "T": t, "dsr": round(res.dsr, 4),
            "sr": round(res.sr_observed, 4), "sr0": round(res.sr0_threshold, 4),
            "passed": bool(res.passed)}


def describe(r: np.ndarray) -> dict[str, Any]:
    r = np.asarray(r, dtype=float)
    n = len(r)
    if n == 0:
        return {"n": 0, "status": "UNMEASURED"}
    sd = float(np.std(r, ddof=1)) if n > 1 else float("nan")
    mean = float(np.mean(r))
    return {"n": n, "mean_r": round(mean, 4), "sd_r": round(sd, 4),
            "win_rate": round(float(np.mean(r > 0)), 4),
            "sharpe_per_trade": round(mean / sd, 4) if sd and sd == sd else None,
            "t_context_only": round(mean / sd * math.sqrt(n), 3) if sd and sd == sd else None,
            "sum_r": round(float(np.sum(r)), 3)}


def load_inputs(bars_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    from mt5desk import families

    h1 = families._h1(pd.read_parquet(bars_path))
    h1 = h1.loc[h1.index >= START]
    meta = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    return h1, meta


def build(params: Mapping[str, Any], h1: pd.DataFrame, meta: dict[str, Any]) -> dict[str, Any]:
    import external_gauntlet as eg  # type: ignore[import-not-found]

    cell = eg.build_cell(SYMBOL, FAMILY, dict(params), meta, h1_override=h1)
    if not isinstance(cell, dict) or "sigs" not in cell:
        raise RuntimeError(f"build_cell failed for {params}: {eg.LAST_BUILD_FAILURE}")
    return cell


def trade_frame(cell: dict[str, Any], meta: dict[str, Any], spread_pts: float,
                slip_pts: float) -> pd.DataFrame:
    from mt5desk.engine import Costs, run_backtest

    costs = Costs.from_symbol(meta[SYMBOL], spread_pts=spread_pts + slip_pts,
                              commission_per_lot=COMMISSION_PER_SIDE)
    res = run_backtest(cell["df"], cell["sigs"], costs)
    rows = [{"entry_time": pd.Timestamp(t.entry_time), "side": t.side, "entry": t.entry,
             "stop": t.stop, "r": float(t.r_multiple), "reason": t.reason,
             "bars_held": t.bars_held} for t in res.trades]
    df = pd.DataFrame(rows)
    if len(df):
        df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    return df


def window(df: pd.DataFrame, name: str) -> pd.DataFrame:
    lo, hi = WINDOWS[name]
    if df.empty:
        return df
    return df.loc[(df["entry_time"] >= lo) & (df["entry_time"] < hi)]


def daily(df: pd.DataFrame) -> np.ndarray:
    if df.empty:
        return np.array([])
    return np.asarray(df.groupby(df["entry_time"].dt.date)["r"].sum().to_numpy(), dtype=float)


def noise_band(r: np.ndarray, n: int, observed: float, draws: int = 20000,
               seed: int = 20261020) -> dict[str, Any]:
    r = np.asarray(r, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(r, size=(draws, n), replace=True).mean(axis=1)
    mu, sd = float(r.mean()), float(r.std(ddof=1))
    lo, hi = float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))
    return {"n": n, "backtest_mean_r": round(mu, 4), "backtest_sd_r": round(sd, 4),
            "normal_95": [round(mu - 1.96 * sd / math.sqrt(n), 4),
                          round(mu + 1.96 * sd / math.sqrt(n), 4)],
            "bootstrap_95": [round(lo, 4), round(hi, 4)],
            "observed": observed,
            "p_mean_le_observed": round(float(np.mean(means <= observed)), 4),
            "inside_95": bool(lo <= observed <= hi)}


def rolling_windows(r: np.ndarray, n: int, observed: float) -> dict[str, Any]:
    r = np.asarray(r, dtype=float)
    if len(r) < n:
        return {"status": "UNMEASURED"}
    m = np.convolve(r, np.ones(n) / n, mode="valid")
    return {"n": n, "windows": len(m),
            "share_mean_le_observed": round(float(np.mean(m <= observed)), 4),
            "share_mean_le_zero": round(float(np.mean(m <= 0)), 4),
            "p05": round(float(np.quantile(m, 0.05)), 4), "p50": round(float(np.median(m)), 4)}


def regime(h1: pd.DataFrame) -> dict[str, Any]:
    """ATR(20) in price and asia-range span (broker 00-07) per window, plus the cost in R a
    13-point spread represents on that window's typical stop (max(1.2 ATR, span))."""
    from mt5desk import families

    atr = families._atr(h1, 20)
    frame = h1.assign(atr=atr, date=h1.index.date, hour=h1.index.hour)
    win = frame.loc[frame["hour"] < 7].groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    span = (win["hi"] - win["lo"])
    at7 = frame.loc[frame["hour"] == 7, ["atr", "date"]].set_index("date")["atr"]
    joined = pd.DataFrame({"span": span, "atr": at7}).dropna()
    joined["stop"] = np.maximum(1.2 * joined["atr"], joined["span"])
    joined.index = pd.to_datetime(joined.index).tz_localize("UTC")
    out: dict[str, Any] = {}
    for name, (lo, hi) in WINDOWS.items():
        j = joined.loc[(joined.index >= lo) & (joined.index < hi)]
        if j.empty:
            out[name] = {"status": "UNMEASURED"}
            continue
        out[name] = {"days": len(j), "atr_median": round(float(j["atr"].median()), 4),
                     "span_median": round(float(j["span"].median()), 4),
                     "stop_median": round(float(j["stop"].median()), 4),
                     "spread13_as_r_median": round(float((0.013 / j["stop"]).median()), 4)}
    out["box_forward_2026-09-18_to_10-19"] = {
        "status": "UNMEASURED",
        "why": "local USDJPY_H1.parquet ends 2026-09-16; run with --bars on the box"}
    return out


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def forward_from_ledger(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"status": "UNMEASURED", "why": "the per-trade forward ledger is box-only "
                "(reports/shadow/ledger_USDJPY_asia.json is not tracked)"}
    rows = json.loads(path.read_text(encoding="utf-8"))
    fwd = [float(r["r_multiple"]) for r in rows if r.get("phase") == "forward"]
    return {"status": "MEASURED", **describe(np.array(fwd))}


def run(bars_path: Path, gauntlet: bool, forward_ledger: Path | None) -> dict[str, Any]:
    h1, meta = load_inputs(bars_path)
    report: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "prereg": "docs/research/USDJPY_ASIA_BREAKOUT_PREREGISTRATION.md",
        # repo-relative when it can be, else the file name: never an absolute path in a report
        "bars": {"path": _rel(bars_path), "first": str(h1.index[0]), "last": str(h1.index[-1])},
        "registry_median_spread_pts": meta[SYMBOL].get("median_spread_pts"),
        "arms": {k: {"spread_pts": v[0], "slip_pts": v[1]} for k, v in ARMS.items()},
        "bar": {"n_trials": BAR_N, "variance": "1/(T-1)", "dsr_threshold": DSR_BAR},
        "variants": {},
    }
    cells: dict[str, dict[str, Any]] = {}
    backtest_h1 = h1.loc[h1.index < SHADOW_START]
    for vid, params in VARIANTS.items():
        cell = build(params, h1, meta)
        cells[vid] = cell
        vrow: dict[str, Any] = {"params": params, "signals": len(cell["sigs"]),
                                "gauntlet_cost_basis": cell.get("_cost_basis"),
                                "fill_hour": cell.get("_fill_hour"), "arms": {}}
        for arm, (sp, sl) in ARMS.items():
            tf = trade_frame(cell, meta, sp, sl)
            arow: dict[str, Any] = {}
            for wname in WINDOWS:
                w = window(tf, wname)
                arow[wname] = describe(w["r"].to_numpy() if len(w) else np.array([]))
                if wname in ("full", "holdout", "in_sample"):
                    arow[wname]["tier_s_per_trade"] = tier_s_dsr(w["r"].to_numpy())
                    arow[wname]["tier_s_daily"] = tier_s_dsr(daily(w))
            if arm == "PRIMARY" and len(tf):
                fullw = window(tf, "full")
                arow["entry_hour_counts"] = {str(k): int(v) for k, v in
                                             fullw["entry_time"].dt.hour.value_counts()
                                             .sort_index().items()}
                arow["by_year"] = {str(k): describe(g["r"].to_numpy()) for k, g in
                                   fullw.groupby(fullw["entry_time"].dt.year)}
            vrow["arms"][arm] = arow
        report["variants"][vid] = vrow

    # ---- selection, exactly as pre-registered: in-sample PRIMARY per-trade Sharpe only
    def _is_sharpe(v: str) -> float:
        s = report["variants"][v]["arms"]["PRIMARY"]["in_sample"].get("sharpe_per_trade")
        return float(s) if s is not None else float("-inf")

    chosen = max(VARIANTS, key=_is_sharpe)
    c = report["variants"][chosen]["arms"]
    checks = {
        "dsr_full_primary_ge_0.95": bool(c["PRIMARY"]["full"]["tier_s_per_trade"].get("passed")),
        "holdout_mean_primary_gt_0": (c["PRIMARY"]["holdout"].get("mean_r") or 0) > 0,
        "full_mean_stress_gt_0": (c["STRESS"]["full"].get("mean_r") or 0) > 0,
    }
    report["selection"] = {"rule": "max in-sample PRIMARY per-trade Sharpe",
                           "in_sample_sharpes": {v: _is_sharpe(v) for v in VARIANTS},
                           "chosen": chosen, "checks": checks,
                           "tier_s_candidate": all(checks.values())}

    # ---- noise: V0's own PRIMARY holdout distribution, n = the forward's trade count
    v0 = trade_frame(cells["V0"], meta, *ARMS["PRIMARY"])
    v0h = window(v0, "holdout")["r"].to_numpy()
    v0z = trade_frame(cells["V0"], meta, *ARMS["ZERO"])
    report["noise"] = {
        "reported_forward": REPORTED_FORWARD,
        "band_from_v0_primary_holdout": noise_band(v0h, FWD_N,
                                                   FWD_MEAN),
        "band_from_v0_zero_cost_holdout": noise_band(window(v0z, "holdout")["r"].to_numpy(),
                                                     FWD_N,
                                                     FWD_MEAN),
        "rolling_20_trade_windows_v0_primary_full": rolling_windows(
            window(v0, "full")["r"].to_numpy(), 20, FWD_MEAN),
    }
    # The selected variant against the forward, read once (out-of-sample check only).
    ch = window(trade_frame(cells[chosen], meta, *ARMS["PRIMARY"]), "holdout")["r"].to_numpy()
    report["noise"]["band_from_chosen_primary_holdout"] = noise_band(
        ch, FWD_N, FWD_MEAN)
    report["regime"] = regime(h1)
    report["forward_ledger"] = forward_from_ledger(forward_ledger)

    if gauntlet:
        report["gauntlet_report_only"] = run_gauntlet_report_only(
            {v: build(VARIANTS[v], backtest_h1, meta) for v in VARIANTS}, meta)
    return report


def run_gauntlet_report_only(cells: dict[str, dict[str, Any]], meta: dict[str, Any]) -> Any:
    """The sealed judge's own verdicts on these five cells, kept in memory and returned.
    Its DSR uses the sweep's program-level trial count and fixed variance, NOT the Tier S bar,
    so it is reported beside the Tier S numbers above, never instead of them."""
    import external_gauntlet as eg

    try:
        out = eg.run_gauntlet(list(cells.values()), "usdjpy_asia_study_report_only", meta)
    except Exception as exc:  # report-only: a refusal is a finding, not a crash
        return {"status": "ERROR", "error": type(exc).__name__}
    verdicts = []
    for v in (out or {}).get("verdicts", []) or []:
        gates = v.get("stages") or v.get("gates") or {}
        verdicts.append({
            "cell": v.get("cell") or v.get("key"),
            "days": v.get("days"),
            "passed_all": v.get("passed"),
            "failed_gates": v.get("failed_gates") or sorted(
                k for k, g in gates.items() if isinstance(g, dict) and g.get("passed") is False),
            "gates": {k: {kk: vv for kk, vv in g.items() if not isinstance(vv, (list, dict))}
                      for k, g in gates.items() if isinstance(g, dict)},
        })
    keep = ("n_trials", "trial_count_basis", "program_level", "gate_fails", "trial_ledger",
            "survivors_passing_all", "constitution")
    return {"status": "MEASURED", "verdicts": verdicts,
            **{k: out.get(k) for k in keep if isinstance(out, dict)}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT), help="where the JSON report is written")
    ap.add_argument("--bars", default=str(BARS))
    ap.add_argument("--gauntlet", action="store_true",
                    help="also run external_gauntlet.run_gauntlet, report-only")
    ap.add_argument("--forward-ledger", default=None)
    a = ap.parse_args(argv)
    rep = run(Path(a.bars), a.gauntlet, Path(a.forward_ledger) if a.forward_ledger else None)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"selection": rep["selection"], "noise": rep["noise"]}, indent=1,
                     default=str))
    return 0

