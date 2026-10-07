"""THE TERMS GATE -- which sources' numbers may reach the gauntlet (audit #204 item 4, #211).

AN ALLOW-LIST THAT FAILS CLOSED (audit #211, 2026-10-07). A source reaches a gauntlet cell, a
conditioning key or a donation only when one of these holds for EVERY component of its id
("a+b" pairs a consensus with an actual; both must pass):

    TERMS_EVIDENCE   the id (or, for "<provider>:<series>" providers, its provider) has a
                     recorded terms basis: url, verbatim quote, scope
    CLEARANCES       a clearance row for it carries status CLEARED AND the quoted permitting
                     clause (`terms_url` + `terms_quote`); a bare "CLEARED" admits nothing

Everything else is HELD: an unknown source, a named hold (TERMS_HELD), a FRED/ALFRED series that
republishes a third party's copyrighted index, and any source at all when the terms fence
(`libs.data.terms_fence`, #162) is installed but cannot be consulted. A held source is MEASURED
AND KEPT: its rows are stored, counted and written to the sensor ledger as state; it only stays
out of cells until its terms are read and quoted.

One door: `release_vintages`, `event_surprise`, `market_state` and every world-sensor engine's
`sensor_engines.emit_conditioner_cells` call `gauntlet_terms` and nothing else.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
#: Where a cleared source is recorded: {"<key>": {"status": "CLEARED", "terms_url": ...,
#: "terms_quote": "<the permitting clause, verbatim>", "by": ..., "checked_at": ...}}. The key is
#: the source id, its provider (the part before ":"), or the TERMS_HELD key that holds it.
CLEARANCES = ROOT / "desks" / "mt5" / "data" / "terms_clearances.json"

_FRED_Q3 = ("Series with a copyright notice are owned by third parties and have special "
            "restrictions ... you must contact the data owner to obtain permission. "
            "Unfortunately, the Federal Reserve Bank of St. Louis cannot give you such "
            "permission.")
_FRED_BASIS = {
    "terms_url": "https://fred.stlouisfed.org/legal/",
    "terms_quote": _FRED_Q3,
    "quote_source": "FRED ToU FAQ Q3, read verbatim on the box (data/data_universe_map.json, "
                    "imf_pcps provenance: 'https://fred.stlouisfed.org/legal/ (200, 117020 b -- "
                    "ToU FAQ Q3 read verbatim)')",
    "scope": "series WITHOUT a third-party copyright notice; the copyrighted ones are held "
             "(fred_third_party). The general permitting clause for un-noticed series is NOT "
             "yet quoted here: the cloud proxy refuses fred.stlouisfed.org, so it is owed a "
             "verbatim read on the box",
    "checked_at": "2026-10-07"}

#: Recorded terms bases. A key with ":" admits that exact id; a bare provider key admits
#: "<provider>:<series>" for any non-empty series (named holds still apply).
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "fred": _FRED_BASIS,
    "alfred": {**_FRED_BASIS, "scope": "ALFRED vintages of the same FRED series, same scope"},
    "mt5:bars": {"terms_url": "",
                 "terms_quote": "(own data: bars from the desk's own MT5 terminal on its own "
                                "broker account, used for its own trading, never redistributed)",
                 "scope": "exact id", "checked_at": "2026-10-07"},
    "desk:sensor_ledger": {"terms_url": "",
                           "terms_quote": "(own data: the desk's derived ledger of sensor rows)",
                           "scope": "exact id", "checked_at": "2026-10-07"},
}

#: Named holds: the reason a known source is held, matched as a substring of the source id.
TERMS_HELD: dict[str, str] = {
    "ff_calendar": "Forex Factory survey median: machine-use terms UNMEASURED",
    "forexfactory": "Forex Factory survey median: machine-use terms UNMEASURED",
    "faireconomy": "Forex Factory survey median (faireconomy mirror): terms UNMEASURED",
    "tradingeconomics": "Trading Economics calendar: commercial terms, machine use not cleared",
    "yahoo": "Yahoo Finance chart API: its terms restrict automated use; machine use UNCLEARED",
    "cboe": "CBOE index values (VIX family): CBOE copyright; machine use for trading UNCLEARED "
            "(on FRED too: FAQ Q3, FRED cannot grant the permission)",
    "taifex": "TAIFEX statistics (TXO put/call): site terms unread (the cloud proxy refuses the "
              "host); machine use UNCLEARED",
    "ice_bofa": "ICE BofA indices republished on FRED: third-party copyright (FAQ Q3)",
}


def fred_third_party(series: str) -> str | None:
    """The TERMS_HELD key for a FRED/ALFRED series that republishes a copyrighted index, else
    None. FRED's CBOE volatility closes (VIXCLS, VXVCLS, GVZCLS, OVXCLS, EVZCLS...) all end in
    "CLS"; ICE BofA indices start "BAML"."""
    s = series.strip().upper()
    if s.endswith("CLS"):
        return "cboe"
    if s.startswith("BAML"):
        return "ice_bofa"
    return None


def _clearance(doc: Any, keys: list[str]) -> str | None:
    """The quoted clearance for the first key that has one, else None."""
    if not isinstance(doc, dict):
        return None
    for k in keys:
        row = doc.get(k)
        if (isinstance(row, dict) and str(row.get("status")) == "CLEARED"
                and str(row.get("terms_url") or "").strip()
                and str(row.get("terms_quote") or "").strip()):
            return f"cleared ({k}): {row.get('terms_url')}"
    return None


def _fence(sid: str) -> str | None:
    """The terms fence's block for `sid`; a fence that is installed but fails blocks everything.
    An absent fence (the module is not on this branch) leaves the allow-list alone to decide,
    and the allow-list is already closed to every source it holds no evidence for."""
    try:
        tf = importlib.import_module("libs.data.terms_fence")
    except ModuleNotFoundError as exc:
        if exc.name == "libs.data.terms_fence":
            return None
        return f"terms fence unavailable ({type(exc).__name__}): held"
    except Exception as exc:
        return f"terms fence unavailable ({type(exc).__name__}): held"
    try:
        fenced = tf.fenced_source(sid)
    except Exception as exc:
        return f"terms fence failed ({type(exc).__name__}): held"
    return f"terms fence: {fenced}" if fenced else None


def _one(sid: str, doc: Any) -> tuple[bool, str]:
    fenced = _fence(sid)
    if fenced:
        return False, fenced
    provider, _, series = sid.partition(":")
    held = [k for k in TERMS_HELD if k in sid]
    if provider in ("fred", "alfred"):
        third = fred_third_party(series)
        if third and third not in held:
            held.append(third)
    if held:
        whys = []
        for key in held:
            cleared = _clearance(doc, [sid, key])
            if not cleared:
                return False, f"HELD_TERMS: {TERMS_HELD[key]}"
            whys.append(cleared)
        return True, "; ".join(whys)
    if sid in TERMS_EVIDENCE or (series.strip() and provider in TERMS_EVIDENCE
                                 and ":" not in provider):
        return True, ""
    cleared = _clearance(doc, [sid, provider])
    if cleared:
        return True, cleared
    return False, (f"HELD_TERMS: no recorded terms basis for '{sid or '(empty)'}' -- the gate "
                   "admits only TERMS_EVIDENCE sources and quoted clearances")


def gauntlet_terms(source_id: str, clearances: Path | None = None) -> tuple[bool, str]:
    """(may this source's numbers reach the gauntlet?, why). Fails closed."""
    sid = str(source_id or "").strip().lower()
    try:
        doc: Any = json.loads((clearances or CLEARANCES).read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    whys: list[str] = []
    for part in sid.split("+"):
        ok, why = _one(part.strip(), doc)
        if not ok:
            return False, why
        if why:
            whys.append(why)
    return True, "; ".join(whys)


__all__ = ["CLEARANCES", "TERMS_EVIDENCE", "TERMS_HELD", "fred_third_party", "gauntlet_terms"]
