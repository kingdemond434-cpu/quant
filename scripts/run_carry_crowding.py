"""Crowding monitor on the PRIMARY edge -- funding-compression early warning.

Round-2 external review finding: the desk's most probable failure mode for cash-and-carry is
SECULAR funding compression as the edge crowds -- a slow grind with no discrete event, invisible
to both the regime-evidence gate (which looks for volatility/inversion events) and the root-cause
buckets (which classify realized PnL surprises, not a slowly eroding forward edge). This is a
DETECTOR only: it writes web/crowding.json for monthly governance to review. It does NOT
autonomously resize the book -- an untested new signal must not touch sizing the same cycle it is
built (root-cause discipline: never modify strategy parameters from a single new signal alone).

Mirrors run_cashcarry_shadow.py's panel construction and backtest/forward split (shadow_start) for
methodological consistency: the 25th-percentile bar is drawn from the BACKTEST period only, exactly
like the existing funding_vol regime-evidence bar, so "crowded" is measured against the strategy's
own pre-registered history, not an arbitrary constant.

    python scripts/run_carry_crowding.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.data.universe import RESEARCH_TOP_N

_CRYPTO = Path("data/lake/bronze/crypto")
_METRICS = Path("data/crypto_metrics.parquet")
_SHADOW_STATE = Path("data/cashcarry_shadow_state.json")
_OUT = Path("web/crowding.json")
_TOP_N = 20
_SUSTAIN_DAYS = 14


def _panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    lake = ParquetLake("data/lake")
    fundings, bases = {}, {}
    for s in list_liquid_perps(top_n=RESEARCH_TOP_N):
        if not (_CRYPTO / s / Timeframe.D1.value).exists():
            continue
        register_instrument(InstrumentSpec(symbol=s, asset_class=AssetClass.CRYPTO, description=s))
        df = lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
        if "funding" not in df.columns or "basis" not in df.columns or len(df) < 60:
            continue
        fundings[s] = df["funding"]
        bases[s] = df["basis"]
    f = pd.DataFrame(fundings).sort_index()
    return f, pd.DataFrame(bases).reindex(f.index)


def _oi_growth() -> dict[str, object]:
    if not _METRICS.exists():
        return {"available": False, "note": "collector not yet run"}
    df = pd.read_parquet(_METRICS)
    daily_oi = df.assign(date=df["ts"].dt.date).groupby("date")["open_interest"].sum().sort_index()
    n_days = len(daily_oi)
    if n_days < 5:
        return {"available": False, "n_days": n_days, "note": "too few days"}
    first, last = float(daily_oi.iloc[0]), float(daily_oi.iloc[-1])
    growth_pct = round((last / first - 1.0) * 100, 2) if first else None
    return {"available": True, "n_days": n_days, "needs_days": 40,
            "status": "IMMATURE -- informational only, not gauntlet-tested (clock started 06-22)",
            "first_day_total_oi": round(first, 2), "latest_total_oi": round(last, 2),
            "growth_pct_since_collector_start": growth_pct}


def main() -> None:
    funding, basis = _panels()
    if funding.shape[1] < 12:
        raise SystemExit("need a liquid perp panel with funding/basis")
    top_f = funding.apply(lambda row: row.nlargest(_TOP_N).mean(), axis=1)
    top_b = basis.apply(lambda row: row.abs().nlargest(_TOP_N).mean(), axis=1)

    dates = top_f.index
    st = json.loads(_SHADOW_STATE.read_text("utf-8")) if _SHADOW_STATE.exists() else {}
    shadow_start = st.get("shadow_start")
    if shadow_start:
        fwd_mask = np.asarray(pd.to_datetime(dates) >= pd.Timestamp(shadow_start, tz="UTC"))
    else:
        fwd_mask = np.zeros(len(dates), dtype=bool)
    bt_f = top_f[~fwd_mask]

    last30, prior30 = top_f.iloc[-30:].mean(), top_f.iloc[-60:-30].mean()
    b_last30, b_prior30 = top_b.iloc[-30:].mean(), top_b.iloc[-60:-30].mean()

    bt_roll_mean = bt_f.rolling(30).mean().dropna()
    bar_25pct = float(bt_roll_mean.quantile(0.25)) if len(bt_roll_mean) >= 30 else None

    streak = 0
    if bar_25pct is not None:
        for v in top_f.iloc[::-1]:
            if v < bar_25pct:
                streak += 1
            else:
                break
    decay_warning = bool(bar_25pct is not None and streak >= _SUSTAIN_DAYS)

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "mechanism": ("secular funding compression as carry crowds -- a slow grind with no "
                      "discrete event, invisible to the regime-evidence gate and the root-cause "
                      "buckets (2026-07-12 round-2 external review finding)"),
        "top20_funding": {"last_30d_avg": round(float(last30), 6),
                          "prior_30d_avg": round(float(prior30), 6),
                          "trend": round(float(last30 - prior30), 6)},
        "top20_basis_abs": {"last_30d_avg": round(float(b_last30), 6),
                            "prior_30d_avg": round(float(b_prior30), 6),
                            "trend": round(float(b_last30 - b_prior30), 6)},
        "funding_25pct_bar_backtest": round(bar_25pct, 6) if bar_25pct is not None else None,
        "consecutive_days_below_bar": streak,
        "decay_warning": decay_warning,
        "decay_warning_rule": (f"top-{_TOP_N} avg funding below its own BACKTEST-period rolling-"
                               f"30d-mean 25th percentile for >= {_SUSTAIN_DAYS} consecutive days"),
        "oi_growth": _oi_growth(),
        "action_if_warning": ("DETECTOR ONLY this cycle -- feeds monthly governance review as "
                              "pre-registered decay evidence. Any Kelly haircut or sizing change "
                              "from this signal requires its own EV-gated, tested, ledgered change "
                              "(root-cause discipline: never resize from a single new signal "
                              "alone); do not wire autonomous action without a dedicated review."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=1), "utf-8")
    print(f"crowding monitor -> {_OUT} | decay_warning={decay_warning} "
          f"(streak={streak}d) | funding trend={out['top20_funding']['trend']} | "
          f"oi_days={out['oi_growth'].get('n_days', 'n/a')}")


if __name__ == "__main__":
    main()
