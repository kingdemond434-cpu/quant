"""Stop-and-reverse into a dislocation: count it, so a second one is evidence and not an anecdote.

WHAT HAPPENED ONCE, MEASURED 2026-09-11. A gold_asia long from 4340.76 held its stop at 4300.69.
One M1 bar ran 4341.34 -> 4288.33 -> 4296.81 -- a 60.10 point range in sixty seconds, with the
spread NORMAL throughout (median 6, max 10) and tick volume 368 against a 350-380 baseline. So it
was not a broker event and not a cost event. The wick took the stop at 4298.87, and because the
bracket's sell_stop sat at that same level the desk OPENED A SHORT AT 4298.87 IN THE SAME SECOND,
at the low tick of the spike. Price was fully back by 15:36 and higher by 15:40; the short stopped
at 4340.68. Two losses of about 72 EUR from one six-minute round trip that ended where it began --
144.83 on a month that made 193.50.

THERE IS NO OCO, NO COOLDOWN AND NO OPPOSITE-LEG CANCELLATION anywhere in the gateway, so a wick
through a stop is STRUCTURALLY GUARANTEED to open the reverse position at the worst available
tick. That is a real weakness and this module deliberately does NOT fix it.

TWO SEPARATE THINGS, AND CONFLATING THEM WAS MY FIRST ERROR. A DISLOCATED ENTRY and a
STOP-AND-REVERSE are different events that happened to coincide once. Measured over 30 days on
account 495044:

    dislocated entries   3 of 30, net -17.00   (+37.66, +17.58, -72.24)  two made money
    stop-and-reverse     3,       net -30.20   (+42.08, -72.24, -0.04)   one made money

Only 2026-09-11 is in both lists. So blocking dislocated entries would have improved a 193.50
month by 17.00 on a sample of three -- noise -- and the reverse is a DIFFERENT mechanism with its
own, also tiny, sample.

AND THE REVERSE IS RECURRING, NOT A ONE-OFF. I first reported it as having happened once. That was
this module's own bug: it required the two deals to be OPPOSITE types, when closing a long and
opening a short are BOTH sell deals, so the only event on record scored as absent. Corrected, the
count is three in thirty days -- roughly weekly, across two different gold sleeves -- and the
third was still open when this was written.

THREE IS STILL NOT A SAMPLE. Building an execution rule on it is fitting logic to a handful of
minutes, which is what L0330 exists to refuse, and one of the three earned +42.08 -- so an OCO
would have cost that. Hence: name the pattern, count it, and let the evidence decide later. If it
never recurs, that is a real answer too (negative_knowledge).

    python desks/mt5/research/stop_reverse_census.py
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mt5_session import attach_or_initialize

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "reports" / "STOP_REVERSE_CENSUS.json"

#: How close in time two deals must be for the second to be a REVERSE of the first rather than an
#: independent decision. Two seconds: the observed case shared a timestamp to the second, and a
#: pending stop filling off the same tick cannot be further apart than the platform's own clock.
SAME_TICK_SECONDS = 2.0

#: How far apart their prices may be, as a fraction of the entry price. The observed pair shared a
#: price EXACTLY; this allows for a venue filling the two legs a few ticks apart.
SAME_PRICE_FRAC = 0.0005

#: A bar is DISLOCATED at this multiple of its own trailing median range. Five is deliberately
#: loose -- the observed events measured 7.4x, 34.9x and 55.9x -- because the purpose here is to
#: COUNT, and a tight threshold would hide the near-misses that decide whether a rule is worth
#: building later.
SPIKE_MULT = 5.0

#: Bars of trailing context the median is taken over. Two hours of M1.
BASELINE_BARS = 120

#: Days of deal history to census. The account's own history is the only sample there is.
WINDOW_DAYS = 45


def _deals(mt5: Any, symbol: str | None = None) -> list[Any]:
    """The window's deals. NAIVE LOCAL TIME on purpose: `history_deals_get` takes the terminal's
    own naive datetimes, and handing it a tz-aware value returns nothing at all. The EPOCH each
    deal carries is what everything downstream reads, and that is converted with an explicit tz.
    """
    frm = datetime.now(tz=UTC) - timedelta(days=WINDOW_DAYS)
    got = mt5.history_deals_get(frm.replace(tzinfo=None), datetime.now()) or ()  # noqa: DTZ005
    return [d for d in got if symbol is None or d.symbol == symbol]


def census(mt5: Any = None) -> dict[str, Any]:
    """Every stop-and-reverse, and every entry on a dislocated bar, with what it earned.

    UNMEASURED IS A VERDICT (L1.28a). No terminal, no history or no bars yields a report that says
    so; it never yields a zero, because "it has not happened" and "I could not look" are the two
    claims this file exists to keep apart.
    """
    out: dict[str, Any] = {"generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "window_days": WINDOW_DAYS, "measured": False}
    if mt5 is None:
        try:
            import MetaTrader5 as _mt5
            mt5 = _mt5
        except ImportError:
            out["why"] = "MetaTrader5 unavailable on this host"
            return out
    if not attach_or_initialize(mt5, allow_autostart=False):
        out["why"] = "no terminal attached in research session; autostart prohibited"
        return out
    try:
        import pandas as pd
    except ImportError:
        out["why"] = "pandas unavailable"
        return out

    deals = _deals(mt5)
    if not deals:
        out.update({"measured": True, "n_deals": 0, "n_stop_and_reverse": 0, "n_spike_entries": 0,
                    "stop_and_reverse": [], "spike_entries": [],
                    "why": "no deals in the window"})
        return out

    # THE TWO CLOCKS MUST BE ONE CLOCK, and getting this wrong is why the first pass at this
    # analysis read prices seventy points away from the bars. `history_deals_get` and
    # `copy_rates_*` both return an epoch; converting one with `fromtimestamp()` (box-local) and
    # the other with `to_datetime(unit="s")` (UTC) silently shifts them by the host's offset.
    # Both are converted here with an explicit tz and never with the naive form.
    entries = [d for d in deals if d.entry == 0]
    exits = [d for d in deals if d.entry == 1]

    pnl_by_pos: dict[int, float] = {}
    for d in deals:
        pnl_by_pos[int(d.position_id)] = (pnl_by_pos.get(int(d.position_id), 0.0)
                                          + float(d.profit) + float(d.swap) + float(d.commission))

    reverses: list[dict[str, Any]] = []
    for e in entries:
        for x in exits:
            if x.position_id == e.position_id or abs(x.time - e.time) > SAME_TICK_SECONDS:
                continue
            if e.price <= 0 or abs(x.price - e.price) / e.price > SAME_PRICE_FRAC:
                continue
            # THE TWO DEALS SHARE A TYPE, AND THAT IS THE WHOLE POINT. Closing a LONG is a
            # SELL deal; opening a SHORT is also a SELL deal. A stop-and-reverse is therefore
            # two deals of the SAME type on one tick, not opposite ones -- the positions are
            # opposite, the deals are not. My first version required opposite types and so
            # scored the 2026-09-11 event, the only one on record, as absent.
            if x.type != e.type:
                continue
            reverses.append({
                "at": datetime.fromtimestamp(e.time, tz=UTC).isoformat(timespec="seconds"),
                "symbol": e.symbol, "opened": "BUY" if e.type == 0 else "SELL",
                "price": round(float(e.price), 2),
                "closed_position": int(x.position_id), "opened_position": int(e.position_id),
                "net_of_opened_position": round(pnl_by_pos.get(int(e.position_id), 0.0), 2),
                "comment": str(e.comment)[:60]})

    spikes: list[dict[str, Any]] = []
    for sym in sorted({d.symbol for d in entries}):
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 20000)
        if rates is None or not len(rates):
            continue
        df = pd.DataFrame(rates)
        df["t"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["rng"] = df["high"] - df["low"]
        df["base"] = df["rng"].rolling(BASELINE_BARS).median()
        idx = df.set_index("t")
        for e in (d for d in entries if d.symbol == sym):
            t = datetime.fromtimestamp(e.time, tz=UTC).replace(second=0, microsecond=0)
            key = pd.Timestamp(t)
            if key not in idx.index:
                continue
            bar = idx.loc[key]
            base = float(bar["base"]) if bar["base"] == bar["base"] else 0.0
            if base <= 0:
                continue
            mult = float(bar["rng"]) / base
            if mult < SPIKE_MULT:
                continue
            spikes.append({"at": t.isoformat(timespec="minutes"), "symbol": sym,
                           "side": "BUY" if e.type == 0 else "SELL",
                           "price": round(float(e.price), 2),
                           "bar_range": round(float(bar["rng"]), 2),
                           "x_median": round(mult, 1),
                           "spread_points": int(bar["spread"]) if "spread" in bar else 0,
                           "net_of_position": round(pnl_by_pos.get(int(e.position_id), 0.0), 2),
                           "comment": str(e.comment)[:60]})

    out.update({
        "measured": True,
        "rule": ("a REVERSE is an entry within 2s and 0.05% of an opposite-direction exit -- one "
                 "price level paying twice. A DISLOCATED entry landed on a bar >= 5x its own "
                 "trailing median range. Counted, never blocked: two of three dislocated entries "
                 "and one of three reverses made money."),
        "n_deals": len(deals), "n_entries": len(entries),
        "n_stop_and_reverse": len(reverses),
        "n_spike_entries": len(spikes),
        "net_of_spike_entries": round(sum(s["net_of_position"] for s in spikes), 2),
        "verdict": ("SAMPLE" if len(reverses) >= 5 else
                    "ANECDOTE: too few to justify an execution rule; L0330 applies"),
        "stop_and_reverse": reverses,
        "spike_entries": spikes,
    })
    return out


def main() -> int:
    doc = census()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    if not doc.get("measured"):
        print("stop-reverse census: UNMEASURED -- " + str(doc.get("why")))
        print("  -> " + str(OUT))
        return 0
    print(f"stop-reverse census: {doc['n_deals']} deal(s), {doc['n_entries']} entries")
    print(f"  stop-and-reverse (one level paying twice): {doc['n_stop_and_reverse']}")
    print(f"  entries on a dislocated bar: {doc['n_spike_entries']}"
          f"  net {doc['net_of_spike_entries']:+.2f}")
    for r in doc["stop_and_reverse"][:6]:
        print(f"    REVERSE {r['at']} {r['symbol']} {r['opened']} @ {r['price']} "
              f"-> net {r['net_of_opened_position']:+.2f}  ({r['comment']})")
    for s in doc["spike_entries"][:6]:
        print(f"    SPIKE   {s['at']} {s['symbol']} {s['side']} @ {s['price']} "
              f"{s['x_median']}x median -> net {s['net_of_position']:+.2f}")
    print(f"  verdict: {doc['verdict']}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
