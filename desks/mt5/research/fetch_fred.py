"""FRED/ALFRED macro fetcher for the research factory (free, no API key via fredgraph CSV).

Macro state vector for the desk:
- yields: DGS2/DGS10/DGS30, DFII10/DFII5 (real), T10YIE/T5YIE (breakevens),
  T10Y2Y (slope), TB3MS
- risk/credit: VIXCLS, BAMLH0A0HYM2 (HY OAS)
- USD/FX: DTWEXBGS (broad), DTWEXM (major), DEXJPUS, DEXUSEU, DEXUSUK,
  DEXCAUS, DEXAUUS, DEXNZUS, DEXSZUS, DEXCHUS
- commodities: GOLDPMGBD228NLBM (London PM fix), DCOILWTICO, PCOPPUSDM
- equities: SP500, NASDAQCOM, NIKKEI225
- policy/liquidity: DFF, SOFR, WALCL (Fed balance sheet)

THIRD-PARTY SERIES ARE NEVER LIVE INPUT (ruling 2026-10-14/20). A series whose FRED notes carry a
copyright notice (libs/data/terms_fence `fred_copyrighted`: VIXCLS, BAMLH0A0HYM2, SP500,
NASDAQCOM, NIKKEI225, PCOPPUSDM, the deleted LBMA fixes) is refused BEFORE any request
(`terms_fence.fred_series_source`). Its state row says UNMEASURED_NO_LICENSED_SOURCE (or names
the desk's own MT5 stand-in) with a missed_growth line, and any lake parquet a pre-ruling run left
behind is moved aside to `*.parquet.ideas_only` so no reader takes a stale copy as current.

NOTE revision policy: fredgraph CSV = current vintage only (revised). True
point-in-time vintages need a free ALFRED API key - upgrade path registered in
data_registry.json. Daily refresh recommended.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parents[2])):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import free_data as fd  # noqa: E402

OUT = Path(r"C:\Users\dell\mt5-research\data\lake")

SERIES = {
    "DGS2": "2y nominal yield",
    "DGS10": "10y nominal yield",
    "DGS30": "30y nominal yield",
    "DFII5": "5y real yield",
    "DFII10": "10y real yield",
    "T5YIE": "5y inflation breakeven",
    "T10YIE": "10y inflation breakeven",
    "T10Y2Y": "10y-2y slope",
    "TB3MS": "3m treasury bill",
    "DFF": "fed funds effective",
    "SOFR": "secured overnight financing rate",
    "WALCL": "Fed balance sheet total",
    "VIXCLS": "VIX",
    "BAMLH0A0HYM2": "HY OAS credit spread",
    "DTWEXBGS": "broad dollar index",
    "DTWEXM": "major-currency dollar index",
    "DEXJPUS": "USDJPY noon",
    "DEXUSEU": "EURUSD noon",
    "DEXUSUK": "GBPUSD noon",
    "DEXCAUS": "USDCAD noon",
    "DEXUSAL": "AUDUSD noon (USD per AUD)",
    "DEXUSNZ": "NZDUSD noon (USD per NZD)",
    "DEXSZUS": "USDCHF noon",
    "DEXCHUS": "CNY per USD noon",
    "DCOILWTICO": "WTI crude spot",
    "ECBDFR": "ECB deposit facility rate",
    "IR3TIB01JPM156N": "Japan 3M interbank (JGB proxy)",
    "PCOPPUSDM": "copper spot",
    "SP500": "S&P 500",
    "NASDAQCOM": "NASDAQ composite",
    "NIKKEI225": "Nikkei 225",
}


def fetch(sid: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    df = pd.read_csv(url, skiprows=1, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.rename(columns={df.columns[0]: sid})
    df = df[~df[sid].isna()]
    return df


def refuse_copyrighted(sid: str, out: Path) -> dict | None:
    """The state row of a third-party series (and the stale lake file moved aside), or None
    for a series FRED may serve as live input. Nothing is requested for a refused series."""
    row = fd.fred_refusal(sid, "fetch_fred")
    if row is None:
        return None
    stale = out / f"fred_{sid}.parquet"
    if stale.exists():
        try:
            os.replace(stale, stale.with_name(stale.name + ".ideas_only"))
            row["stale_lake_moved_aside"] = stale.name + ".ideas_only"
        except OSError as e:
            row["stale_lake_moved_aside"] = f"FAILED: {e!r}"
    return row


def main(out: Path | None = None) -> None:
    out = out or OUT
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for sid, note in SERIES.items():
        cut = refuse_copyrighted(sid, out)
        if cut is not None:
            summary[sid] = {"note": note, **cut}
            print(f"{sid}: {cut['status']} (third-party series, refused before request)")
            continue
        try:
            df = fetch(sid)
            df.to_parquet(out / f"fred_{sid}.parquet")
            summary[sid] = {"bars": len(df), "first": str(df.index.min()),
                            "last": str(df.index.max()), "note": note}
            print(f"{sid}: {len(df)} rows {df.index.min().date()} -> {df.index.max().date()}")
        except Exception as e:  # noqa: BLE001
            summary[sid] = {"error": repr(e)}
            print(f"{sid}: FAILED {e!r}")
    (out / "fred_fetch_state.json").write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(),
                    "revision_policy": "current vintage only; ALFRED API key = point-in-time upgrade",
                    "series": summary,
                    "unmeasured_no_licensed_source": sorted(
                        k for k, v in summary.items()
                        if v.get("status") == fd.UNMEASURED_NO_LICENSED_SOURCE),
                    "missed_growth": [v["missed_growth"] for v in summary.values()
                                      if isinstance(v.get("missed_growth"), dict)]},
                   indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()