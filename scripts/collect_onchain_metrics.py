#!/usr/bin/env python3
"""On-chain FUNDAMENTALS collector -- the licence-clean Glassnode/Coin-Metrics replacement.

Reconstructs the vendor metric class from primary public chain data (blockchain.info charts, free,
no key). Facts are not copyrightable; a vendor's curated series is. Coin Metrics Community is
EXCLUDED from production by ruling 2026-07-26 (CC BY-NC 4.0 "non-commercial internal business
purposes" + ToU 6(iii) banning use in any AI system) -- so the desk reconstructs the same facts
itself rather than licensing someone else's copy of them.

METRIC MAP (verified 1:1 against the CM fields the desk had probed):
    AdrActCnt   -> n-unique-addresses
    TxCnt       -> n-transactions
    FeeTotUSD   -> transaction-fees-usd
    (throughput -> estimated-transaction-volume-usd, already used by collect_onchain_activity)

Writes data/onchain_metrics.jsonl (one row per UTC day, append-only, deduped).
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_BASE = "https://api.blockchain.info/charts"
_METRICS = {
    "active_addresses": "n-unique-addresses",
    "tx_count": "n-transactions",
    "fees_usd": "transaction-fees-usd",
    "throughput_usd": "estimated-transaction-volume-usd",
}
_OUT = Path("data/onchain_metrics.jsonl")


def _series(chart: str) -> dict[str, float]:
    url = f"{_BASE}/{chart}?timespan=5years&format=json&sampled=false"
    req = urllib.request.Request(url, headers={"User-Agent": "quant-onchain-metrics"})
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode())
    return {datetime.fromtimestamp(int(p["x"]), tz=UTC).date().isoformat(): float(p["y"])
            for p in d.get("values", [])}


def main() -> None:
    series = {}
    for name, chart in _METRICS.items():
        try:
            series[name] = _series(chart)
        except Exception as exc:                 # one dead chart must not lose the others
            print(f"  {name}: FETCH FAILED {exc!r}")
    if not series:
        raise SystemExit("all charts failed -- nothing written")

    dates = sorted(set.intersection(*(set(v) for v in series.values())))
    if not dates:
        raise SystemExit("no aligned dates across metrics")

    seen = set()
    if _OUT.exists():
        for line in _OUT.read_text("utf-8", errors="ignore").splitlines():
            try:
                seen.add(json.loads(line)["date"])
            except Exception:
                continue

    n = 0
    with _OUT.open("a", encoding="utf-8") as fh:
        for d in dates:
            if d in seen:
                continue
            fh.write(json.dumps({"date": d, **{k: round(v[d], 4) for k, v in series.items()}})
                     + "\n")
            n += 1
    last = dates[-1]
    print(f"onchain-metrics: +{n} rows (total span {dates[0]} -> {last}, "
          f"{len(dates)} aligned days)")
    print("  latest: " + ", ".join(f"{k}={series[k][last]:,.0f}" for k in series))


if __name__ == "__main__":
    main()
