"""The lane 103 instruments were routed to and which had no engine.

`research/universe_policy.py` does not exclude single-name equities -- it ROUTES them: "they are
traded on news, financial reports and earnings reaction", and 103 of the registry's 251 symbols
carry that routing. The reasoning is sound and measured (on one docket, single-name equities were
44.8% of cells and about 61% of the multiple-testing charge, spent on the class least suited to
statistical discovery, and `deflated_sharpe` rejected 42 of 42). But the lane those instruments
were routed INTO did not exist: `event_calendar` and `event_density` are readers, `news_desk`
idles, `earnability` had no consumer at all. Forty-one percent of the universe was assigned to a
department with no staff.

This is the executor. It takes DATED events -- an insider cluster from `libs.research.form4`, an
earnings date, a macro print -- and produces the ordinary `Signal` objects every other family
produces, so the existing gauntlet judges an event hypothesis exactly as harshly as a price one.
That is the whole design: the event lane must not become a second, gentler standard.

WHY THIS IS A DIFFERENT CAUSE AND NOT ANOTHER PRICE FAMILY. Every registered family reads the
price path. This one fires on a fact from outside the tape -- a filing, a print -- and its failure
mode is its own: it loses when the event was already priced, which is uncorrelated with a trend
exhausting or a range breaking. An instrument can be perfectly quiet on every price-based reading
and have three officers buying it that morning.

THE POINT-IN-TIME RULE IS INHERITED AND ENFORCED AGAIN HERE. An event carries `at` -- the moment
the market could first know. Entry is the first bar that OPENS at or after it; never the bar
containing it, whose open precedes the news. Getting this wrong is silent and flattering, so the
family re-checks rather than trusting its input: `test_an_event_cannot_be_traded_on_the_bar_that_
contains_it` is the guard.

NO SCORE THRESHOLD LIVES HERE. Which events are worth trading is the miner's decision and the
gauntlet's verdict. A family that filtered its own input on a score would be choosing its
evidence after seeing it.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1

#: The two claims an event permits, kept as separate modes so the family cannot pick whichever
#: fits after seeing the data -- the same discipline `family_clock_transition` applies to its three.
MODES = ("drift", "fade")

#: The field carrying the moment the market could first know. `libs.research.form4` writes
#: `knowable_at` into `at`; nothing here may read a transaction or announcement date.
AT_KEY = "at"


def _event_times(events: Sequence[dict[str, Any]], symbol: str) -> list[pd.Timestamp]:
    """Every knowable-at for `symbol`, sorted, tz-aware. Malformed rows are skipped, not guessed."""
    out: list[pd.Timestamp] = []
    for e in events or ():
        if str(e.get("symbol", "")).upper() != symbol.upper():
            continue
        raw = e.get(AT_KEY)
        if not raw:
            continue
        try:
            ts = pd.Timestamp(raw)
        except (TypeError, ValueError):
            continue
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        out.append(ts)
    return sorted(set(out))


def family_event_reaction(
    df: pd.DataFrame,
    *,
    events: Sequence[dict[str, Any]] | None = None,
    symbol: str = "",
    mode: str = "drift",
    side: int = 1,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 48,
    cooldown_bars: int = 12,
) -> list[Signal]:
    """Trade the bars after a dated event, entering only once the market could know about it.

    `side` is the direction the EVENT implies -- +1 for an insider cluster (people buying their
    own company), -1 for the mirror hypothesis. `mode` then says whether the claim is that the
    reaction continues (`drift`) or overshoots (`fade`), and the two are separate hypotheses.
    """
    if not events or mode not in MODES or side not in (1, -1) or symbol == "":
        return []
    d = _h1(df)
    if len(d) < atr_n + 4:
        return []
    times = _event_times(events, symbol)
    if not times:
        return []

    atr = _atr(d, atr_n)
    close = d["close"].astype(float)
    index = d.index
    signals: list[Signal] = []
    armed_from = 0
    for ts in times:
        # THE FIRST BAR THAT OPENS AT OR AFTER THE NEWS. `searchsorted(..., "left")` on a bar
        # index whose labels are OPEN times gives the first bar not starting before `ts`. The bar
        # CONTAINING the event opened before it, so entering there buys at a price set while the
        # filing was still private -- the flattering, silent version of this study.
        pos = int(index.searchsorted(ts, side="left"))
        if pos <= armed_from or pos >= len(d) - 1:
            continue
        a = float(atr.iloc[pos])
        if not np.isfinite(a) or a <= 0:
            continue
        direction = side if mode == "drift" else -side
        px = float(close.iloc[pos])
        signals.append(Signal(
            time=index[pos], side=direction,
            stop=px - direction * stop_atr * a,
            target=px + direction * stop_atr * a * rr,
            ttl_bars=int(min(ttl_bars, max(1, hold_bars * 2))),
            tag=f"event_{mode}", trigger=None, wait_bars=1))
        armed_from = pos + max(1, int(cooldown_bars))
    return signals
