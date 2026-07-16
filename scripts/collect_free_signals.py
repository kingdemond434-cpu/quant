"""Collect free regime/breadth signals -> data/free_signals.parquet + web/free_signals.json.

Captures every free family: Fear & Greed, BTC dominance / total mcap, Hyperliquid funding (mean +
cross-asset dispersion across ~230 perps), and Binance calendar basis. Emits a de-risk
leverage_multiplier (<=1.0) from Fear & Greed extremes -- a FREE drawdown/giveback overlay (cut size
in extreme greed = crash risk, and in extreme fear = high vol). Runs on the executor flywheel.

    python scripts/collect_free_signals.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.freesources import (
    calendar_basis,
    coingecko_global,
    fear_greed,
    hyperliquid_funding,
)

_ARCH = Path("data/free_signals.parquet")
_WEB = Path("web/free_signals.json")


def _derisk(fng: float) -> float:
    """De-risk multiplier (<=1.0): extreme greed = crash risk; extreme fear = high vol."""
    if fng >= 80:
        return 0.70
    if fng >= 70:
        return 0.85
    if fng <= 12:
        return 0.85
    return 1.0


def _label(fng: float) -> str:
    return ("Extreme Fear" if fng < 25 else "Fear" if fng < 45 else "Neutral"
            if fng < 55 else "Greed" if fng < 75 else "Extreme Greed")


def main() -> None:
    fg = fear_greed(limit=2)
    fng = float(fg["fng"].iloc[-1]) if len(fg) else 50.0
    g = coingecko_global()
    hl = hyperliquid_funding()
    cb = calendar_basis()
    hl_vals = list(hl.values())
    hl_mean = float(np.mean(hl_vals)) if hl_vals else 0.0
    hl_disp = float(np.std(hl_vals)) if hl_vals else 0.0
    mult = _derisk(fng)
    now = datetime.now(tz=UTC)

    row = {"timestamp": now, "fng": fng, "btc_dom": g.get("btc_dominance"),
           "total_mcap_usd": g.get("total_mcap_usd"), "hl_funding_mean": hl_mean,
           "hl_funding_disp": hl_disp, "btc_cal_basis": cb.get("BTCUSDT"),
           "eth_cal_basis": cb.get("ETHUSDT"), "derisk_mult": mult}
    df = pd.DataFrame([row])
    if _ARCH.exists():
        old = pd.read_parquet(_ARCH)
        df = pd.concat([old, df], ignore_index=True)
        df["day"] = pd.to_datetime(df["timestamp"]).dt.date
        df = df.drop_duplicates("day", keep="last").drop(columns="day")
    _ARCH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_ARCH, index=False)

    out = {
        "updated": now.isoformat(),
        "fear_greed": fng, "fng_label": _label(fng),
        "btc_dominance": g.get("btc_dominance"),
        "total_mcap_usd_bn": round(g.get("total_mcap_usd", 0.0) / 1e9, 1),
        "mcap_change_24h": g.get("mcap_change_24h"),
        "hyperliquid_assets": len(hl), "hl_funding_mean": round(hl_mean, 6),
        "hl_funding_dispersion": round(hl_disp, 6),
        "calendar_basis_annualised": cb,
        "derisk_multiplier": mult, "archive_rows": len(df),
        "note": ("FREE regime/breadth layer. Fear&Greed drives the de-risk overlay (<=1.0); "
                 "Hyperliquid funding + calendar basis forward-archive for cross-venue / "
                 "term-structure carry once enough history accrues."),
    }
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(out, indent=2, default=str), "utf-8")
    print(f"free signals: F&G {fng:.0f} ({_label(fng)}) -> de-risk {mult}x | BTC dom "
          f"{g.get('btc_dominance', 0):.1f}% | HL {len(hl)} perps (disp {hl_disp:.5f}) | "
          f"cal-basis BTC {cb.get('BTCUSDT')} | archive {len(df)} rows")


if __name__ == "__main__":
    main()
