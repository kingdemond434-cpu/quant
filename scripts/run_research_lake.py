"""Net-of-cost FX research on the Parquet lake (offline, no live MT5 dependency).

Runs the autonomous lab over the 26-year FX daily history already in the lake, focused on the
committee-recommended niche (carry + cross-asset + the price families that actually fit FX). Two
things make this more than a re-run:

  * Lever 4 (cross-asset depth): a synthetic BROAD-USD-STRENGTH index is built from the USD majors
    and fed as each symbol's reference series, so the cross-asset family stops degrading to flat and
    expresses a real "currency vs. broad USD" signal.
  * Net-of-cost: per-symbol per-turnover cost from a calibrated prior, plus the execution-gap and
    cross-campaign-deflation gates already wired into the lab.

Honest by construction: most likely reports zero survivors, net of cost, on 26 years of data.

Usage:
    python scripts/run_research_lake.py
    python scripts/run_research_lake.py --symbols EURUSD,GBPUSD --families carry,cross_asset
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from migrations import MIGRATIONS

from libs.autodiscovery.models import Family, MarketSeries
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.autodiscovery.reports import (
    failure_analysis_report,
    research_report,
    survivor_report,
)
from libs.autodiscovery.research_roi import ResearchROIMonitor
from libs.autodiscovery.validation import SESSION_DAYS_PER_YEAR
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_BRONZE = Path("data/lake/bronze")
_OUT = Path("reports/research_lake")
# USD majors and the sign that makes a positive return == stronger USD.
_USD_MAJORS = {"EURUSD": -1.0, "GBPUSD": -1.0, "AUDUSD": -1.0, "NZDUSD": -1.0,
               "USDJPY": +1.0, "USDCHF": +1.0, "USDCAD": +1.0}
# Per-side cost prior in return space, by asset class (conservative; calibrate on real fills).
_COST_PER_SIDE = {AssetClass.FX: 8e-5, AssetClass.METAL: 1.5e-4, AssetClass.ENERGY: 2e-4}


def _discover_lake_symbols() -> dict[str, AssetClass]:
    """Map every symbol present in the bronze lake to its asset class (from the dir layout)."""
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
        for sym_dir in ac_dir.iterdir():
            if (sym_dir / Timeframe.D1.value).exists():
                found[sym_dir.name] = ac
    return found


def _load(lake: ParquetLake, symbol: str) -> pd.DataFrame:
    df = lake.read_bars(Layer.BRONZE, symbol, Timeframe.D1)
    return df.set_index("timestamp")


def _usd_strength_index(
    frames: dict[str, pd.DataFrame], *, exclude: str | None = None
) -> pd.Series:
    """Cumulative broad-USD-strength level from the majors (equal-weight), excluding ``exclude``.

    Excluding the tested symbol removes the self-reference that would otherwise let a symbol
    predict an index containing itself (a subtle look-ahead / circularity).
    """
    rets = []
    for sym, sign in _USD_MAJORS.items():
        if sym in frames and sym != exclude:
            rets.append(sign * frames[sym]["close"].pct_change())
    if not rets:
        return pd.Series(dtype="float64")
    usd_ret = pd.concat(rets, axis=1).mean(axis=1).fillna(0.0)
    return (1.0 + usd_ret).cumprod()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,USDJPY,USDCHF,USDCAD,AUDUSD,NZDUSD")
    parser.add_argument("--families", default="carry,cross_asset,momentum,mean_reversion")
    parser.add_argument("--db", default="data/sor_research_lake.sqlite")
    args = parser.parse_args()

    available = _discover_lake_symbols()
    if not available:
        raise SystemExit("no D1 data in the lake; run scripts/ingest_history.py first")
    for sym, ac in available.items():  # register so ParquetLake.path resolves
        register_instrument(InstrumentSpec(symbol=sym, asset_class=ac, description=sym))

    lake = ParquetLake("data/lake")
    requested = [s.strip() for s in args.symbols.split(",") if s.strip() in available]
    # Load requested symbols + the majors needed to build the USD index.
    need = set(requested) | (set(_USD_MAJORS) & set(available))
    frames = {s: _load(lake, s) for s in need}
    usd = _usd_strength_index(frames)  # full index, for reporting only
    # Per-symbol USD index excluding the symbol itself (no self-reference).
    usd_by_symbol = {s: _usd_strength_index(frames, exclude=s) for s in requested}

    def provider(symbol: str) -> MarketSeries | None:
        if symbol not in frames:
            return None
        df = frames[symbol]
        ref_idx = usd_by_symbol.get(symbol, usd)
        ref = (ref_idx.reindex(df.index, method="ffill").to_numpy("float64")
               if len(ref_idx) else None)
        return MarketSeries(
            close=df["close"].to_numpy(dtype="float64"),
            high=df["high"].to_numpy(dtype="float64"),
            low=df["low"].to_numpy(dtype="float64"),
            volume=df["volume"].to_numpy(dtype="float64"),
            hour=np.array([t.hour for t in df.index], dtype="float64"),
            ref_close=ref,
        )

    def cost_provider(symbol: str) -> float:
        return _COST_PER_SIDE.get(available.get(symbol, AssetClass.FX), 1e-4)

    families = [Family(f.strip()) for f in args.families.split(",") if f.strip()] or None
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    # D1 FX bars on the SESSION calendar (~252 tradeable days): this runner is the 26-year FX
    # daily history, not crypto, so its clock is 252/yr -- not the 6240 hourly constant that
    # annualised it until R0086 (libs/autodiscovery/validation.py), which was 4.976x too large.
    lab = AutoDiscoveryLab(db, provider, bar=Timeframe.D1,
                           days_per_year=SESSION_DAYS_PER_YEAR,
                           cost_provider=cost_provider, families=families)

    fam_names = [f.value for f in (families or [])]
    print(f"lake symbols available: {len(available)} | testing {len(requested)}: {requested}")
    print(f"USD-strength index points: {len(usd)} | families: {fam_names}")
    result = lab.cycle(requested)
    print(f"\n[cycle] tested={result.tested} survivors={result.survivors} "
          f"rejected={result.rejected} promoted_paper={result.promoted_to_paper}")

    _OUT.mkdir(parents=True, exist_ok=True)
    reports = {
        "research_report": research_report(lab.store),
        "survivor_report": survivor_report(lab.store),
        "failure_analysis_report": failure_analysis_report(lab.store),
        "research_roi_report": ResearchROIMonitor(lab.store).report().model_dump(),
    }
    for name, payload in reports.items():
        (_OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    print(f"reports -> {_OUT}/")
    if result.survivors == 0:
        print("ZERO survivors net-of-cost (honest result; nothing promoted to registry).")
    db.close()


if __name__ == "__main__":
    main()
