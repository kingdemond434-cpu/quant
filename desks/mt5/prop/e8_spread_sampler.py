"""Sample E8's spreads across the hours the certified book actually fires.

WHY THIS EXISTS RATHER THAN ONE READING. The first measurement of this venue was taken at 23:56
UTC -- the daily rollover -- and showed AUDNZD at 36.8 pips and AUDCAD at 29.9. Those are
rollover numbers, not trading numbers, and sizing a $100,000 evaluation off them would be as
wrong as sizing off the tightest tick of the London session.

IT MATTERS MORE HERE THAN ANYWHERE ELSE. Every one of the 51 tradeable certificates fires in the
ASIA window, which opens directly after this rollover, and the desk has already measured on its
own venue that AUDNZD's spread widens 88x at hour 00 against a mechanism that dies at 2.34x cost.
If that holds at E8 the book is untradeable at the hour it is certified for, and that is a fact
worth having BEFORE the first trade rather than after twenty.

Writes desks/mt5/reports/E8_SPREADS.json -- per symbol, per UTC hour: n, median, p90, min.
"""
from __future__ import annotations

import collections
import json
import logging
import pathlib
import statistics
import sys
import time
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parents[3]
for _p in (str(ROOT / "desks" / "mt5"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
logging.disable(logging.ERROR)

from prop.tradelocker_venue import TradeLockerVenue  # noqa: E402

OUT = ROOT/"desks"/"mt5"/"reports"/"E8_SPREADS.json"
SYMS = ["EURUSD","XAUUSD","USDCHF","USDCAD","EURGBP","GBPJPY","EURJPY","USDJPY","CADJPY",
        "AUDUSD","AUDNZD","AUDCAD","AUDCHF","CADCHF","EURAUD","EURCHF","GBPAUD","GBPCHF","NZDCAD"]
INTERVAL_S = 300
HOURS = 10

v = TradeLockerVenue().connect()
samples: dict[str, list[tuple[int, float]]] = collections.defaultdict(list)
if OUT.exists():
    try:
        for s, rows in (json.loads(OUT.read_text(encoding="utf-8")).get("raw") or {}).items():
            samples[s] = [tuple(r) for r in rows]
    except Exception:
        pass

deadline = time.time() + HOURS*3600
while time.time() < deadline:
    hour = datetime.now(UTC).hour
    for s in SYMS:
        try:
            bid, ask = v.quote(s)
            samples[s].append((hour, round(1e4*(ask-bid)/bid, 3)))
        except Exception:
            pass
    by_hour: dict[str, dict[str, dict[str, float]]] = {}
    # PER SYMBOL: did the quote actually MOVE while we watched it? See the block below.
    liveness: dict[str, dict[str, object]] = {}
    doc: dict[str, object] = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "unit": "basis points of price (spread/bid * 1e4)",
        "rule": "median per UTC hour; the asia window is what the certified book trades",
        "raw": dict(samples), "by_hour": by_hour, "liveness": liveness}
    for s, rows in samples.items():
        per: dict[int, list[float]] = collections.defaultdict(list)
        for h, bp in rows:
            per[h].append(bp)
        by_hour[s] = {str(h): {"n": len(x), "median": round(statistics.median(x), 3),
                               "min": round(min(x), 3), "max": round(max(x), 3)}
                      for h, x in sorted(per.items())}
        # A FROZEN QUOTE IS NOT A MEASURED SPREAD (added 2026-09-14).
        #
        # `v.quote()` answers while the market is SHUT -- it returns the last quote the venue
        # holds -- so a sampler that runs over a weekend records a real number that is not a
        # tradeable cost. Measured on the first live run: every symbol came back with
        # min == max == median across 11 samples spanning several hours, and USDJPY published
        # 17.3 bps against a normal ~0.7 while AUDUSD published 26.8. Those are closing-auction
        # spreads, and a cost model fed from them is pessimistic by 10-20x on the majors.
        #
        # It would have been WORSE THAN WRONG, because it is wrong in the direction that looks
        # prudent: the executor's spread fence refuses a trade whose cost exceeds a fraction of
        # its stop, so a frozen weekend quote does not mis-size anything -- it silently refuses
        # the cheapest instruments on the account, and the refusal reads as a cost discipline.
        #
        # Zero dispersion over samples drawn in more than one hour is the signature, and it is
        # not something a live market produces. It is published rather than dropped: the reading
        # is real, it is simply a reading of a closed venue, and a consumer must be able to tell
        # those apart (WS-005).
        _all = [bp for _, bp in rows]
        _hours = {h for h, _ in rows}
        _frozen = len(_all) >= 3 and len(_hours) > 1 and max(_all) == min(_all)
        liveness[s] = {
            "n_samples": len(_all),
            "distinct_hours": len(_hours),
            "distinct_values": len(set(_all)),
            "quote_moved": not _frozen,
            "verdict": "FROZEN_QUOTE_MARKET_LIKELY_CLOSED" if _frozen else "LIVE",
            "usable_as_cost": not _frozen,
        }
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    time.sleep(INTERVAL_S)
print("done", OUT)
