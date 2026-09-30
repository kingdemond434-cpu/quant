"""NEWS REACTION -- the unscheduled headline, whose arrival time is itself the signal.

`research/empty_cluster_forcer.py` named this file as the one artifact that makes the
`news_reaction` alpha cluster reachable: "distinct from `event_reaction`, which classifies into
event_surprise: that family trades the SCHEDULED release, this one trades the UNSCHEDULED
headline". Until a dated stream of unscheduled primary-source headlines existed there was nothing
for it to read. `research/corporate_disclosure.py` now writes one: guidance revisions, buybacks,
tender offers, M&A, equity issuance, trading halts, regulator inquiries, contract wins and 8-K
items that no calendar announced in advance -- from TDnet, EDINET, DART, cninfo, SSE, SZSE and
EDGAR, in the issuers' own languages.

THE SPLIT FROM `event_reaction` IS THE CLOCK, NOT THE CODE. The execution is the event
executor's own (`family_event_reaction`: entry on the first bar that OPENS after the headline was
knowable, UTC stamps converted into the bars' broker clock, drift and fade as separate claims).
What differs is which events a cell may name: this family reads only UNSCHEDULED categories, so a
cell here and a cell there can never be the same question counted twice.

REFUSES -- returns no signals -- without a stream spec (`mt5desk.disclosure_events`), with a spec
naming a scheduled category, or when the stream holds no event for the symbol. No stream is
UNMEASURED; it never falls back to price.
"""
from __future__ import annotations

import pandas as pd
from mt5desk.families import Signal

#: Categories `research/corporate_disclosure.classify` marks SCHEDULED. A news_reaction cell on
#: one of them would duplicate an event_reaction cell under another cluster's name.
SCHEDULED_CATEGORIES: frozenset[str] = frozenset({"earnings", "periodic_report", "monthly_sales",
                                                  "dividend"})


def family_news_reaction(
    df: pd.DataFrame,
    *,
    event_stream: str = "",
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
    """Trade the bars after an unscheduled disclosure on `symbol`, drift or fade."""
    from mt5desk.disclosure_events import parse_spec
    from mt5desk.family_event_reaction import family_event_reaction

    spec = parse_spec(event_stream)
    if spec is None or not symbol or spec["category"] in SCHEDULED_CATEGORIES:
        return []
    return family_event_reaction(
        df, events=[], symbol=symbol, mode=mode, side=side, hold_bars=hold_bars, atr_n=atr_n,
        stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars, cooldown_bars=cooldown_bars,
        clock="utc", event_stream=event_stream)
