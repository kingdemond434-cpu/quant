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

#: WRITE WHERE THE READER LOOKS (2026-10-06). This was `C:\Users\dell\mt5-research\data\lake`,
#: the retired laptop's checkout, while `research/free_shadows.py` reads `fred_*.parquet` from the
#: desk's own `data/lake`. Writer and reader never met, so the FRED half of the state lake was
#: frozen at whatever the laptop last copied over -- and `data/states/free_states.parquet` ends
#: 2026-08-14. `fetch_cot.py`, `fetch_cot_disagg.py` and `fetch_tff.py` had the same defect and
#: were repointed at `config.DATA`; this one was missed. Same fix, same single source of truth.
OUT = Path(__file__).resolve().parents[1] / "data" / "lake"

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


class FredFetchFailed(RuntimeError):
    """Every series failed (or came back empty): the pass fetched NOTHING."""


def main() -> int:
    """Fetch every series; record each outcome in `fred_fetch_state.json`.

    A TOTAL FAILURE IS A FAILURE (audit of #222, 2026-10-07). This returned None whatever
    happened, so a pass where FRED refused every request (a proxy 403, DNS down, the CSV endpoint
    moved) was recorded `OK` by `state_lake_refresh` -- which then did not retry it for a day --
    while the state file said only that each series had an `error`. An EMPTY frame is a failure
    too: a 200 with no rows is not a series. So: every series failed -> the state file says
    `status: FAILED` and this RAISES `FredFetchFailed` (the refresh driver records FAILED and
    retries next pass); some failed -> `status: PARTIAL` with the failures named (a series the
    state lake needs is refused downstream by `free_shadows`, by name); all fetched -> `OK`. A
    failed series never overwrites the parquet already on disk."""
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    failed: list[str] = []
    for sid, note in SERIES.items():
        try:
            df = fetch(sid)
            if df.empty:
                raise ValueError("fetched 0 rows")
            df.to_parquet(OUT / f"fred_{sid}.parquet")
            summary[sid] = {"bars": len(df), "first": str(df.index.min()),
                            "last": str(df.index.max()), "note": note}
            print(f"{sid}: {len(df)} rows {df.index.min().date()} -> {df.index.max().date()}")
        except Exception as e:  # noqa: BLE001
            summary[sid] = {"error": repr(e)}
            failed.append(sid)
            print(f"{sid}: FAILED {e!r}")
    n_ok = len(SERIES) - len(failed)
    status = "OK" if not failed else ("FAILED" if n_ok == 0 else "PARTIAL")
    (OUT / "fred_fetch_state.json").write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(),
                    "status": status, "n_ok": n_ok, "n_failed": len(failed),
                    "failed": failed,
                    "revision_policy": "current vintage only; ALFRED API key = point-in-time upgrade",
                    "series": summary}, indent=2), encoding="utf-8")
    if status == "FAILED":
        raise FredFetchFailed(f"all {len(SERIES)} FRED series failed or came back empty "
                              f"(first: {summary[failed[0]]['error'][:200]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
