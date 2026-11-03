"""SMARD (BUNDESNETZAGENTUR): HOURLY GERMAN POWER LOAD, RESIDUAL LOAD AND GENERATION BY TYPE.

The LIVE-eligible twin of `research/entsoe_power.py`. ENTSO-E's Actual Total Load (6.1.A) and
Actual Generation per Production Type (16.1.B&C) are IDEAS_ONLY (off ENTSO-E's free re-use list);
SMARD republishes the same German series under CC BY 4.0. A producer registered in
`alt_proxies.run` (it rides the `alt_proxies` hourly leg; nothing here is a second clock).

DATA. SMARD's "Marktdaten visualisieren" charts read static JSON at

    https://www.smard.de/app/chart_data/<filter>/<region>/index_hour.json
        -> {"timestamps": [<ms>, ...]}           one per week (Monday 00:00 Berlin)
    https://www.smard.de/app/chart_data/<filter>/<region>/<filter>_<region>_hour_<ms>.json
        -> {"meta_data": {...}, "series": [[<ms hour start>, <MWh or null>], ...]}

Filter ids (the third-party description github.com/bundesAPI/smard-api, read 2026-10-20; SMARD's
own user manual (Benutzerhandbuch 04/2026) documents the categories but no ids or URLs, so the
ids are a third party's reading of SMARD's app and a wrong one comes back as a 404 window,
recorded, never as a zero): 410 Stromverbrauch Gesamt (Netzlast), 4359 Residuallast, and
Stromerzeugung 1223 Braunkohle, 4069 Steinkohle, 4071 Erdgas, 1224 Kernenergie, 4067 Wind
Onshore, 1225 Wind Offshore, 4068 Photovoltaik, 4066 Biomasse, 1226 Wasserkraft, 4070
Pumpspeicher, 1227 Sonstige Konventionelle, 1228 Sonstige Erneuerbare. Regions DE-LU (the market
area since 2018-10-01; all filters, the cells' zone) and DE (load and residual load only).
Hourly points are folded per Berlin local day into daily series exactly as entsoe_power folds
them (a day is published only when every UTC hour of it is present; absent is never zero).

TERMS: LIVE (API_PERMITTED, no key), on SMARD's own words. `SOURCE_POLICY_ROW` quotes the "Data
use" page (smard.de/en/datennutzung), the "All about our 'Data download' section" article
(2023-03-16) and the user manual (04/2026): the Market data visuals data -- the section these
chart_data files feed, whose main categories are Electricity generation and Electricity
consumption -- "is licensed under a Creative Commons Attribution 4.0 International Licence";
"All the data published are covered by" it; and under s.111d EnWG the platform's data "has been
made freely available for public use". CC BY 4.0 s.2(a)(4) licenses the rights "in all media and
formats". Attribution "Bundesnetzagentur | SMARD.de", the licence, and that the desk changed the
data (daily aggregates) ride every payload (`CREDIT`). SMARD's pages say nothing about automated
access either way, and the chart_data URLs are not documented by SMARD itself: both are recorded
in the row (`open_points`) for the auditor, and robots.txt still decides every fetch. One row
edit (`status` -> IDEAS_ONLY) turns live input off.

POINT IN TIME. SMARD's manual states for both items: "Die Daten werden spätestens eine Stunde
nach der Betriebsperiode ... an die ENTSO-E Transparenzplattform übermittelt" (Regulation
543/2013 Art. 6.1(a), 16.1(b)); SMARD then takes them from ENTSO-E and verifies them, so it is
never earlier than that. A point is available no earlier than max(the instant this desk fetched
it, its hour end + 1h); a daily value no earlier than max(the fetch, the local day's end + 1h).
`merge_vintages` (stamp_floor_fetch) applies it; `series_asof` shows a cell only a value whose
stamp is at or before the decision and whose day is strictly before the decision's day. The
fetch floor is what binds in practice: it is always at or after SMARD's own publication.

FETCH. robots.txt of www.smard.de decides every pass (fail closed: unreadable is not permission;
it could not be read from the authoring container on 2026-10-20). DESK UA, retries=0, requests
spaced MIN_INTERVAL_S (or the robots crawl-delay) apart. 401/403/429, an HTML/WAF body or a
non-JSON body is a hard stop held for a PERSON in the shared hold shape. A per-region cursor
walks the index's weekly files forward; a caught-up region re-reads the weeks covering its last
RECENT_D days. Outcomes: OK | UNCHANGED | PARTIAL:BUDGET (cursor kept) | FAILED:<cause> (an empty
pass is FAILED, never zero) | HELD:HARD_STOP | UNMEASURED (no fetch this pass).

CELLS. The entsoe_power DE-LU cells (GER40/EURUSD on load, XNGUSD on residual load, gas burn and
the wind+solar share), judged by `libs.research.release_gain.release_gain` at the Tier S bar
`release_gain.tier_s_t_required` gives each cell's own n; no bar literal lives here. Every tested
cell is charged; passing cells are donated only while the terms row is LIVE.

LIVE YIELD IS UNMEASURED until the trading box runs the alt_proxies leg: this was written against
fixtures in a container whose reader could not fetch smard.de's robots.txt.
"""
from __future__ import annotations

import contextlib
import json
import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from research import entsoe_power as _E

SOURCE_ID = "smard_power"
HOST = "www.smard.de"
BASE_URL = "https://www.smard.de/app/chart_data"
RESOLUTION = "hour"
UNMEASURED = "UNMEASURED"

#: SMARD filter id -> (component, label). Ids from github.com/bundesAPI/smard-api (third party).
LOAD, RESIDUAL = 410, 4359
GEN: dict[int, str] = {1223: "lignite", 4069: "hard_coal", 4071: "gas", 1224: "nuclear",
                       4067: "wind_on", 1225: "wind_off", 4068: "pv", 4066: "biomass",
                       1226: "hydro", 4070: "pumped_storage", 1227: "other_conventional",
                       1228: "other_renewable"}
FILTER_LABEL: dict[int, str] = {
    LOAD: "Stromverbrauch: Gesamt (Netzlast)", RESIDUAL: "Stromverbrauch: Residuallast",
    1223: "Stromerzeugung: Braunkohle", 4069: "Stromerzeugung: Steinkohle",
    4071: "Stromerzeugung: Erdgas", 1224: "Stromerzeugung: Kernenergie",
    4067: "Stromerzeugung: Wind Onshore", 1225: "Stromerzeugung: Wind Offshore",
    4068: "Stromerzeugung: Photovoltaik", 4066: "Stromerzeugung: Biomasse",
    1226: "Stromerzeugung: Wasserkraft", 4070: "Stromerzeugung: Pumpspeicher",
    1227: "Stromerzeugung: Sonstige Konventionelle",
    1228: "Stromerzeugung: Sonstige Erneuerbare"}
WIND_SOLAR = ("wind_on", "wind_off", "pv")
#: Generation types published as their own daily series (the rest only enter the total).
GEN_SERIES = ("gas", "lignite", "hard_coal", "nuclear", "wind_on", "wind_off", "pv")
#: Region -> (series slug, filters read). DE-LU is the market area the cells use.
REGIONS: dict[str, tuple[str, tuple[int, ...]]] = {
    "DE-LU": ("de_lu", (LOAD, RESIDUAL, *GEN)),
    "DE": ("de", (LOAD, RESIDUAL)),
}
#: SMARD manual 04/2026, p.47 (Stromverbrauch Gesamt) and p.38 (Realisierte Erzeugung): "spätestens
#: eine Stunde nach der Betriebsperiode" to ENTSO-E (Reg. 543/2013 Art. 6.1(a), 16.1(b)).
PUBLICATION_LAG = timedelta(hours=1)
LAG_SOURCE = ("SMARD Benutzerhandbuch 04/2026 p.38 and p.47: 'spätestens eine Stunde nach der "
              "Betriebsperiode' (Reg. 543/2013 Art. 6.1(a), 16.1(b)); SMARD republishes after "
              "that, so the fetch-time floor binds")
DEPTH_D = 365                   # a region's first pass reaches this far back
RECENT_D = 3                    # a caught-up region re-reads the weeks covering these days
MIN_INTERVAL_S = 2.0
BUDGET_S = 60.0                 # this producer's share of the alt_proxies leg
TIMEOUT_S = 30.0
MAX_BYTES = 8 * 1024 * 1024
HARD_STOP = (401, 403, 429)
BLOCK_VERDICT: dict[int, str] = {401: "NEEDS_KEY", 403: "METHOD_BLOCKED", 429: "METHOD_BLOCKED"}

CREDIT = ("Bundesnetzagentur | SMARD.de, licensed under CC BY 4.0 "
          "(https://creativecommons.org/licenses/by/4.0/); hourly Stromverbrauch and "
          "Stromerzeugung folded to daily aggregates by the desk (changed).")
TERMS_URL = "https://www.smard.de/en/datennutzung"
DOWNLOAD_ARTICLE_URL = "https://www.smard.de/en/all-about-our-data-download-section-210130"
MANUAL_URL = ("https://www.smard.de/resource/blob/220052/9d526adf4b948599da4a956dfae6dab9/"
              "smard-benutzerhandbuch-04-2026-data.pdf")
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode.en"
FILTER_IDS_URL = "https://github.com/bundesAPI/smard-api"
READ_AT = "2026-10-20"
API_PERMITTED = "API_PERMITTED"
IDEAS_ONLY = "IDEAS_ONLY"
LIVE_STATUSES = frozenset({API_PERMITTED})

#: THIS SOURCE'S ROW, in `libs/data/terms_fence.SOURCE_POLICY`'s shape (terms_fence is not on
#: this branch's line; the row moves into SOURCE_POLICY unchanged when the two meet).
SOURCE_POLICY_ROW: dict[str, dict[str, Any]] = {
    "smard": {
        "hosts": (HOST,), "status": API_PERMITTED, "key_env": (),
        "sources": (SOURCE_ID,), "routes": (SOURCE_ID,),
        "why": ("SMARD's own Data use page licenses the Market data visuals data (whose "
                "categories are Electricity generation and Electricity consumption, the data "
                "the chart_data files carry) under CC BY 4.0, and s.111d EnWG makes it freely "
                "available for public use; CC BY 4.0 s.2(a)(4) covers all media and formats. "
                "LIVE input with the attribution on every payload; robots.txt decides each fetch"),
        "attribution": CREDIT,
        "open_points": (
            "SMARD's pages say nothing about automated access either way (no permission and no "
            "prohibition beyond the licence); the chart_data URLs and filter ids are documented "
            "only by a third party (bundesAPI/smard-api), not by SMARD; robots.txt of "
            "www.smard.de could not be read by the authoring container on 2026-10-20, so the "
            "box's first pass is the first robots reading"),
        "terms": {
            "url": TERMS_URL, "checked_at": READ_AT,
            "documents": {"data_use": TERMS_URL, "download_article": DOWNLOAD_ARTICLE_URL,
                          "user_manual": MANUAL_URL, "licence": LICENCE_URL,
                          "filter_ids_third_party": FILTER_IDS_URL},
            "clauses": {
                "data_use_cc_by": ("Data from the section Market data visuals, which can be "
                                   "downloaded showing longer periods of time from the Download "
                                   "section, is licensed under a Creative Commons Attribution "
                                   "4.0 International Licence."),
                "data_use_enwg": ("In accordance with section 111d of the Energy Industry Act "
                                  "(Energiewirtschaftsgesetz - EnWG), the data published on "
                                  "this platform has been made freely available for public "
                                  "use."),
                "data_use_share": ("Data under a CC BY 4.0 licence may be shared, redistributed "
                                   "and adapted as long as appropriate credit is given."),
                "data_use_attribution": ("Data from the website www.smard.de should be "
                                         "attributed to 'Bundesnetzagentur | SMARD.de'."),
                "download_all_data": ("All the data published are covered by the Creative "
                                      "Commons Attribution 4.0 International Licence and so can "
                                      "be downloaded and used free of charge as long as you "
                                      "credit the source."),
                "download_categories": ("If you want to download market data, you can choose "
                                        "from the same main categories as in the \"Market data "
                                        "visuals\" section: \"Electricity generation\", "
                                        "\"Electricity consumption\", \"Market\" and "
                                        "\"Balancing\"."),
                "manual_p6": ("Diese können gemäß der Creative Commons Namensnennung 4.0 "
                              "International Lizenz kostenfrei heruntergeladen, gespeichert und "
                              "weiterverwendet werden."),
                "manual_p8": ("Das Gleiche gilt für die Marktdaten, die im Seitenbereich Daten "
                              "herunterladen zum Download zur Verfügung stehen."),
                "manual_p9": "Als Quelle ist \"Bundesnetzagentur | SMARD.de\" zu verwenden.",
                "manual_p47_load_lag": ("Die Daten werden spätestens eine Stunde nach der "
                                        "Betriebsperiode an die ENTSO-E Transparenzplattform "
                                        "übermittelt."),
                "manual_p38_gen_lag": ("Die Daten werden spätestens eine Stunde nach der "
                                       "Betriebsperiode (vgl. Art. 16 Abs. 2 b Verordnung (EU) Nr. "
                                       "543/2013) an die ENTSO-E Transparenzplattform "
                                       "übermittelt."),
                "cc_by_2a4": ("The Licensor authorizes You to exercise the Licensed Rights in "
                              "all media and formats whether now known or hereafter created, "
                              "and to make technical modifications necessary to do so."),
            },
            "scope": {
                "Stromverbrauch Gesamt / Residuallast (filters 410, 4359)":
                    "COVERED: Market data visuals category Electricity consumption",
                "Stromerzeugung by type (filters 1223..4071)":
                    "COVERED: Market data visuals category Electricity generation",
            },
        },
        "missed_growth": {
            "delta_elogw": UNMEASURED,
            "cause": ("smard_power held or IDEAS_ONLY: DE-LU load and generation-mix cells on "
                      "XNGUSD, GER40, EURUSD are measured but never donated or read as live "
                      "input")},
    },
}
POLICY_KEY = "smard"


def policy() -> dict[str, Any]:
    return SOURCE_POLICY_ROW[POLICY_KEY]


def live_input() -> bool:
    """True only when the terms row permits live input. FAIL CLOSED."""
    return str(policy().get("status")) in LIVE_STATUSES


# ============================================================================ URLs and HTTP
def index_url(filt: int, region: str) -> str:
    return f"{BASE_URL}/{filt}/{region}/index_{RESOLUTION}.json"


def week_url(filt: int, region: str, ts_ms: int) -> str:
    return f"{BASE_URL}/{filt}/{region}/{filt}_{region}_{RESOLUTION}_{ts_ms}.json"


Getter = Callable[[str], tuple[bytes, str]]


def http_get(url: str, ua: str) -> tuple[bytes, str]:
    """One GET, no retry. Raises HTTPError / URLError on failure."""
    ctx = None
    with contextlib.suppress(Exception):
        from libs.data.polite_fetch import ssl_context
        ctx = ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=ctx) as fh:
        return fh.read(MAX_BYTES), str(fh.headers.get("Content-Type") or "")


# ============================================================================ the answer
def _json(body: bytes) -> Any:
    """The parsed body, or None for anything that is not a JSON object (an HTML/WAF page)."""
    head = body.lstrip()[:1]
    if head != b"{" or b"<html" in body[:2048].lower():
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def parse_index(body: bytes) -> list[int] | None:
    doc = _json(body)
    if not isinstance(doc, dict) or not isinstance(doc.get("timestamps"), list):
        return None
    return sorted({int(t) for t in doc["timestamps"] if isinstance(t, int | float)})


def parse_week(body: bytes) -> list[tuple[datetime, float]] | None:
    """(hour start UTC, MWh) for every non-null finite point; None when not chart_data JSON. A
    null is a value not yet published: absent, never zero."""
    doc = _json(body)
    if not isinstance(doc, dict) or not isinstance(doc.get("series"), list):
        return None
    out: list[tuple[datetime, float]] = []
    for row in doc["series"]:
        if not isinstance(row, list) or len(row) != 2 or row[1] is None:
            continue
        try:
            t, v = int(row[0]), float(row[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            out.append((datetime.fromtimestamp(t / 1000, UTC), v))
    return out


def point_available_at(end: datetime, fetched_at: datetime) -> datetime:
    """THE PIT RULE FOR ONE POINT: late-biased, max(its own response's fetch instant, the end of
    its hour + the documented publication deadline)."""
    return max(fetched_at, end + PUBLICATION_LAG)


# ============================================================================ the fold
def fold_days(slug: str, comps: dict[str, list[tuple[datetime, float]]], days: Iterable[date],
              cet_offset_h: Callable[[datetime], int]) -> list[tuple[str, date, float]]:
    """(series, local day, value) for every COMPLETE local day. `comps` maps a component ("load",
    "residual", or a GEN label) to its hourly points. A component is published for a day only
    when every UTC hour of that day carries it; the generation total and share need every
    generation component that appears in the day to be complete (one null all day is absent,
    never zero) AND every generation filter to have been read at all."""
    hourly = {c: {int(t.timestamp() // 3600): v for t, v in pts} for c, pts in comps.items()}
    out: list[tuple[str, date, float]] = []
    gens = [g for g in GEN.values() if g in hourly]
    # The mix needs EVERY generation file read (a type whose file answered, even all-null, is
    # known; a type whose file was never read -- a 404, a budget cut -- leaves the total unknown).
    mix_read = all(g in comps for g in GEN.values())
    for d in days:
        a, b = _E.day_bounds(d, cet_offset_h)
        hours = list(range(int(a.timestamp() // 3600), int(b.timestamp() // 3600)))
        if not hours:
            continue

        def full(c: str, hours: list[int] = hours) -> bool:
            m = hourly.get(c) or {}
            return all(h in m for h in hours)

        def mean(c: str, hours: list[int] = hours) -> float:
            return sum(hourly[c][h] for h in hours) / len(hours)

        if full("load"):
            out.append((f"{slug}_load_mean", d, round(mean("load"), 3)))
        if full("residual"):
            out.append((f"{slug}_residual_load", d, round(mean("residual"), 3)))
        present = [g for g in gens if any(h in hourly[g] for h in hours)]
        for g in GEN_SERIES:
            if g in present and full(g):
                out.append((f"{slug}_gen_{g}", d, round(mean(g), 3)))
        if mix_read and present and all(full(g) for g in present) and any(
                g in present for g in WIND_SOLAR):
            total = sum(mean(g) for g in present)
            ws = sum(mean(g) for g in WIND_SOLAR if g in present)
            if total > 0:
                out.append((f"{slug}_ren_share", d, round(100.0 * ws / total, 4)))
    return out


def _component(filt: int) -> str:
    return "load" if filt == LOAD else "residual" if filt == RESIDUAL else GEN[filt]


# ============================================================================ the source row
#: Declared priors, untested (the gain test decides and charges every cell): entsoe_power's
#: DE-LU cells, on SMARD's licensed series.
SERIES_INSTRUMENTS: dict[str, dict[str, int]] = {
    "de_lu_load_mean": {"GER40": 1, "EURUSD": 1},
    "de_lu_residual_load": {"XNGUSD": 1},
    "de_lu_gen_gas": {"XNGUSD": 1},
    "de_lu_ren_share": {"XNGUSD": -1},
}
SIGNAL_SERIES = tuple(SERIES_INSTRUMENTS)


def rule_for(cet_offset_h: Callable[[datetime], int]) -> Callable[[date], datetime]:
    def rule(period: date) -> datetime:
        """Local day `period` is complete one hour after its last hour ends; `stamp_floor_fetch`
        raises it to the read when later."""
        return _E.day_bounds(period, cet_offset_h)[1] + PUBLICATION_LAG
    return rule


def make_source(ap: Any) -> Any:
    return ap.Source(
        id=SOURCE_ID, name="SMARD (Bundesnetzagentur) load, residual load and generation, DE",
        url=BASE_URL, region="EU", language="de", cadence="daily", parse=None,
        rule=rule_for(ap.cet_offset_h), stamp_floor_fetch=True, transform="anomaly_daily",
        instruments={}, series_instruments=dict(SERIES_INSTRUMENTS),
        signal_series=SIGNAL_SERIES, key_env=None,
        terms="confirmed" if live_input() else "to_confirm",
        mechanism=("metered German load and the generation mix are published within hours; gas "
                   "burn and residual load move European gas demand, and load tracks industrial "
                   "activity, weeks before any survey or official print"),
        payer="gas and index holders pricing German demand from monthly data and weather",
        constraint="official activity and gas-demand statistics are monthly and late",
        licence=f"CC BY 4.0 (Bundesnetzagentur | SMARD.de); {policy()['status']}",
        source_culture="EU/de", participant_structure=("physical_flow", "institutional"),
        failure_mode_hypothesis=("fails when load moves with temperature already in the "
                                 "forecast, or when LNG supply rather than burn sets the gas "
                                 "price"),
        crowding_prior="medium",
        note="no key; chart_data weekly hourly files folded to Berlin local days")


# ============================================================================ holds
def hold_row(status: int | str, url: str, cause: str, now: datetime) -> dict[str, Any]:
    """THE SHARED PERSON-HELD RECORD (entsoe_power.hold_row's shape). No expiry, no retry."""
    verdict = (BLOCK_VERDICT.get(status, "METHOD_BLOCKED") if isinstance(status, int)
               else "METHOD_BLOCKED")
    return {"key": f"site:{HOST}", "verdict": verdict,
            "status": status if isinstance(status, int) else (status or None),
            "host": HOST, "url": url[:300], "held_at": now.timestamp(),
            "released_by": None, "released_at": None,
            "since": now.isoformat(timespec="seconds"), "cause": cause[:300],
            "waits_for": "a person",
            "release": ("a person sets released_by and released_at on sources.smard_power."
                        "hard_stop in desks/mt5/data/alt_proxies/state.json (or deletes it)"),
            "missed_growth": {"delta_elogw": UNMEASURED,
                              "cause": (f"{SOURCE_ID} held after {cause[:200]}: no load or "
                                        "generation rows until a person releases the hold")}}


# ============================================================================ the pass
def _week_days(ts_ms: int, ap: Any, before: date) -> list[date]:
    """The Berlin local days a weekly file covers, strictly before `before`."""
    start = ap.cet_local(datetime.fromtimestamp(ts_ms / 1000, UTC)).date()
    return [d for d in (start + timedelta(days=i) for i in range(7)) if d < before]


def collect(ap: Any, paths: Any, src: Any, sst: dict[str, Any], store: dict[str, Any],
            now: datetime, *, fetch: bool, fixtures: Path | None, deadline: float,
            getter: Getter | None = None, robots_getter: Getter | None = None,
            sleep: Callable[[float], None] = time.sleep,
            clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict[str, Any]:
    """Fetch (or read fixtures), fold, merge into the vintage store. Returns the pass record."""
    out: dict[str, Any] = {"requests": 0, "fetched": 0, "parsed": 0, "errors": [],
                           "merge": {"added": 0, "revised": 0}, "unmeasured_windows": []}
    today = ap.cet_local(now).date()

    def fail(cause: str, *, hold: int | str | None = None, url: str = BASE_URL
             ) -> dict[str, Any]:
        out["errors"].append(cause)
        out["outcome"] = out["status"] = f"FAILED:{cause.split(':', 1)[0]}"
        out["why"] = cause
        if hold is not None:
            sst["hard_stop"] = hold_row(hold, url, cause, now)
            out["hard_stop"] = dict(sst["hard_stop"])
        return out

    def take(slug: str, comps: dict[str, list[tuple[datetime, float]]], days: list[date],
             seen: datetime) -> None:
        rows = fold_days(slug, comps, days, ap.cet_offset_h)
        obs = [ap.Obs(s, d, v) for s, d, v in rows]
        out["parsed"] += len(obs)
        m = ap.merge_vintages(store, src, obs, seen)
        out["merge"]["added"] += m["added"]
        out["merge"]["revised"] += m["revised"]

    if fixtures is not None:
        for region, (slug, _filters) in REGIONS.items():
            fp = fixtures / f"{SOURCE_ID}.{slug}.json"
            if not fp.exists():
                continue
            doc = json.loads(fp.read_text("utf-8"))
            comps: dict[str, list[tuple[datetime, float]]] = {}
            for filt_s, week in doc.items():
                pts = parse_week(json.dumps(week).encode())
                if pts is not None:
                    comps[_component(int(filt_s))] = pts
            if not any(comps.values()):
                continue
            all_t = [t for p in comps.values() for t, _v in p]
            days = list(_E._days(ap.cet_local(min(all_t)).date(), ap.cet_local(max(all_t)).date()))
            take(slug, comps, [d for d in days if d < today], now)
            out["fetched"] += 1
            out.setdefault("regions", []).append(region)
        if not out["parsed"]:
            return fail("EMPTY: no fixture folded to a complete local day")
        out["outcome"] = "OK"
        return out
    if not fetch:
        out["why"] = "no fetch this pass (--no-fetch): UNMEASURED, not zero"
        out["outcome"] = UNMEASURED
        return out
    if ap.held_by_person(sst, now, out):
        return out
    ua = _E._ua(ap)
    get: Getter = getter or (lambda url: http_get(url, ua))
    rb = ap.robots_verdict(index_url(LOAD, "DE-LU"), robots_getter or ap.http_get)
    out["robots"] = rb
    if rb["verdict"] == "hard_stop":
        import re
        rcode = re.search(r"(\d{3})", str(rb.get("note")))
        return fail(f"HARD_STOP: {rb['note']}", hold=int(rcode.group(1)) if rcode else "ROBOTS",
                    url=str(rb.get("robots") or BASE_URL))
    if rb["verdict"] != "allow":
        return fail(f"ROBOTS_{rb['verdict'].upper()}: {rb['note']}")
    delay = max(MIN_INTERVAL_S, float(rb.get("crawl_delay") or 0.0))
    cursors: dict[str, int] = sst.setdefault("cursor", {})
    done: dict[str, bool] = dict.fromkeys(REGIONS, False)
    state = {"first": True, "cut": False}
    missing: list[str] = []          # regions whose index answered 404 this pass

    def one(url: str, what: str) -> tuple[bytes, datetime] | dict[str, Any] | None:
        """One spaced GET. bytes+fetch instant, a failed record (stop the pass), or None (404,
        the window is UNMEASURED) -- or None with state['cut'] when the budget ended."""
        if not state["first"]:
            if time.monotonic() + delay > deadline:
                out["errors"].append(f"budget reached before {what}: the rest is owed to the "
                                     "next pass (cursor kept)")
                state["cut"] = True
                return None
            sleep(delay)
        state["first"] = False
        out["requests"] += 1
        try:
            body, ctype = get(url)
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            with contextlib.suppress(Exception):
                exc.close()
            if code in HARD_STOP:
                return fail(f"HARD_STOP: HTTP {code} on {what}", hold=code, url=url)
            if code == 404:
                out["unmeasured_windows"].append({"what": what, "status": UNMEASURED,
                                                  "why": "HTTP 404: no file for this window",
                                                  "url": url})
                return None
            return fail(f"HTTP_ERROR: HTTP {code} on {what}")
        except Exception as exc:
            return fail(f"TRANSPORT: {type(exc).__name__}: {str(exc)[:120]}")
        at = clock()
        out["fetched"] += 1
        if _json(body) is None:
            return fail(f"WAF: a non-JSON body on {what}", hold="WAF", url=url)
        with contextlib.suppress(Exception):
            ap.vault(paths, src, body, url, ctype or "application/json", at)
        return body, at

    floor_ms = int((now - timedelta(days=DEPTH_D)).timestamp() * 1000)
    recent_ms = int((now - timedelta(days=RECENT_D)).timestamp() * 1000)
    for region, (slug, filters) in REGIONS.items():
        if state["cut"]:
            break
        got = one(index_url(LOAD, region), f"{region} index")
        if isinstance(got, dict):
            return got
        if got is None:
            if state["cut"]:
                break
            missing.append(region)
            continue
        stamps = parse_index(got[0])
        if not stamps:
            return fail(f"INDEX: {region} index_{RESOLUTION}.json carries no timestamps")
        cur = cursors.get(region)
        start = int(cur) if isinstance(cur, int | float) else floor_ms
        # The week containing `start` (the last stamp at or before it), then every later week.
        prior = [t for t in stamps if t <= start]
        weeks = prior[-1:] + [t for t in stamps if t > start]
        for i, ts in enumerate(weeks):
            wk: dict[str, list[tuple[datetime, float]]] = {}
            seen: datetime | None = None
            for filt in filters:
                g = one(week_url(filt, region, ts), f"{region} {filt} week {ts}")
                if isinstance(g, dict):
                    return g
                if g is None:
                    if state["cut"]:
                        break
                    continue
                pts = parse_week(g[0])
                if pts is None:
                    return fail(f"PARSE: {region} {filt} week {ts} is not chart_data JSON")
                wk[_component(filt)] = pts
                seen = g[1] if seen is None else max(seen, g[1])
            if state["cut"]:
                break
            if seen is not None:
                take(slug, wk, _week_days(ts, ap, today), seen)
            if i == len(weeks) - 1:
                done[region] = True
                back = [t for t in stamps if t <= recent_ms]
                cursors[region] = back[-1] if back else ts
            else:
                cursors[region] = weeks[i + 1]
    out["caught_up"] = done
    if not out["parsed"]:
        if state["cut"]:
            return fail("BUDGET: the budget ended before any window completed (cursor kept)")
        if out["requests"] and len(out["unmeasured_windows"]) >= out["requests"]:
            return fail("ALL_WINDOWS_404: every file requested answered 404")
        return fail("EMPTY: SMARD answered with no complete local day" if out["fetched"]
                    else "BUDGET: no request completed inside the budget")
    if missing:
        out["outcome"] = out["status"] = "PARTIAL:INDEX_404"
        out["why"] = f"index 404 for {','.join(missing)}: those regions are UNMEASURED this pass"
        return out
    if not all(done.values()):
        behind = ",".join(r for r, ok in done.items() if not ok)
        out["outcome"] = out["status"] = "PARTIAL:BUDGET"
        out["why"] = f"budget cut before {behind} caught up (cursor kept)"
        return out
    out["outcome"] = out["status"] = ("UNCHANGED" if not (out["merge"]["added"]
                                                          or out["merge"]["revised"]) else "OK")
    return out


# ============================================================================ cells
def gain_tests(ap: Any, paths: Any, src: Any, pts: dict[str, list[dict[str, Any]]]
               ) -> dict[str, dict[str, Any]]:
    """entsoe_power.gain_tests on this source: every allowed (series, instrument) cell judged by
    release_gain at `release_gain.tier_s_t_required` for that cell's n; keys carry this id."""
    got = _E.gain_tests(ap, paths, src, pts)
    out: dict[str, dict[str, Any]] = {}
    for key, res in got.items():
        _sid, series, sym = key.split("|")
        res = dict(res)
        if "live_input" in res:
            res["live_input"] = live_input()
        out[f"{SOURCE_ID}|{series}|{sym}"] = res
    return out


def cells(ap: Any, src: Any, gains: dict[str, dict[str, Any]], now: datetime
          ) -> list[dict[str, Any]]:
    """PASSING cells as exogenous_conditioner recipes, carrying this source's attribution."""
    out = []
    for c in _E.cells(ap, src, gains, now):
        out.append({**c, "source": SOURCE_ID, "credit": CREDIT, "live_input": live_input(),
                    "terms_status": policy()["status"],
                    "provenance": {**c["provenance"], "organ": SOURCE_ID,
                                   "terms_row": POLICY_KEY}})
    return out


# ============================================================================ the producer
def run_pass(ap: Any, paths: Any, state: dict[str, Any], now: datetime, *, fetch: bool,
             fixtures: Path | None, deadline: float, dry_run: bool = False,
             donate: bool = True, getter: Getter | None = None,
             robots_getter: Getter | None = None,
             sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> dict[str, Any]:
    """One pass: collect, build PIT points, judge cells, charge trials, donate only when LIVE."""
    src = make_source(ap)
    sst = state.setdefault("sources", {}).setdefault(SOURCE_ID, {})
    store_p = paths.obs_dir / f"{SOURCE_ID}.json"
    store = ap._read_json(store_p, {})
    rec = collect(ap, paths, src, sst, store, now, fetch=fetch, fixtures=fixtures,
                  deadline=deadline, getter=getter, robots_getter=robots_getter, sleep=sleep,
                  clock=clock)
    if not dry_run:
        ap._atomic(store_p, store)
    rec["store_rows"] = len(store)
    pts = ap.build_points(src, store) if store else {}
    rec["series"] = {k: len(v) for k, v in sorted(pts.items())}
    live = live_input()
    gains = gain_tests(ap, paths, src, pts) if pts and fixtures is None else {}
    tested = ("PASS", "FAIL", "UNDERPOWERED")
    n_tested = sum(1 for g in gains.values() if g.get("verdict") in tested)
    passing = cells(ap, src, gains, now)
    donation: dict[str, Any] = {"donated": 0}
    if donate and not dry_run:
        donation = ap._donate(paths, SOURCE_ID, passing if live else [], n_tested,
                              {ap.DIRECT_FAMILY: n_tested}, now)
    if live and pts and not dry_run:
        ap._atomic(paths.axes / f"alt_{SOURCE_ID}.json", {**ap.axis_doc(src, pts, now),
                                                         "credit": CREDIT})
        rec["lake_series"] = ap.write_lake_series(paths, src, pts)
    return {
        **rec, "id": SOURCE_ID, "credit": CREDIT,
        "terms": {"row": POLICY_KEY, "status": policy()["status"], "live_input": live,
                  "missed_growth": None if live else policy()["missed_growth"]},
        "filters": {str(f): FILTER_LABEL[f] for f in REGIONS["DE-LU"][1]},
        "pit_rule": ("point available = max(response fetch instant, hour end + 1h); daily "
                     "value = max(fetch, Berlin local day end + 1h); lag source: " + LAG_SOURCE),
        "gain_tests": gains, "n_cells_tested": n_tested,
        "cells": {"n_passing": len(passing), "donation": donation,
                  "rule": ("passing cells donate only when the terms row is LIVE; every tested "
                           "cell is charged either way"),
                  "passing": passing},
        "live_yield": "UNMEASURED until the trading box runs the alt_proxies leg",
    }


def smard_asof(ap: Any, decision_at: datetime, store_path: Path | None = None
               ) -> dict[str, Any]:
    """The consumer: latest daily values KNOWN at `decision_at` (alt_proxies.series_asof, the
    one PIT reader: stamp <= decision and day < decision day). A non-LIVE row answers nothing."""
    if not live_input():
        return {"status": policy()["status"], "series": {}, "credit": CREDIT,
                "why": "SMARD terms row is not LIVE: never read as live input"}
    got = ap.series_asof(SOURCE_ID, decision_at, store_path)
    return {**got, "credit": CREDIT}
