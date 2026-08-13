#!/usr/bin/env python3
"""STAGE-A SCREEN: Coinbase-vs-Binance BTC spot premium -- a FREE substitute for CME futures basis
(pre-registered BEFORE any result is read).

================================================================================================
THIS DOCSTRING IS THE PRE-REGISTRATION, written before this screen was ever run against real
data. Nothing below it may be edited in response to a result -- if a trial's construction needs
to change, that is a NEW pre-registration and a new dated file, not an edit to this one.
================================================================================================

WHY THIS CLASS
--------------
scripts/screen_cme_basis.py tests whether regulated institutional demand (priced via CME's
cash-settled BTC futures basis) carries forward information about BTC returns beyond what perp
funding already shows -- but that screen is DATA-BLOCKED on this desk: CME futures history is a
one-time paid drop (R0143: buying a licensed feed is a principal decision, never a collector's),
and it has not been purchased. Found 2026-08-13 hunting a free alternative per the desk's own
FREE-DATA-FIRST / PAID-SOURCE-SUBSTITUTION principle (docs/policy/PRE_DEEPSEEK_MASTER_MANDATE.md):
no existing organ tests the same regulated-vs-offshore mechanism through a free construction. This
file is that substitute.

TEMPERING PRIOR, on the record before any number is read: a RELATED but DISTINCT mechanism --
BTC-native exchange netflow via CoinMetrics (scripts/screen_exchange_netflow.py, disposed R0024)
-- already ran over 3,265 days and came back SCREEN-WEAK, with its best cell's raw IC -0.0345
(mechanism-correct sign) SIGN-FLIPPING to residual IC +0.0124 once the desk's own de-contamination
gate was applied: what looked like real edge was same-period contamination, not lead. This axis
inherits the identical de-contamination gate (libs.research.axis_screen.stage_a_screen) for
exactly that reason, and the right prior walking in is skepticism, not expectation.

1. THE ECONOMIC MECHANISM -- WHO PAYS WHOM, AND WHY THE PAYMENT PERSISTS
------------------------------------------------------------------------
Coinbase Exchange disproportionately serves US-regulated, KYC'd institutional and retail demand
(Coinbase Custody, Coinbase Prime's institutional client base, US retail under domestic
compliance); Binance's spot/perp flow is dominated by offshore, leverage-heavy, crypto-native
demand. A Coinbase price that runs rich or cheap relative to Binance -- the "Coinbase premium" --
is a lower-fidelity, spot-market analogue of the SAME divergence CME-basis-minus-perp-funding was
built to isolate: regulated-cohort positioning that the offshore-native desk does not otherwise
observe. WHO PAYS: whichever side's flow is momentarily inelastic pays the spread until arbitrage
capital (constrained by KYC transfer times, not instantaneous) closes it.

WHAT WOULD KILL THE STORY. If cross-exchange arbitrageurs close the spread within the same UTC
day the premium is measured, the premium and next-day return will show only same-period
contamination -- exactly the CoinMetrics finding above, and exactly what the de-contamination
gate is built to catch. This screen is built to be able to report that honestly.

2. THE FALSIFIABLE CLAIM
------------------------
  H0 (the desk's standing prior, and what a null result CONFIRMS):
      For every pre-registered (construction x horizon) cell, the Coinbase premium observed at
      the moment it became readable has zero forward information about BTCUSDT's return: |IC| <
      0.03.

  H1 (what would refute H0):
      At least one cell shows |IC| >= 0.03 with best timing Sharpe >= 0.5, passes the angle-20
      de-contamination gate, and is POWERED by the harness's own detection floor.

DATA -- ZERO NEW COLLECTOR NEEDED (activate, not build). scripts/collect_primary_market_flow.py
already fetches Coinbase BTC-USD daily UTC closes as its ETF-flow target leg (observation records
with source="price_btc_coinbase" in data/primary_market_flow.jsonl, scheduled 23:41 UTC daily,
~1450-day bootstrap via Coinbase's public keyless candles endpoint). This screen only READS that
already-collected series -- it adds no new network dependency. Binance BTCUSDT D1 closes come
from the bronze crypto lake, the same source and registration convention
scripts/screen_cme_basis.py and scripts/run_discovery.py already use.

3. TRIAL GRID (ALL three run and logged every time, winner or not)
---------------------------------------------------------------------
  T1  premium_level        -> BTC 1d fwd return   (raw divergence)
  T2  premium_change_1d    -> BTC 1d fwd return    (impulse -- did today's premium MOVE)
  T3  premium_level        -> BTC 5d fwd return, NON-OVERLAPPING 5-day sampling (screen_cme_
      basis.py's own non-overlap discipline against overlap-inflated t-stats)

Raw signal values (not pre-z-scored) are passed to stage_a_screen, which applies its own causal
rolling z-score (zwin=20) -- pre-z-scoring here would double-transform the signal, which every
other axis screen on this desk deliberately avoids.

ALIGNMENT: both legs are UTC daily closes; premium[t] is computed from day t's closes and predicts
BTCUSDT's day t+1 return via stage_a_screen's own internal forward shift -- conservatively no
look-ahead (the same alignment screen_cme_basis.py uses for its own daily cell).

MEASURED 2026-08-13: unlike the stablecoin-flow screen (R0437's neighbor), Coinbase's ~1450-day
bootstrap means this screen can be POWERED on its very first real run rather than waiting on a
forward clock -- the first scheduled fire is the real verdict, not a "day N/40" wait.

INTENDED CADENCE (header comment only -- ops/crontab.manifest is owned by another pass):
    # 5 0 * * *  daily, 00:05 UTC -- 24 minutes after collect_primary_market_flow.py's 23:41 run,
    #            so the day's Coinbase observation is always on disk before this screen reads it.

    python scripts/screen_coinbase_premium.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument  # noqa: E402
from libs.data.lake import Layer, ParquetLake, Timeframe  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402

_FLOW_LEDGER = Path("data/primary_market_flow.jsonl")
_SOURCE = "price_btc_coinbase"
_OUT = Path("reports/axis_screens/coinbase_premium_20260813.json")
_MIN_ROWS = 60


def _coinbase_closes() -> pd.Series:
    """Daily Coinbase BTC-USD closes already collected by collect_primary_market_flow.py.

    Reads observation rows only (never 'run' status rows), deduped by stamp keeping the LATEST
    first_seen_utc for a given day -- the ledger is append-only and a stamp can appear more than
    once across bootstrap + daily runs. Absent/unreadable ledger returns an empty series, never a
    crash: this container has no local data/ (gitignored), so an empty result here is expected,
    not an error.
    """
    try:
        lines = _FLOW_LEDGER.read_text("utf-8").splitlines()
    except OSError:
        return pd.Series(dtype="float64")
    by_day: dict[str, float] = {}
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") != "observation" or row.get("source") != _SOURCE:
            continue
        stamp, value = row.get("stamp"), row.get("value")
        if stamp is None or value is None:
            continue
        try:
            by_day[str(stamp)] = float(value)
        except (TypeError, ValueError):
            continue
    if not by_day:
        return pd.Series(dtype="float64")
    idx = pd.to_datetime(sorted(by_day), utc=True)
    return pd.Series([by_day[d] for d in sorted(by_day)], index=idx)


def _btc_closes() -> pd.Series:
    """BTCUSDT D1 close, from the same bronze crypto lake and registration convention
    scripts/screen_cme_basis.py and scripts/run_discovery.py already use."""
    register_instrument(InstrumentSpec(symbol="BTCUSDT", asset_class=AssetClass.CRYPTO,
                                       description="BTCUSDT"))
    lake = ParquetLake("data/lake")
    df = lake.read_bars(Layer.BRONZE, "BTCUSDT", Timeframe.D1)
    if df.empty:
        return pd.Series(dtype="float64")
    return df.set_index(pd.to_datetime(df["timestamp"], utc=True))["close"]


def _downsample(sig: np.ndarray, ret_1d: np.ndarray, step: int) -> tuple[np.ndarray, np.ndarray]:
    """Non-overlapping step-day periods: signal at period start, compounded period return.
    Identical construction to scripts/screen_cme_basis.py's own _downsample."""
    n = len(sig) // step
    s = np.array([sig[i * step] for i in range(n)])
    r = np.array([float(np.prod(1.0 + ret_1d[i * step:(i + 1) * step]) - 1.0) for i in range(n)])
    return s, r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the artifact to stdout")
    args = ap.parse_args()

    coinbase = _coinbase_closes()
    binance = _btc_closes()
    if coinbase.empty or binance.empty:
        out = {"status": "DATA-BLOCKED",
               "why": (f"{_FLOW_LEDGER} has no {_SOURCE!r} observations" if coinbase.empty
                       else "BTCUSDT bronze lake absent on this box"),
               "coinbase_rows": len(coinbase), "binance_rows": len(binance)}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"screen_coinbase_premium: {out['status']} -- {out['why']}")
        if args.json:
            print(json.dumps(out, indent=1))
        return 0

    df = pd.DataFrame({"coinbase": coinbase, "binance": binance}).dropna()
    df["premium_level"] = df["coinbase"] / df["binance"] - 1.0
    df["premium_change_1d"] = df["premium_level"].diff()
    df["ret_1d"] = df["binance"].pct_change()
    df = df.dropna(subset=["premium_level", "premium_change_1d", "ret_1d"])

    if len(df) < _MIN_ROWS:
        out = {"status": "INSUFFICIENT-DATA",
               "why": f"{len(df)} aligned days, need >= {_MIN_ROWS}",
               "coinbase_rows": len(coinbase), "binance_rows": len(binance), "aligned_rows": len(df)}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"screen_coinbase_premium: {out['status']} -- {out['why']}")
        if args.json:
            print(json.dumps(out, indent=1))
        return 0

    ret_arr = df["ret_1d"].to_numpy("float64")
    trials = [
        stage_a_screen(df["premium_level"].to_numpy("float64"), ret_arr,
                       name="premium_level->btc_1d"),
        stage_a_screen(df["premium_change_1d"].to_numpy("float64"), ret_arr,
                       name="premium_change_1d->btc_1d"),
    ]
    s5, r5 = _downsample(df["premium_level"].to_numpy("float64"), ret_arr, 5)
    trials.append(stage_a_screen(s5, r5, name="premium_level->btc_5d", horizon_days=5.0, zwin=12))

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "coinbase_premium",
        "n_days": len(df),
        "range": [str(df.index.min().date()), str(df.index.max().date())],
        "alignment": "same-day UTC closes; stage_a_screen predicts target_ret[t+1] from "
                     "signal[t] internally (no look-ahead).",
        "tempering_prior": "related BTC-native exchange netflow (screen_exchange_netflow.py, "
                           "R0024) screened SCREEN-WEAK with a same-period-contamination sign "
                           "flip on de-contam -- this axis inherits the same gate for that reason",
        "why_this_axis": "free substitute for CME-basis (screen_cme_basis.py, DATA-BLOCKED, "
                         "R0143 licensed-feed decision not made) -- same regulated-vs-offshore "
                         "mechanism, built entirely from already-collected free data",
        "trials": trials,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"screen_coinbase_premium: {len(df)} aligned days [{out['range'][0]}..{out['range'][1]}]")
    for t in trials:
        print(f"  {t['name']:24} n={t.get('n', 0):>5} {t.get('verdict', '?')}")
    if args.json:
        print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    _law_guard()
    raise SystemExit(main())
