"""THE TERMS GATE -- which sources' numbers may reach the gauntlet (audit #204 item 4, #211).

AN ALLOW-LIST THAT FAILS CLOSED (audit #211, 2026-10-07). A source reaches a gauntlet cell, a
conditioning key or a donation only when one of these holds for EVERY component of its id
("a+b" pairs a consensus with an actual; both must pass):

    TERMS_EVIDENCE   the id (or, for "<provider>:<series>" providers, its provider) has a
                     recorded terms basis: url, verbatim quote, scope
    CLEARANCES       a clearance row for it carries status CLEARED AND the quoted permitting
                     clause (`terms_url` + `terms_quote`); a bare "CLEARED" admits nothing

Everything else is HELD: an unknown source, a named hold (TERMS_HELD), EVERY FRED/ALFRED series
(FRED is held as an input to fitted models: coordinator ruling on prohibition (j), 2026-10-07;
the fitted inputs move to the public-domain owners' own feeds), and any source at all when the
terms fence (`libs.data.terms_fence`, #162) is installed but cannot be consulted. A held source
is MEASURED AND KEPT: its rows are stored, counted and written to the sensor ledger as state;
it only stays out of cells until its terms are read and quoted.

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

#: 17 U.S.C. 105, verbatim. The only basis quoted for the owners' own feeds: each agency's own
#: site-terms page is owed a verbatim read ON THE BOX (the cloud proxy refuses treasury.gov,
#: bls.gov and eia.gov), and a term found there that narrows machine use re-holds the provider.
_USC105_URL = "https://www.law.cornell.edu/uscode/text/17/105"
_USC105_QUOTE = ("Copyright protection under this title is not available for any work of the "
                 "United States Government")
_USC105_NOTE = ("statute only: the agency's own site-terms page is owed a verbatim read on the "
                "box (the cloud proxy refuses the host)")

#: Recorded terms bases. A key with ":" admits that exact id; a bare provider key admits
#: "<provider>:<series>" for any non-empty series (named holds still apply).
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "mt5:bars": {"terms_url": "",
                 "terms_quote": "(own data: bars from the desk's own MT5 terminal on its own "
                                "broker account, used for its own trading, never redistributed)",
                 "scope": "exact id", "checked_at": "2026-10-07"},
    "forced_flow_calendar": {"terms_url": "",
                             "terms_quote": "(own data: dated windows computed from published "
                                            "RULES -- month-ends, quarterly expiries, inventory "
                                            "weeks, central-bank meeting dates -- by "
                                            "research/forced_flow_calendar.py; no vendor feed)",
                             "scope": "exact id (event_response_atlas source)",
                             "checked_at": "2026-10-07"},
    # THE PUBLIC-DOMAIN OWNERS (2026-10-07, ruling on prohibition (j)): the fitted inputs FRED
    # used to carry, read from the executive agency that publishes them. Bare provider keys, so
    # "treasury:DGS10", "bls:CUSR0000SA0" and "eia:WCESTUS1" pass. Fed board (H.10/G.19) and BEA
    # ids are NOT admitted: no quoted basis for either is held (see TERMS_HELD "frb:"/"bea:").
    **{owner: {"terms_url": _USC105_URL, "terms_quote": _USC105_QUOTE,
               "scope": f"{agency}: an executive agency of the United States Government, so its "
                        "published statistics are a work of the United States Government",
               "note": _USC105_NOTE, "checked_at": "2026-10-07"}
       for owner, agency in (("treasury", "U.S. Department of the Treasury (daily par and real "
                                          "yield curve rates)"),
                             ("bls", "U.S. Bureau of Labor Statistics, Department of Labor "
                                     "(CPI-U)"),
                             ("eia", "U.S. Energy Information Administration, Department of "
                                     "Energy (Weekly Petroleum Status Report)"))},
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
    "fred_index": "an equity index FRED republishes under its owner's copyright (S&P Dow Jones "
                  "Indices, Nasdaq, Nikkei, Wilshire): FAQ Q3, FRED cannot grant the permission",
    "bea:": "BEA (PCE): no BEA API key is held and BEA's terms have not been quoted; held until "
            "a quoted basis exists",
    "frb:": "Federal Reserve Board releases (H.10 dollar index, G.19): the Board's site terms "
            "have not been quoted; held until a quoted basis exists",
    "fred_label": "a FRED series whose terms label is not on the display register: only series "
                  "owned by a US federal agency (public domain, 17 USC 105) are fetched",
}

#: Why every FRED/ALFRED id is held from the gauntlet (coordinator ruling on prohibition (j),
#: 2026-10-07): FRED is not an input to fitted models. The fitted inputs move to the owners' own
#: feeds (Treasury H.15, BLS, BEA, the Fed board's H.10/G.19, EIA). A quoted clearance under the
#: exact id or under "fred"/"alfred" is the only way back in.
FRED_FITTED_HOLD = ("FRED/ALFRED is held as an input to fitted models (ruling on prohibition "
                    "(j), 2026-10-07); read the public-domain owner's own feed instead")

#: Equity indices FRED republishes under a third party's copyright. Held from every use.
FRED_INDEX_SERIES = frozenset({"SP500", "DJIA", "DJCA", "DJTA", "DJUA", "NASDAQCOM", "NASDAQ100",
                               "NIKKEI225", "WILL5000IND", "WILL5000INDFC", "WILL5000PR",
                               "WILL5000PRFC", "WILLLRGCAP", "WILLSMLCAP"})

#: THE DISPLAY REGISTER: the FRED series the desk may fetch for display and cross-check, each with
#: the US federal owner whose work it is (public domain under 17 USC 105). A series not named here
#: is never fetched (fails closed). FRED's own per-series label ("Public Domain: Citation
#: requested") is owed a verbatim read on the box: the cloud proxy refuses fred.stlouisfed.org.
FRED_DISPLAY: dict[str, str] = {
    **dict.fromkeys(("DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30", "DFII10"),
                    "Board of Governors, H.15 Selected Interest Rates"),
    "T10Y2Y": "St. Louis Fed calculation from H.15 (DGS10 - DGS2)",
    "T5YIE": "St. Louis Fed calculation from H.15 nominal and TIPS yields",
    "T10YIE": "St. Louis Fed calculation from H.15 nominal and TIPS yields",
    "DTWEXBGS": "Board of Governors, H.10 Foreign Exchange Rates",
    "WALCL": "Board of Governors, H.4.1 Factors Affecting Reserve Balances",
    "M2SL": "Board of Governors, H.6 Money Stock Measures",
    **dict.fromkeys(("WCESTUS1", "WCSSTUS1", "WGTSTUS1", "WDISTUS1", "WPULEUS3"),
                    "U.S. Energy Information Administration, Weekly Petroleum Status Report"),
    "CPIAUCSL": "U.S. Bureau of Labor Statistics, CPI-U",
    "PCEPI": "U.S. Bureau of Economic Analysis, PCE price index",
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


def fred_display_terms(series: str, clearances: Path | None = None) -> tuple[bool, str]:
    """(may the desk FETCH this FRED series for display or cross-check?, why). Never a licence
    for a fitted model -- `gauntlet_terms` holds every FRED id. Fails closed: a series off the
    display register, a third-party index or a copyrighted close is not fetched unless a quoted
    clearance names it."""
    s = str(series or "").strip().upper()
    try:
        doc: Any = json.loads((clearances or CLEARANCES).read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    key = fred_third_party(s) or ("fred_index" if s in FRED_INDEX_SERIES else None)
    if key is None and s not in FRED_DISPLAY:
        key = "fred_label"
    if key is None:
        return True, f"public domain: {FRED_DISPLAY[s]}"
    cleared = _clearance(doc, [f"fred:{s.lower()}", key])
    return (True, cleared) if cleared else (False, f"HELD_TERMS: {TERMS_HELD[key]}")


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
        third = fred_third_party(series) or (
            "fred_index" if series.strip().upper() in FRED_INDEX_SERIES else None)
        if third and third not in held:
            held.append(third)
    fred_why = ""
    if provider in ("fred", "alfred"):
        # the FRED hold stands on its own: a third party's clearance (CBOE, ICE) never lifts it
        fred_why = _clearance(doc, [sid, provider]) or ""
        if not fred_why:
            return False, f"HELD_TERMS: {FRED_FITTED_HOLD}"
        if not held:
            return True, fred_why
    if held:
        whys = []
        for key in held:
            cleared = _clearance(doc, [sid, key])
            if not cleared:
                return False, f"HELD_TERMS: {TERMS_HELD[key]}"
            whys.append(cleared)
        return True, "; ".join(([fred_why] if fred_why else []) + whys)
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


__all__ = ["CLEARANCES", "FRED_DISPLAY", "FRED_FITTED_HOLD", "FRED_INDEX_SERIES", "TERMS_EVIDENCE",
           "TERMS_HELD", "fred_display_terms", "fred_third_party", "gauntlet_terms"]
