"""Trade a named moment in the market's plumbing: a fix, a settlement, a handoff, a rollover.

THE MECHANISM CLASS. One of the few Renaissance effects ever described publicly was a fifteen-
minute mismatch between the closing times of S&P options and futures. It was not a pattern in
price; it was a fact about the calendar of the venues. This desk's offering has a whole clock of
such moments -- the London fix, the NY option cut, the CME close, the cash-index close, the
broker's own rollover -- and each is a moment when flow is FORCED rather than chosen: benchmarks
must be matched, options must be settled, positions must be marked. Forced flow is the most
reliable source of temporary mispricing there is, and none of it was expressible here.

WHY A DEDICATED FAMILY AND NOT `family_generic`. The generic coordinate family has a
`session_transition` event and a `month_end` context, but its contexts are fixed hour ranges
written in one clock. A plumbing hypothesis is about ONE stamp-hour, named, and that hour must
sit on the certificate unambiguously -- "the London fix" is 16:00 London, which is 15:00 or 16:00
UTC by season and 18:00 or 19:00 in the broker's stamp. The family therefore takes the STAMP HOUR
explicitly and the miner does the conversion once, with the offset it measured, so a certified
cell can be rebuilt exactly whatever anyone later believes about time zones.

THREE CLAIMS PER MOMENT, all tested so none is chosen after the fact:
    into      position taken `lead_bars` before the moment and closed at it -- flow anticipation
    out_of    position taken at the moment and held `hold_bars` -- the unwind
    fade      the move INTO the moment is faded out of it -- the mismatch closing

`side` is +1/-1 and is a hypothesis parameter; the miner tests both.

REFUSES a stamp hour the bars never carry (a 24h-market family run on an index that closes), and
a `label` that is not one of the catalogue's -- a plumbing cell with no named cause is a
time-of-day curve fit wearing a better story.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1, bars_per_day

#: The catalogue of plumbing moments, in UTC hours by season. DECLARED, because they are facts
#: about venues rather than anything price can reveal. (summer_utc, winter_utc).
CATALOGUE: dict[str, dict] = {
    "london_fix":       {"utc": (15, 16), "why": "WM/Reuters 16:00 London benchmark: passive FX "
                                                 "flow must be executed at the fix"},
    "ny_option_cut":    {"utc": (14, 15), "why": "10:00 NY option expiry: strikes pin and "
                                                 "delta hedges unwind into it"},
    "cme_fx_close":     {"utc": (21, 22), "why": "CME currency futures settle; basis trades "
                                                 "and spot hedges rebalance"},
    "cash_equity_close": {"utc": (20, 21), "why": "US cash close: index rebalancing, "
                                                  "closing auctions, CFD marks"},
    "comex_settle":     {"utc": (17, 18), "why": "COMEX metals settlement window"},
    "tokyo_open":       {"utc": (0, 0),   "why": "Tokyo 09:00: the first liquid Asian bid "
                                                 "after the New York close"},
    "london_open":      {"utc": (7, 8),   "why": "London 08:00: the largest FX liquidity "
                                                 "handoff of the day"},
    "ny_open":          {"utc": (13, 14), "why": "New York 09:30 equity open feeding FX and "
                                                 "metals risk appetite"},
    "broker_rollover":  {"utc": None,     "why": "the broker's daily swap and mark; spreads "
                                                 "widen by contract rather than sentiment",
                         "stamp": (23, 0)},
}

MODES = ("into", "out_of", "fade")


def stamp_hours_for(label: str, broker_utc_offset_h: int) -> tuple[int, ...]:
    """The broker stamp-hours a catalogue moment lands on, both seasons, deduplicated."""
    spec = CATALOGUE.get(label)
    if spec is None:
        return ()
    if spec.get("stamp") is not None:
        return tuple(sorted(set(int(h) % 24 for h in spec["stamp"])))
    return tuple(sorted({(int(h) + int(broker_utc_offset_h)) % 24 for h in spec["utc"]}))


def family_clock_transition(
    df: pd.DataFrame,
    *,
    label: str = "",
    stamp_hour: int = -1,
    mode: str = "out_of",
    side: int = 1,
    lead_bars: int = 2,
    hold_bars: int = 4,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """Signals at (or before) one named stamp-hour, every day the bars carry it."""
    if label not in CATALOGUE or mode not in MODES or side not in (1, -1):
        return []
    if not (0 <= int(stamp_hour) <= 23):
        return []
    d = _h1(df)
    # SIXTY DAYS OF HISTORY, on whatever chart this is. `24 * 60` was an hourly spelling of
    # "sixty days" and it asks a D1 chart for 1,440 bars (five and a half years) while waving
    # through an M1 frame an hour long. Identical on H1, where bars_per_day is 24.
    if len(d) < bars_per_day(d) * 60:
        return []
    hours = d.index.hour
    at = np.flatnonzero(hours == int(stamp_hour))
    if at.size < 40:
        return []                      # the bars do not carry this hour often enough to claim it
    atr = _atr(d, atr_n)
    close = d["close"].astype(float).to_numpy()
    signals: list[Signal] = []
    for i in at:
        if mode == "into":
            j = i - int(lead_bars)
            if j < 1:
                continue
            entry, ttl, s = j, int(lead_bars), side
        elif mode == "out_of":
            entry, ttl, s = i, int(hold_bars), side
        else:                          # fade: the direction of the move INTO the moment, reversed
            j = i - int(lead_bars)
            if j < 1:
                continue
            move = close[i] - close[j]
            if move == 0.0:
                continue
            entry, ttl, s = i, int(hold_bars), (-1 if move > 0 else 1) * side
        a = float(atr.iloc[entry])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(close[entry])
        signals.append(Signal(time=d.index[entry], side=s, stop=px - s * stop_atr * a,
                              target=px + s * stop_atr * a * rr, ttl_bars=max(1, ttl),
                              tag=f"clock_transition:{label}:{mode}", trigger=None,
                              wait_bars=1))
    return signals
