"""Compute FULL per-candidate performance + every trade from the lake, for the neon dashboard.

For each (symbol x family x param-variant) over the FX daily lake, this rebuilds the position
series from the existing generators, runs a net-of-cost backtest, extracts every trade
(entry/exit/PnL/bars-held), and computes the full performance profile:
trades, win rate, profit factor, expectancy, avg win/loss, payoff, Sharpe, Sortino, Calmar,
CAGR, max drawdown, % positive bars, avg holding period.

Writes web/data.json (consumed by the static dashboard). Reuses libs.autodiscovery.generators and
the Parquet lake; changes no engine logic. Honest: these are research backtests, not live results.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from api import db as sor  # read-only access to the system-of-record (status/lifecycle)

from libs.autodiscovery.generators import GENERATORS
from libs.autodiscovery.models import MarketSeries
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.validation import drawdown_metrics

_BRONZE = Path("data/lake/bronze")
_OUT = Path("web/data.json")
_MAJORS = {"EURUSD": -1.0, "GBPUSD": -1.0, "AUDUSD": -1.0, "NZDUSD": -1.0,
           "USDJPY": 1.0, "USDCHF": 1.0, "USDCAD": 1.0}
_COST_PER_SIDE = {AssetClass.FX: 8e-5, AssetClass.METAL: 1.5e-4, AssetClass.ENERGY: 2e-4}
_PPY = 252.0


def _discover() -> dict[str, AssetClass]:
    found: dict[str, AssetClass] = {}
    if not _BRONZE.exists():
        return found
    for ac_dir in _BRONZE.iterdir():
        if not ac_dir.is_dir():
            continue
        try:
            ac = AssetClass(ac_dir.name)
        except ValueError:
            continue
        for sym in ac_dir.iterdir():
            if (sym / Timeframe.D1.value).exists():
                found[sym.name] = ac
    return found


def _safe(x: float) -> float:
    return float(x) if math.isfinite(x) else 0.0


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0)) if len(equity) else 0.0


def _extract_trades(close: np.ndarray, pos: np.ndarray, cost_side: float) -> dict[str, Any]:
    ret = np.zeros_like(close)
    ret[1:] = close[1:] / close[:-1] - 1.0
    lag = np.zeros_like(pos)
    lag[1:] = pos[:-1]                                   # lag-1: trade today on yesterday's signal
    turnover = np.abs(np.diff(pos, prepend=0.0))
    net = lag * ret - turnover * cost_side
    equity = np.cumprod(1.0 + net)

    trades: list[dict[str, Any]] = []
    i = 0
    n = len(pos)
    while i < n:
        if pos[i] == 0:
            i += 1
            continue
        side = np.sign(pos[i])
        j = i
        while j + 1 < n and np.sign(pos[j + 1]) == side and pos[j + 1] != 0:
            j += 1
        seg = net[i + 1: j + 2]                          # realised over the holding window
        tr = float(np.sum(seg))
        trades.append({
            "dir": "long" if side > 0 else "short",
            "entry_i": int(i), "exit_i": int(j),
            "bars": int(j - i + 1),
            "entry": round(float(close[i]), 5), "exit": round(float(close[min(j + 1, n - 1)]), 5),
            "ret": round(tr, 5),
        })
        i = j + 1

    return {"net": net, "equity": equity, "trades": trades}


def _metrics(net: np.ndarray, equity: np.ndarray, trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = [t["ret"] for t in trades if t["ret"] > 0]
    losses = [t["ret"] for t in trades if t["ret"] < 0]
    gross_w = sum(wins)
    gross_l = abs(sum(losses))
    mu = float(np.mean(net)) if len(net) else 0.0
    sd = float(np.std(net)) if len(net) else 0.0
    downside = net[net < 0]
    dsd = float(np.std(downside)) if len(downside) else 0.0
    n_years = max(1e-9, len(net) / _PPY)
    cagr = _safe(equity[-1] ** (1.0 / n_years) - 1.0) if len(equity) and equity[-1] > 0 else -1.0
    mdd = _max_drawdown(equity)
    dd = drawdown_metrics.report(np.log1p(net)) if len(net) else {
        "ulcer_index": float("nan"), "martin_ratio": float("nan"),
        "return_over_max_drawdown": float("nan")}
    win_rate = len(wins) / len(trades) if trades else 0.0
    avg_w = float(np.mean(wins)) if wins else 0.0
    avg_l = float(np.mean([abs(x) for x in losses])) if losses else 0.0
    return {
        "trades": len(trades),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(_safe(gross_w / gross_l), 3) if gross_l > 0 else 0.0,
        "expectancy": round(win_rate * avg_w - (1 - win_rate) * avg_l, 6),
        "avg_win": round(avg_w, 5), "avg_loss": round(avg_l, 5),
        "payoff": round(_safe(avg_w / avg_l), 3) if avg_l > 0 else 0.0,
        "sharpe": round(_safe(mu / sd * math.sqrt(_PPY)), 3) if sd > 0 else 0.0,
        "sortino": round(_safe(mu / dsd * math.sqrt(_PPY)), 3) if dsd > 0 else 0.0,
        "cagr": round(cagr, 4),
        "total_return": round(_safe(equity[-1] - 1.0), 4) if len(equity) else 0.0,
        "max_drawdown": round(mdd, 4),
        "calmar": round(_safe(cagr / abs(mdd)), 3) if mdd < 0 else 0.0,
        # Path-severity trio from libs.validation.drawdown_metrics (wired 2026-08-19: the module
        # shipped 08-01 with zero production callers while this script computed a weaker inline
        # max-drawdown one line up). report() wants LOG returns; net is arithmetic per bar.
        "ulcer_index": round(_safe(float(dd["ulcer_index"])), 4),
        "martin_ratio": round(_safe(float(dd["martin_ratio"])), 3),
        "return_over_max_drawdown": round(_safe(float(dd["return_over_max_drawdown"])), 3),
        "pct_pos_bars": round(float(np.mean(net > 0)), 4) if len(net) else 0.0,
        "avg_bars_held": round(float(np.mean([t["bars"] for t in trades])), 1) if trades else 0.0,
    }


def _monthly(net: np.ndarray, dates: list[str]) -> list[dict[str, Any]]:
    """Monthly NET return % = product of (1+daily net) within each calendar month - 1."""
    by_month: dict[str, float] = {}
    for r, d in zip(net, dates, strict=False):
        ym = d[:7]
        by_month[ym] = (1.0 + by_month.get(ym, 0.0)) * (1.0 + float(r)) - 1.0
    return [{"ym": k, "ret": round(v, 5)} for k, v in sorted(by_month.items())]


def _governance() -> dict[str, Any]:
    """Real lifecycle/governance state from the system-of-record (read-only)."""
    rows = sor.query("SELECT status, COUNT(*) AS n FROM research_candidates GROUP BY status")
    counts = {r["status"]: int(r["n"]) for r in rows}
    registry = counts.get("registry", 0)
    promoted = registry + counts.get("paper", 0) + counts.get("shadow", 0)
    return {
        "ladder": {
            "rejected": counts.get("rejected", 0),
            "shadow": counts.get("shadow", 0),
            "paper": counts.get("paper", 0),
            "registry": registry,
            "archived": counts.get("archived", 0),
        },
        "survivors": registry,
        "promoted": promoted,
        "pending_approval": registry,   # REGISTRY = eligible for human sign-off before any capital
        "decay_tracked": promoted,      # decay/half-life/re-validation apply to promoted alphas
        "note": (
            "Real capital is never auto-allocated. Decay, half-life and re-validation engage only "
            "for promoted alphas; with 0 survivors the registry and approval queue are empty."
        ),
    }


def _downsample(equity: np.ndarray, dates: list[str], n: int = 240) -> list[dict[str, Any]]:
    idx = (
        range(len(equity)) if len(equity) <= n
        else np.linspace(0, len(equity) - 1, n).astype(int)
    )
    return [{"t": dates[i], "v": round(float(equity[i]), 5)} for i in idx]


def main() -> None:
    available = _discover()
    if not available:
        raise SystemExit("no lake data; run scripts/ingest_history.py first")
    for sym, ac in available.items():
        register_instrument(InstrumentSpec(symbol=sym, asset_class=ac, description=sym))
    lake = ParquetLake("data/lake")

    symbols = [s for s in _MAJORS if s in available]
    frames = {s: lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
              for s in symbols}
    # Broad-USD index (self-excluded per symbol) for the cross-asset family.
    usd_by_symbol = {}
    for s in symbols:
        rets = [sign * frames[o]["close"].pct_change()
                for o, sign in _MAJORS.items() if o in frames and o != s]
        usd_by_symbol[s] = (1.0 + pd.concat(rets, axis=1).mean(axis=1).fillna(0.0)).cumprod()

    candidates: list[dict[str, Any]] = []
    for sym in symbols:
        df = frames[sym]
        dates = [t.date().isoformat() for t in df.index]
        close = df["close"].to_numpy("float64")
        ref = usd_by_symbol[sym].reindex(df.index, method="ffill").to_numpy("float64")
        series = MarketSeries(
            close=close, high=df["high"].to_numpy("float64"), low=df["low"].to_numpy("float64"),
            volume=df["volume"].to_numpy("float64"),
            hour=np.array([t.hour for t in df.index], dtype="float64"), ref_close=ref,
        )
        cost = _COST_PER_SIDE.get(available[sym], 1e-4)
        for spec in GENERATORS:
            for variant in spec.param_variants:
                try:
                    pos = np.asarray(spec.fn(series, dict(variant)), dtype="float64")
                except Exception:
                    continue
                bt = _extract_trades(close, pos, cost)
                if bt["trades"] == [] and float(np.sum(np.abs(pos))) == 0:
                    continue  # inert (e.g. session on D1) -> skip
                m = _metrics(bt["net"], bt["equity"], bt["trades"])
                pstr = ",".join(f"{k}={v}" for k, v in variant.items()) or "—"
                candidates.append({
                    "id": f"{sym}:{spec.family.value}:{spec.subtype}:{pstr}",
                    "symbol": sym, "family": spec.family.value, "subtype": spec.subtype,
                    "params": pstr, "mechanism": spec.mechanism.value,
                    "metrics": m,
                    "pnl_usd": round(m["total_return"] * 100_000),  # on a $100k notional (backtest)
                    "equity": _downsample(bt["equity"], dates),
                    "monthly": _monthly(bt["net"], dates),
                    "trades": bt["trades"][-500:],   # cap trade list for display
                })

    candidates.sort(key=lambda c: c["metrics"]["sharpe"], reverse=True)
    payload = {
        # pd.Timestamp.utcnow() is deprecated and REMOVED in pandas 4 (Pandas4Warning).
        # Still tz-aware, so this was never a naive/aware correctness bug -- it is a
        # scheduled breakage. The only genuine instance behind gap #50.
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "universe": symbols,
        "n_candidates": len(candidates),
        "cost_model": "per-symbol per-side (FX 0.8 bps); net-of-cost",
        "note": "Research backtests on lake history. NOT live results. 0 net-of-cost survivors.",
        "governance": _governance(),
        "candidates": candidates,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, separators=(",", ":")), "utf-8")
    print(f"wrote {_OUT}  candidates={len(candidates)}  size={_OUT.stat().st_size // 1024} KB")
    if candidates:
        best = candidates[0]
        print(f"top by Sharpe: {best['id']}  sharpe={best['metrics']['sharpe']} "
              f"trades={best['metrics']['trades']} win_rate={best['metrics']['win_rate']}")


if __name__ == "__main__":
    main()
