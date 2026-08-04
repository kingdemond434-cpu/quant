#!/usr/bin/env python3
"""Walk-forward falsification run of the intraday rotation/continuation hypothesis.

Pre-registered: docs/research/INTRADAY_ROTATION_PREREGISTRATION.md. Engine:
libs/research/intraday_rotation.py (lookahead-probed by its test suite before this ran).
Protocol, verbatim from the registration: 6-month train / 2-month test rolling walk-forward,
OOS ONLY reported; per-window the best config on TRAIN (by expectancy, n>=20) is the one that
trades TEST; the full 540-config grid count is what the Sharpe is deflated by; nulls are random
entries through the IDENTICAL exit machinery, and buy-and-hold.

    PYTHONPATH=. python scripts/run_intraday_rotation.py
"""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.intraday_rotation import (
    EXIT_VARIANTS,
    K_GRID,
    M_GRID,
    N_GRID,
    STOP_ATR_BUFFER,
    TAKER_BPS,
    Trade,
    _resolve,
    atr,
    bootstrap_sizing,
    deflated_sharpe,
    expectancy,
    half_kelly,
    run_config,
    wilson_ci,
)

_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _ROOT / "data" / "binance_vision"
_OUT = _ROOT / "reports" / "intraday_rotation.json"
_PLOTS = _ROOT / "reports"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
BARS_PER_DAY = 288
TRAIN = 182 * BARS_PER_DAY
TEST = 61 * BARS_PER_DAY
MIN_TRAIN_TRADES = 20
N_NULL_REPS = 50
RISK_FRACS = (0.0025, 0.005, 0.01, 0.02, 0.03, 0.05)

ROT_GRID = [("rotation", n, 0, m, v)
            for n, m, v in itertools.product(N_GRID, M_GRID, EXIT_VARIANTS)]
CONT_GRID = [("continuation", n, k, m, v)
             for n, k, m, v in itertools.product(N_GRID, K_GRID, M_GRID, EXIT_VARIANTS)]
N_CONFIGS_TOTAL = (len(ROT_GRID) + len(CONT_GRID)) * len(SYMBOLS)   # deflation denominator


def _load(sym: str) -> dict[str, np.ndarray]:
    f = next(_CACHE.glob(f"{sym}-5m-*.npz"))
    with np.load(f, allow_pickle=True) as z:
        return {k: z[k] for k in z.files}


def _null_run(data: dict[str, np.ndarray], cfg: tuple, n_trades: int, lo: int, hi: int,
              rng: np.random.Generator) -> float:
    """Random entries, IDENTICAL exit machinery: same M/variant, ATR-buffer stop off the entry
    bar, coin-flip side. This is null (a) of the registration -- what the exits alone earn."""
    _, _n, _k, m, variant = cfg
    high, low, close = data["high"], data["low"], data["close"]
    a = atr(high, low, close)
    times = data["open_time"]
    f_t = data.get("funding_time", np.empty(0))
    f_r = data.get("funding_rate", np.empty(0))
    rs: list[float] = []
    tries = 0
    while len(rs) < n_trades and tries < n_trades * 20:
        tries += 1
        i = int(rng.integers(lo, hi - m - 2))
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        side = 1 if rng.random() < 0.5 else -1
        stop_px = (low[i] - STOP_ATR_BUFFER * a[i] if side > 0
                   else high[i] + STOP_ATR_BUFFER * a[i])
        if abs(close[i] - stop_px) <= 0:
            continue
        opp = close[i] + side * 3.0 * abs(close[i] - stop_px)
        t = _resolve(side, i, float(close[i]), float(stop_px), high, low, close, float(opp),
                     variant, m, times, f_t, f_r, "NULL", TAKER_BPS)
        if t is not None:
            rs.append(t.r_multiple)
    return float(np.mean(rs)) if rs else 0.0


def main() -> int:
    oos: dict[str, list[Trade]] = {"rotation": [], "continuation": []}
    oos_meta: dict[str, list[dict[str, Any]]] = {"rotation": [], "continuation": []}
    selections: list[dict[str, Any]] = []
    plateau: dict[str, dict[str, list[float]]] = {"rotation": {}, "continuation": {}}
    null_means: dict[str, list[float]] = {"rotation": [], "continuation": []}
    bh_test_returns: list[float] = []
    unfilled = {"continuation_signals_unfilled": 0, "continuation_signals_filled": 0}
    rng = np.random.default_rng(2026)

    for sym in SYMBOLS:
        data = _load(sym)
        n_bars = len(data["close"])
        w = 0
        while TRAIN + (w + 1) * TEST <= n_bars:
            tr_lo, tr_hi = w * TEST, w * TEST + TRAIN
            te_lo, te_hi = tr_hi, tr_hi + TEST
            bh_test_returns.append(float(data["close"][te_hi - 1] / data["close"][te_lo] - 1))
            for grid, strat in ((ROT_GRID, "rotation"), (CONT_GRID, "continuation")):
                best, best_exp = None, -1e9
                for cfg in grid:
                    _, n, k, m, v = cfg
                    r = run_config(data, symbol=sym, strategy=strat, n=n, k=k, m=m,
                                   variant=v, start=tr_lo, stop=tr_hi)
                    ex = expectancy(r.r_series())
                    key = f"N{n}/K{k}/M{m}/{v}"
                    plateau[strat].setdefault(key, []).append(ex["exp_r"])
                    if ex["n"] >= MIN_TRAIN_TRADES and ex["exp_r"] > best_exp:
                        best, best_exp = cfg, ex["exp_r"]
                if best is None:
                    selections.append({"symbol": sym, "window": w, "strategy": strat,
                                       "selected": None,
                                       "why": f"no config reached {MIN_TRAIN_TRADES} "
                                              "train trades"})
                    continue
                _, n, k, m, v = best
                t_res = run_config(data, symbol=sym, strategy=strat, n=n, k=k, m=m,
                                   variant=v, start=te_lo, stop=te_hi)
                if strat == "continuation":
                    unfilled["continuation_signals_unfilled"] += t_res.n_unfilled
                    unfilled["continuation_signals_filled"] += len(t_res.trades)
                oos[strat].extend(t_res.trades)
                oos_meta[strat].extend(
                    {"symbol": sym, "window": w,
                     "ts": float(data["open_time"][t.entry_i])} for t in t_res.trades)
                selections.append({"symbol": sym, "window": w, "strategy": strat,
                                   "selected": f"N{n}/K{k}/M{m}/{v}",
                                   "train_exp_r": round(best_exp, 4),
                                   "oos_trades": len(t_res.trades)})
                if t_res.trades:
                    nulls = [_null_run(data, best, len(t_res.trades), te_lo, te_hi, rng)
                             for _ in range(max(3, N_NULL_REPS // 10))]
                    null_means[strat].extend(nulls)
            w += 1
        print(f"{sym}: done ({w} windows)")

    doc: dict[str, Any] = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "MEASURED",
        "preregistration": "docs/research/INTRADAY_ROTATION_PREREGISTRATION.md",
        "protocol": {"train_bars": TRAIN, "test_bars": TEST, "symbols": list(SYMBOLS),
                     "n_configs_deflation": N_CONFIGS_TOTAL,
                     "oos_only": True},
        "selections": selections,
        "unfilled": unfilled,
    }

    for strat in ("rotation", "continuation"):
        trades = oos[strat]
        meta = oos_meta[strat]
        r = np.asarray([t.r_multiple for t in trades])
        ex = expectancy(r)
        wins = int(np.sum(r > 0))
        lo_ci, hi_ci = wilson_ci(wins, len(r))
        sizing = bootstrap_sizing(r, risk_fracs=RISK_FRACS) if len(r) >= 20 else []
        hk = half_kelly(r)
        dsr = deflated_sharpe(ex["sharpe_r"], max(len(r), 2), N_CONFIGS_TOTAL)
        nulls = np.asarray(null_means[strat])
        null_beat = (float(np.mean(ex["exp_r"] > nulls)) if len(nulls) else None)
        # buckets
        years: dict[str, dict[str, float]] = {}
        hours: dict[int, list[float]] = {}
        for t, mrow in zip(trades, meta, strict=True):
            y = datetime.fromtimestamp(mrow["ts"] / 1000, tz=UTC).year
            years.setdefault(str(y), {"n": 0, "sum_r": 0.0})
            years[str(y)]["n"] += 1
            years[str(y)]["sum_r"] += t.r_multiple
            hours.setdefault(t.hour_utc, []).append(t.r_multiple)
        doc[strat] = {
            "oos": ex, "win_ci_95": [round(lo_ci, 3), round(hi_ci, 3)],
            "expectancy_reportable": len(r) >= 200,
            "deflated_sharpe_prob": round(dsr, 4),
            "vs_random_entry_null": {"n_null_runs": len(nulls),
                                     "null_mean_exp_r": (round(float(np.mean(nulls)), 4)
                                                         if len(nulls) else None),
                                     "frac_nulls_beaten": null_beat},
            "half_kelly_risk_frac": hk,
            "principal_ask_3_5_pct_inside_half_kelly_ci": bool(
                hk["lo"] <= 0.03 and hk["hi"] >= 0.05) if hk["half_kelly"] > 0 else False,
            "sizing_sweep": sizing,
            "by_year": {y: {"n": v["n"], "exp_r": round(v["sum_r"] / max(v["n"], 1), 4)}
                        for y, v in sorted(years.items())},
            "by_utc_hour_top": sorted(
                ((h, round(float(np.mean(v)), 3), len(v)) for h, v in hours.items()
                 if len(v) >= 10), key=lambda x: -x[1])[:5],
            "exit_reasons": {k: int(sum(1 for t in trades if t.exit_reason == k))
                             for k in ("stop", "target", "time")},
        }

    # plateau: mean train expectancy per config across windows (the plateau-vs-peak exhibit)
    doc["parameter_plateau"] = {
        strat: sorted(((k, round(float(np.mean(v)), 4), len(v))
                       for k, v in plateau[strat].items()), key=lambda x: -x[1])[:12]
        for strat in plateau
    }
    doc["buy_and_hold"] = {"mean_test_window_return": round(float(np.mean(bh_test_returns)), 4),
                           "n_windows": len(bh_test_returns)}

    # deployment gate, verbatim from the registration. "Deflated Sharpe > 1.0" is read strictly:
    # the OOS ANNUALISED Sharpe after costs must exceed 1.0 AND survive deflation over the full
    # config count (DSR probability >= 0.95). Trades/year converts the per-trade statistic; the
    # elapsed OOS span is the denominator, not the bar count (bar count is not evidence).
    gate: dict[str, Any] = {}
    for strat in ("rotation", "continuation"):
        d = doc[strat]
        r = np.asarray([t.r_multiple for t in oos[strat]])
        meta = oos_meta[strat]
        year_ok = all(v["exp_r"] > 0 for v in d["by_year"].values()) if d["by_year"] else False
        sizing_ok = False
        for row in d["sizing_sweep"]:
            if row["risk_frac"] == 0.01:
                sizing_ok = row["p95_max_dd"] < 0.25
        ann_sr = 0.0
        if len(r) > 2 and meta:
            span_y = max((max(m["ts"] for m in meta) - min(m["ts"] for m in meta))
                         / (365.25 * 86400 * 1000), 1e-6)
            sd = float(np.std(r, ddof=1))
            if sd > 0:
                ann_sr = float(np.mean(r) / sd * np.sqrt(len(r) / span_y))
        d["oos_annualised_sharpe_after_costs"] = round(ann_sr, 3)
        checks = {
            "oos_trades_over_200": len(r) > 200,
            "positive_expectancy_all_year_buckets": year_ok,
            "deflated_sharpe_over_1": bool(ann_sr > 1.0
                                           and d["deflated_sharpe_prob"] >= 0.95),
            "max_dd_under_25pct_p95_at_1pct_risk": sizing_ok,
        }
        gate[strat] = {**checks, "oos_annualised_sharpe": round(ann_sr, 3),
                       "dsr_prob": d["deflated_sharpe_prob"],
                       "verdict": "GO" if all(checks.values())
                                  else "NO-GO: paper trade >=100 further trades"}
    doc["deployment_gate"] = gate

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    _plots(oos, doc)
    for strat in ("rotation", "continuation"):
        d = doc[strat]
        print(f"{strat}: n={d['oos']['n']} exp_r={d['oos']['exp_r']:.4f} "
              f"win={d['oos']['win']:.2f} CI={d['win_ci_95']} dsr_p={d['deflated_sharpe_prob']}")
    print(f"wrote {_OUT}")
    return 0


def _plots(oos: dict[str, list[Trade]], doc: dict[str, Any]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        doc["plots"] = "matplotlib absent -- data tables in JSON only"
        return
    for strat, trades in oos.items():
        if not trades:
            continue
        r = np.asarray([t.r_multiple for t in trades])
        eq = np.cumprod(1 + 0.01 * r)
        peak = np.maximum.accumulate(eq)
        fig, ax = plt.subplots(3, 1, figsize=(9, 10))
        ax[0].plot(eq)
        ax[0].set_title(f"{strat}: OOS equity at 1% risk/trade ({len(r)} trades)")
        ax[1].fill_between(range(len(eq)), 1 - eq / peak, color="tab:red", alpha=0.6)
        ax[1].set_title("underwater")
        ax[2].hist(r, bins=40)
        ax[2].set_title("R-multiple distribution (net)")
        fig.tight_layout()
        fig.savefig(_PLOTS / f"intraday_{strat}.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
