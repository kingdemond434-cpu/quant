"""Which lane an instrument belongs to: statistical hypothesis discovery, or event-driven.

PRINCIPAL'S ORDER, 2026-09-06: single-name equities are NOT hunted for statistical hypotheses.
They are traded on news, financial reports and earnings reaction. Forex, metals, energy, soft
commodities, indices, bonds and Fusion's crypto CFDs remain the hypothesis-discovery universe.

WHY THIS IS RIGHT AND NOT MERELY A PREFERENCE, recorded because a later reader will be tempted to
"restore breadth" by putting the shares back. Two independent reasons:

  A single name's hourly path is dominated by its own scheduled disclosures. An hypothesis of the
  form "Apple mean-reverts after a session-range breakout" is fitted across earnings dates,
  guidance, product events and index reconstitutions, and the fitted parameter is a blend of
  regimes that never recur in that mixture. The mechanism that actually moves the instrument --
  the announcement and the market's reaction function to it -- is not in the feature set at all.

  TRIAL COUNT IS A SHARED COST, and this is the part that is easy to miss. The deflated Sharpe
  charge and the SPA/PBO program-level tests divide the family-wise error budget across EVERY
  hypothesis the desk tested, so each equity cell raises the bar that every FX and metals cell
  must clear. Measured 2026-09-06: 597 trials in the campaign, and `deflated_sharpe` rejected 42
  of 42 judged cells. On that same docket 10,575 of 23,627 cells (44.8%) were single-name
  equities and a further 3,839 were equity tickers from a non-Fusion vocabulary -- about 61% of
  the multiple-testing charge, spent on the asset class least suited to the method, and paid for
  by the classes best suited to it.

So this is not a reduction in breadth. It is the same evidence budget spent where the mechanism
being modelled is the mechanism actually present.

NO SYMBOL LIST, EVER. Routing is by ASSET CLASS, read from MetaTrader's own registry entry and
falling back to the desk's pattern classifier. A share CFD listed tomorrow is routed correctly
the day it appears, and no edit here is required -- the failure mode of a hand-kept list is that
it is right on the day it is written and silently wrong afterwards.

WHAT THIS IS NOT. Equities are not removed from the desk's universe: the MT5 universe mandate
stands, they remain tradable, their bars and ticks are still collected, and the news/earnings
lane is where their edge is sought. `lane()` says which process may mint a hypothesis about an
instrument -- never whether the desk may hold it.
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe" / "universe.json"

#: The lane an instrument's edge is sought in.
HYPOTHESIS = "hypothesis"       # statistical discovery: the gauntlet, the miners, the sweeps
EVENT = "event"                 # news, financial reports, earnings reaction
UNCLASSIFIED = "unclassified"   # class unknown -- routed to NEITHER, and reported

#: Asset classes whose edge is sought through announcements rather than through price statistics.
#: Matched case- and separator-insensitively against both the registry's `asset_class` string and
#: the desk's pattern classifier, so "Equities", "equity" and "US Shares" all land here.
EVENT_DRIVEN_CLASSES = frozenset({
    "equities", "equity", "equities us", "shares", "share", "stock", "stocks",
})

#: Everything the gauntlet and the miners may hunt. Declared positively: a class that appears in
#: neither set is UNCLASSIFIED and is hunted by nothing until somebody decides where it belongs.
#: An unknown instrument quietly joining the discovery universe is how a vocabulary from another
#: broker got 3,839 cells onto this docket in the first place.
HYPOTHESIS_CLASSES = frozenset({
    "forex", "forex majors", "forex crosses", "forex exotics",
    "fx", "fx_major", "fx_cross", "fx_exotic",
    "commodity", "commodities", "soft commodity", "soft commodities", "soft",
    "metal", "metals", "precious metals",
    "energy", "indices", "index", "bond", "bonds", "crypto", "cryptocurrency",
})


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


@lru_cache(maxsize=1)
def _registry() -> dict[str, dict]:
    try:
        data = json.loads(UNIVERSE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k).upper(): v for k, v in data.items() if isinstance(v, dict)}


def asset_class_of(symbol: str) -> str:
    """The instrument's class, from MetaTrader's registry first and the classifier second.

    THE REGISTRY WINS because it is the broker's own answer, derived from the symbol's path and
    sector rather than inferred from its name. The pattern classifier is the fallback for a
    symbol whose registry row has not synced yet -- it is good, but it reads tickers, and a
    ticker is exactly what lies about a share CFD called `3M` or `A`.
    """
    row = _registry().get(str(symbol).strip().upper())
    if not isinstance(row, dict):
        # NOT IN THE BROKER'S REGISTRY, SO NOT ROUTED. The pattern classifier's last rule is
        # `\d?[A-Z]{1,12} -> equity`, a deliberate catch-all that serves its own purpose (share
        # CFDs arrive as company names and it must not report a whole asset class as unknown) but
        # is far too generous to decide a lane with: `NOTREAL` classified as an equity and was
        # routed to the news desk. Routing is a decision about a real instrument; a string that
        # is not in the registry is not one, and it must reach UNCLASSIFIED where it is reported.
        return ""
    declared = _norm(row.get("asset_class"))
    if declared:
        return declared
    # In the registry but carrying no class of its own -- 3 of 251 today. Here the classifier is
    # trustworthy, because the symbol is known to be a real broker instrument and only its label
    # is missing.
    try:
        sys.path.insert(0, str(BASE))
        from mt5desk.universe import asset_class as _pattern_class
        return _norm(_pattern_class(symbol))
    except Exception:                                                   # noqa: BLE001
        return ""


def lane(symbol: str) -> str:
    """`HYPOTHESIS`, `EVENT` or `UNCLASSIFIED` for `symbol`. Never raises."""
    klass = asset_class_of(symbol)
    if not klass:
        return UNCLASSIFIED
    if klass in EVENT_DRIVEN_CLASSES:
        return EVENT
    if klass in HYPOTHESIS_CLASSES:
        return HYPOTHESIS
    # A class the desk has never seen is NOT admitted by default. Absence of a rule is not a
    # permission, and defaulting to the discovery lane would let any new vocabulary spend the
    # trial budget before anybody noticed it had arrived.
    return UNCLASSIFIED


def may_hypothesise(symbol: str) -> bool:
    """True only for instruments whose edge is sought statistically."""
    return lane(symbol) == HYPOTHESIS


def split(symbols) -> dict[str, list[str]]:
    """Group an iterable of symbols by lane -- for reports that must name what they set aside."""
    out: dict[str, list[str]] = {HYPOTHESIS: [], EVENT: [], UNCLASSIFIED: []}
    for symbol in symbols:
        out[lane(symbol)].append(symbol)
    for key in out:
        out[key] = sorted(set(out[key]))
    return out
