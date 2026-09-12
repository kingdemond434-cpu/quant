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
import json, pathlib, sys, time, logging, statistics, collections
from datetime import UTC, datetime
ROOT = pathlib.Path(r"C:\opt\quant")
sys.path.insert(0, str(ROOT/"desks"/"mt5")); sys.path.insert(0, str(ROOT))
logging.disable(logging.ERROR)
from prop.tradelocker_venue import TradeLockerVenue, VenueError

OUT = ROOT/"desks"/"mt5"/"reports"/"E8_SPREADS.json"
SYMS = ["EURUSD","XAUUSD","USDCHF","USDCAD","EURGBP","GBPJPY","EURJPY","USDJPY","CADJPY",
        "AUDUSD","AUDNZD","AUDCAD","AUDCHF","CADCHF","EURAUD","EURCHF","GBPAUD","GBPCHF","NZDCAD"]
INTERVAL_S = 300
HOURS = 10

v = TradeLockerVenue().connect()
samples = collections.defaultdict(list)
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
    doc = {"generated_utc": datetime.now(UTC).isoformat(),
           "unit": "basis points of price (spread/bid * 1e4)",
           "rule": "median per UTC hour; the asia window is what the certified book trades",
           "raw": {k: v_ for k, v_ in samples.items()}, "by_hour": {}}
    for s, rows in samples.items():
        per = collections.defaultdict(list)
        for h, bp in rows:
            per[h].append(bp)
        doc["by_hour"][s] = {str(h): {"n": len(x), "median": round(statistics.median(x), 3),
                                      "min": round(min(x), 3), "max": round(max(x), 3)}
                             for h, x in sorted(per.items())}
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    time.sleep(INTERVAL_S)
print("done", OUT)
