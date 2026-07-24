"""On-chain economic-throughput collector + Stage-A screen (2026-07-23 orthogonal-axis batch).

The desk's data is almost entirely price/derivatives (funding, OI, basis, breadth, ETF & stablecoin
flows, vol surface, liquidations, kimchi). This adds the FIRST genuinely on-chain-USAGE axis:
Bitcoin's estimated USD economic throughput -- NOT price-derived, so it barely co-moves with the
same-day return (that low same-period correlation is exactly the orthogonality we want).

Screened this session across 6 usage/congestion metrics (n-transactions, fees, mempool-size,
active-addresses, throughput, confirmation-time). Two passed the hardened de-contam gate --
active-addresses and throughput -- but they are the same construct (z20 corr +0.64) and their
equal-weight COMPOSITE degraded to Sharpe 0.39, so the standalone Sharpes are partly day-specific.
HONEST STATUS: weak (IC ~-0.05) + fragile REVERSAL, but genuinely orthogonal (same-period ~-0.06)
and survives orthogonalisation. That profile earns exactly ONE thing under the two-stage law: a
forward clock with ZERO promotion authority. If the reversal was luck it will read FAILING forward
under the Holm bar and cost nothing; if it holds it is a real non-price edge. Direction = reversal
(high-throughput z -> lower forward return; activity/throughput spikes cluster near local tops).

hash-rate / difficulty / miner-revenue are DELIBERATELY not here -- already ingested by
scripts/ingest_axes.py (miner-economics) + hypothesised in run_axis_generate (hashrate_capit).
Free blockchain.info charts, no key. stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research.axis_screen import stage_a_screen

_CHART = ("https://api.blockchain.info/charts/estimated-transaction-volume-usd"
          "?timespan=2years&format=json&sampled=false")
_BINANCE = "https://api.binance.com/api/v3/klines"
_SERIES = Path("data/onchain_activity.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-onchain"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _throughput() -> dict[str, float]:
    d = _get(_CHART)
    return {datetime.fromtimestamp(int(p["x"]), tz=UTC).date().isoformat(): float(p["y"])
            for p in d.get("values", [])} if isinstance(d, dict) else {}


def _binance_daily(sym: str, n: int = 500) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    thru = _throughput()
    gbtc = _binance_daily("BTCUSDT")
    if not (thru and gbtc):
        raise SystemExit(f"fetch failed: throughput={len(thru)} binance={len(gbtc)}")
    dates = sorted(set(thru) & set(gbtc))
    if len(dates) < 90:
        raise SystemExit(f"only {len(dates)} aligned days")

    sig = np.array([thru[d] for d in dates])
    btc = np.array([gbtc[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0

    # 20d z-score of throughput = the traded signal
    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0

    scr = stage_a_screen(sig, ret, name="onchain_activity_throughput")   # honest screen (no clock)

    # forward clock accrues UNCONDITIONALLY from pre-registration (like kimchi) -- one row/day
    today = datetime.now(tz=UTC).date().isoformat()
    rec = {"date": today, "throughput_usd": round(float(sig[-1]), 1),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"ONCHAIN-THROUGHPUT SCREEN | {len(dates)} aligned days")
    print(f"  current z20: {z[-1]:+.2f}   throughput ${sig[-1]:,.0f}")
    print(f"  IC {scr['ic']:+.4f} | same-period {scr['same_period_corr']:+.3f} "
          f"| residual IC {scr['residual_ic']:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM {scr['sharpe_momentum']}  "
          f"REVERSAL {scr['sharpe_reversal']}")
    print(f"  VERDICT (Stage-A, zero promotion authority): {scr['verdict']}  "
          f"[reversal, direction=-1; weak+fragile per composite check -- forward clock decides]")


if __name__ == "__main__":
    main()
