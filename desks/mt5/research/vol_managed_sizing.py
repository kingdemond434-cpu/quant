#!/usr/bin/env python3
"""DOES GARCH-SCALED SIZING RAISE E[log W]? The Rule-1 proof a vol forecast needs before it sizes.

    python desks/mt5/research/vol_managed_sizing.py [--fraction 0.01] [--boot 1000]

The principal (2026-11-13): "yes use garch". `garch_vs_ewma` measures that GARCH FORECASTS
better than EWMA (27/31 symbols on the holdout). A better forecast is not yet more money: the live
book sizes by ATR stops and the allocator's fraction, and nowhere reads a variance forecast. The
one place a forecast can enter is a VOL-MANAGED CAPITAL MODIFIER (Moreira-Muir 2017): scale each
sleeve's risk by the ratio of its symbol's normal volatility to tomorrow's forecast,

    w_t = clip( sigma_bar_t / sigma_hat_t , W_MIN, W_MAX )

where sigma_hat_t is the forecast for day t from returns strictly before it, and sigma_bar_t is
the root-mean of the forecasts over the trailing year before t. That is two-sided by construction
(bigger in calm, smaller in storms; GROWTH_GOVERNANCE capital_modifiers law) and causal.

GROWTH GOVERNANCE RULE 1: a modifier must PROVE it raises robust forward E[log W]. This module is
that proof, run per sleeve and on the pooled book, for three variants on the same days:

    none     the sleeve as it trades today
    ewma     scaled by the RiskMetrics forecast
    garch    scaled by the walk-forward GARCH forecast (the `garch_vs_ewma` default)

and, so leverage is never mistaken for timing, a LEVERAGE-MATCHED baseline: `none` scaled by the
variant's own mean weight. A variant earns only if it beats BOTH `none` and its matched baseline,
with the stationary block-bootstrap CI on the pooled per-year Delta log W above zero.

THE EVIDENCE is the allocator's own daily-R matrix (`pf_allocator_cache/daily_r.parquet`, one
column per sleeve, R per day), each sleeve mapped to its symbol by name. A sleeve whose symbol
cannot be read is UNMEASURED, never assumed.

Writes reports/VOL_MANAGED_SIZING.json. SIZES NOTHING: adoption is a capital-modifier change with
its own review, and only a variant this report marks EARNS may be proposed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import garch as G  # noqa: E402
from libs.research.volatility_signals import EWMA_LAMBDA  # noqa: E402

from research import proposer_common as pc  # noqa: E402

REPORT = _DESK / "reports" / "VOL_MANAGED_SIZING.json"
MATRIX = _DESK / "data" / "pf_allocator_cache" / "daily_r.parquet"
W_MIN, W_MAX = 0.5, 2.0
REF_DAYS = 252
MIN_BARS_PER_DAY = 12
MIN_ACTIVE_DAYS = 60
FRACTION = 0.01
BLOCK = 20
VARIANTS = ("none", "ewma", "garch")


def daily_closes(h1: pd.DataFrame) -> pd.Series:
    c = pd.to_numeric(h1["close"], errors="coerce")
    c = c[np.isfinite(c) & (c > 0)]
    day = c.index.floor("D")
    counts = c.groupby(day).size()
    last = c.groupby(day).last()
    return last[counts >= MIN_BARS_PER_DAY]


def forecasts_by_day(h1: pd.DataFrame) -> dict[str, pd.Series]:
    """Per UTC day d: the variance forecast FOR d's return from returns strictly before d."""
    last = daily_closes(h1)
    r = np.diff(np.log(last.to_numpy(dtype="float64")))
    days = last.index[1:]
    warm = r[:500]
    h0 = float(np.var(warm[np.isfinite(warm)])) if len(warm) else 0.0
    ew = G.filter_variance(r, 0.0, 1.0 - EWMA_LAMBDA, EWMA_LAMBDA, h0=h0)[:-1]
    ga = G.walk_forward_variance(r)
    return {"ewma": pd.Series(ew, index=days), "garch": pd.Series(ga, index=days)}


def weights(var: pd.Series) -> pd.Series:
    """w_t = clip(sigma_bar / sigma_hat), sigma_bar from forecasts over the trailing year BEFORE t."""
    v = var.where(var > 0)
    ref = v.shift(1).rolling(REF_DAYS, min_periods=REF_DAYS // 2).mean()
    return (np.sqrt(ref / v)).clip(W_MIN, W_MAX)


def symbol_of(name: str, symbols: set[str]) -> str | None:
    n = str(name)
    if n.lower().startswith("gold_") or n.lower().startswith("xau"):
        return "XAUUSD"
    head = n.split(".")[0].split("@")[0].split("_")[0].upper()
    if head in symbols:
        return head
    for s in sorted(symbols, key=len, reverse=True):
        if n.upper().startswith(s):
            return s
    return None


def _log_growth(r: np.ndarray, f: float) -> np.ndarray:
    x = np.maximum(1.0 + f * r, 1e-9)
    return np.log(x)


def _block_boot(d: np.ndarray, reps: int, seed: int = 11) -> tuple[float, float]:
    """90% CI of mean(d) by stationary block bootstrap (mean block BLOCK days)."""
    n = len(d)
    if n < 2 * BLOCK:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    p = 1.0 / BLOCK
    means = np.empty(reps)
    for b in range(reps):
        idx = np.empty(n, dtype=np.int64)
        i = int(rng.integers(n))
        for k in range(n):
            idx[k] = i
            i = int(rng.integers(n)) if rng.random() < p else (i + 1) % n
        means[b] = d[idx].mean()
    lo, hi = np.quantile(means, [0.05, 0.95])
    return float(lo), float(hi)


def evaluate(daily: pd.DataFrame, sym_of: dict[str, str], fc: dict[str, dict[str, pd.Series]],
             *, fraction: float = FRACTION, reps: int = 1000) -> dict[str, Any]:
    """Per sleeve and pooled: E[log W] per year for each variant, and the leverage-matched check."""
    per: dict[str, Any] = {}
    pooled: dict[str, list[pd.Series]] = {v: [] for v in VARIANTS}
    pooled_matched: dict[str, list[pd.Series]] = {v: [] for v in VARIANTS}
    for name in daily.columns:
        sym = sym_of.get(name)
        if not sym or sym not in fc:
            per[name] = {"status": "UNMEASURED", "why": "symbol not read from the sleeve name"
                         if not sym else f"no forecast for {sym}"}
            continue
        r = pd.to_numeric(daily[name], errors="coerce").fillna(0.0)
        w = {m: weights(fc[sym][m]).reindex(r.index) for m in ("ewma", "garch")}
        ok = r.index[np.isfinite(w["ewma"]) & np.isfinite(w["garch"])]
        r = r.reindex(ok)
        active = int((r != 0).sum())
        if active < MIN_ACTIVE_DAYS:
            per[name] = {"status": "UNMEASURED", "why": f"{active} active days in the forecast "
                                                        f"window, need {MIN_ACTIVE_DAYS}"}
            continue
        series = {"none": r, "ewma": r * w["ewma"].reindex(ok), "garch": r * w["garch"].reindex(ok)}
        row: dict[str, Any] = {"status": "MEASURED", "symbol": sym, "days": len(r),
                               "active_days": active}
        for v, s in series.items():
            pooled[v].append(s)
            row[f"elogw_yr_{v}"] = round(252 * float(_log_growth(s.to_numpy(), fraction).mean()), 5)
        for v in ("ewma", "garch"):
            on = r != 0
            mw = float(w[v].reindex(ok)[on].mean())
            row[f"mean_weight_{v}"] = round(mw, 4)
            matched = r * mw
            pooled_matched[v].append(matched)
            row[f"elogw_yr_matched_{v}"] = round(
                252 * float(_log_growth(matched.to_numpy(), fraction).mean()), 5)
        per[name] = row
    out: dict[str, Any] = {"fraction": fraction, "sleeves": per}
    meas = [k for k, v in per.items() if v.get("status") == "MEASURED"]
    out["sleeves_measured"] = len(meas)
    if not meas:
        out["verdict"] = {v: "UNMEASURED" for v in ("ewma", "garch")}
        return out
    book = {v: pd.concat(pooled[v], axis=1).fillna(0.0).sum(axis=1) for v in VARIANTS}
    lg = {v: _log_growth(book[v].to_numpy(), fraction) for v in VARIANTS}
    out["book_elogw_yr"] = {v: round(252 * float(lg[v].mean()), 5) for v in VARIANTS}
    verdict: dict[str, Any] = {}
    for v in ("ewma", "garch"):
        matched = pd.concat(pooled_matched[v], axis=1).fillna(0.0).sum(axis=1)
        lm = _log_growth(matched.to_numpy(), fraction)
        d_none = lg[v] - lg["none"]
        d_match = lg[v] - lm
        ci_n = _block_boot(d_none, reps)
        ci_m = _block_boot(d_match, reps)
        wins = sum(1 for k in meas if per[k][f"elogw_yr_{v}"] > per[k]["elogw_yr_none"])
        earns = (np.isfinite(ci_n[0]) and ci_n[0] > 0 and np.isfinite(ci_m[0]) and ci_m[0] > 0)
        verdict[v] = {
            "delta_vs_none_yr": round(252 * float(d_none.mean()), 5),
            "ci90_vs_none_yr": [round(252 * x, 5) for x in ci_n],
            "delta_vs_leverage_matched_yr": round(252 * float(d_match.mean()), 5),
            "ci90_vs_leverage_matched_yr": [round(252 * x, 5) for x in ci_m],
            "sleeves_improved": wins, "of": len(meas),
            "EARNS": bool(earns)}
    g, e = lg["garch"], lg["ewma"]
    ci_ge = _block_boot(g - e, reps)
    verdict["garch_vs_ewma"] = {"delta_yr": round(252 * float((g - e).mean()), 5),
                                "ci90_yr": [round(252 * x, 5) for x in ci_ge]}
    out["verdict"] = verdict
    return out


def load_matrix(path: Path | None = None) -> pd.DataFrame | None:
    p = path or MATRIX
    try:
        m = pd.read_parquet(p)
    except (OSError, ValueError, ImportError):
        return None
    m.index = pd.DatetimeIndex(pd.to_datetime(m.index, utc=True, errors="coerce")).floor("D")
    return m[~m.index.isna()]


def run(*, fraction: float = FRACTION, reps: int = 1000,
        daily: pd.DataFrame | None = None, source: str | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    if daily is None:
        daily = load_matrix()
        source = str(MATRIX.relative_to(_DESK)) if daily is not None else None
    if daily is None or daily.empty:
        rep: dict[str, Any] = {"generated_at": now, "status": "UNMEASURED",
                               "why": f"no allocator daily-R matrix at {MATRIX.name}"}
    else:
        have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
        sym_of = {c: s for c in daily.columns if (s := symbol_of(c, have))}
        fc: dict[str, dict[str, pd.Series]] = {}
        for s in sorted(set(sym_of.values())):
            d = pc.bars(s)
            if d is not None and len(d) > 24 * 600:
                fc[s] = forecasts_by_day(d)
        rep = {"generated_at": now, "status": "MEASURED", "source": source,
               "rule": {"w": f"clip(sigma_bar/sigma_hat, {W_MIN}, {W_MAX})",
                        "sigma_bar": f"root-mean forecast over the trailing {REF_DAYS} days",
                        "earns": "pooled 90% block-bootstrap CI of Delta E[log W] above zero "
                                 "against BOTH the unscaled book and the leverage-matched book"},
               **evaluate(daily, sym_of, fc, fraction=fraction, reps=reps)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fraction", type=float, default=FRACTION)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args(argv)
    rep = run(fraction=a.fraction, reps=a.boot)
    print(json.dumps({k: rep.get(k) for k in ("status", "why", "sleeves_measured",
                                               "book_elogw_yr", "verdict")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

