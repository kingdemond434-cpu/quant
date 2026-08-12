"""New-listing watch -- the data clock for the new-listing funding-spike sleeve (inbox #53).

Day-1 perp listings routinely print extreme funding (one-sided spec flow, no arb capital yet):
a structurally recurring, capacity-tiny dislocation -- exactly the desk's niche. This collector
starts that family's clock NOW with the simplest robust mechanism: a daily diff of the exchange
symbol universe (announcement pages need scraping and rot; exchangeInfo is the ground truth).
Each new perp is logged with its funding rate at detection, so in N weeks the desk has a real
panel of listing-funding trajectories to pre-register against. R0292: the same exchangeInfo
read also carries every perp's deliveryDate, so scheduled DELISTINGS (the other §42 ground)
are surfaced in data/delisting_schedule.json BEFORE the symbol leaves the universe, not as a
set-difference after the unwind is over. Read-only public endpoints, writes only its own
artifacts. Freeze-safe.

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
_SCHED = Path("data/delisting_schedule.json")
#: Binance's "no scheduled delivery" placeholder (2100-12-25). A PERPETUAL whose deliveryDate
#: differs from this has a delisting DATE, published while the symbol may still be TRADING --
#: the leading signal for the §42 delisting-unwind ground. Quarterlies are excluded by
#: contractType: their real deliveryDate is the product, not a delisting (R0292).
_DELIVERY_SENTINEL = 4133404800000


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-listing-watch"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _delivery_dates(symbols: list[dict]) -> dict[str, int]:
    """USDT perps carrying a REAL deliveryDate -> {symbol: delivery_ms}, any status."""
    out: dict[str, int] = {}
    for s in symbols:
        sym = str(s.get("symbol", ""))
        if not sym.endswith("USDT") or s.get("contractType") != "PERPETUAL":
            continue
        ms = int(s.get("deliveryDate") or _DELIVERY_SENTINEL)
        if ms != _DELIVERY_SENTINEL:
            out[sym] = ms
    return out


def main() -> None:
    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    symbols = info.get("symbols", [])
    now = {s["symbol"] for s in symbols
           if s.get("status") == "TRADING" and str(s["symbol"]).endswith("USDT")}
    if not now:
        raise SystemExit("empty universe read -- refusing to diff")
    ts = datetime.now(tz=UTC)
    sched = _delivery_dates(symbols)
    status = {str(s.get("symbol", "")): str(s.get("status", "")) for s in symbols}
    # The schedule artifact is a venue-truth snapshot (past settlements included, ordered by
    # delivery): the historical panel for the delisting-unwind event study lives here, while
    # listings.jsonl gets only NEWLY-SEEN schedule rows so detection time is never conflated
    # with event time on rows that predate the watch (L1.46).
    _SCHED.write_text(json.dumps({
        "ts": ts.isoformat(), "n": len(sched),
        "scheduled": [{"symbol": k,
                       "delivery_ms": v,
                       "delivery_ts": datetime.fromtimestamp(v / 1000, tz=UTC).isoformat(),
                       "status": status.get(k, "")}
                      for k, v in sorted(sched.items(), key=lambda kv: kv[1])],
    }, indent=1), "utf-8")

    if not _SNAP.exists():                       # first run: baseline only, no false "listings"
        _SNAP.write_text(json.dumps({"ts": ts.isoformat(), "symbols": sorted(now),
                                     "delivery_dates": sched}), "utf-8")
        print(f"listing-watch: baseline {len(now)} perps (no diff on first run)")
        return

    snap = json.loads(_SNAP.read_text("utf-8"))
    prev = set(snap["symbols"])
    # Legacy snapshots predate the key: baseline the schedule silently rather than bursting
    # 100+ pre-watch settlements into the log as if detected today.
    prev_sched: dict[str, int] = ({k: int(v) for k, v in snap["delivery_dates"].items()}
                                  if "delivery_dates" in snap else sched)
    fresh = sorted(now - prev)
    gone = sorted(prev - now)                    # delistings matter too (symbol-status risk)
    newly_scheduled = sorted(k for k, v in sched.items() if prev_sched.get(k) != v)
    if fresh or newly_scheduled:
        try:
            prem = {p["symbol"]: p for p in _get(f"{_FAPI}/fapi/v1/premiumIndex")}
        except Exception:                         # funding enrich is best-effort
            prem = {}
        with _LOG.open("a", encoding="utf-8") as fh:
            for sym in fresh:
                fh.write(json.dumps({
                    "ts": ts.isoformat(), "event": "listed", "symbol": sym,
                    "funding_at_detect": float(prem.get(sym, {}).get("lastFundingRate", 0) or 0),
                    "mark_at_detect": float(prem.get(sym, {}).get("markPrice", 0) or 0),
                }) + "\n")
            for sym in newly_scheduled:
                fh.write(json.dumps({
                    "ts": ts.isoformat(), "event": "delist_scheduled", "symbol": sym,
                    "delivery_ts": datetime.fromtimestamp(sched[sym] / 1000, tz=UTC).isoformat(),
                    "days_to_delivery": round(sched[sym] / 1000 / 86400
                                              - ts.timestamp() / 86400, 1),
                    "funding_at_detect": float(prem.get(sym, {}).get("lastFundingRate", 0) or 0),
                    "mark_at_detect": float(prem.get(sym, {}).get("markPrice", 0) or 0),
                }) + "\n")
    if gone:
        with _LOG.open("a", encoding="utf-8") as fh:
            for sym in gone:
                fh.write(json.dumps({"ts": ts.isoformat(),
                                     "event": "delisted", "symbol": sym}) + "\n")
    _SNAP.write_text(json.dumps({"ts": ts.isoformat(), "symbols": sorted(now),
                                 "delivery_dates": sched}), "utf-8")
    print(f"listing-watch: {len(now)} perps | new {len(fresh)} {fresh[:4]} "
          f"| gone {len(gone)} | delist-sched {len(sched)} (+{len(newly_scheduled)} new)")


if __name__ == "__main__":
    main()
