"""Ingest free MT5 ETF CFDs -- unlocks rates/duration, credit, and sector-rotation sleeves.

The broker's "Stock CFDs" group holds liquid, continuous ETF CFDs (TLT/IEF/SHY/LQD/EMB for the rates
curve + credit; sector SPDRs for rotation; QQQ/EEM for broad equity). These are a genuinely new,
economically-distinct asset class for us -- orthogonal to the FX/commodity/crypto book -- and they
cost nothing beyond ingest. Stored under clean tickers; entries appended to the multiasset coverage
so the portfolio runner picks them up automatically.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.schema import BAR_COLUMNS
from libs.data.timeframe import Timeframe

_COVERAGE = Path("reports/multiasset_coverage.json")
# clean ticker -> MT5 symbol name (warm, >=1500 bars confirmed). All classified EQUITY (ETF).
_ETFS: dict[str, str] = {
    "TLT": "TLT.NAS", "IEF": "IEF.NAS", "SHY": "SHY.NAS", "LQD": "LQD.NYSE", "EMB": "EMB.NAS",
    "QQQ": "QQQ.NAS", "EEM": "EEM.NYSE",
    "XLE": "XLE.NYSE", "XLF": "XLF.NYSE", "XLI": "XLI.NYSE", "XLP": "XLP.NYSE", "XLU": "XLU.NYSE",
    "XLK": "XLK.NYSE", "XLV": "XLV.NYSE", "XLY": "XLY.NYSE",
    "GDX": "GDX.NYSE", "UNG": "UNG.NYSE", "SMH": "SMH.NAS", "CIBR": "CIBR.NAS", "SKYY": "SKYY.NAS",
}


def _canonical(rates) -> pd.DataFrame:  # type: ignore[no-untyped-def]
    df = pd.DataFrame(rates)
    return pd.DataFrame({
        "timestamp": pd.to_datetime(df["time"], unit="s", utc=True),
        "open": df["open"].astype("float64"), "high": df["high"].astype("float64"),
        "low": df["low"].astype("float64"), "close": df["close"].astype("float64"),
        "volume": df["tick_volume"].astype("float64"),
    })[list(BAR_COLUMNS)]


def main() -> None:
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct is None or int(acct.trade_mode) != 0:
        mt5.shutdown()
        raise SystemExit("refusing: not a DEMO account")
    lake = ParquetLake("data/lake")
    start = datetime(2010, 1, 1, tzinfo=UTC)
    now = datetime.now(tz=UTC)

    cov = json.loads(_COVERAGE.read_text("utf-8")) if _COVERAGE.exists() else []
    cov = [c for c in cov if c.get("symbol") not in _ETFS]      # drop stale ETF rows, re-add fresh
    landed = 0
    for ticker, mt5name in _ETFS.items():
        mt5.symbol_select(mt5name, True)
        mt5.symbol_info_tick(mt5name)
        time.sleep(0.1)
        rates = mt5.copy_rates_range(mt5name, mt5.TIMEFRAME_D1, start, now)
        n = 0 if rates is None else len(rates)
        if n < 250:
            print(f"  {ticker:5} ({mt5name}) {n} bars -- skip")
            cov.append({"symbol": ticker, "asset_class": "equity", "bars": 0})
            continue
        register_instrument(InstrumentSpec(symbol=ticker, asset_class=AssetClass.EQUITY,
                                           description=f"ETF {ticker} ({mt5name})"))
        frame = _canonical(rates)
        lake.write_bars(Layer.BRONZE, ticker, Timeframe.D1, frame)
        cov.append({"symbol": ticker, "asset_class": "equity", "bars": len(frame),
                    "first": str(frame["timestamp"].iloc[0].date()),
                    "last": str(frame["timestamp"].iloc[-1].date()), "mt5_name": mt5name})
        landed += 1
        print(f"  {ticker:5} ({mt5name}) {len(frame)} bars")
    mt5.shutdown()
    _COVERAGE.write_text(json.dumps(cov, indent=2), "utf-8")
    print(f"\nlanded {landed}/{len(_ETFS)} ETFs -> lake + {_COVERAGE}")


if __name__ == "__main__":
    main()
