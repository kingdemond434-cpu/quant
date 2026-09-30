"""JAPAN: the largest jurisdiction on the desk's map with no pack, and its own grounds said so.

MEASURED 2026-09-23. `pack_cells` walked every world ground that already holds documents to the
one registry door and published, per ground, the reason any of them could not name an MT5
instrument. Two of the seventeen survivors gave the same reason and it was not a thesis problem:

    asia:estat_jp_customs   6 documents   www.e-stat.go.jp   "the country code jp is covered by
    asia:boj_timeseries     1 document    www.stat-search.boj.or.jp   no pack under countries/"

Seventy-five packs exist and not one of them declares `jp`. Meanwhile `research/japan/mandate.py`
carries thirty-odd Japanese actors with their instruments attached, `japan/calendars.py` carries
the BoJ's meeting clock and `japan/miners_policy.py` mines it. The desk had the knowledge and was
missing the DECLARATION that the conversion path reads.

WHAT THIS PACK IS, EXACTLY. A door with a derived instrument list. It states no new mechanism,
duplicates no miner and overrides nothing: `research/japan/` remains the department that does the
work. The one thing it adds is the pair `(EXECUTABLE_INSTRUMENTS, REGION_COMMAND)` that
`pack_cells.country_pack` asks for, so a Japanese ground's documents become cells the one
gauntlet can judge.

WHY THE LIST IS DERIVED AND NOT TYPED. Two sources, both already on the desk, intersected with
the broker's own quote list:

  1. THE BROKER'S UNIVERSE REGISTRY (`data/universe/universe.json`). Every six-character symbol
     ending in JPY is a yen pair the account can actually trade. Typing that list by hand would
     be a claim about the broker; reading it is a measurement of the broker.
  2. THE JAPAN DEPARTMENT'S OWN ACTOR MAP (`research/japan/mandate.py`). Its actors declare the
     instruments each one moves -- USDJPY, EURJPY, JPN225 and the carry crosses. Anything it
     names that the broker does not quote (UST10Y, UST05Y) is dropped by the intersection rather
     than argued about.

If the department is absent or the registry unreadable, the list falls back to the yen pairs
alone, which is still a measurement and never an empty tuple: a pack that cannot name an
instrument would put its grounds straight back where they were.

JAPAN'S ONE STANDING PROPERTY, stated once so the pack is not merely plumbing: the yen is the
world's funding currency, so a Japanese policy or flow surprise transmits as a CARRY unwind
across every JPY cross at once rather than as an idiosyncratic move in one of them. That is why
the whole cross set is executable here and not just USDJPY, and it is the department's claim, not
a new one.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]          # countries/jp/pack.py -> desks/mt5
UNIVERSE = BASE / "data" / "universe" / "universe.json"

CODE = "JP"
NAME = "Japan"
REGION_COMMAND = "asia"
REGION_DESK = "ASIA"
FOREST = "japan"
CURRENCY = "JPY"
JURISDICTIONS: tuple[str, ...] = ("jp",)
NATIVE_LANGUAGES: tuple[str, ...] = ("ja", "en")
COT_CURRENCY = "JAPANESE YEN"
FISCAL_YEAR_END = "03-31"
EXPORT_ECONOMY = "manufactured_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"

MISSION = ("hold the jurisdiction so its already-crawled grounds -- the BoJ time-series portal, "
           "e-Stat customs, and everything the world crawler reaches under .jp -- name the "
           "instruments the Japan department already knows they move. The mechanisms live in "
           "research/japan/; this pack is the declaration the conversion path reads.")

#: The department that owns Japan's research. Named here so nothing re-implements it.
DEPARTMENT_MODULE = "research.japan.mandate"


def _quoted() -> tuple[str, ...]:
    """Every symbol the broker's own universe registry lists. Empty when it cannot be read."""
    try:
        doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(str(k) for k in doc) if isinstance(doc, dict) else ()


def _yen_pairs(quoted: tuple[str, ...]) -> tuple[str, ...]:
    """The six-character JPY pairs the account can trade, USDJPY first because it is the axis."""
    pairs = sorted(s for s in quoted
                   if len(s) == 6 and s.isalpha() and s.upper().endswith("JPY"))
    return tuple(["USDJPY"] * ("USDJPY" in pairs) + [p for p in pairs if p != "USDJPY"])


def _department_instruments(quoted: tuple[str, ...]) -> tuple[str, ...]:
    """What the Japan department's own actor map names, kept only where the broker quotes it."""
    try:
        from research.japan import mandate
    except Exception:
        return ()
    seen: list[str] = []
    for actor in (getattr(mandate, "ACTORS", ()) or ()):
        if not isinstance(actor, dict):
            continue
        for sym in (actor.get("instruments") or ()):
            s = str(sym)
            if s in quoted and s not in seen:
                seen.append(s)
    for sym in (getattr(mandate, "JPY_CROSSES", ()) or ()):
        s = str(sym)
        if s in quoted and s not in seen:
            seen.append(s)
    return tuple(seen)


def _executable() -> tuple[str, ...]:
    quoted = _quoted()
    out: list[str] = []
    for sym in _yen_pairs(quoted) + _department_instruments(quoted):
        if sym not in out:
            out.append(sym)
    return tuple(out)


#: DERIVED at import from the broker's registry and the Japan department's actor map. Never typed.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = _executable()

#: Where Japanese information is published. These are the grounds already in the crawler's
#: registry that this pack now gives an instrument to; the list is documentation of what exists,
#: not a new crawl target -- the crawler's own registry remains the only source of grounds.
KNOWN_GROUNDS: tuple[dict[str, Any], ...] = (
    {"id": "asia:boj_timeseries", "host": "www.stat-search.boj.or.jp",
     "publishes": "the Bank of Japan's own time-series portal: policy rate, monetary base, "
                  "TANKAN, the effective exchange rate"},
    {"id": "asia:estat_jp_customs", "host": "www.e-stat.go.jp",
     "publishes": "the government statistics portal: trade by partner and commodity, the trade "
                  "balance that is the yen's own flow story"},
)

BOUNDARIES: tuple[str, ...] = (
    "this pack states no mechanism of its own: research/japan/ owns Japan's research and this "
    "file must never grow a miner, a rule or a calendar",
    "EXECUTABLE_INSTRUMENTS is derived at import and never hard-coded; a symbol the broker stops "
    "quoting leaves the list on the next process start with no edit here",
    "nothing here judges, sizes or vetoes anything",
)
