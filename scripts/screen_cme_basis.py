"""Stage-A screen: CME BTC front-contract annualized basis vs BTC forward returns.

MECHANISM (pre-registered before compute, 2026-07-24): the CME basis prices REGULATED
institutional demand (cash-settled, TradFi cohort, ETF/CTA arb flow) while perp funding
prices offshore leverage demand. A rich/cheap CME basis vs its own recent range is an
institutional-positioning impulse the perp-native desk does not otherwise observe; the
divergence (CME basis minus perp funding) isolates the institutional-vs-offshore leg.

TIMESTAMP ALIGNMENT (declared): Databento CME ohlcv-1d bars are stamped at the session
open; the CME session close prints ~21:00-22:00 UTC on day t, BEFORE the Binance UTC
close (00:00 UTC t+1) that defines target day t. stage_a_screen then predicts target
day t+1 from signal day t, so the signal is ~26h old at entry -- conservatively NO
look-ahead. The 5d/20d horizons use NON-OVERLAPPING downsampled periods (no overlap
inflation; the dev-momentum lesson).

TRIALS (all logged, winner or not): T1 basis_ann->1d, T2 ->5d, T3 ->20d,
T4 divergence(basis_ann - funding_ann)->1d. Verdicts + trial count go to
reports/axis_screens/ + research_memory + the ledger. Stage A has ZERO promotion
authority -- a survivor earns only a pre-registered forward clock.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument  # noqa: E402
from libs.data.lake import Layer, ParquetLake, Timeframe  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402

CME = ROOT / "data" / "lake" / "bronze" / "cme"
OUT = ROOT / "reports" / "axis_screens"
_SCALE = 1e-9
_MIN_DTE_D = 7.0


def _front_basis() -> pd.DataFrame:
    """Per UTC day: nearest-expiry (>7d) traded BTC contract's close and days-to-expiry."""
    defs = pd.read_csv(
        CME / "BTC_FUT_definition_2018-01-01_2026-07-20.csv",
        usecols=["instrument_id", "raw_symbol", "instrument_class", "expiration"],
    )
    defs = defs[defs["instrument_class"] == "F"].drop_duplicates("instrument_id")
    exp = dict(zip(defs["instrument_id"], defs["expiration"], strict=False))

    bars = pd.read_csv(
        CME / "BTC_FUT_ohlcv-1d_2018-01-01_2026-07-20.csv",
        usecols=["ts_event", "instrument_id", "close", "volume"],
    )
    bars = bars[bars["volume"] > 0]
    bars["expiration"] = bars["instrument_id"].map(exp)
    bars = bars.dropna(subset=["expiration"])
    bars["dte_d"] = (bars["expiration"] - bars["ts_event"]) / 86_400e9
    bars = bars[bars["dte_d"] > _MIN_DTE_D]
    bars["day"] = pd.to_datetime(bars["ts_event"], utc=True).dt.floor("D")
    front = bars.sort_values("dte_d").groupby("day").first()
    front["fut_close"] = front["close"] * _SCALE
    return front[["fut_close", "dte_d"]]


def _spot() -> pd.DataFrame:
    register_instrument(InstrumentSpec(symbol="BTCUSDT", asset_class=AssetClass.CRYPTO,
                                       description="BTCUSDT"))
    lake = ParquetLake(str(ROOT / "data" / "lake"))
    df = lake.read_bars(Layer.BRONZE, "BTCUSDT", Timeframe.D1)
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    out = df.set_index("day")[["close"]].rename(columns={"close": "spot_close"})
    if "funding" in df.columns:
        out["funding"] = df.set_index("day")["funding"]
    return out


def _downsample(sig: np.ndarray, ret_1d: np.ndarray, step: int) -> tuple[np.ndarray, np.ndarray]:
    """Non-overlapping step-day periods: signal at period start, compounded period return."""
    n = len(sig) // step
    s = np.array([sig[i * step] for i in range(n)])
    r = np.array([float(np.prod(1.0 + ret_1d[i * step:(i + 1) * step]) - 1.0) for i in range(n)])
    return s, r


def main() -> None:
    front = _front_basis()
    spot = _spot()
    df = front.join(spot, how="inner").dropna(subset=["fut_close", "spot_close"])
    df["basis_ann"] = (df["fut_close"] / df["spot_close"] - 1.0) * (365.0 / df["dte_d"])
    df["ret_1d"] = df["spot_close"].pct_change()
    df = df.dropna(subset=["basis_ann", "ret_1d"])

    sig = df["basis_ann"].to_numpy()
    ret = df["ret_1d"].to_numpy()
    trials = []
    trials.append(stage_a_screen(sig, ret, name="cme_basis_ann->btc_1d"))
    for step, nm in ((5, "cme_basis_ann->btc_5d"), (20, "cme_basis_ann->btc_20d")):
        s_d, r_d = _downsample(sig, ret, step)
        trials.append(stage_a_screen(s_d, r_d, name=nm, zwin=12 if step == 5 else 6))
    if "funding" in df.columns and df["funding"].notna().sum() > 500:
        div = (df["basis_ann"] - df["funding"].fillna(0.0) * 3.0 * 365.0).to_numpy()
        trials.append(stage_a_screen(div, ret, name="cme_minus_perp_funding->btc_1d"))
    else:
        trials.append({"name": "cme_minus_perp_funding->btc_1d",
                       "verdict": "NOT-RUN (no funding column in lake D1 frame)"})

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "cme",
        "n_days": len(df),
        "range": [str(df.index.min().date()), str(df.index.max().date())],
        "alignment": "CME session close ~22:00 UTC day t predicts Binance close-to-close day t+1"
                     " (signal ~26h old at entry; no look-ahead). 5d/20d non-overlapping.",
        "trials": trials,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cme_basis_20260724.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
