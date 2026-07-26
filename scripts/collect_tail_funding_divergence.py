#!/usr/bin/env python3
"""Cross-venue funding divergence on the thin tail of the perp universe (§42 hunting ground).

    python3 scripts/collect_tail_funding_divergence.py

Reads public funding + open-interest endpoints on Binance and Bybit, keeps the THIN half of the
shared universe by open interest, and logs every harvestable cross-venue funding gap to
`data/tail_funding_divergence.jsonl`. Starting the clock is the whole job: a divergence that shows
up once is noise, and only a panel accumulated over weeks can say whether these gaps PERSIST long
enough to be worth two venues of operational overhead.

WHY THE TAIL. §42: the liquid names are where every funded arbitrageur already looks, so a gap
there is gone before a small book reaches it. A thin perp listed on two venues can carry a
persistent gap for days because nobody with real capital will build plumbing for a $30k position.
That is the one place a book this size is not the worst-capitalised participant in the trade.

Read-only public endpoints, no keys, no orders, no capital. Freeze-safe. Degrades to an honest
"could not read venue X" and exit 0 rather than failing the daily cycle -- a collector that breaks
the cycle when one exchange has a bad minute is worse than a collector that skips a day.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_OUT = ROOT / "data/tail_funding_divergence.jsonl"
_TIMEOUT = 20


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-tail-funding"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read().decode())


def _binance() -> list[object]:
    """Funding + mark from premiumIndex, open interest from the 24h ticker (quoteVolume proxy)."""
    from libs.research.tail_funding import VenueQuote
    prem = _get("https://fapi.binance.com/fapi/v1/premiumIndex")
    tick = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    vol = {str(t["symbol"]): float(t.get("quoteVolume", 0) or 0)
           for t in tick if isinstance(t, dict)}
    out = []
    for p in prem if isinstance(prem, list) else []:
        sym = str(p.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        out.append(VenueQuote(symbol=sym, venue="binance",
                              funding_rate=float(p.get("lastFundingRate", 0) or 0),
                              open_interest_usd=vol.get(sym, 0.0)))
    return out


def _bybit() -> list[object]:
    from libs.research.tail_funding import VenueQuote
    data = _get("https://api.bybit.com/v5/market/tickers?category=linear")
    rows = (data or {}).get("result", {}).get("list", []) if isinstance(data, dict) else []
    out = []
    for r in rows:
        sym = str(r.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        out.append(VenueQuote(symbol=sym, venue="bybit",
                              funding_rate=float(r.get("fundingRate", 0) or 0),
                              open_interest_usd=float(r.get("turnover24h", 0) or 0)))
    return out


def main() -> int:
    from libs.research.tail_funding import divergences

    quotes: list[object] = []
    reached: list[str] = []
    for name, fn in (("binance", _binance), ("bybit", _bybit)):
        try:
            got = fn()
        except Exception as exc:
            print(f"[tail-funding] {name} unreachable ({type(exc).__name__}) -- skipping")
            continue
        quotes.extend(got)
        reached.append(name)
        print(f"[tail-funding] {name}: {len(got)} USDT perps")

    if len(reached) < 2:
        print("[tail-funding] need TWO venues for a spread -- nothing to compare, not a failure")
        return 0

    divs = divergences(quotes)  # type: ignore[arg-type]
    credible = [d for d in divs if d.credible]
    now = datetime.now(tz=UTC).isoformat()
    with _OUT.open("a", encoding="utf-8") as fh:
        for d in divs:
            fh.write(json.dumps({"ts": now, "venues": reached, **d.model_dump()}) + "\n")

    print(f"[tail-funding] {len(divs)} gap(s) over the bar, {len(credible)} credible")
    for d in credible[:5]:
        print(f"  {d.symbol:<14} {d.spread_annual:>7.1%} annual  long {d.long_venue} / "
              f"short {d.short_venue}  thin-leg OI ${d.min_oi_usd:,.0f}")
    for d in (x for x in divs if not x.credible):
        print(f"  [FLAGGED] {d.symbol}: {d.note[:90]}")
    print(f"[tail-funding] appended to {_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
