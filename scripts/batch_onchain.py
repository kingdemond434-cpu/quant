"""Batch on-chain USAGE/CONGESTION screen -- genuinely orthogonal to the desk's derivatives data.
NOT price-derived: network demand, fee pressure, mempool congestion, active addresses. Free
blockchain.info charts (hash-rate/difficulty/miner-revenue are ALREADY ingested elsewhere -- those
are deliberately EXCLUDED here to avoid redundancy). Hardened harness (SUSPECT-LOOKAHEAD rail).
Run from repo root."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _binance() -> dict[str, float]:
    rows = _get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=500")
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def _chart(name: str) -> dict[str, float]:
    d = _get(f"https://api.blockchain.info/charts/{name}?timespan=2years&format=json&sampled=false")
    return {datetime.fromtimestamp(int(p["x"]), tz=UTC).date().isoformat(): float(p["y"])
            for p in d.get("values", [])}


# genuinely-new usage/congestion metrics (NOT hash-rate/difficulty/miners-revenue = already have)
CHARTS = ["n-transactions",           # network demand
          "transaction-fees",         # fee pressure (BTC)
          "mempool-size",             # congestion (bytes)
          "n-unique-addresses",       # active addresses / adoption
          "estimated-transaction-volume-usd",  # economic throughput
          "median-confirmation-time"] # congestion / latency


def main() -> None:
    gb = _binance()
    dates_b = sorted(gb)
    btc = np.array([gb[d] for d in dates_b])
    retmap = {dates_b[0]: 0.0}
    for i in range(1, len(dates_b)):
        retmap[dates_b[i]] = btc[i] / btc[i - 1] - 1.0

    results = []
    for name in CHARTS:
        try:
            series = _chart(name)
        except Exception as e:  # noqa: BLE001
            print(f"{name:34s} DATA-BLOCKED ({type(e).__name__})")
            continue
        dates = sorted(set(series) & set(gb))
        if len(dates) < 90:
            print(f"{name:34s} thin ({len(dates)}d)")
            continue
        sig = np.array([series[d] for d in dates])
        ret = np.array([retmap[d] for d in dates])
        r = stage_a_screen(sig, ret, name=name)   # pure screen -- no clock (screens don't pre-register)
        results.append(r)
        print(f"{name:34s} {len(dates)}d | IC {r.get('ic')} | same {r.get('same_period_corr')} "
              f"| resid {r.get('residual_ic')} | momSh {r.get('sharpe_momentum')} "
              f"| revSh {r.get('sharpe_reversal')} | {r['verdict']}")

    Path("data/batch_onchain_screen.json").write_text(
        json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "results": results}, indent=1),
        "utf-8")
    surv = [r["name"] for r in results if r["verdict"] == "SCREEN-INTERESTING"]
    print(f"\nSURVIVORS (passed de-contam): {surv or 'NONE'}")


if __name__ == "__main__":
    main()
