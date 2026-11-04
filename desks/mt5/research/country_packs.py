"""COUNTRY OPEN-DATA PACKS -- the official central-bank and statistics-office doors for the
regions the desk had dark (REGION_GAP_RANK 2026-11-03: Turkey rank 3, Poland 4, South Africa 5,
Sweden 10; every one 0 YIELDED).

NOT A LANE. This module declares doors, parsers and release clocks and nothing else: it fetches
nothing on its own, has no schedule and writes no artifact. `world_dataset_hunter` (leg
`world_dataset_hunt`, hourly) reads `doors()` as part of its direct doors, fetches each through
its own budgeted, terms-fenced, robots-labelled client, PIT-merges the series into the world store
and exposes them per MT5 symbol; `world_macro_proposer` mints `world_macro_state` cells from that
exposure and the family reloads each series by `series_key`. So a pack series reaches the
gauntlet by exactly the path every DBnomics series already takes.

TERMS FAIL CLOSED. Every door names its `terms_fence.SOURCE_POLICY` row. A door on an IDEAS_ONLY
row is HELD before any request (its parser is still built and tested on fixtures, and the row
carries the missed-growth line); a door on an API_PERMITTED row whose key is absent reads
NEEDS_KEY; a door whose series code has no default and no configured value reads NEEDS_CONFIG.
None of those three is a zero and none counts toward the liveness streak.

PIT BY RELEASE TIME. Each door carries the instant its publisher releases a reading, pushed late
where the clock is approximate (each rule is named below). A series row's `release_at` maps each
period to that instant, and the hunter stamps `available_time` from it instead of a cadence lag.
SWESTR prints its own `publicationTime`, which is used as given.

LIVENESS. The hunter counts, per door, consecutive attempts that delivered nothing (a classified
fetch failure or an empty parse); `liveness()` turns that into the DEPENDENCY_LIVENESS shape the
fred-axis fix introduced (verdict RED when any door's streak exceeds RED_AFTER_RUNS = 2).
"""
from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

try:
    from research import asia_gold_physical as _agp
except ImportError:                                                           # pragma: no cover
    import asia_gold_physical as _agp  # type: ignore[no-redef]

UNMEASURED = "UNMEASURED"
#: A door is RED when it has delivered nothing on MORE than this many consecutive attempts.
RED_AFTER_RUNS = 2
#: How long a door waits after a success (data arrives daily; a 6h refresh keeps first_seen
#: within hours of release) and after a failure (so three failures read RED within a day).
REFRESH_OK_H = 6.0
RETRY_FAIL_H = 6.0
#: Days of history asked for on a door's FIRST pass (the store dedupes; later passes ask for the
#: recent window only). Daily series need >= 250 points to pass the hunter's quality floor.
BACKFILL_DAYS = {"daily": 560, "monthly": 365 * 8, "weekly": 365 * 3}
RECENT_DAYS = {"daily": 40, "monthly": 400, "weekly": 120}
#: The NBP API refuses a range longer than this (api.nbp.pl/en.html, quoted in pl_nbp).
NBP_MAX_RANGE_D = 93

EVDS_BASE = os.environ.get("ALT_EVDS_BASE", "https://evds3.tcmb.gov.tr/igmevdsms-dis/")
NBP_API = "https://api.nbp.pl/api/"
NBP_RATES_XML = os.environ.get("ALT_NBP_RATES_URL",
                               "https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml")
RIKSBANK_SWEA = "https://api.riksbank.se/swea/v1/Observations/"
RIKSBANK_SWESTR = "https://api.riksbank.se/swestr/v1/all/SWESTR"
SCB_API = "https://api.scb.se/OV0104/v1/doris/en/ssd/"
SCB_CPI_TABLE = os.environ.get("ALT_SCB_CPI_TABLE", "PR/PR0101/PR0101A/KPItotM")
SARB_RATES = "https://custom.resbank.co.za/SarbWebApi/WebIndicators/HomePageRates"


@dataclass(frozen=True)
class Req:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    data: bytes | None = None


@dataclass(frozen=True)
class Door:
    id: str
    pack: str
    provider: str
    name: str
    policy: str
    freq: str
    parse: str
    currencies: tuple[str, ...] = ()
    stems: tuple[str, ...] = ()
    code: str = ""
    code_env: str = ""
    release: str = ""
    what: str = ""


@dataclass(frozen=True)
class Pack:
    country: str
    iso2: str
    currency: str
    publishers: tuple[str, ...]
    #: Local equity indices the pack would inform; mapped only when the broker registry holds one.
    local_indices: tuple[str, ...]
    #: High-value series the pack could not build, each with its reason (recorded, never zero).
    not_built: tuple[tuple[str, str], ...] = ()


PACKS: dict[str, Pack] = {
    "tr": Pack("Turkey", "TR", "TRY", ("CBRT EVDS",), ("TR30", "TUR30", "BIST30", "XU100"),
               (("inflation surprise vs consensus", "no free consensus series; cpi_yoy_chg is the "
                 "acceleration proxy"),)),
    "pl": Pack("Poland", "PL", "PLN", ("NBP",), ("PL20", "POL20", "WIG20"),
               (("CPI / current account", "GUS and NBP balance-of-payments APIs not yet read for "
                 "terms; BIS and DBnomics doors carry PL CPI meanwhile"),
                ("FX reserves", "NBP publishes reserves as XLSX only; no machine door read"))),
    "se": Pack("Sweden", "SE", "SEK", ("Sveriges Riksbank", "Statistics Sweden"),
               ("SE30", "SWE30", "OMXS30"),
               (("current account / FX reserves", "SCB BoP tables and Riksbank reserves not yet "
                 "mapped to a table id"),)),
    "za": Pack("South Africa", "ZA", "ZAR", ("SARB", "Stats SA"), ("SA40", "SAF40", "JSE40"),
               (("CPI / current account", "Stats SA: Incapsula WAF, terms UNREAD (za_statssa_macro "
                 "IDEAS_ONLY)"),
                ("policy rate (live)", "SARB IDEAS_ONLY (za_sarb); BIS WS_CBPOL carries ZA policy "
                 "rate through the existing BIS direct door"))),
}

#: Default EVDS codes. Each was taken from the EVDS catalogue's published naming, NOT read on the
#: box: a wrong code parses to [] and the door turns RED after three passes, which is the check.
#: Overridable per code with the env var named on the door; a door with no default and no value
#: reads NEEDS_CONFIG.
DOORS: tuple[Door, ...] = (
    Door("tr_usdtry_cbrt", "tr", "CBRT_EVDS", "CBRT indicative USD/TRY buying rate (EVDS)",
         "tr_evds_macro", "daily", "evds", ("TRY",), code="TP.DK.USD.A.YTL",
         code_env="ALT_EVDS_USDTRY_SERIES", release="tr_fx",
         what="CBRT 15:30 TR indicative rate, stamped 13:00 UTC on its date"),
    Door("tr_funding_cost", "tr", "CBRT_EVDS", "CBRT weighted average cost of funding (EVDS)",
         "tr_evds_macro", "daily", "evds", ("TRY",), code="TP.APIFON4",
         code_env="ALT_EVDS_FUNDING_SERIES", release="tr_funding",
         what="CBRT funding cost, stamped 15:00 UTC on its date (published after the market)"),
    Door("tr_cpi", "tr", "CBRT_EVDS", "Turkey CPI (TUIK, via EVDS)", "tr_evds_macro", "monthly",
         "evds_cpi", ("TRY",), code="TP.FG.J0", code_env="ALT_EVDS_CPI_SERIES", release="tr_cpi",
         what="TUIK CPI on the 3rd of the next month 10:00 TR, stamped 07:00 UTC that day "
              "(next weekday)"),
    Door("tr_fx_reserves", "tr", "CBRT_EVDS", "CBRT gross FX reserves (EVDS)", "tr_evds_macro",
         "weekly", "evds", ("TRY",), code_env="ALT_EVDS_RESERVES_SERIES", release="tr_weekly",
         what="CBRT Thursday release for the prior Friday, stamped Friday + 6 days 12:00 UTC"),
    Door("tr_current_account", "tr", "CBRT_EVDS", "Turkey current account balance (EVDS)",
         "tr_evds_macro", "monthly", "evds", ("TRY",), code_env="ALT_EVDS_CA_SERIES",
         release="month_plus_45",
         what="CBRT BoP release ~6 weeks after the month, stamped month end + 45 days"),
    Door("pl_fx_usd", "pl", "NBP", "NBP table A USD/PLN fixing", "pl_nbp", "daily", "nbp_fx",
         ("PLN",), code="USD", release="nbp_fix",
         what="NBP table A published ~11:45-12:15 Warsaw, stamped 11:30 UTC"),
    Door("pl_fx_eur", "pl", "NBP", "NBP table A EUR/PLN fixing", "pl_nbp", "daily", "nbp_fx",
         ("PLN",), code="EUR", release="nbp_fix", what="as pl_fx_usd"),
    Door("pl_gold", "pl", "NBP", "NBP gold price PLN per gram", "pl_nbp", "daily", "nbp_gold",
         ("PLN",), ("XAU",), release="nbp_fix", what="published with table A, stamped 11:30 UTC"),
    Door("pl_policy_rates", "pl", "NBP", "NBP policy rates (reference, lombard, deposit)",
         "pl_nbp", "daily", "nbp_rates", ("PLN",), release="effective",
         what="each rate stepped forward from its 'obowiazuje_od' date (announced the day "
              "before), stamped 00:00 UTC on each business day it is in force"),
    Door("se_policy_rate", "se", "RIKSBANK", "Riksbank policy rate (SWEA SECBREPOEFF)",
         "se_riksbank", "daily", "swea", ("SEK",), code="SECBREPOEFF", release="effective",
         what="the rate in force that day, stamped 00:00 UTC (decided days earlier)"),
    Door("se_usdsek", "se", "RIKSBANK", "Riksbank USD/SEK fixing (SWEA SEKUSDPMI)",
         "se_riksbank", "daily", "swea", ("SEK",), code="SEKUSDPMI", release="se_fix",
         what="Riksbank fixing ~16:15 CET, stamped 16:00 UTC"),
    Door("se_eursek", "se", "RIKSBANK", "Riksbank EUR/SEK fixing (SWEA SEKEURPMI)",
         "se_riksbank", "daily", "swea", ("SEK",), code="SEKEURPMI", release="se_fix",
         what="as se_usdsek"),
    Door("se_swestr", "se", "RIKSBANK", "SWESTR overnight rate", "se_riksbank", "daily",
         "swestr", ("SEK",), release="given",
         what="its own publicationTime (next business day ~09:00 CET); else +1 weekday 09:00 UTC"),
    Door("se_cpi", "se", "SCB", "Sweden CPI (SCB KPI, 1980=100)", "se_scb", "monthly", "scb_cpi",
         ("SEK",), code=SCB_CPI_TABLE, code_env="ALT_SCB_CPI_TABLE", release="se_cpi",
         what="SCB CPI mid next month 08:00 CET, stamped month end + 16 days 07:00 UTC"),
    Door("za_sarb_rates", "za", "SARB", "SARB home-page rates (repo, prime, JIBAR, ZAR)",
         "za_sarb", "daily", "sarb", ("ZAR",), release="se_fix",
         what="held (IDEAS_ONLY); stamped 16:00 UTC on its date if ever unblocked"),
)
BY_ID = {d.id: d for d in DOORS}


# ----------------------------------------------------------------------------- release ----
def _weekday_on_or_after(t: datetime) -> datetime:
    while t.weekday() >= 5:
        t += timedelta(days=1)
    return t


def _month_end(y: int, m: int) -> date:
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def release_at(rule: str, period: date) -> datetime:
    """The instant a reading for `period` is first knowable (UTC), per the door's named rule."""
    d = datetime(period.year, period.month, period.day, tzinfo=UTC)
    if rule == "tr_fx":
        return d + timedelta(hours=13)
    if rule == "tr_funding":
        return d + timedelta(hours=15)
    if rule == "tr_cpi":
        nxt = d + timedelta(days=1)                                 # period is the month END
        return _weekday_on_or_after(datetime(nxt.year, nxt.month, 3, 7, tzinfo=UTC))
    if rule == "tr_weekly":
        return d + timedelta(days=6, hours=12)
    if rule == "month_plus_45":
        return _weekday_on_or_after(d + timedelta(days=45, hours=8))
    if rule == "nbp_fix":
        return d + timedelta(hours=11, minutes=30)
    if rule == "se_fix":
        return d + timedelta(hours=16)
    if rule == "se_cpi":
        return _weekday_on_or_after(d + timedelta(days=16, hours=7))
    if rule == "given":
        return _weekday_on_or_after(d + timedelta(days=1, hours=9))
    return d                                                         # "effective"


# ----------------------------------------------------------------------------- parsers ----
def _num(v: Any) -> float | None:
    try:
        x = float(str(v).replace(",", ".").strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None


def parse_evds(body: bytes, door: Door, code: str) -> list[tuple[str, float]]:
    """The asia-gold EVDS client's parser: (YYYY-MM-DD or YYYY-MM, value)."""
    out = []
    for r in _agp.parse_evds(body, code):
        p = r["date"][:7] if r.get("freq") == "M" else r["date"]
        out.append((p, float(r["value"])))
    return out


def parse_nbp_fx(body: bytes, door: Door, code: str = "") -> list[tuple[str, float]]:
    doc = _json(body)
    rates = doc.get("rates") if isinstance(doc, dict) else None
    out = []
    for r in rates if isinstance(rates, list) else []:
        if isinstance(r, dict) and (v := _num(r.get("mid"))) is not None:
            d = str(r.get("effectiveDate") or "")[:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                out.append((d, v))
    return out


def parse_nbp_gold(body: bytes, door: Door, code: str = "") -> list[tuple[str, float]]:
    doc = _json(body)
    out = []
    for r in doc if isinstance(doc, list) else []:
        if isinstance(r, dict) and (v := _num(r.get("cena"))) is not None:
            d = str(r.get("data") or "")[:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                out.append((d, v))
    return out


_POZ = re.compile(r"<pozycja\b([^>]*)/?>", re.I)
_POZYCJE = re.compile(r"<(?:pozycje|tabela)\b([^>]*)>(.*?)</(?:pozycje|tabela)>", re.I | re.S)
_ATTR = re.compile(r'([\w:]+)\s*=\s*"([^"]*)"')
_NBP_RATE_IDS = {"ref": "reference", "lom": "lombard", "dep": "deposit", "red": "rediscount"}


def nbp_rate_events(body: bytes) -> dict[str, list[tuple[date, float]]]:
    """NBP rates XML -> {rate: [(effective date, %)]}. A `pozycja` dates itself with
    `obowiazuje_od` or inherits its parent block's; Polish decimal commas are read."""
    text = body.decode("utf-8", "replace")
    out: dict[str, dict[date, float]] = {}

    def take(attrs: dict[str, str], parent_from: str) -> None:
        rid = _NBP_RATE_IDS.get(attrs.get("id", "").lower())
        v = _num(attrs.get("oprocentowanie"))
        when = attrs.get("obowiazuje_od") or parent_from
        if not rid or v is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", when[:10]):
            return
        out.setdefault(rid, {})[date.fromisoformat(when[:10])] = v

    blocks = list(_POZYCJE.finditer(text))
    for b in blocks:
        parent = dict(_ATTR.findall(b.group(1))).get("obowiazuje_od", "")
        for m in _POZ.finditer(b.group(2)):
            take(dict(_ATTR.findall(m.group(1))), parent)
    if not blocks:
        for m in _POZ.finditer(text):
            take(dict(_ATTR.findall(m.group(1))), "")
    return {k: sorted(v.items()) for k, v in out.items()}


def step_daily(events: list[tuple[date, float]], start: date, end: date
               ) -> list[tuple[str, float]]:
    """A stepped policy rate as the business-day series of the rate IN FORCE each day."""
    out = []
    ev = sorted(events)
    i, cur = 0, None
    d = start
    while d <= end:
        while i < len(ev) and ev[i][0] <= d:
            cur = ev[i][1]
            i += 1
        if cur is not None and d.weekday() < 5:
            out.append((d.isoformat(), cur))
        d += timedelta(days=1)
    return out


def parse_swea(body: bytes, door: Door, code: str = "") -> list[tuple[str, float]]:
    doc = _json(body)
    out = []
    for r in doc if isinstance(doc, list) else []:
        if isinstance(r, dict) and (v := _num(r.get("value"))) is not None:
            d = str(r.get("date") or "")[:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                out.append((d, v))
    return out


def parse_swestr(body: bytes, door: Door, code: str = ""
                 ) -> tuple[list[tuple[str, float]], dict[str, str]]:
    """SWESTR rows -> points and each point's OWN publication instant (UTC ISO)."""
    doc = _json(body)
    rows = doc if isinstance(doc, list) else [doc] if isinstance(doc, dict) else []
    pts, rel = [], {}
    for r in rows:
        if not isinstance(r, dict) or (v := _num(r.get("rate"))) is None:
            continue
        d = str(r.get("date") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        pts.append((d, v))
        pub = str(r.get("publicationTime") or "")
        try:
            t = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if t.tzinfo is None:                     # SWESTR prints Stockholm local time
                t = t.replace(tzinfo=UTC) - timedelta(hours=2 if 3 < t.month < 11 else 1)
            rel[d] = t.astimezone(UTC).isoformat()
        except ValueError:
            pass
    return pts, rel


def parse_jsonstat_months(body: bytes, door: Door, code: str = "") -> list[tuple[str, float]]:
    """A one-content json-stat2 table over a time dimension of 'YYYYMmm' -> (YYYY-MM, value)."""
    doc = _json(body)
    if not isinstance(doc, dict):
        return []
    dims = doc.get("id") or []
    sizes = doc.get("size") or []
    vals = doc.get("value")
    tdim = next((d for d in dims if str(d).lower() in ("tid", "time", "month")), None)
    if not tdim or not isinstance(vals, list) or len(dims) != len(sizes):
        return []
    if any(s != 1 for d, s in zip(dims, sizes, strict=False) if d != tdim):
        return []                               # more than one series in the body: refuse
    idx = ((doc.get("dimension") or {}).get(tdim) or {}).get("category", {}).get("index") or {}
    order = sorted(idx, key=lambda k: idx[k]) if isinstance(idx, dict) else list(idx)
    out = []
    for i, lab in enumerate(order):
        m = re.fullmatch(r"(\d{4})M(\d{2})", str(lab))
        if m and i < len(vals) and (v := _num(vals[i])) is not None:
            out.append((f"{m[1]}-{m[2]}", v))
    return out


def parse_sarb(body: bytes, door: Door, code: str = "") -> dict[str, list[tuple[str, float]]]:
    """SARB home-page indicator rows -> one series per indicator name (fixtures only: held)."""
    doc = _json(body)
    out: dict[str, list[tuple[str, float]]] = {}
    for r in doc if isinstance(doc, list) else []:
        if not isinstance(r, dict) or (v := _num(r.get("Value"))) is None:
            continue
        d = str(r.get("Date") or "")[:10]
        name = re.sub(r"[^a-z0-9]+", "_", str(r.get("Name") or "").lower()).strip("_")
        if name and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            out.setdefault(name, []).append((d, v))
    return out


def yoy(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Monthly index -> year-on-year % (the inflation rate)."""
    by = dict(points)
    out = []
    for p, v in points:
        prev = by.get(f"{int(p[:4]) - 1:04d}{p[4:]}")
        if prev:
            out.append((p, round(100.0 * (v / prev - 1.0), 6)))
    return out


def diff(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """First difference (the inflation ACCELERATION: the free stand-in for a surprise)."""
    return [(points[i][0], round(points[i][1] - points[i - 1][1], 6))
            for i in range(1, len(points))]


# -------------------------------------------------------------------------- the doors ----
def door_code(door: Door) -> str:
    v = os.environ.get(door.code_env, "").strip() if door.code_env else ""
    return v or door.code


def gate(door: Door) -> tuple[str, str] | None:
    """(state, why) when the door may not be fetched this pass; None when it may."""
    from libs.data import terms_fence as tf
    st = tf.status(door.policy)
    if st == tf.NEEDS_KEY:
        keys = ",".join(tf.SOURCE_POLICY[door.policy].get("key_env") or ())
        return "NEEDS_KEY", f"{keys} absent on this host"
    held = tf.input_source(door.id)
    if held:
        return "HELD", f"terms_fence {held} is {tf.status(held)}: never live input"
    if st != tf.API_PERMITTED:
        return "HELD", f"terms_fence {door.policy} is {st}"
    if door.parse.startswith("evds") and not _agp.evds_code_ok(door_code(door)):
        return "NEEDS_CONFIG", f"{door.code_env} unset (no default EVDS code was readable)"
    return None


def requests_for(door: Door, now: datetime, *, first: bool) -> list[Req]:
    """The requests one attempt makes. Keys travel in headers only, never in a URL."""
    end = now.date()
    days = (BACKFILL_DAYS if first else RECENT_DAYS).get(door.freq, 400)
    start = end - timedelta(days=days)
    code = door_code(door)
    if door.parse.startswith("evds"):
        if door.parse == "evds_cpi":
            start = end - timedelta(days=365 * 8 + 31)       # yoy needs the prior year too
        key = os.environ.get("EVDS_API_KEY", "")
        return [Req(_agp.evds_url(EVDS_BASE, code, start, end), {_agp.EVDS_KEY_HEADER: key})]
    if door.parse in ("nbp_fx", "nbp_gold"):
        out, a = [], start
        while a <= end:
            b = min(end, a + timedelta(days=NBP_MAX_RANGE_D - 1))
            path = (f"exchangerates/rates/A/{code}/{a}/{b}/" if door.parse == "nbp_fx"
                    else f"cenyzlota/{a}/{b}/")
            out.append(Req(f"{NBP_API}{path}?format=json"))
            a = b + timedelta(days=1)
        return out
    if door.parse == "nbp_rates":
        return [Req(NBP_RATES_XML)]
    if door.parse == "swea":
        return [Req(f"{RIKSBANK_SWEA}{code}/{start}/{end}")]
    if door.parse == "swestr":
        return [Req(f"{RIKSBANK_SWESTR}?fromDate={start}")]
    if door.parse == "scb_cpi":
        body = json.dumps({"query": [], "response": {"format": "json-stat2"}}).encode()
        return [Req(f"{SCB_API}{code}", {"Content-Type": "application/json"}, body)]
    if door.parse == "sarb":
        return [Req(SARB_RATES)]
    raise ValueError(door.parse)


def series_from_bodies(door: Door, bodies: list[bytes], now: datetime
                       ) -> list[dict[str, Any]]:
    """Bodies of one attempt -> hunter series dicts, each carrying `release_at` per period.
    An empty list is EMPTY (the caller counts it toward the door's streak)."""
    code = door_code(door)
    named: dict[str, list[tuple[str, float]]] = {}
    given: dict[str, str] = {}
    if door.parse in ("evds", "evds_cpi"):
        pts = [p for b in bodies for p in parse_evds(b, door, code)]
        if door.parse == "evds_cpi":
            pts = sorted(dict(pts).items())
            named = {"cpi_index": pts, "cpi_yoy": yoy(pts), "cpi_yoy_chg": diff(yoy(pts))}
        else:
            named = {door.id: pts}
    elif door.parse == "nbp_fx":
        named = {door.id: [p for b in bodies for p in parse_nbp_fx(b, door)]}
    elif door.parse == "nbp_gold":
        named = {door.id: [p for b in bodies for p in parse_nbp_gold(b, door)]}
    elif door.parse == "nbp_rates":
        start = now.date() - timedelta(days=BACKFILL_DAYS["daily"])
        for b in bodies:
            for rid, ev in nbp_rate_events(b).items():
                named[f"nbp_{rid}_rate"] = step_daily(ev, start, now.date())
    elif door.parse == "swea":
        named = {door.id: [p for b in bodies for p in parse_swea(b, door)]}
    elif door.parse == "swestr":
        sw: list[tuple[str, float]] = []
        for b in bodies:
            got, rel = parse_swestr(b, door)
            sw += got
            given.update(rel)
        named = {door.id: sw}
    elif door.parse == "scb_cpi":
        pts = [p for b in bodies for p in parse_jsonstat_months(b, door)]
        named = {"cpi_index": pts, "cpi_yoy": yoy(pts), "cpi_yoy_chg": diff(yoy(pts))}
    elif door.parse == "sarb":
        for b in bodies:
            for k, v in parse_sarb(b, door).items():
                named.setdefault(k, []).extend(v)
    out = []
    for name, raw in named.items():
        pts = sorted(dict(raw).items())
        if not pts:
            continue
        stamps: dict[str, str] = {}
        for p, _ in pts:
            if p in given:
                stamps[p] = given[p]
                continue
            d = (_month_end(int(p[:4]), int(p[5:7])) if len(p) == 7
                 else date.fromisoformat(p[:10]))
            stamps[p] = release_at(door.release, d).isoformat()
        out.append({"code": name, "name": f"{door.name} {name}".strip(),
                    "freq": door.freq, "dims": {"REF_AREA": PACKS[door.pack].iso2},
                    "points": pts, "release_at": stamps})
    return out


Fetch = Callable[[Req], bytes]


def fetch_door(door: Door, get: Fetch, now: datetime, *, first: bool) -> list[dict[str, Any]]:
    """One attempt: every request through `get` (the hunter's client), then the parse."""
    bodies = [get(r) for r in requests_for(door, now, first=first)]
    return series_from_bodies(door, bodies, now)


# ------------------------------------------------------------------------ mapping, report ----
def unmapped_indices(universe_symbols: set[str]) -> dict[str, list[str]]:
    """Per pack, the local indices the broker registry does NOT hold (recorded, never dropped)."""
    up = {s.upper() for s in universe_symbols}
    return {k: [i for i in p.local_indices if i.upper() not in up] for k, p in PACKS.items()}


def mapped_indices(universe_symbols: set[str]) -> dict[str, list[str]]:
    up = {s.upper() for s in universe_symbols}
    return {k: [i for i in p.local_indices if i.upper() in up] for k, p in PACKS.items()}


def door_verdict(row: dict[str, Any]) -> str:
    state = str(row.get("pack_state") or "")
    if state in ("HELD", "NEEDS_KEY", "NEEDS_CONFIG"):
        return state
    streak = int(row.get("empty_streak") or 0)
    if streak > RED_AFTER_RUNS:
        return "RED"
    if streak > 0:
        return "AMBER"
    if row.get("fetched_at"):
        return "GREEN"
    return UNMEASURED


def liveness(rows: dict[str, dict[str, Any]], now: datetime) -> dict[str, Any]:
    """The DEPENDENCY_LIVENESS shape (fred-axis fix, Rule 23) for the country-pack doors.

    RED when any door has delivered nothing on more than RED_AFTER_RUNS consecutive attempts;
    UNMEASURED when no door has ever delivered and none is RED (a host that never reached them);
    GREEN otherwise. HELD / NEEDS_KEY / NEEDS_CONFIG doors are listed with their cause and never
    counted GREEN."""
    deps: dict[str, dict[str, Any]] = {}
    for d in DOORS:
        r = rows.get(d.id) or {}
        deps[d.id] = {"pack": d.pack, "policy": d.policy, "verdict": door_verdict(r),
                      "empty_streak": int(r.get("empty_streak") or 0),
                      "first_empty_at": r.get("first_empty_at"),
                      "last_ok_at": r.get("fetched_at"),
                      "last_reason": r.get("fail_reason"),
                      "release_rule": d.what}
    red = sorted(k for k, v in deps.items() if v["verdict"] == "RED")
    delivered = any(v["verdict"] in ("GREEN", "AMBER") and v["last_ok_at"]
                    for v in deps.values())
    verdict = "RED" if red else ("GREEN" if delivered else UNMEASURED)
    sources = {}
    for k in PACKS:
        vs = [v["verdict"] for v in deps.values() if v["pack"] == k]
        sources[k] = ("RED" if "RED" in vs else "GREEN" if "GREEN" in vs else
                      "AMBER" if "AMBER" in vs else
                      "HELD" if vs and all(x == "HELD" for x in vs) else UNMEASURED)
    return {"at": now.isoformat(timespec="seconds"), "organ":
            "desks/mt5/research/world_dataset_hunter.py (country packs)",
            "verdict": verdict, "red_after_runs": RED_AFTER_RUNS, "red": red,
            "dependencies": deps, "sources": sources,
            "rule": ("RED when a door delivers nothing on more than two consecutive attempts; "
                     "HELD/NEEDS_KEY/NEEDS_CONFIG are holds with a cause, never GREEN, never 0")}


def missed_growth_lines() -> dict[str, dict[str, Any]]:
    """The missed-growth line of every pack policy row that holds (read from the fence row)."""
    from libs.data import terms_fence as tf
    out = {}
    for pol in sorted({d.policy for d in DOORS} | {"za_statssa_macro"}):
        row = tf.SOURCE_POLICY.get(pol) or {}
        if row.get("missed_growth"):
            out[pol] = dict(row["missed_growth"])
    return out
