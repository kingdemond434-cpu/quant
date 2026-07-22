"""New-listing watch -- the data clock for the new-listing funding-spike sleeve (inbox #53).

Day-1 perp listings routinely print extreme funding (one-sided spec flow, no arb capital yet):
a structurally recurring, capacity-tiny dislocation -- exactly the desk's niche. This collector
starts that family's clock NOW with the simplest robust mechanism: a daily diff of the exchange
symbol universe (announcement pages need scraping and rot; exchangeInfo is the ground truth).
Each new perp is logged with its funding rate at detection, so in N weeks the desk has a real
panel of listing-funding trajectories to pre-register against. Read-only public endpoints,
writes only its own artifacts. Freeze-safe.

    python scripts/run_listing_watch.py
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_FAPI = "https://fapi.binance.com"
_SNAP = Path("data/listing_universe.json")
_LOG = Path("data/listings.jsonl")


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-listing-watch"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def main() -> None:
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    now = {s["symbol"] for s in info.get("symbols", [])
           if s.get("status") == "TRADING" and str(s["symbol"]).endswith("USDT")}
    if not now:
        raise SystemExit("empty universe read -- refusing to diff")

    if not _SNAP.exists():                       # first run: baseline only, no false "listings"
        _SNAP.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                     "symbols": sorted(now)}), "utf-8")
        print(f"listing-watch: baseline {len(now)} perps (no diff on first run)")
        return

    prev = set(json.loads(_SNAP.read_text("utf-8"))["symbols"])
    fresh = sorted(now - prev)
    gone = sorted(prev - now)                    # delistings matter too (symbol-status risk)
    if fresh:
        try:
            prem = {p["symbol"]: p for p in _get(f"{_FAPI}/fapi/v1/premiumIndex")}
        except Exception:                         # noqa: BLE001 -- funding enrich is best-effort
            prem = {}
        with _LOG.open("a", encoding="utf-8") as fh:
            for sym in fresh:
                fh.write(json.dumps({
                    "ts": datetime.now(tz=UTC).isoformat(), "event": "listed", "symbol": sym,
                    "funding_at_detect": float(prem.get(sym, {}).get("lastFundingRate", 0) or 0),
                    "mark_at_detect": float(prem.get(sym, {}).get("markPrice", 0) or 0),
                }) + "\n")
    if gone:
        with _LOG.open("a", encoding="utf-8") as fh:
            for sym in gone:
                fh.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                     "event": "delisted", "symbol": sym}) + "\n")
    _SNAP.write_text(json.dumps({"ts": datetime.now(tz=UTC).isoformat(),
                                 "symbols": sorted(now)}), "utf-8")
    print(f"listing-watch: {len(now)} perps | new {len(fresh)} {fresh[:4]} | gone {len(gone)}")


if __name__ == "__main__":
    main()
