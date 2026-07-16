"""Classify the current crypto market regime (trend x vol) from BTC daily bars.

Writes data/crypto_regime.json so the executor and dashboard can show the LIVE regime and let every
sleeve's regime fit (from crypto_portfolio.json's regime table) be read in context. Cheap -- one
daily BTC kline pull. Run once per UTC day (the always-on executor calls it; run_crypto_testnet).

    python scripts/classify_regime.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.data.crypto_source import fetch_klines

_OUT = Path("data/crypto_regime.json")


def main() -> None:
    df = fetch_klines("BTCUSDT", interval="1d")
    if df.empty or "close" not in df:
        raise SystemExit("no BTC klines")
    close = df["close"].astype(float).to_numpy()
    rets = np.diff(close) / close[:-1]
    base = close[-61] if len(close) > 61 else close[0]
    mom = float(close[-1] / base - 1.0)
    trend = "bull" if mom >= 0 else "bear"
    rv14 = float(np.std(rets[-14:])) if len(rets) >= 14 else float(np.std(rets))
    # median of trailing 14d realized vol over the last ~year -> the high/low-vol divider
    window = [float(np.std(rets[i - 14:i])) for i in range(14, len(rets))][-365:]
    rv_med = float(np.median(window)) if window else rv14
    vol = "high_vol" if rv14 > rv_med else "low_vol"
    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "regime": f"trend:{trend} / vol:{vol}",
        "trend": trend,
        "vol": vol,
        "btc_60d_mom": round(mom, 4),
        "rv14_ann": round(rv14 * (365 ** 0.5), 3),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"regime: {out['regime']}  (BTC 60d mom {mom:+.1%}, rv14 {out['rv14_ann']:.0%} ann)")


if __name__ == "__main__":
    main()
