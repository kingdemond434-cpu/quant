"""Causal compendium screens: endpoint HP trend, futures trend and contrarian.

Signals use genuine dated GC/CL contract curves; P&L is measured on the corresponding Fusion MT5
CFD proxy with recorded spread and contractual commission. This is a screen with zero promotion
authority. Positive dated series must still enter the universal ten-gate program.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
for path in (BASE, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

CURVES = BASE / "data" / "futures_curves"
UNIVERSE = BASE / "data" / "universe"
OUT = BASE / "reports" / "curve_strategy_screen.json"
SERIES = BASE / "data" / "cell_series" / "curve_compendium"
PROXIES = {"GC": ("XAUUSD",), "CL": ("XTIUSD", "USOIL", "WTIUSD")}
REGISTRY = BASE / "research" / "futures_state_sources.json"
#: The registry rows the GC/CL curves come from: Yahoo's delayed quotes of CME/COMEX/NYMEX
#: contracts. A cell may be MINTED from them only while every one of these rows reads OPEN.
CURVE_SOURCES = ("yahoo_futures", "cme_settlements")


def mint_permission(registry: Path = REGISTRY) -> dict:
    """May the curves mint trading cells? (Governance ruling 2026-11-11 00:41Z.)

    Only when every CURVE_SOURCES row in futures_state_sources.json reads terms OPEN. IDEAS_ONLY,
    HELD, any other class, a missing row or an unreadable registry all answer no: the screen may
    still read the curves and propose ideas, but writes no cell series, and the universal gate
    reads none. Fails closed by construction."""
    classes: dict[str, str] = {}
    try:
        doc = json.loads(registry.read_text(encoding="utf-8"))
        rows = {r.get("id"): r for r in doc.get("sources") or [] if isinstance(r, dict)}
        for sid in CURVE_SOURCES:
            classes[sid] = str((rows.get(sid) or {}).get("terms") or "MISSING")
    except (OSError, ValueError, AttributeError) as exc:
        return {"mint": False, "classes": {sid: "UNREADABLE" for sid in CURVE_SOURCES},
                "why": f"registry unreadable: {type(exc).__name__}"}
    closed = {sid: c for sid, c in classes.items() if c != "OPEN"}
    return {"mint": not closed, "classes": classes,
            "why": "every curve source reads OPEN" if not closed else
            "ideas only: " + ", ".join(f"{k}={v}" for k, v in sorted(closed.items())),
            "reopens": "every CURVE_SOURCES row in futures_state_sources.json reads terms OPEN"}


def endpoint_hp(values: pd.Series, window: int = 128, lam: float = 129_600.0) -> pd.Series:
    """Rolling HP endpoint only; later observations can never revise an earlier value."""
    if window < 8 or lam <= 0:
        raise ValueError("HP window >=8 and lambda >0 are required")
    eye = np.eye(window)
    second_difference = np.diff(eye, n=2, axis=0)
    factor = cho_factor(eye + lam * second_difference.T @ second_difference, check_finite=False)
    raw = np.log(pd.to_numeric(values, errors="coerce").to_numpy(float))
    out = np.full(len(raw), np.nan)
    for end in range(window - 1, len(raw)):
        sample = raw[end - window + 1:end + 1]
        if np.isfinite(sample).all():
            out[end] = cho_solve(factor, sample, check_finite=False)[-1]
    return pd.Series(out, index=values.index)


def strategy_positions(front: pd.Series) -> dict[str, pd.Series]:
    log_price = np.log(front.astype(float))
    hp = endpoint_hp(front)
    trend_63 = np.sign(log_price.diff(63)).shift(1).fillna(0.0)
    hp_trend = np.sign(hp.diff(5)).shift(1).fillna(0.0)
    move_5 = log_price.diff(5)
    scale = move_5.rolling(126, min_periods=60).std()
    contrarian = (-np.sign(move_5) * (move_5.abs() > scale)).shift(1).fillna(0.0)
    return {"endpoint_hp_trend": hp_trend, "futures_trend_63d": trend_63,
            "futures_contrarian_5d": contrarian}


def costed_returns(
    close: pd.Series, position: pd.Series, meta: dict, *, spread_crossings: float = 2.0,
) -> pd.Series:
    aligned = pd.concat([close.rename("close"), position.rename("position")], axis=1).dropna()
    gross = aligned["position"] * aligned["close"].pct_change().fillna(0.0)
    contract = max(float(meta.get("contract_size", 1.0)), 1.0)
    spread_price = (float(meta.get("median_spread_pts", 0.0))
                    * float(meta.get("tick_size", 0.0)) * spread_crossings)
    commission_price = 4.50 / contract
    turnover = aligned["position"].diff().abs().fillna(aligned["position"].abs())
    friction = turnover * (spread_price + commission_price) / aligned["close"]
    return (gross - friction).rename("net_return")


def _proxy(root: str) -> tuple[str, Path] | None:
    for symbol in PROXIES[root]:
        path = UNIVERSE / f"{symbol}_H1.parquet"
        if path.exists():
            return symbol, path
    return None


def run() -> dict:
    meta = json.loads((UNIVERSE / "universe.json").read_text("utf-8"))
    rows = []
    permit = mint_permission()
    if permit["mint"]:
        SERIES.mkdir(parents=True, exist_ok=True)
    for root in PROXIES:
        curve_path, proxy = CURVES / f"{root}_curve.parquet", _proxy(root)
        if not curve_path.exists() or proxy is None:
            rows.append({"root": root, "status": "UNMEASURED", "why": "curve or MT5 proxy absent"})
            continue
        symbol, proxy_path = proxy
        curve = pd.read_parquet(curve_path)
        front = (curve[curve["curve_rank"] == 1].set_index("date")["close"]
                 .sort_index().groupby(level=0).last())
        h1 = pd.read_parquet(proxy_path).sort_index()
        close = h1["close"].resample("1D").last().dropna()
        close.index = pd.to_datetime(close.index, utc=True).normalize()
        for family, position in strategy_positions(front).items():
            returns = costed_returns(close, position, meta.get(symbol, {})).dropna()
            if permit["mint"]:
                stress = costed_returns(
                    close, position, meta.get(symbol, {}), spread_crossings=3.0,
                ).reindex(returns.index)
                pd.concat([returns, stress.rename("stress_x3_return")], axis=1).to_parquet(
                    SERIES / f"{root}_{family}.parquet", compression="zstd",
                )
            mean, sd = float(returns.mean()), float(returns.std(ddof=1))
            t_stat = mean / (sd / math.sqrt(len(returns))) if len(returns) > 1 and sd > 0 else 0.0
            positive = len(returns) >= 60 and mean > 0
            rows.append({"root": root, "symbol": symbol, "family": family, "status": "MEASURED",
                         "n_days": len(returns), "mean_daily_net": mean, "t_stat": t_stat,
                         "disposition": ("REJECT" if not positive else "GAUNTLET_REQUIRED"
                                         if permit["mint"] else "IDEA_ONLY")})
    ideas = [r for r in rows if r.get("disposition") == "IDEA_ONLY"]
    # The fence's two-sided missed-growth line: what it holds back (positive screens that could
    # not be minted) and what reopens it. No certificate exists for them, so no E[log W] is
    # claimed: UNMEASURED, said with the count, never a clean zero.
    missed = {"gate": "curve_terms_fence", "verdict": "NOT_BINDING" if permit["mint"] or not ideas
              else "UNMEASURED", "held_cells": len(ideas),
              "held": [f"{r['root']}_{r['family']}" for r in ideas],
              "why": permit["why"], "reopens": permit.get("reopens")}
    report = {"rows": rows, "promotion_authority": False, "mint_permission": permit,
              "missed_growth": [missed],
              "next_gate": "universal original ten gates over the complete dated series matrix"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
