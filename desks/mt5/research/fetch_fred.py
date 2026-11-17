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

REFUSED ON TERMS (governance/fred-terms-ruling-2026-11-13.md): FRED/ALFRED terms refuse every
automated fetch. `fetch` raises before any request is built and `main` writes a BLOCKED_ON_TERMS
state file with its missed_growth line. Parquet files already in the lake stay readable.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

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


#: FRED/ALFRED terms refuse every automated fetch (governance/fred-terms-ruling-2026-11-13.md).
BLOCKED_ON_TERMS = ("FRED/ALFRED (stlouisfed.org) terms refuse every automated fetch "
                    "(governance/fred-terms-ruling-2026-11-13.md)")
MISSED_GROWTH = {"mechanism": "fred_terms_refusal",
                 "what_is_lost": "fresh fredgraph series for the research lake",
                 "size": "UNMEASURED",
                 "stand_in": "primary publishers (Fed H.15/H.10, Treasury, BLS, ECB)",
                 "reopens_when": "the St. Louis Fed grants written permission for automated use"}


def fetch(sid: str) -> pd.DataFrame:
    """REFUSED ON TERMS: raises before any request is built. Kept so callers fail loudly."""
    raise RuntimeError(f"BLOCKED_ON_TERMS: {sid}: {BLOCKED_ON_TERMS}")


def main() -> None:
    """Write the BLOCKED_ON_TERMS state file. Nothing is fetched; lake parquet stays as it is."""
    summary = {sid: {"status": "BLOCKED_ON_TERMS", "note": note} for sid, note in SERIES.items()}
    (OUT / "fred_fetch_state.json").write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(),
                    "status": "BLOCKED_ON_TERMS", "reason": BLOCKED_ON_TERMS,
                    "missed_growth": MISSED_GROWTH, "series": summary}, indent=2),
        encoding="utf-8")
    print(f"FRED BLOCKED_ON_TERMS -- {BLOCKED_ON_TERMS}")


if __name__ == "__main__":
    main()