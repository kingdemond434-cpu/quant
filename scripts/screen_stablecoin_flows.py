#!/usr/bin/env python3
"""STAGE-A SCREEN: on-chain stablecoin exchange-flow + supply-growth axis (pre-registered
BEFORE any result is read).

================================================================================================
THIS DOCSTRING IS THE PRE-REGISTRATION, written before this screen was ever run against real
data. Nothing below it may be edited in response to a result -- if a trial's construction needs
to change, that is a NEW pre-registration and a new dated file, not an edit to this one.
================================================================================================

WHY THIS CLASS
--------------
scripts/run_stablecoin_flows.py has archived a daily on-chain snapshot (data/stablecoin_flows_
archive.json: USDT+USDC balances on exchange wallets, plus global USDT+USDC L1 totalSupply())
since its first run, on a declared 40-day forward clock (web/stablecoin_flows.json's own
"validate signal->return at day 40, not before"). That day has now passed (2026-08-13: the live
clock reads 41/40d) and nothing has ever screened it -- the archiver computes netflow/supply
deltas for DISPLAY but contains no validation logic at all, and no other organ in this tree
consumes data/stablecoin_flows_archive.json. A mature, keyless, orthogonal signal was sitting
untested; this file is that test.

TEMPERING PRIOR, on the record before any number is read: a RELATED but DISTINCT mechanism --
BTC-native exchange netflow via CoinMetrics (scripts/screen_exchange_netflow.py, disposed R0024)
-- already ran over 3,265 days and came back SCREEN-WEAK, with its best cell's raw IC -0.0345
(mechanism-correct sign) SIGN-FLIPPING to residual IC +0.0124 once the desk's own de-contamination
gate was applied: what looked like real edge was same-period contamination, not lead. That is a
different construction (BTC-native asset flow vs. stablecoin dry-powder reserves/minting) so it
does not substitute for testing this signal, but it is the right prior to hold walking in: this
mechanism family has a track record of looking good raw and dying under de-contamination, and
this screen inherits that same de-contamination gate (libs.research.axis_screen.stage_a_screen)
for exactly that reason.

1. THE ECONOMIC MECHANISM -- WHO PAYS WHOM, AND WHY THE PAYMENT PERSISTS
------------------------------------------------------------------------
TWO orthogonal constructions, both already computed daily by the archiver (WHERE vs HOW MANY):

  EXCHANGE RESERVE (netflow_1d, netflow_7d). A stablecoin holder moving USDT/USDC onto an
  exchange wallet is pre-committing settlement capital to a venue before any trade prints --
  the transfer is observable with a lag ahead of the trade it funds. Rising reserves = dry
  powder accumulating = latent buying capacity; falling reserves = capital withdrawn (spent,
  or de-risked off-exchange). The payment persists because the transfer is a real on-chain
  settlement action, not an expressed opinion -- unlike price, it cannot be walked back costlessly.

  GLOBAL SUPPLY (supply_1d, supply_7d). USDT/USDC total supply changes only when Tether/Circle
  mint or burn against fiat collateral movements -- net NEW capital entering (or leaving) the
  stablecoin system at all, independent of WHERE it then sits. Orthogonal to exchange reserve by
  construction: supply can grow while reserves fall (new capital parked off-exchange) or shrink
  while reserves rise (existing capital consolidating onto venues).

  WHAT WOULD KILL THE STORY. If the settlement lag is shorter than one UTC day -- the mint/transfer
  and the resulting trade both land inside the same daily bar -- the signal and next-day return
  would show only same-period contamination, exactly the CoinMetrics finding above. This screen is
  built to be able to report that honestly (angle-20 de-contam gate is mandatory, not optional).

2. THE FALSIFIABLE CLAIM
------------------------
  H0 (the desk's standing prior, and what a null result CONFIRMS):
      For every pre-registered (construction x horizon) cell, the signal observed at the moment
      it BECAME READABLE (the archiver's own daily UTC snapshot) has zero forward information
      about BTCUSDT's return: |IC| < 0.03.

  H1 (what would refute H0):
      At least one cell shows |IC| >= 0.03 with best timing Sharpe >= 0.5, passes the angle-20
      de-contamination gate, and is POWERED by the harness's own detection floor.

TARGET: BTCUSDT daily close-to-close return (data/lake bronze crypto D1, the same source and
convention scripts/screen_cme_basis.py and scripts/screen_oi_ls_axes.py already use). BTC is the
single largest, most liquid asset and the dominant driver of aggregate crypto risk sentiment --
the natural single-series proxy for a market-wide dry-powder signal that is not asset-specific by
construction (the archiver tracks aggregate exchange balances, not a per-symbol panel).

3. TRIAL GRID (ALL five run and logged every time, winner or not)
-------------------------------------------------------------------
  T1  netflow_1d  -> BTC 1d fwd return   (fast dry-powder signal)
  T2  netflow_7d  -> BTC 1d fwd return   (smoothed dry-powder signal)
  T3  supply_1d   -> BTC 1d fwd return   (fast minting signal)
  T4  supply_7d   -> BTC 1d fwd return   (smoothed minting signal)
  T5  netflow_7d  -> BTC 5d fwd return, NON-OVERLAPPING 5-day sampling (matches T2's own
      smoothing window; screen_cme_basis.py's non-overlap discipline against overlap-inflated
      t-stats)

Raw signal values (not pre-z-scored) are passed to stage_a_screen, which applies its own causal
rolling z-score (zwin=20) -- pre-z-scoring here would double-transform the signal and is exactly
what every other axis screen on this desk deliberately avoids.

ALIGNMENT: the archiver's daily row for UTC day t is written once per day by
scripts/run_stablecoin_flows.py (invoked inside daily_research_cycle.py, 02:00 UTC); the signal
for day t is therefore known by the following day's screen at the earliest. stage_a_screen
predicts target_ret[t+1] from signal[t] internally, which is conservative (no look-ahead) given
this alignment.

MEASURED 2026-08-13, answering "is this signal genuinely idle or already tested": neither -- it
was accumulating correctly (archiver healthy, 41/40d) but had never been screened, which is a
different and narrower defect than "idle". Found investigating a direct question about whether
every data-gated candidate on this desk was actually being exploited once it matured.

INTENDED CADENCE (header comment only -- ops/crontab.manifest is owned by another pass):
    # 30 4 * * *  daily, 04:30 UTC -- 2.5h after daily_research_cycle.py's 02:00 start, comfortably
    #             past even a worst-case ci_gate timeout (3900s) plus every step ahead of
    #             stablecoin_flows in that cycle's step table, so the day's archive row is always
    #             written before this screen reads it.

    python scripts/screen_stablecoin_flows.py [--json]
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

_ARCHIVE = Path("data/stablecoin_flows_archive.json")
_OUT = Path("reports/axis_screens/stablecoin_flows_20260813.json")
_MIN_ROWS = 40  # matches run_stablecoin_flows.py's own pre-registered clock (_NEEDS_DAYS)


def _load_archive() -> pd.DataFrame:
    """The daily stablecoin archive as a date-indexed frame, or empty if absent/unreadable.

    Never a crash: an absent archive (this container, or any fresh box before the archiver's
    first run) is DATA-BLOCKED, not an error.
    """
    try:
        rows = json.loads(_ARCHIVE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return pd.DataFrame()
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame([r for r in rows if isinstance(r, dict) and "date" in r])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.set_index("date").sort_index()


def _btc_returns() -> pd.Series:
    """BTCUSDT D1 close-to-close return, from the same bronze crypto lake and registration
    convention scripts/screen_cme_basis.py and scripts/screen_oi_ls_axes.py already use."""
    register_instrument(InstrumentSpec(symbol="BTCUSDT", asset_class=AssetClass.CRYPTO,
                                       description="BTCUSDT"))
    lake = ParquetLake("data/lake")
    df = lake.read_bars(Layer.BRONZE, "BTCUSDT", Timeframe.D1)
    if df.empty:
        return pd.Series(dtype="float64")
    s = df.set_index(pd.to_datetime(df["timestamp"], utc=True))["close"]
    return s.pct_change()


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

    arch = _load_archive()
    if arch.empty or len(arch) < _MIN_ROWS:
        out = {"status": "DATA-BLOCKED" if arch.empty else "INSUFFICIENT-DATA",
               "why": (f"{_ARCHIVE} absent -- archiver has not run on this box yet" if arch.empty
                       else f"{len(arch)} rows archived, need >= {_MIN_ROWS}"),
               "rows_archived": len(arch)}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"screen_stablecoin_flows: {out['status']} -- {out['why']}")
        if args.json:
            print(json.dumps(out, indent=1))
        return 0

    ret = _btc_returns()
    df = arch.join(ret.rename("ret_1d"), how="inner")
    df["netflow_1d"] = df["total"].diff()
    df["netflow_7d"] = df["total"].diff(7)
    df["supply_1d"] = df["supply_total"].diff()
    df["supply_7d"] = df["supply_total"].diff(7)
    df = df.dropna(subset=["netflow_1d", "netflow_7d", "supply_1d", "supply_7d", "ret_1d"])

    if len(df) < _MIN_ROWS:
        out = {"status": "INSUFFICIENT-DATA",
               "why": (f"{len(df)} rows survive alignment with BTC D1 bars and the 7d-diff "
                       f"warmup, need >= {_MIN_ROWS}"),
               "rows_archived": len(arch), "rows_aligned": len(df)}
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"screen_stablecoin_flows: {out['status']} -- {out['why']}")
        if args.json:
            print(json.dumps(out, indent=1))
        return 0

    ret_arr = df["ret_1d"].to_numpy("float64")
    trials = [
        stage_a_screen(df["netflow_1d"].to_numpy("float64"), ret_arr, name="netflow_1d->btc_1d"),
        stage_a_screen(df["netflow_7d"].to_numpy("float64"), ret_arr, name="netflow_7d->btc_1d"),
        stage_a_screen(df["supply_1d"].to_numpy("float64"), ret_arr, name="supply_1d->btc_1d"),
        stage_a_screen(df["supply_7d"].to_numpy("float64"), ret_arr, name="supply_7d->btc_1d"),
    ]
    s5, r5 = _downsample(df["netflow_7d"].to_numpy("float64"), ret_arr, 5)
    trials.append(stage_a_screen(s5, r5, name="netflow_7d->btc_5d", horizon_days=5.0, zwin=12))

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "stablecoin_flows",
        "n_days": len(df),
        "range": [str(df.index.min().date()), str(df.index.max().date())],
        "alignment": "archiver writes day t's row once, 02:00 UTC day t+1 at the earliest; "
                     "stage_a_screen predicts target_ret[t+1] from signal[t] (no look-ahead).",
        "tempering_prior": "related BTC-native exchange netflow (screen_exchange_netflow.py, "
                           "R0024) screened SCREEN-WEAK with a same-period-contamination sign "
                           "flip on de-contam -- this axis inherits the same gate for that reason",
        "trials": trials,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"screen_stablecoin_flows: {len(df)} aligned days "
          f"[{out['range'][0]}..{out['range'][1]}]")
    for t in trials:
        print(f"  {t['name']:22} n={t.get('n', 0):>5} {t.get('verdict', '?')}")
    if args.json:
        print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    _law_guard()
    raise SystemExit(main())
