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

NOTE revision policy: fredgraph CSV = current vintage only (revised). True
point-in-time vintages need a free ALFRED API key - upgrade path registered in
data_registry.json. Daily refresh recommended.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

OUT = Path(r"C:\Users\dell\mt5-research\data\lake")
OUT.mkdir(parents=True, exist_ok=True)

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


def main() -> None:
    summary = {}
    for sid, note in SERIES.items():
        try:
            df = fetch(sid)
            df.to_parquet(OUT / f"fred_{sid}.parquet")
            summary[sid] = {"bars": len(df), "first": str(df.index.min()),
                            "last": str(df.index.max()), "note": note}
            print(f"{sid}: {len(df)} rows {df.index.min().date()} -> {df.index.max().date()}")
        except Exception as e:  # noqa: BLE001
            summary[sid] = {"error": repr(e)}
            print(f"{sid}: FAILED {e!r}")
    (OUT / "fred_fetch_state.json").write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(),
                    "revision_policy": "current vintage only; ALFRED API key = point-in-time upgrade",
                    "series": summary}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()