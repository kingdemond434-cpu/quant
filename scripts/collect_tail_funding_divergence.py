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

CENSORED PRINTS (R0293). Venues CLAMP funding at a per-symbol min/max, and the thin tail is
precisely the cohort that pins there. A print at >=99% of its clamp is CENSORED data -- the venue
saying "at least this much" -- so each recorded row carries ``censored: true/false`` (per-symbol
clamps from libs/data/funding_caps for Binance, instruments-info for Bybit). Rows are labelled,
NEVER dropped: censoring truncates the spread (it is a lower bound) and is itself a regime fact
(funding pinned at its cap can no longer pull perp to index).

READERS OF data/tail_funding_divergence.jsonl (none in-repo as of 2026-08-04 -- verified by grep):
any future consumer MUST exclude rows with ``censored: true`` from spread statistics or bucket
them separately. A censored print averaged into the uncensored panel re-creates the exact
measurement error this label exists to prevent.
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
    """Funding + mark from premiumIndex, open interest from the 24h ticker (quoteVolume proxy).

    R0293: premiumIndex returns the CLAMPED print but not the clamp, so the per-symbol caps come
    from libs/data/funding_caps -- one extra keyless fundingInfo fetch when this box can reach
    Binance (the VPS can; the dev container gets HTTP 451 and degrades to cache/static tiers,
    honestly labelled). refresh=True here IS the refresh-on-VPS mechanism: this collector runs
    daily on the VPS via daily_research_cycle, rewriting data/funding_caps.json with venue truth.
    """
    from libs.data.funding_caps import get_caps
    from libs.research.tail_funding import VenueQuote
    prem = _get("https://fapi.binance.com/fapi/v1/premiumIndex")
    tick = _get("https://fapi.binance.com/fapi/v1/ticker/24hr")
    caps = get_caps(refresh=True)
    print(f"[tail-funding] binance funding clamps: {caps.source} "
          f"({len(caps.caps)} adjusted symbols + tier defaults)")
    vol = {str(t["symbol"]): float(t.get("quoteVolume", 0) or 0)
           for t in tick if isinstance(t, dict)}
    out = []
    for p in prem if isinstance(prem, list) else []:
        sym = str(p.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        rate = float(p.get("lastFundingRate", 0) or 0)
        out.append(VenueQuote(symbol=sym, venue="binance", funding_rate=rate,
                              open_interest_usd=vol.get(sym, 0.0),
                              funding_cap=caps.clamp_for(sym, rate)))
    return out


def _bybit_caps() -> dict[str, tuple[float, float]]:
    """Per-symbol (upper, lower) funding clamps from instruments-info -- same host, same keyless
    access as the tickers call below, so if tickers answer this almost always does too. Failure
    degrades to {} (cap unknown -> never labelled), it does not lose the venue's quotes."""
    caps: dict[str, tuple[float, float]] = {}
    cursor = ""
    for _ in range(5):                    # linear fits in one 1000-row page; bound the loop anyway
        url = ("https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000"
               + (f"&cursor={cursor}" if cursor else ""))
        data = _get(url)
        result = (data or {}).get("result", {}) if isinstance(data, dict) else {}
        for r in result.get("list", []) or []:
            try:
                caps[str(r["symbol"])] = (float(r["upperFundingRate"]),
                                          float(r["lowerFundingRate"]))
            except (KeyError, TypeError, ValueError):
                continue                  # a symbol without published clamps stays unlabelled
        cursor = str(result.get("nextPageCursor") or "")
        if not cursor:
            break
    return caps


def _bybit() -> list[object]:
    from libs.research.tail_funding import VenueQuote
    data = _get("https://api.bybit.com/v5/market/tickers?category=linear")
    rows = (data or {}).get("result", {}).get("list", []) if isinstance(data, dict) else []
    try:
        caps = _bybit_caps()
    except Exception as exc:
        print(f"[tail-funding] bybit clamps unreadable ({type(exc).__name__}) -- "
              "quotes kept, censor label unavailable on this venue this run")
        caps = {}
    out = []
    for r in rows:
        sym = str(r.get("symbol", ""))
        if not sym.endswith("USDT"):
            continue
        rate = float(r.get("fundingRate", 0) or 0)
        pair = caps.get(sym)
        # Sidedness: a positive print pins at the UPPER clamp, a negative one at the LOWER.
        cap = (abs(pair[0]) if rate >= 0 else abs(pair[1])) if pair else None
        out.append(VenueQuote(symbol=sym, venue="bybit", funding_rate=rate,
                              open_interest_usd=float(r.get("turnover24h", 0) or 0),
                              funding_cap=cap))
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
    # R0293 buckets: a censored row is recorded (never dropped) but shown apart -- a print pinned
    # at its clamp is the clamp's number, not the market's, and must not read as an opportunity.
    credible = [d for d in divs if d.credible and not d.censored]
    censored = [d for d in divs if d.censored]
    now = datetime.now(tz=UTC).isoformat()
    with _OUT.open("a", encoding="utf-8") as fh:
        for d in divs:
            fh.write(json.dumps({"ts": now, "venues": reached, **d.model_dump()}) + "\n")

    print(f"[tail-funding] {len(divs)} gap(s) over the bar, {len(credible)} credible, "
          f"{len(censored)} censored (clamp-pinned; recorded + labelled, not ranked)")
    for d in credible[:5]:
        print(f"  {d.symbol:<14} {d.spread_annual:>7.1%} annual  long {d.long_venue} / "
              f"short {d.short_venue}  thin-leg OI ${d.min_oi_usd:,.0f}")
    for d in (x for x in divs if not x.credible and not x.censored):
        print(f"  [FLAGGED] {d.symbol}: {d.note[:90]}")
    for d in censored:
        print(f"  [CENSORED] {d.symbol}: {d.note[:90]}")
    print(f"[tail-funding] appended to {_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
