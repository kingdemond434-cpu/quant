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

#: FRED's terms, CITED NOT QUOTED (coordinator, 2026-10-07): no verbatim text could be captured --
#: the cloud proxy refuses fred.stlouisfed.org and summaries are not quotes -- so nothing here
#: quotes FRED, and the hold below does not rest on a quote. Section headings per unverified
#: summaries; /mnt/project-files/terms/fred_tou_sec_iv_2026-10-07.md marks both clauses NOT FOUND.
FRED_TERMS_CITATION: dict[str, str] = {
    "terms_url": "https://fred.stlouisfed.org/legal/terms/",
    "sections": "II. Prohibited Use (ML/AI training ban; letter unresolved between (f) and (k)); "
                "III. Use of Data with Copyright Restrictions (the per-series labels)",
    "verbatim": "VERBATIM_PENDING",
    "checked_at": "2026-10-07"}

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
            "(on FRED too: third-party copyright, FRED ToU section III, VERBATIM_PENDING)",
    "taifex": "TAIFEX statistics (TXO put/call): site terms unread (the cloud proxy refuses the "
              "host); machine use UNCLEARED",
    "ice_bofa": "ICE BofA indices republished on FRED: third-party copyright (FRED ToU section "
                "III, VERBATIM_PENDING)",
    "fred_index": "an equity index FRED republishes under its owner's copyright (S&P Dow Jones "
                  "Indices, Nasdaq, Nikkei, Wilshire; FRED ToU section III, VERBATIM_PENDING)",
    "fred_label": "a FRED series with no recorded per-series terms label (FRED ToU section "
                  "III, VERBATIM_PENDING): labels are captured outside the cloud into "
                  "desks/mt5/data/fred_series_labels.json; until one is recorded the series is "
                  "neither fetched nor displayed",
}

#: Why every FRED/ALFRED id is held from the gauntlet (coordinator ruling on prohibition (j),
#: 2026-10-07): FRED is not an input to fitted models. The fitted inputs move to the owners' own
#: feeds (Treasury H.15, BLS, BEA, the Fed board's H.10/G.19, EIA). A quoted clearance under the
#: exact id or under "fred"/"alfred" is the only way back in.
FRED_FITTED_HOLD = ("FRED/ALFRED is held as an input to fitted models (FRED ToU section II, "
                    "Prohibited Use, VERBATIM_PENDING; ruling 2026-10-07); read the "
                    "public-domain owner's own feed instead")

#: Equity indices FRED republishes under a third party's copyright. Held from every use.
FRED_INDEX_SERIES = frozenset({"SP500", "DJIA", "DJCA", "DJTA", "DJUA", "NASDAQCOM", "NASDAQ100",
                               "NIKKEI225", "WILL5000IND", "WILL5000INDFC", "WILL5000PR",
                               "WILL5000PRFC", "WILLLRGCAP", "WILLSMLCAP"})

#: THE OWNER MAP: the public-domain owner each FRED series the desk used comes from. It admits
#: NOTHING (the swap to the owners' own feeds reads it); FRED fetch/display is decided by the
#: recorded per-series label alone (`fred_display_terms`).
FRED_OWNERS: dict[str, str] = {
    **dict.fromkeys(("DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30", "DFII10"),
                    "Board of Governors, H.15 Selected Interest Rates (Treasury curves)"),
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

#: THE LABEL REGISTER (built, empty until labels are captured outside the cloud):
#: {"<SERIES>": {"label": "<FRED's per-series label, verbatim>", "url": "<series page>",
#:               "captured_at": "...", "by": "..."}}. A series is fetched or displayed only when
#: its recorded label is one of ADMITTED_LABELS; the labels' own wording is VERBATIM_PENDING.
FRED_LABELS = ROOT / "desks" / "mt5" / "data" / "fred_series_labels.json"
ADMITTED_LABELS = frozenset({"public domain: citation requested",
                             "copyrighted: citation required"})


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


def _label(series: str, labels: Path | None) -> str | None:
    """The recorded, admitted FRED label for `series`, else None (absent file, absent row, no
    url or capture time, or a label outside ADMITTED_LABELS all fail closed)."""
    try:
        doc: Any = json.loads((labels or FRED_LABELS).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    row = doc.get(series) if isinstance(doc, dict) else None
    if not (isinstance(row, dict) and str(row.get("url") or "").strip()
            and str(row.get("captured_at") or "").strip()):
        return None
    label = " ".join(str(row.get("label") or "").split())
    return label if label.lower() in ADMITTED_LABELS else None


def fred_display_terms(series: str, clearances: Path | None = None,
                       labels: Path | None = None) -> tuple[bool, str]:
    """(may the desk FETCH this FRED series for display or cross-check?, why). Never a licence
    for a fitted model -- `gauntlet_terms` holds every FRED id. Fails closed: only a series whose
    per-series label is recorded and admitted is fetched, and a third-party index or copyrighted
    close additionally needs its owner's quoted clearance."""
    s = str(series or "").strip().upper()
    label = _label(s, labels) if s else None
    if label is None:
        return False, f"HELD_TERMS: {TERMS_HELD['fred_label']}"
    key = fred_third_party(s) or ("fred_index" if s in FRED_INDEX_SERIES else None)
    if key is None:
        return True, f"FRED label recorded: {label}"
    try:
        doc: Any = json.loads((clearances or CLEARANCES).read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
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


__all__ = ["ADMITTED_LABELS", "CLEARANCES", "FRED_FITTED_HOLD", "FRED_INDEX_SERIES", "FRED_LABELS",
           "FRED_OWNERS", "FRED_TERMS_CITATION", "TERMS_EVIDENCE", "TERMS_HELD",
           "fred_display_terms", "fred_third_party", "gauntlet_terms"]
