"""WHAT MAY HOLD CAPITAL IN THE LIVE ACCOUNT -- one file, read by the gateway and the promoter.

THE PRINCIPAL'S ORDER (2026-09-17, live message): "the forex sleeves still didn't stop, they keep
firing, please disable all of them in my current live account, it's critical they're losing me
money" and "the bad m15 sleeve of gold is too". Measured on account 495044 the same hour, over
the trailing three days: 258 forex deals for **-73.24 EUR** (EURCHF -43.54 across 100 deals,
CHFNOK -10.38, AUDCAD -5.67, USDCHF -5.30, EURGBP -5.19, and eight more pairs negative; the only
positive symbol on the account was XAUUSD at +24.94).

WHY THIS FILE AND NOT ANOTHER RETIREMENT. The forex rows had been retired before -- by the decay
monitor, and again by the `discovered` family ban -- and they came BACK, because retirement acts
on rows while AUTOMATIC PROMOTION (principal, 2026-09-04) keeps writing new ones the moment a
clock matures: "all promotion candidates get into the live account immediately, no waiting, no
permission, fully automatically, always." A rule that only deletes rows loses that race forever.
This is an ADMISSION policy instead: the promoter may not write such a row and the gateway may
not trade one, so the next promotion wave cannot restore what the principal just stopped.

THIS IS NOT A RISK REDUCTION UNDER GROWTH GOVERNANCE, AND THE DISTINCTION MATTERS. The standing
order is that no session lowers the desk's aggressiveness by fiat (docs/GROWTH_GOVERNANCE.md, and
"NEVER REDUCE AGGRESSIVENESS", given three times). This is the PRINCIPAL'S OWN instruction about
which mechanisms may hold his capital today, with the loss that caused it measured above -- the
same class of act as the `discovered` family ban and the M15 removal. Heat, the gold floor, the
daily-loss parameters and the allocator's fractions are untouched: the freed heat goes to the
XAUUSD book, it is not left idle. A future session may widen this ONLY on the principal's word
(edit `data/live_sleeve_policy.json`, which is data with an author and a date) or on evidence the
principal has accepted -- never because a reviewer thinks the book looks narrow.

SCOPE IS THE LIVE ACCOUNT, NOT THE PROP ACCOUNT. The principal's words were "my current live
account" (495044). The E8 prop book is deliberately BUILT on forex mechanisms -- session range
breakout, overnight gap decay and carry are three of its four independent mechanisms
(docs/PROP_FIRM_E8.md) -- so applying this policy there would break the plan he designed, on an
account whose drawdown is E8's rule rather than his balance. E8 keeps its own family ban
(prop/e8_book.py reads research/family_policy.py) and is not filtered here.

FAIL-CLOSED. An absent or unreadable policy file reads as THESE DEFAULTS, not as "nothing
banned". The opposite convention (family_policy.py, where a missing file bans nothing) is right
for a research ban and wrong here: a truncated JSON file must not put forex back in a live
account at 3am.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: desks/mt5
BASE = Path(__file__).resolve().parents[1]
POLICY_FILE = BASE / "data" / "live_sleeve_policy.json"

#: The live sleeve universe by the principal's order of 2026-09-17. XAUUSD only.
DEFAULT_LIVE_SYMBOLS: frozenset[str] = frozenset({"XAUUSD"})
#: Symbol -> timeframes that may never take capital on it, with "*" meaning EVERY symbol.
#: The principal, 2026-09-17, twice: "the bad m15 sleeve of gold is too" and then "make sure the
#: m15 scalps r gone only m5 stays". M15 is therefore banned desk-wide, not only on gold: the
#: XAUUSD-only entry would have let an M15 sleeve on any future live symbol through, which is
#: exactly the shape of hole the last two retirements left.
DEFAULT_BANNED_TIMEFRAMES: dict[str, frozenset[str]] = {
    "*": frozenset({"M15"}), "XAUUSD": frozenset({"M15"})}
#: Families banned for live capital here as well as in research (see research/family_policy.py).
DEFAULT_BANNED_FAMILIES: frozenset[str] = frozenset({"discovered"})
ORDER = ("principal 2026-09-17: forex sleeves and the XAUUSD M15 sleeve are disabled in the "
         "live account (measured cause: -73.24 EUR of forex deals in three days on account "
         "495044 while XAUUSD made +24.94)")


@dataclass(frozen=True)
class Policy:
    live_symbols: frozenset[str] = DEFAULT_LIVE_SYMBOLS
    banned_timeframes: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: dict(DEFAULT_BANNED_TIMEFRAMES))
    banned_families: frozenset[str] = DEFAULT_BANNED_FAMILIES
    source: str = "defaults"
    by: str = ORDER

    def as_dict(self) -> dict[str, Any]:
        return {"live_symbols": sorted(self.live_symbols),
                "banned_timeframes": {k: sorted(v) for k, v in self.banned_timeframes.items()},
                "banned_families": sorted(self.banned_families),
                "source": self.source, "by": self.by}


def policy(path: Path | None = None) -> Policy:
    """The live policy in force. The file may only be authored by the principal's order; an
    unreadable or malformed file falls back to the defaults WITH the fallback named."""
    p = path or POLICY_FILE
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return Policy()
    if not isinstance(doc, dict):
        return Policy()
    syms = doc.get("live_symbols")
    tfs = doc.get("banned_timeframes")
    fams = doc.get("banned_families")
    live = frozenset(str(s).upper() for s in syms) if isinstance(syms, list) and syms \
        else DEFAULT_LIVE_SYMBOLS
    banned_tf: dict[str, frozenset[str]] = dict(DEFAULT_BANNED_TIMEFRAMES)
    if isinstance(tfs, dict):
        for sym, values in tfs.items():
            if isinstance(values, list):
                banned_tf[str(sym).upper()] = frozenset(str(v).upper() for v in values)
    banned_fam = frozenset(str(f).lower() for f in fams) if isinstance(fams, list) \
        else DEFAULT_BANNED_FAMILIES
    return Policy(live, banned_tf, banned_fam, source=str(p),
                  by=str(doc.get("by") or ORDER))


def refuse(row: Mapping[str, Any], pol: Policy | None = None) -> str | None:
    """The reason this sleeve may not hold live capital, or None when it may.

    A row with NO symbol is refused: an untradeable row is not a permission, and the gateway
    would otherwise size something it cannot name.
    """
    p = pol or policy()
    sym = str(row.get("symbol") or "").strip().upper()
    if not sym:
        return "row carries no symbol; it cannot be admitted to the live account"
    if sym not in p.live_symbols:
        return (f"{sym} is outside the live sleeve universe {sorted(p.live_symbols)} -- {p.by}")
    _params = row.get("params") if isinstance(row.get("params"), Mapping) else {}
    tf = str(row.get("timeframe") or row.get("chart") or _params.get("timeframe")
             or "").strip().upper()
    banned_tf = p.banned_timeframes.get(sym, frozenset()) | p.banned_timeframes.get(
        "*", frozenset())
    if tf and tf in banned_tf:
        return f"{sym} {tf} is disabled in the live account -- {p.by}"
    fam = str(row.get("family") or "").strip().lower()
    if fam and fam in p.banned_families:
        return f"family {fam!r} is banned from live capital -- {p.by}"
    alias = gold_window_alias(row)
    if alias:
        return (f"folded into {alias}: a versioned copy of the same gold window places the same "
                f"bracket on the same range, so it is one bet sized as several -- the window's "
                f"own leg carries its risk ({FOLD_BY})")
    return None


#: Who ordered the fold, carried on every refusal so the log says it was not a session's taste.
FOLD_BY = "principal, 2026-09-25, session 01TdyfpvAgTRnPCvgFBZzfNw"

_GOLD_WINDOW_VERSION = re.compile(r"^(gold_(?:asia|london_am|afternoon))_v\d+$")


def gold_window_alias(row: Mapping[str, Any]) -> str | None:
    """The parent window a versioned gold row duplicates (`gold_london_am_v3` -> `gold_london_am`).

    ONE WINDOW, ONE LEG (principal, 2026-09-25). The v2/v3/v4 rows of each gold window trade the
    same range breakout on the same bars as the window itself: on 2026-09-11 `gold_london_am_v2`
    carried the parent's exact entry prices with a 25.1 stop against 28.4. Stacked, three to four
    legs put 16-21% of a EUR 650 account on ONE gold-direction signal -- measured E[log] per trade
    goes from +6.8e-4 at one leg to -131e-4 at 21% once the forward edge is half the backtest's.
    Removing the copies RAISES robust E[log W] (Rule 1); the parent windows' 0.02-lot floor and
    every allocator fraction are untouched.
    """
    m = _GOLD_WINDOW_VERSION.match(str(row.get("name") or "").strip())
    return m.group(1) if m else None


def admit(rows: Iterable[Mapping[str, Any]], pol: Policy | None = None
          ) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    """(admitted, [(row, reason), ...]). Pure; the caller decides what to do with the refusals --
    the gateway drops them from the roster, the promoter writes RETIRED onto them."""
    p = pol or policy()
    keep: list[dict[str, Any]] = []
    refused: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        why = refuse(row, p)
        if why:
            refused.append((dict(row), why))
        else:
            keep.append(dict(row))
    return keep, refused
