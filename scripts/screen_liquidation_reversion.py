#!/usr/bin/env python3
"""STAGE-A SCREEN: post-liquidation-cascade reversion, regime-gated (R0116, §42, L1.11a).

THE MECHANISM, AND WHO IS FORCED. A liquidation engine is the purest forced participant on any
venue: when maintenance margin breaks it market-closes the position at whatever price the book
offers, and it CANNOT decline, wait for a better level, or size down. If that flow is large
relative to resting depth it pushes price past fair value, and the overshoot should decay once the
forced cohort is exhausted -- a transient, not a trend. The regime gate is the intensity itself:
the claim is only made when forced flow is measurably present, never as a standing reversal rule.

WHY THIS DESK CAN SCREEN IT AND A VENDOR SUBSCRIBER CANNOT. Both series are our own capture:
`data/liquidations.parquet` (Bybit `allLiquidation`, 57k events since 2026-07-09) and the Bybit
trade tape under `data/moat/bybit/<sym>/`. Nothing here is purchasable as a joined product.

CLOCK PROVENANCE (L1.46), declared because a cross-source join without it is an assumption:
  * liquidations  `ts` = Bybit venue stamp `T` (liquidation_listener.py:94-96), with a
                  now()-fallback when `T` is absent -- a MIXED clock, so the fallback share is
                  measured and reported rather than assumed to be zero.
  * trades        `time` inside each trade object = Bybit venue execution stamp (the poll wrapper
                  `t` is our receive clock and is NOT used).
Both legs are therefore the SAME venue on the SAME clock, which is why Bybit is the price source
even though the Binance tape is longer: a cross-venue price leg would put an unmodelled basis and
a second clock inside a reversion measurement of at most 30 minutes.

THE SIDE-SEMANTICS TRAP, HANDLED IN THE OPEN. Bybit's `allLiquidation` `S` field has meant the
ORDER side in one stream generation and the POSITION side in another -- the two are exact
opposites, and guessing wrong flips the sign of every result. So the mapping is not guessed: it is
CALIBRATED against contemporaneous price (which side coincides with a same-bar price drop is a
data-dictionary fact, not a prediction), the calibration is printed, and BOTH mappings are counted
as trials. The forward direction is then fixed by the mechanism -- forced flow overshoots, so fade
it -- and is not re-chosen after seeing the answer.

TRIALS ARE DECLARED, NOT SELECTED (garden-of-forking-paths). Every (horizon, mapping) cell below
is one DSR-counted trial and ALL of them are reported, winners and losers alike. The burst
threshold k and the trailing window are pre-registered constants in this file and are not swept.

ZERO PROMOTION AUTHORITY (two-stage law). A SCREEN-INTERESTING verdict earns a pre-registered
forward clock and not one cent. The audited harness `libs.research.axis_screen.stage_a_screen`
does the analytical last mile so the angle-20 de-contamination gate cannot be skipped.

    python scripts/screen_liquidation_reversion.py [--symbol BTCUSDT] [--json]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402

_LIQ = _ROOT / "data/liquidations.parquet"
_TAPE = _ROOT / "data/moat/bybit"
_OUT = _ROOT / "reports/axis_screens"

#: PRE-REGISTERED CONSTANTS. Frozen before the first run; sweeping these and reporting the best
#: would be data-mining our own collector (the §42 rule that put listing_events.py's thresholds in
#: code). Changing one is a new pre-registration, not a tuning step.
BURST_Z = 2.0            # intensity z above which forced flow is called PRESENT (the regime gate)
TRAIL_BARS = 20          # trailing window for the intensity z-score -- causal, ends at bar t
HORIZONS_MIN = (5, 15, 30)   # the row's stated 5-30min reversion window, as three declared cells


def _bars_from_tape(symbol: str, minutes: int) -> pd.DataFrame:
    """Last-trade price per bar from our own Bybit trade tape, on the VENUE clock.

    Returns a frame indexed by bar-open UTC with `close` and `vol`. Reads the venue `time` inside
    each trade object; the wrapper `t` (our receive stamp) is deliberately ignored so the two legs
    of the join share one clock.
    """
    d = _TAPE / symbol
    if not d.is_dir():
        return pd.DataFrame()
    last: dict[int, tuple[int, float]] = {}     # bar -> (latest venue ms, price)
    vol: dict[int, float] = defaultdict(float)
    step = minutes * 60_000
    for f in sorted(d.glob("*.jsonl.gz")):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue                # a truncated tail line is skipped, never fatal
                    if rec.get("k") != "trades":
                        continue
                    for tr in rec.get("v") or []:
                        try:
                            ms = int(tr["time"])
                            px = float(tr["price"])
                            sz = float(tr.get("size", 0) or 0)
                        except (KeyError, TypeError, ValueError):
                            continue
                        b = ms - ms % step
                        prev = last.get(b)
                        if prev is None or ms >= prev[0]:
                            last[b] = (ms, px)
                        vol[b] += sz * px
        except (OSError, EOFError):
            continue                            # a corrupt hour is dropped, and said so below
    if not last:
        return pd.DataFrame()
    idx = sorted(last)
    return pd.DataFrame(
        {"close": [last[b][1] for b in idx], "vol": [vol[b] for b in idx]},
        index=pd.to_datetime(idx, unit="ms", utc=True),
    )


def _liquidations(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(_LIQ)
    df = df[df["symbol"] == symbol].copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.sort_values("ts")


def _cells(bars: pd.DataFrame, liq: pd.DataFrame, minutes: int) -> dict[str, Any]:
    """Build the aligned (signal, target) pair for one horizon, both mappings of the side field."""
    freq = f"{minutes}min"
    grid = bars.resample(freq).last().dropna(subset=["close"])
    ret = np.log(grid["close"]).diff()

    liq = liq.set_index("ts")
    buy = liq[liq["side"] == "Buy"]["notional"].resample(freq).sum()
    sell = liq[liq["side"] == "Sell"]["notional"].resample(freq).sum()
    tot = liq["notional"].resample(freq).sum()

    df = pd.DataFrame({"ret": ret, "buy": buy, "sell": sell, "tot": tot}).fillna(
        {"buy": 0.0, "sell": 0.0, "tot": 0.0})
    df = df.dropna(subset=["ret"])
    if len(df) < TRAIL_BARS * 3:
        return {"error": f"only {len(df)} bars at {minutes}m -- below the {TRAIL_BARS * 3} floor"}

    # CAUSAL intensity z: mean/sd over the trailing window ENDING at t (shift(1) excludes t itself
    # from its own baseline, which would shrink every spike toward the mean it created).
    base = df["tot"].shift(1).rolling(TRAIL_BARS)
    z = (df["tot"] - base.mean()) / base.std(ddof=0)
    df["z"] = z.replace([np.inf, -np.inf], np.nan)

    # SIDE-SEMANTICS CALIBRATION -- a data-dictionary question answered from contemporaneous price,
    # never from the forward return. Whichever side coincides with a same-bar DROP is the one whose
    # forced flow sells. Reported, and both mappings are screened regardless of which wins.
    net = df["buy"] - df["sell"]
    corr_now = float(np.corrcoef(net.to_numpy(), df["ret"].to_numpy())[0, 1]) if len(df) > 2 else 0.0
    return {"df": df, "net": net, "contemporaneous_corr_net_vs_ret": round(corr_now, 4),
            "n_bars": len(df), "n_burst": int((df["z"] > BURST_Z).sum())}


def run(symbol: str = "BTCUSDT") -> dict[str, Any]:
    bars_1m = _bars_from_tape(symbol, 1)
    if bars_1m.empty:
        return {"status": "NO-DATA", "detail": f"no Bybit trade tape for {symbol}"}
    liq = _liquidations(symbol)
    if liq.empty:
        return {"status": "NO-DATA", "detail": f"no liquidation events for {symbol}"}

    overlap0 = max(bars_1m.index.min(), liq["ts"].min())
    overlap1 = min(bars_1m.index.max(), liq["ts"].max())
    trials: list[dict[str, Any]] = []

    for minutes in HORIZONS_MIN:
        built = _cells(bars_1m, liq, minutes)
        if "error" in built:
            trials.append({"horizon_min": minutes, "verdict": "NO-DATA", **built})
            continue
        df, net = built["df"], built["net"]
        # BOTH mappings are trials. `sign=+1` reads a positive net (buy-minus-sell) as UPWARD
        # forced pressure; `sign=-1` reads it as downward. The mechanism says FADE the pressure,
        # so the signal is minus the pressure in both cases -- only the reading of the field flips.
        for sign, label in ((1, "S=order-side"), (-1, "S=position-side")):
            pressure = sign * net.to_numpy()
            gate = (df["z"] > BURST_Z).to_numpy()
            signal = np.where(gate, -pressure, 0.0)        # regime-gated: silent outside a burst
            target = df["ret"].to_numpy()
            res = stage_a_screen(
                signal, target,
                name=f"liq_reversion_{symbol}_{minutes}m_{label}",
                zwin=TRAIL_BARS, horizon_days=minutes / (60.0 * 24.0), clock=None)
            trials.append({
                "horizon_min": minutes, "side_mapping": label,
                "n_bars": built["n_bars"], "n_burst": built["n_burst"],
                "contemporaneous_corr_net_vs_ret": built["contemporaneous_corr_net_vs_ret"],
                **{k: v for k, v in res.items() if k != "clock"},
            })

    interesting = [t for t in trials if t.get("verdict") == "SCREEN-INTERESTING"]
    underpowered = [t for t in trials if t.get("verdict") == "SCREEN-UNDERPOWERED"]
    status = ("SCREEN-INTERESTING" if interesting else
              "SCREEN-UNDERPOWERED" if underpowered and len(underpowered) == len(trials) else
              "SCREEN-WEAK")
    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "row": "R0116", "symbol": symbol, "status": status,
        "law": "Stage-A only (two-stage law): ZERO promotion authority. A pass earns a "
               "pre-registered forward clock, never capital.",
        "clock_provenance": {
            "liquidations": "Bybit venue stamp `T` (mixed: now() fallback when absent)",
            "prices": "Bybit venue trade `time` (our receive stamp `t` deliberately unused)",
            "same_venue_same_clock": True,
        },
        "overlap_start": overlap0.isoformat(), "overlap_end": overlap1.isoformat(),
        "overlap_days": round((overlap1 - overlap0).total_seconds() / 86400.0, 2),
        "n_liquidation_events": len(liq),
        "pre_registered": {"burst_z": BURST_Z, "trail_bars": TRAIL_BARS,
                           "horizons_min": list(HORIZONS_MIN)},
        "trials_declared": len(trials),
        "trials": trials,
        "note": "EVERY declared cell is reported, winners and losers alike -- reporting only the "
                "best of six would be the garden-of-forking-paths the screen-on-discovery duty "
                "forbids. Both side-field mappings are counted as trials because the field's "
                "meaning is genuinely ambiguous across Bybit stream generations.",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = run(args.symbol)
    _OUT.mkdir(parents=True, exist_ok=True)
    out = _OUT / f"liquidation_reversion_{args.symbol}.json"
    out.write_text(json.dumps(rep, indent=2, default=str), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return 0
    print(f"R0116 liquidation-reversion screen | {rep['status']}")
    if rep.get("status") == "NO-DATA":
        print(f"  {rep.get('detail')}")
        return 0
    print(f"  overlap {rep['overlap_days']}d ({rep['overlap_start'][:16]} -> "
          f"{rep['overlap_end'][:16]}), {rep['n_liquidation_events']} liquidation events")
    for t in rep["trials"]:
        if t.get("verdict") is None:
            print(f"  {t['horizon_min']:>3}m  {t.get('verdict', 'NO-DATA')}  {t.get('error', '')}")
            continue
        print(f"  {t['horizon_min']:>3}m {t['side_mapping']:18} {t['verdict']:22} "
              f"IC={t.get('ic'):+.4f} n_eff={t.get('n_eff')} bursts={t['n_burst']}/{t['n_bars']} "
              f"contam={t.get('same_period_corr')}")
    print(f"-> {out.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
