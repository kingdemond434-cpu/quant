#!/usr/bin/env python3
"""THE CONTRACT FOR REFLECTIVE FACTOR TIMING, measured on the desk's own bars.

    python desks/mt5/research/reflective_timing_contract.py [--out PATH]

`libs/research/reflective_timing` ships only if it shows gain (subsystem admission rule). This
file is the measurement: seven daily factors built from the H1 bars in `desks/mt5/universe/`, a
six-variable regime vector built from the same bars (PIT: row t uses closes up to t), and three
books compared walk-forward on the same days:

    equal    1/K in every factor, rebalanced on the same clock
    analog   regime-analogue tilt, no reflection (the "pure quant" timing)
    reflect  analogue tilt corrected by graded past calls in similar regimes

The whole grid (horizon x K analogues x method) is run and every cell is counted as a trial; the
headline is the pre-declared default (horizon 21, K 20, reflect), never the best cell. Where the
FRED archive exists (the box), the same headline also runs on the paper's MACRO regime vector and
the verdict reads that one. GAIN needs reflect over equal weight with the 90% bootstrap CI above
zero AND reflect over analog-only. The news gate is UNMEASURED: no PIT headline archive in git.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from libs.research import reflective_timing as rt  # noqa: E402

UNIVERSE = ROOT / "desks" / "mt5" / "universe"
OUT = ROOT / "desks" / "mt5" / "reports" / "REFLECTIVE_TIMING.json"
USD_BASE = ("USDJPY", "USDCHF", "USDCAD")
USD_QUOTE = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")
CARRY = ("AUDJPY", "NZDJPY", "CADJPY")
COST_PER_TURNOVER = 1e-4       # 1bp per unit of one-way weight change, charged in every factor
HEADLINE_H, HEADLINE_K = 21, 20
HEADLINE = {"horizon": HEADLINE_H, "k_analogs": HEADLINE_K, "method": "reflect"}


def load_daily_closes() -> tuple[np.ndarray, list[str], np.ndarray]:
    import pandas as pd

    frames = {}
    for p in sorted(UNIVERSE.glob("*_H1.parquet")):
        sym = p.name[: -len("_H1.parquet")]
        if sym in ("BTCUSD", "ETHUSD"):
            continue
        df = pd.read_parquet(p, columns=["close"])
        frames[sym] = df["close"].resample("1D").last()
    panel = pd.DataFrame(frames).dropna(how="all")
    panel = panel[panel.index.dayofweek < 5].ffill().dropna()
    return panel.to_numpy(float), list(panel.columns), panel.index.strftime("%Y-%m-%d").to_numpy()


def _xs_book(signal: np.ndarray, rets: np.ndarray, frac: float = 0.3) -> np.ndarray:
    """Long the top `frac`, short the bottom `frac` of yesterday's signal; net of turnover cost."""
    t, n = rets.shape
    q = max(1, round(frac * n))
    w = np.zeros((t, n))
    for i in range(1, t):
        s = signal[i - 1]
        if np.isnan(s).any():
            continue
        order = np.argsort(s)
        w[i, order[-q:]] = 1.0 / q
        w[i, order[:q]] = -1.0 / q
    gross = np.sum(w * rets, axis=1)
    turn = np.r_[0.0, np.abs(np.diff(w, axis=0)).sum(axis=1)]
    return np.asarray(gross - COST_PER_TURNOVER * turn, dtype=float)


def _rolling(x: np.ndarray, win: int, fn: str) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    for i in range(win - 1, x.shape[0]):
        seg = x[i - win + 1: i + 1]
        out[i] = seg.sum(axis=0) if fn == "sum" else seg.std(axis=0, ddof=1)
    return out


def build(closes: np.ndarray, syms: list[str]) -> tuple[np.ndarray, list[str], np.ndarray]:
    lr = np.vstack([np.zeros((1, closes.shape[1])), np.diff(np.log(closes), axis=0)])
    col = {s: i for i, s in enumerate(syms)}
    fx = [s for s in syms if not s.startswith("X")]
    fxi = [col[s] for s in fx]
    usd = np.mean([lr[:, col[s]] for s in USD_BASE if s in col]
                  + [-lr[:, col[s]] for s in USD_QUOTE if s in col], axis=0)
    carry = np.mean([lr[:, col[s]] for s in CARRY if s in col], axis=0)
    gold = lr[:, col["XAUUSD"]]
    r_fx = lr[:, fxi]
    mom63 = _rolling(r_fx, 63, "sum")
    rev5 = -_rolling(r_fx, 5, "sum")
    vol63 = _rolling(r_fx, 63, "std")
    lagged = np.sign(np.vstack([np.full((1, len(fxi)), np.nan), mom63[:-1]])) * r_fx
    ok = ~np.isnan(lagged)
    tsmom = np.where(ok.any(axis=1),
                     np.nansum(lagged, axis=1) / np.maximum(ok.sum(axis=1), 1), 0.0)
    factors = np.column_stack([
        usd, carry, gold,
        _xs_book(mom63, r_fx), _xs_book(rev5, r_fx), _xs_book(-vol63, r_fx),
        tsmom,
    ])
    names = ["usd", "jpy_carry", "gold", "xs_momentum", "xs_reversal", "xs_lowvol", "ts_momentum"]

    def cum(x: np.ndarray, w: int) -> np.ndarray:
        return _rolling(x.reshape(-1, 1), w, "sum")[:, 0]

    def vol(x: np.ndarray, w: int) -> np.ndarray:
        return _rolling(x.reshape(-1, 1), w, "std")[:, 0]

    disp = np.full(lr.shape[0], np.nan)
    corr = np.full(lr.shape[0], np.nan)
    for i in range(62, lr.shape[0]):
        seg = r_fx[i - 20: i + 1]
        disp[i] = float(np.mean(np.std(seg, axis=1)))
        c = np.corrcoef(r_fx[i - 62: i + 1].T)
        corr[i] = float(np.nanmean(np.abs(c[np.triu_indices_from(c, 1)])))
    states = np.column_stack([cum(usd, 63), vol(usd, 21), cum(gold, 63), cum(carry, 63),
                              disp, corr])
    return factors, names, states


def macro_states(days: np.ndarray) -> np.ndarray | None:
    """The paper's regime vector: FRED macro ranks (libs/portfolio/macro_state), as of the day
    BEFORE each row so an observation-dated print cannot label its own day. None off the box."""
    try:
        from libs.portfolio import macro_state
        doc = macro_state.daily_states()
    except Exception:
        return None
    dims = [dim for dim in macro_state.SERIES if dim in doc.get("states", {})]
    if len(dims) < 3:
        return None
    from datetime import date, timedelta
    out = np.full((len(days), len(dims)), np.nan)
    for i, d in enumerate(days):
        prev = (date.fromisoformat(str(d)) - timedelta(days=1)).isoformat()
        for j, dim in enumerate(dims):
            v = doc["states"][dim].get(prev)
            if v is not None:
                out[i, j] = v
    return out if np.isfinite(out).all(axis=1).mean() > 0.5 else None


def run(out: Path = OUT) -> dict[str, Any]:
    closes, syms, days = load_daily_closes()
    factors, names, states = build(closes, syms)
    start = 64                                     # first row with a full regime vector
    f, s, d = factors[start:], states[start:], days[start:]
    grid: list[dict[str, Any]] = []
    series: dict[tuple[int, int, str], np.ndarray] = {}
    for h in (5, 21):
        eq = rt.run_timing(f, s, rt.TimingConfig(horizon=h), method="equal")
        series[(h, 0, "equal")] = eq.returns
        grid.append({"horizon": h, "k_analogs": None, "method": "equal", **rt.metrics(eq.returns)})
        for k in (10, 20, 40):
            for m in ("analog", "reflect"):
                res = rt.run_timing(f, s, rt.TimingConfig(horizon=h, k_analogs=k), method=m)
                series[(h, k, m)] = res.returns
                row = {"horizon": h, "k_analogs": k, "method": m, **rt.metrics(res.returns)}
                if res.multipliers:
                    row["mean_reflect_multiplier"] = float(np.mean(res.multipliers))
                grid.append(row)
    h, k = HEADLINE_H, HEADLINE_K
    head = series[(h, k, "reflect")]
    vs_equal = rt.block_bootstrap_diff(head, series[(h, 0, "equal")])
    vs_analog = rt.block_bootstrap_diff(head, series[(h, k, "analog")])
    analog_vs_equal = rt.block_bootstrap_diff(series[(h, k, "analog")], series[(h, 0, "equal")])
    macro: dict[str, Any] = {"status": "UNMEASURED: no FRED macro archive on this machine"}
    ms = macro_states(d)
    if ms is not None:
        cfg = rt.TimingConfig(horizon=h, k_analogs=k)
        m_an = rt.run_timing(f, ms, cfg, method="analog").returns
        m_re = rt.run_timing(f, ms, cfg, method="reflect").returns
        grid += [{"horizon": h, "k_analogs": k, "method": f"{m}_macro", **rt.metrics(x)}
                 for m, x in (("analog", m_an), ("reflect", m_re))]
        macro = {"analog": rt.metrics(m_an), "reflect": rt.metrics(m_re),
                 "reflect_vs_equal": rt.block_bootstrap_diff(m_re, series[(h, 0, "equal")]),
                 "reflect_vs_analog": rt.block_bootstrap_diff(m_re, m_an)}
    trials = sum(1 for g in grid if g["method"] != "equal")
    # The verdict reads the paper's own regime vector when the box has it, else the price vector.
    judged = macro if ms is not None else {"reflect_vs_equal": vs_equal,
                                           "reflect_vs_analog": vs_analog}
    gain = (judged["reflect_vs_equal"].get("ci_lo", -1.0) > 0.0
            and judged["reflect_vs_analog"].get("sharpe_diff", 0.0) > 0.0)
    reflect_rows = [g for g in grid if g["method"] == "reflect"]
    analog_rows = {(g["horizon"], g["k_analogs"]): g for g in grid if g["method"] == "analog"}
    wins = sum(1 for g in reflect_rows
               if g["sharpe"] > analog_rows[(g["horizon"], g["k_analogs"])]["sharpe"])
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "git bars desks/mt5/universe/*_H1.parquet -> daily closes",
        "span": [str(d[0]), str(d[-1])], "n_days": len(d),
        "factors": names,
        "regime_vector": ["usd_63d", "usd_vol_21d", "gold_63d", "jpy_carry_63d",
                          "fx_dispersion_21d", "fx_abs_corr_63d"],
        "cost_per_turnover": COST_PER_TURNOVER,
        "headline_config": HEADLINE,
        "headline": {
            "equal": rt.metrics(series[(h, 0, "equal")]),
            "analog": rt.metrics(series[(h, k, "analog")]),
            "reflect": rt.metrics(head),
            "reflect_vs_equal": vs_equal,
            "reflect_vs_analog": vs_analog,
            "analog_vs_equal": analog_vs_equal,
        },
        "headline_macro_regime": macro,
        "reflect_beats_analog_cells": f"{wins}/{len(reflect_rows)}",
        "trials_charged": trials,
        "news_gate": "UNMEASURED: no point-in-time headline archive in git for this span",
        "verdict": "GAIN" if gain else "NO_GAIN_SHOWN",
        "grid": grid,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=float) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    rep = run(a.out)
    hd = rep["headline"]
    print(f"{rep['span'][0]}..{rep['span'][1]}  n={rep['n_days']}  trials={rep['trials_charged']}")
    for m in ("equal", "analog", "reflect"):
        x = hd[m]
        print(f"  {m:8s} sharpe {x['sharpe']:+.2f}  elog/yr {x['elog_ann']:+.4f}  "
              f"maxDD {x['max_dd_log']:.3f}")
    for key in ("reflect_vs_equal", "reflect_vs_analog", "analog_vs_equal"):
        b = hd[key]
        print(f"  {key:18s} dSharpe {b['sharpe_diff']:+.2f}  90% CI [{b['ci_lo']:+.2f}, "
              f"{b['ci_hi']:+.2f}]")
    print(f"  reflect beats analog in {rep['reflect_beats_analog_cells']} cells; "
          f"verdict {rep['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
