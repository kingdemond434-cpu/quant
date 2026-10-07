"""DOMAIN HYPOTHESIS FACTORIES: weather degree days, job postings, payments, numeric NDVI.

WHAT WAS MISSING (DATA-43 / DATA-25, audit of 2026-10-06). No weather HDD/CDD factory, no forecast
revision or model-disagreement series, no job-postings factory and no payments factory existed
anywhere, and the desk held no numeric NDVI. The other alternative-data domains already had
parsers in `alt_proxies.py` (FIRMS, PortWatch, customs, card/retail spending, attention) but no
single place said, per domain, which source feeds it, under what terms, and in what state.

ONE INTERFACE, THE EXISTING DOORS. Every factory here is the same four steps, and every step is a
door the desk already has -- nothing below is a second lane:

  1. FETCH, FAIL CLOSED ON TERMS. A source is requested only when `TERMS_RECORDS` holds a
     PERMITS verdict with a clause quoted verbatim from the source's own terms page (read
     2026-10-07). Anything else is HELD and no request for it is ever built (`guarded_get`
     refuses even if one were). A source whose key env var is absent reads NEEDS_KEY, never zero;
     no key is printed, logged or written (`_redact`).
  2. PIT SERIES THROUGH alt_proxies' VINTAGE STORE. Parsed values become `alt_proxies.Obs` and go
     through `alt_proxies.merge_vintages` (append-only, first value kept, a revision is its own
     stamped fact), `build_points` (available_time / first_seen_at / revision_time / vintage_id /
     pit_quality) and `write_lake_series` -- so each factory series lands in
     `data/lake/series/alt_<store>__<series>.csv`, the envelope `exogenous_conditioner` and
     `cell_modifiers` already read, and in `data/axes/alt_<store>.json` for the forge.
  3. HYPOTHESES THE COMPILER READS. Each factory declares a small, fixed set of pre-registered
     (series, instrument, prior sign) hypotheses. A hypothesis is minted only once its lake series
     has `MIN_POINTS` PIT points (the family refuses below 30 anyway), as an EXACT_RECIPE
     `exogenous_conditioner` row donated through `proposer_common.donate` (stamped, lane-filtered,
     pre-registered) into `data/intelligence/domain_factories/`. Nothing here tests a cell, so
     each donation carries tests_run=0; the gauntlet is the judge and charges the trials.
  4. ONE HOURLY REPORT: `reports/DOMAIN_FACTORIES.json`, per factory and per source a status from
     {FETCHED, HELD, NEEDS_KEY, UNMEASURED}, the terms record, the key state, the series written
     and the hypotheses minted or held back with the reason.

THE FACTORIES.

  weather   NOAA CPC population-weighted daily HDD/CDD by Census division (observed; the
            anomaly is the trailing 7-day sum against the same window in up to ten prior years),
            and two forecast models for 22 stations across the nine divisions -- GFS extended MOS
            bulletins (tgftp.nws.noaa.gov) and the NWS gridpoint forecast (api.weather.gov, NDFD).
            EVERY FORECAST VINTAGE IS KEPT (`weather_forecast_vintages.json`); the revision is the
            latest vintage minus the latest one issued at least 20 h before it, for the same
            target date; the disagreement is GFS-MOS minus NDFD for the same target date when the
            two runs were issued within 24 h of each other. Base 65 F (NOAA). Europe: ECMWF open
            data PERMITS (CC-BY-4.0, quoted) but is GRIB2 and no GRIB decoder exists on the base,
            so it is UNMEASURED and never fetched; Open-Meteo's free tier is non-commercial, HELD.
            Hypotheses: XNGUSD, XTIUSD (USOIL) and XBRUSD (UKOIL) on the HDD anomaly, the HDD/CDD
            revision and the model disagreement.
  jobs      Indeed Hiring Lab job-postings index (CC BY 4.0) per country and per sector, and BLS
            JOLTS openings (public domain, BLS_API_KEY). USAJOBS has no permitting clause on its
            own terms pages and Adzuna's terms forbid aggregation for research: both HELD (their
            key state is still reported; ADZUNA_APP_ID is not held, so that route also reads
            NEEDS_KEY). Hypotheses on the country indices and currencies.
  payments  NO NEW FETCHER: the card/payment series alt_proxies already collects (Opportunity
            Insights card spend, BCB Pix/card/boleto) are re-expressed per country as one
            payments series; every payment source without a verbatim permitting quote, or refused
            by alt_proxies (NPCI, BKM, Cielo, MCT holidays, PayInc BETI, BOK ECOS), is HELD.
  ndvi      Numeric NDVI (MOD13Q1 250 m 16-day composites) from the ORNL DAAC TESViS web service,
            keyless, averaged over a 3x3 km window per crop region and stamped at the composite's
            own processing date; the anomaly is against the same composite window in prior years.
            Mapped to the soft/grain CFDs (CORN, WHEAT, SOYBEAN, COFARA, COFROB, USCOCOA, UKCOCOA,
            SUGAR, SUGARRAW, COTTON, OJ) with a negative prior (greener supply, lower price).

  satellite_facility / shipping_ais / customs / attention / spending -- a factory row ONLY where a
            parser already exists in alt_proxies; nothing is fetched here for them. The row reports
            each source's state (from alt_proxies' own store) and the factory's terms verdict;
            minting for them stays with `alt_proxies.direct_cells`, which donates only gain-tested
            cells. Electricity, procurement, supply-chain exhaust and search/app attention have no
            parser on the base and get no row (listed under `no_parser_domains`).

LIVE YIELD IS UNMEASURED UNTIL THE TRADING BOX RUNS THIS. The parsers were written against small
synthetic fixtures shaped like each publisher's file (tests/fixtures/domain_factories); the
authoring container cannot reach these hosts.

    python desks/mt5/research/domain_factories.py --once [--budget-s 240]
    python desks/mt5/research/domain_factories.py --once \
        --fixtures tests/fixtures/domain_factories --no-donate
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402

ORGAN = "domain_factories"
FETCHED, HELD, NEEDS_KEY, UNMEASURED = "FETCHED", "HELD", "NEEDS_KEY", "UNMEASURED"
STATUSES = (FETCHED, HELD, NEEDS_KEY, UNMEASURED)
UA = "quant-desk-domain-factories/1.0 (public statistics research; internal use)"
TIMEOUT = 30.0
MAX_BYTES = 24 * 1024 * 1024
#: PIT points a lake series needs before a hypothesis on it is minted. The family refuses to
#: emit below 30 observations; minting earlier would only queue an unjudgeable cell.
MIN_POINTS = 30
#: A minted hypothesis is re-donated no sooner than this; in between it is already in the intake.
REMINT_DAYS = 30
TERMS_CHECKED = "2026-10-07"


# ============================================================================ paths
@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def base(self) -> Path:
        return self.desk / "data" / "domain_factories"

    @property
    def state(self) -> Path:
        return self.base / "state.json"

    @property
    def obs_dir(self) -> Path:
        return self.base / "obs"

    @property
    def forecast_vintages(self) -> Path:
        return self.base / "weather_forecast_vintages.json"

    @property
    def cpc_store(self) -> Path:
        return self.base / "cpc_degree_days.json"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "DOMAIN_FACTORIES.json"

    @property
    def alt(self) -> A.Paths:
        """alt_proxies' own paths on the same desk: its lake, axes and vintage stores."""
        return A.Paths(self.desk)


DEFAULT_PATHS = Paths(DESK)


# ============================================================================ terms (fail closed)
@dataclass(frozen=True)
class Terms:
    verdict: str            # PERMITS | PROHIBITS | NONCOMMERCIAL | UNREAD
    terms_url: str
    terms_quote: str
    note: str = ""
    checked_at: str = TERMS_CHECKED

    @property
    def permits(self) -> bool:
        return self.verdict == "PERMITS" and bool(self.terms_quote.strip())


_NWS_QUOTE = ("The information on National Weather Service (NWS) Web pages are in the "
              "public domain, unless specifically noted otherwise, and may be used without "
              "charge for any lawful purpose so long as you do not: 1) claim it is your own "
              "(e.g., by claiming copyright for NWS information -- see below), 2) use it in a "
              "manner that implies an endorsement or affiliation with NOAA/NWS, or 3) modify its "
              "content and then present it as official government material.")

#: Every source this organ names, with the clause read from its OWN terms page. Only a PERMITS
#: row with a quote is ever fetched. Quotes are verbatim as read on TERMS_CHECKED.
TERMS_RECORDS: dict[str, Terms] = {
    # ---- weather
    "cpc_degree_days": Terms(
        "PERMITS", "https://www.weather.gov/disclaimer", _NWS_QUOTE,
        note=("CPC is an NWS/NCEP centre; its own disclaimer URLs (cpc.ncep.noaa.gov/disclaimer"
              ".php, /climate/disclaimer.shtml) returned 404, so the NWS statement that governs "
              "NWS web servers is the record")),
    "nws_mex_mos": Terms(
        "PERMITS", "https://www.weather.gov/disclaimer",
        ("The information on National Weather Service Web servers and Web sites is in the public "
         "domain, unless specifically annotated otherwise, and may be used freely by the "
         "public."),
        note="tgftp.nws.noaa.gov is an NWS web server; GFSX MOS bulletins are NWS products"),
    "nws_api_ndfd": Terms(
        "PERMITS", "https://www.weather.gov/documentation/services-web-api",
        ("All of the information presented via the API is intended to be open data, free to use "
         "for any purpose."),
        note="the API requires an identifying User-Agent; this organ sends one"),
    "ecmwf_open_data": Terms(
        "PERMITS", "https://www.ecmwf.int/en/forecasts/datasets/open-data",
        "The data may be redistributed and used commercially, subject to appropriate attribution.",
        note="CC-BY-4.0; GRIB2 only, and no GRIB decoder is installed on the base"),
    "open_meteo": Terms(
        "NONCOMMERCIAL", "https://open-meteo.com/en/terms",
        "You may only use the free API services for non-commercial purposes.",
        note="this desk is commercial and holds no paid subscription: HELD"),
    # ---- jobs
    "indeed_hiring_lab": Terms(
        "PERMITS", "https://github.com/hiring-lab/job_postings_tracker",
        ("The data generated by Indeed Hiring Lab are available under the Creative Commons "
         "Attribution 4.0 International License. / The data and files that we have generated are "
         "freely available for public use, as long as Indeed Hiring Lab is cited as a source.")),
    "bls_jolts": Terms(
        "PERMITS", "https://www.bls.gov/opub/copyright-information.htm",
        ("You are free to use our public domain material without specific permission, although "
         "we do ask that you cite the Bureau of Labor Statistics as the source.")),
    "usajobs": Terms(
        "UNREAD", "https://developer.usajobs.gov/guides/terms-of-use", "",
        note=("no permitting clause found: the developer Terms of Use page carries only the "
              "federal system-use warning ('Unauthorized user attempts or acts to ... (4) accrue "
              "resources for unauthorized use or (5) otherwise misuse this system are strictly "
              "prohibited.'), and the usajobshelp terms and conditions say nothing on reuse")),
    "adzuna": Terms(
        "PROHIBITS", "https://developer.adzuna.com/docs/terms_of_service",
        ("It may not be used in its original format or in aggregation (including but not limited "
         "to vacancy counts, average salaries etc) to deliver any ongoing work or research, apart "
         "from the purpose stated prior, without written consent."),
        note="commercial use is a 14-day validation trial only"),
    # ---- ndvi
    "ornl_modis_ndvi": Terms(
        "PERMITS", "https://daac.ornl.gov/about/",
        ("Data hosted by the ORNL DAAC is openly shared, without restriction, in accordance with "
         "NASA's Earth Science program Data and Information Policy."),
        note=("MOD13Q1 is an LP DAAC product: 'All LP DAAC current data and products acquired "
              "through the LP DAAC have no restrictions on reuse, sale, or redistribution.' "
              "(lpdaac.usgs.gov/data/data-citation-and-policies/)")),
    # ---- payments (sources alt_proxies fetches; the factory re-reads its store)
    "us_oi_card_spend": Terms(
        "PERMITS", "https://github.com/OpportunityInsights/EconomicTracker",
        "Anyone is welcome to use this data",
        note="quote as recorded by alt_proxies.TERMS (2026-09-30)"),
    "br_bcb_payments": Terms(
        "PERMITS", "https://dadosabertos.bcb.gov.br/dataset/estatisticas-meios-pagamentos",
        "Open Data Commons Open Database License (ODbL)",
        note="the dataset page's licence field; the dataset is marked as meeting the Open "
             "Definition"),
    # ---- alt_proxies-backed domains with a verbatim quote on record
    "cn_firms_industrial": Terms(
        "PERMITS", "https://www.earthdata.nasa.gov/learn/use-data/data-use-policy",
        ("Unless the content is marked with a use restriction or license, data provided from a "
         "NASA led mission are licensed as Creative Commons Zero (CC0). There are no restrictions "
         "on the use of these data.")),
    "imf_portwatch_ports": Terms(
        "PERMITS", "https://www.imf.org/external/terms.htm",
        ("Users may download, extract, copy, create derivative works, publish, distribute, and "
         "sell Data obtained from IMF Sites, including for commercial purposes")),
    "imf_portwatch_chokepoints": Terms(
        "PERMITS", "https://www.imf.org/external/terms.htm",
        ("Users may download, extract, copy, create derivative works, publish, distribute, and "
         "sell Data obtained from IMF Sites, including for commercial purposes")),
    "gdelt_events_country": Terms(
        "PERMITS", "https://www.gdeltproject.org/about.html",
        ("all datasets released by the GDELT Project are available for unlimited and unrestricted "
         "use for any academic, commercial, or governmental use")),
}


def _alt_terms(sid: str) -> Terms:
    """The factory's record for an alt_proxies source: its own row above, else a verbatim quote
    alt_proxies holds in TERMS_EVIDENCE, else UNREAD (HELD here)."""
    if sid in TERMS_RECORDS:
        return TERMS_RECORDS[sid]
    ev = A.TERMS_EVIDENCE.get(sid) or {}
    quote = str(ev.get("terms_quote") or "")
    src = A.BY_ID.get(sid)
    if src is not None and src.terms == "confirmed" and quote and not quote.startswith("("):
        return Terms("PERMITS", str(ev.get("terms_url") or ""), quote,
                     note="quote as recorded by alt_proxies.TERMS_EVIDENCE",
                     checked_at=str(ev.get("checked_at") or ""))
    why = A.TERMS.get(sid, ("", ""))[1]
    verdict = "PROHIBITS" if src is not None and src.terms == "refused" else "UNREAD"
    return Terms(verdict, str(ev.get("terms_url") or ""), "",
                 note=(f"alt_proxies terms {src.terms if src else 'unknown'}: {why}; "
                       "no verbatim permitting clause on record, so this factory holds it"))


class HeldSource(RuntimeError):
    """A request was built for a source whose terms do not permit it. Never raised in a correct
    pass: the factories build no request for a HELD source. This is the backstop."""


def _http_get(url: str, headers: Mapping[str, str]) -> bytes:
    from libs.data import terms_fence
    terms_fence.check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, **dict(headers)})
    with terms_fence.guarded_urlopen(req, timeout=TIMEOUT, context=A._tls()) as r:
        body: bytes = r.read(MAX_BYTES)
        return body


Getter = Callable[["Req"], bytes]


@dataclass(frozen=True)
class Req:
    source: str
    url: str
    fixture: str
    headers: tuple[tuple[str, str], ...] = ()
    key_env: str | None = None


def guarded_get(req: Req, getter: Getter) -> bytes:
    t = TERMS_RECORDS.get(req.source)
    if t is None or not t.permits:
        raise HeldSource(f"{req.source}: terms {t.verdict if t else 'absent'}; never fetched")
    return getter(req)


def live_getter(req: Req) -> bytes:
    return _http_get(req.url, dict(req.headers))


def fixture_getter(root: Path) -> Getter:
    def get(req: Req) -> bytes:
        p = root / req.fixture
        if not p.exists():
            raise FileNotFoundError(f"no fixture {req.fixture}")
        return p.read_bytes()
    return get


def _redact(text: str, key_env: str | None) -> str:
    key = os.environ.get(key_env or "", "") if key_env else ""
    return text.replace(key, f"<{key_env}>") if key else text


def key_state(envs: Iterable[str], environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    missing = [e for e in envs if not env.get(e)]
    return f"NEEDS_KEY:{','.join(missing)}" if missing else "PRESENT"


@dataclass
class SourceRun:
    """One source's pass: status, why, and what it fetched. `status` is one of STATUSES."""
    id: str
    status: str = UNMEASURED
    why: str = ""
    requests: int = 0
    ok: int = 0
    errors: list[str] = field(default_factory=list)
    key_state: str = "NONE_REQUIRED"
    parsed: int = 0

    def as_dict(self) -> dict[str, Any]:
        t = TERMS_RECORDS.get(self.id) or _alt_terms(self.id)
        return {"status": self.status, "why": self.why, "requests": self.requests,
                "ok": self.ok, "errors": self.errors[:6], "key_state": self.key_state,
                "parsed": self.parsed,
                "terms": {"verdict": t.verdict, "url": t.terms_url, "quote": t.terms_quote,
                          "note": t.note, "checked_at": t.checked_at}}


def preflight(sid: str, key_envs: tuple[str, ...] = (), *, parser: bool = True,
              parser_note: str = "", environ: Mapping[str, str] | None = None) -> SourceRun:
    """The status a source has BEFORE any request: HELD (terms), NEEDS_KEY, or UNMEASURED with
    no parser. A source that passes stays UNMEASURED until a request returns parseable data."""
    run = SourceRun(sid)
    t = TERMS_RECORDS.get(sid)
    if key_envs:
        run.key_state = key_state(key_envs, environ)
    if t is None or not t.permits:
        run.status = HELD
        run.why = (f"terms {t.verdict if t else 'UNREAD'}: never fetched"
                   + (f" ({t.note})" if t and t.note else ""))
        return run
    if run.key_state.startswith("NEEDS_KEY"):
        run.status = NEEDS_KEY
        run.why = f"{run.key_state}: env var absent, nothing requested"
        return run
    if not parser:
        run.status = UNMEASURED
        run.why = f"no parser on the base: {parser_note}; never fetched"
        return run
    run.why = "not yet requested this pass"
    return run


def runnable(run: SourceRun) -> bool:
    return run.status == UNMEASURED and run.why == "not yet requested this pass"


def _fetch(run: SourceRun, req: Req, getter: Getter, deadline: float) -> bytes | None:
    if time.monotonic() > deadline:
        run.errors.append("budget exhausted before request")
        return None
    run.requests += 1
    try:
        body = guarded_get(req, getter)
    except HeldSource:
        raise
    except Exception as exc:
        run.errors.append(_redact(f"{type(exc).__name__}: {str(exc)[:160]}", req.key_env))
        return None
    run.ok += 1
    return body


def _close(run: SourceRun, parsed: int) -> None:
    """FETCHED only when a request came back AND parsed to something; otherwise UNMEASURED with
    the errors that say why. A run that requested nothing keeps its preflight status."""
    run.parsed += parsed
    if run.status != UNMEASURED:
        return
    if run.ok and run.parsed:
        run.status, run.why = FETCHED, f"{run.ok}/{run.requests} requests ok, {run.parsed} parsed"
    elif run.requests:
        run.why = (f"{run.ok}/{run.requests} requests ok, nothing parsed: live yield UNMEASURED"
                   + (f" ({run.errors[0]})" if run.errors else ""))
    else:
        run.why = "no request due this pass (cursor/refresh): UNMEASURED this pass"


# ============================================================================ shared store helpers
def _read_json(p: Path, default: Any) -> Any:
    return A._read_json(p, default)


def _atomic(p: Path, doc: Any) -> None:
    A._atomic(p, doc)


def store_source(sid: str, name: str, *, transform: str = "given",
                 rule: Callable[[date], datetime] | None = None, cadence: str = "daily",
                 region: str = "US", mechanism: str = "", payer: str = "", constraint: str = "",
                 licence: str = "", failure: str = "", signal_series: tuple[str, ...] = ()
                 ) -> A.Source:
    """An alt_proxies Source used only as the key of a vintage store and a lake file: the PIT
    machinery (merge_vintages / build_points / write_lake_series) is the one alt_proxies owns."""
    return A.Source(
        id=sid, name=name, url="factory:" + sid, region=region, language="en", cadence=cadence,
        parse=None, rule=rule or A._lag_rule(1, 0), transform=transform, instruments={},
        signal_series=signal_series, mechanism=mechanism, payer=payer, constraint=constraint,
        licence=licence, source_culture=f"{region}/en", participant_structure=("physical_flow",),
        failure_mode_hypothesis=failure, crowding_prior="medium", terms="confirmed")


def merge_into(paths: Paths, src: A.Source, obs: list[A.Obs], now: datetime) -> dict[str, int]:
    p = paths.obs_dir / f"{src.id}.json"
    store = _read_json(p, {})
    res = A.merge_vintages(store, src, obs, now)
    _atomic(p, store)
    return res


def publish(paths: Paths, src: A.Source, now: datetime, *, dry_run: bool
            ) -> dict[str, list[dict[str, Any]]]:
    """Points per series from the store; lake CSVs and the axis doc unless dry_run."""
    store = _read_json(paths.obs_dir / f"{src.id}.json", {})
    pts = A.build_points(src, store) if store else {}
    if pts and not dry_run:
        A.write_lake_series(paths.alt, src, pts)
        _atomic(paths.alt.axes / f"alt_{src.id}.json", A.axis_doc(src, pts, now))
    return pts


# ============================================================================ degree-day math
#: NOAA's convention: base 65 F. The European convention is 18 C (EUROSTAT uses 15.5/18 C).
BASE_F = 65.0
BASE_C = 18.0


def daily_mean(tmin: float, tmax: float) -> float:
    return (float(tmin) + float(tmax)) / 2.0


def hdd(tmean: float, base: float = BASE_F) -> float:
    return max(0.0, base - float(tmean))


def cdd(tmean: float, base: float = BASE_F) -> float:
    return max(0.0, float(tmean) - base)


def hdd_c(tmean_c: float, base: float = BASE_C) -> float:
    return hdd(tmean_c, base)


def cdd_c(tmean_c: float, base: float = BASE_C) -> float:
    return cdd(tmean_c, base)


def degree_days(tmin: float, tmax: float, kind: str, base: float = BASE_F) -> float:
    m = daily_mean(tmin, tmax)
    return hdd(m, base) if kind == "hdd" else cdd(m, base)


# ============================================================================ weather: geography
#: CPC numbers the Census divisions 1..9 in this order.
DIVISIONS: dict[int, str] = {1: "New England", 2: "Middle Atlantic", 3: "East North Central",
                             4: "West North Central", 5: "South Atlantic",
                             6: "East South Central", 7: "West South Central", 8: "Mountain",
                             9: "Pacific"}
#: 2020 Census resident population share by division (approximate, sums to 1 after
#: normalisation). The CONUS forecast aggregate weights divisions by these; the observed CONUS
#: series is CPC's own when its file carries one.
DIVISION_WEIGHTS: dict[int, float] = {1: 0.0455, 2: 0.1283, 3: 0.1430, 4: 0.0652, 5: 0.1995,
                                      6: 0.0585, 7: 0.1237, 8: 0.0751, 9: 0.1605}
#: Forecast stations: ICAO -> (division, lat, lon). Large population centres per division.
STATIONS: dict[str, tuple[int, float, float]] = {
    "KBOS": (1, 42.36, -71.01), "KBDL": (1, 41.94, -72.68),
    "KLGA": (2, 40.78, -73.87), "KPHL": (2, 39.87, -75.24), "KPIT": (2, 40.49, -80.23),
    "KORD": (3, 41.98, -87.90), "KDTW": (3, 42.21, -83.35), "KCMH": (3, 39.99, -82.88),
    "KMSP": (4, 44.88, -93.22), "KSTL": (4, 38.75, -90.37), "KMCI": (4, 39.30, -94.71),
    "KATL": (5, 33.64, -84.43), "KDCA": (5, 38.85, -77.04), "KMIA": (5, 25.79, -80.29),
    "KCLT": (5, 35.21, -80.94),
    "KBNA": (6, 36.12, -86.68), "KMEM": (6, 35.04, -89.98),
    "KDFW": (7, 32.90, -97.04), "KIAH": (7, 29.98, -95.34),
    "KDEN": (8, 39.86, -104.67), "KPHX": (8, 33.43, -112.01),
    "KLAX": (9, 33.94, -118.41), "KSEA": (9, 47.45, -122.31), "KSFO": (9, 37.62, -122.37)}
#: A CONUS aggregate needs at least this many of the nine divisions; fewer is UNMEASURED.
MIN_DIVISIONS = 6
MEX_BULLETINS = ("feus21.kwno.mex.ne1", "feus22.kwno.mex.se1", "feus23.kwno.mex.nc1",
                 "feus24.kwno.mex.sc1", "feus25.kwno.mex.rm1", "feus26.kwno.mex.wc0")
MEX_URL = "https://tgftp.nws.noaa.gov/data/raw/fe/{name}.txt"
CPC_URL = ("https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_data/{year}/"
           "Population.{kind}.txt")
NWS_POINTS_URL = "https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
NWS_FORECAST_URL = "https://api.weather.gov/gridpoints/{office}/{x},{y}/forecast"
#: Observed history depth (years) the anomaly's normal is drawn from, and its minimum.
CPC_YEARS = 10
NORMAL_MIN_YEARS = 3
#: Observed and forecast-derived obs are emitted for this many trailing days.
OBS_EMIT_DAYS = 730
#: A "previous" vintage for the revision is the latest issued at least this long before the latest.
REVISION_GAP_H = 20
#: Two models' runs count as contemporaneous for the disagreement within this window.
DISAGREE_WINDOW_H = 24
#: Raw forecast vintages are kept while their target date is within this many days.
VINTAGE_KEEP_D = 45


# ============================================================================ weather: parsers
_MEX_HEAD = re.compile(r"^\s*([A-Z0-9]{3,5})\s+GFSX MOS GUIDANCE\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+"
                       r"(\d{2})(\d{2}) UTC", re.M)
_MEX_DAY = re.compile(r"([A-Z]{3})\s+(\d{1,2})")


def _target(issued: date, dom: int) -> date | None:
    """The calendar date of a day-of-month printed in a bulletin issued on `issued` (always on or
    after the issue date, rolling into the next month)."""
    for k in range(0, 12):
        d = issued + timedelta(days=k)
        if d.day == dom:
            return d
    return None


def parse_mex(body: bytes) -> list[dict[str, Any]]:
    """GFSX MOS bulletins: per station, the issue time and the (min, max) of each of the seven
    forecast days. The N/X row (12Z) pairs night min then day max; X/N (00Z) the reverse. 999 is
    missing. The eighth column (with climatology) is ignored."""
    text = body.decode("latin-1", errors="replace")
    out: list[dict[str, Any]] = []
    heads = list(_MEX_HEAD.finditer(text))
    for i, h in enumerate(heads):
        block = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        station = h.group(1)
        try:
            issued = datetime(int(h.group(4)), int(h.group(2)), int(h.group(3)),
                              int(h.group(5)), int(h.group(6)), tzinfo=UTC)
        except ValueError:
            continue
        lines = block.splitlines()
        days_line = next((ln for ln in lines if _MEX_DAY.search(ln) and "|" in ln
                          and not ln.lstrip().startswith(("FHR", "N/X", "X/N"))), None)
        tline = next((ln for ln in lines if ln.lstrip().startswith(("N/X", "X/N"))), None)
        if days_line is None or tline is None:
            continue
        days = [int(m.group(2)) for m in _MEX_DAY.finditer(days_line)][:7]
        order_nx = tline.lstrip().startswith("N/X")
        segs = tline.lstrip()[3:].split("|")
        for j, seg in enumerate(segs[:7]):
            if j >= len(days):
                break
            ints = [int(v) for v in re.findall(r"-?\d+", seg)]
            if len(ints) < 2 or 999 in ints[:2]:
                continue
            a, b = ints[0], ints[1]
            tmin, tmax = (a, b) if order_nx else (b, a)
            tgt = _target(issued.date(), days[j])
            if tgt is None:
                continue
            out.append({"model": "gfs_mos", "station": station,
                        "issued_at": issued.isoformat(timespec="seconds"),
                        "target": tgt.isoformat(), "tmin": float(tmin), "tmax": float(tmax)})
    return out


def parse_cpc(body: bytes) -> dict[str, dict[str, float]]:
    """CPC daily degree-day file: 'Region|YYYYMMDD|...' then one pipe row per region.
    Returns {region_label: {YYYYMMDD: value}}; non-numeric cells (missing) are skipped."""
    text = body.decode("utf-8", errors="replace")
    dates: list[str] = []
    out: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2:
            continue
        if cells[0].lower() == "region":
            dates = [c for c in cells[1:] if re.fullmatch(r"\d{8}", c)]
            continue
        if not dates or not cells[0]:
            continue
        row: dict[str, float] = {}
        for d, c in zip(dates, cells[1:], strict=False):
            try:
                v = float(c)
            except ValueError:
                continue
            if v >= 0 and math.isfinite(v):
                row[d] = v
        if row:
            out[cells[0].upper()] = row
    return out


def parse_nws_points(body: bytes) -> dict[str, Any] | None:
    try:
        p = json.loads(body.decode("utf-8"))["properties"]
        return {"office": str(p["gridId"]), "x": int(p["gridX"]), "y": int(p["gridY"])}
    except (ValueError, KeyError, TypeError):
        return None


def parse_nws_forecast(body: bytes, station: str) -> list[dict[str, Any]]:
    """NWS gridpoint forecast (NDFD): per local date, the daytime period's temperature is the max
    and the night period starting that date the min (the X/N pairing MOS uses). The vintage is
    the forecast's own `generatedAt` (else `updateTime`)."""
    try:
        props = json.loads(body.decode("utf-8"))["properties"]
    except (ValueError, KeyError, TypeError):
        return []
    issued = A._t(props.get("generatedAt") or props.get("updateTime"))
    if issued is None:
        return []
    hi: dict[str, float] = {}
    lo: dict[str, float] = {}
    for per in props.get("periods") or []:
        try:
            d = str(per["startTime"])[:10]
            t = float(per["temperature"])
            unit = str(per.get("temperatureUnit") or "F").upper()
        except (KeyError, TypeError, ValueError):
            continue
        if unit == "C":
            t = t * 9.0 / 5.0 + 32.0
        (hi if per.get("isDaytime") else lo).setdefault(d, t)
    return [{"model": "nws_ndfd", "station": station,
             "issued_at": issued.astimezone(UTC).isoformat(timespec="seconds"),
             "target": d, "tmin": lo[d], "tmax": hi[d]} for d in sorted(hi) if d in lo]


# ============================================================================ weather: vintages
def vintage_key(r: Mapping[str, Any]) -> str:
    return f"{r['model']}|{r['station']}|{r['target']}|{r['issued_at']}"


def merge_forecasts(store: dict[str, Any], rows: Iterable[Mapping[str, Any]],
                    seen_at: datetime) -> int:
    """Append-only: a (model, station, target, issued) vintage is written once, with the instant
    this box first saw it. Nothing is overwritten; a re-issued run is a new key."""
    added = 0
    for r in rows:
        k = vintage_key(r)
        if k in store:
            continue
        store[k] = {"model": r["model"], "station": r["station"], "target": r["target"],
                    "issued_at": r["issued_at"], "tmin": r["tmin"], "tmax": r["tmax"],
                    "first_seen_at": seen_at.isoformat(timespec="seconds")}
        added += 1
    return added


def prune_forecasts(store: dict[str, Any], today: date) -> int:
    cut = (today - timedelta(days=VINTAGE_KEEP_D)).isoformat()
    old = [k for k, r in store.items() if str(r.get("target")) < cut]
    for k in old:
        del store[k]
    return len(old)


def _runs(store: Mapping[str, Any], model: str, now: datetime
          ) -> dict[str, dict[str, dict[str, Mapping[str, Any]]]]:
    """{station: {issued_at: {target: row}}} for one model, only vintages SEEN by `now`."""
    out: dict[str, dict[str, dict[str, Mapping[str, Any]]]] = {}
    for r in store.values():
        if r.get("model") != model:
            continue
        seen = A._t(r.get("first_seen_at"))
        if seen is None or seen > now:
            continue
        out.setdefault(str(r["station"]), {}).setdefault(str(r["issued_at"]), {})[
            str(r["target"])] = r
    return out


def _dd_run(run: Mapping[str, Mapping[str, Any]], kind: str) -> dict[str, float]:
    return {t: degree_days(r["tmin"], r["tmax"], kind) for t, r in run.items()}


def latest_runs(store: Mapping[str, Any], model: str, now: datetime, kind: str
                ) -> dict[str, tuple[str, dict[str, float]]]:
    """{station: (issued_at, {target: dd})} from each station's latest run seen by `now`."""
    out: dict[str, tuple[str, dict[str, float]]] = {}
    for st, runs in _runs(store, model, now).items():
        last = max(runs)
        out[st] = (last, _dd_run(runs[last], kind))
    return out


def revisions(store: Mapping[str, Any], model: str, now: datetime, kind: str
              ) -> dict[str, dict[str, float]]:
    """{station: {target: latest - previous}}: previous is the latest run issued at least
    REVISION_GAP_H before the latest ("today's forecast minus yesterday's"), same target date."""
    out: dict[str, dict[str, float]] = {}
    for st, runs in _runs(store, model, now).items():
        issued = sorted(runs)
        last = issued[-1]
        last_t = A._t(last)
        if last_t is None:
            continue
        prev = [i for i in issued[:-1]
                if (t := A._t(i)) is not None and t <= last_t - timedelta(hours=REVISION_GAP_H)]
        if not prev:
            continue
        a, b = _dd_run(runs[last], kind), _dd_run(runs[prev[-1]], kind)
        common = {t: a[t] - b[t] for t in a if t in b}
        if common:
            out[st] = common
    return out


def disagreement(store: Mapping[str, Any], now: datetime, kind: str,
                 model_a: str = "gfs_mos", model_b: str = "nws_ndfd"
                 ) -> dict[str, dict[str, float]]:
    """{station: {target: model_a - model_b}} from each model's latest run, only where the two
    runs were issued within DISAGREE_WINDOW_H of each other."""
    la, lb = latest_runs(store, model_a, now, kind), latest_runs(store, model_b, now, kind)
    out: dict[str, dict[str, float]] = {}
    for st, (ia, da) in la.items():
        if st not in lb:
            continue
        ib, db = lb[st]
        ta, tb = A._t(ia), A._t(ib)
        if ta is None or tb is None or abs((ta - tb).total_seconds()) > DISAGREE_WINDOW_H * 3600:
            continue
        common = {t: da[t] - db[t] for t in da if t in db}
        if common:
            out[st] = common
    return out


def aggregate(per_station: Mapping[str, Mapping[str, float]], region: str
              ) -> dict[str, float]:
    """{target: value} for `region` ('conus' or 'div<n>'): mean over the division's stations;
    CONUS is the population-weighted mean over divisions present (>= MIN_DIVISIONS)."""
    by_div: dict[int, dict[str, list[float]]] = {}
    for st, vals in per_station.items():
        if st not in STATIONS:
            continue
        div = STATIONS[st][0]
        for t, v in vals.items():
            by_div.setdefault(div, {}).setdefault(t, []).append(float(v))
    if region.startswith("div"):
        d = by_div.get(int(region[3:]), {})
        return {t: sum(v) / len(v) for t, v in d.items()}
    targets = sorted({t for d in by_div.values() for t in d})
    out: dict[str, float] = {}
    for t in targets:
        parts = [(DIVISION_WEIGHTS[div], sum(d[t]) / len(d[t]))
                 for div, d in by_div.items() if t in d]
        if len(parts) < MIN_DIVISIONS:
            continue
        w = sum(p[0] for p in parts)
        out[t] = sum(p[0] * p[1] for p in parts) / w
    return out


def window_sum(per_target: Mapping[str, float], start: date, days: int, min_days: int
               ) -> float | None:
    keys = [(start + timedelta(days=k)).isoformat() for k in range(days)]
    vals = [per_target[k] for k in keys if k in per_target]
    return sum(vals) if len(vals) >= min_days else None


def forecast_metrics(store: Mapping[str, Any], now: datetime) -> dict[str, float]:
    """Today's forecast-derived values per region: the 7-day forecast HDD/CDD (GFS-MOS, NDFD
    when MOS is absent), the 6-day revision per model and the GFS-MOS minus NDFD disagreement."""
    out: dict[str, float] = {}
    start = now.date() + timedelta(days=1)
    regions = ("conus", *(f"div{n}" for n in DIVISIONS))
    for kind in ("hdd", "cdd"):
        lvl = {st: v for st, (_, v) in latest_runs(store, "gfs_mos", now, kind).items()}
        if not lvl:
            lvl = {st: v for st, (_, v) in latest_runs(store, "nws_ndfd", now, kind).items()}
        rev_m = revisions(store, "gfs_mos", now, kind)
        rev_n = revisions(store, "nws_ndfd", now, kind)
        dis = disagreement(store, now, kind)
        for reg in regions:
            for name, per, days, need in ((f"{kind}_fcst_wk", lvl, 7, 5),
                                          (f"{kind}_rev_wk", rev_m, 6, 3),
                                          (f"{kind}_rev_ndfd_wk", rev_n, 6, 3),
                                          (f"{kind}_dis_wk", dis, 6, 3)):
                v = window_sum(aggregate(per, reg), start, days, need)
                if v is not None:
                    out[f"{reg}_{name}"] = round(v, 4)
    return out


# ============================================================================ weather: observed
def _shift_year(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:                                   # 29 Feb -> 28 Feb
        return d.replace(year=d.year - years, day=28)


def anomaly7(series: Mapping[date, float], d: date, years: int = CPC_YEARS,
             min_years: int = NORMAL_MIN_YEARS) -> float | None:
    """Trailing 7-day sum at d minus the mean of the same 7-day window in prior years."""
    def s7(end: date) -> float | None:
        vals = [series.get(end - timedelta(days=k)) for k in range(7)]
        return sum(v for v in vals if v is not None) if all(v is not None for v in vals) else None
    cur = s7(d)
    if cur is None:
        return None
    hist = [v for y in range(1, years + 1) if (v := s7(_shift_year(d, y))) is not None]
    if len(hist) < min_years:
        return None
    return cur - sum(hist) / len(hist)


def cpc_conus(store: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """CPC's own CONUS row when its file carries one, else the population-weighted division mean
    (all nine divisions required -- an observed aggregate is never partial)."""
    for label in ("CONUS", "US", "USA"):
        if label in store:
            return dict(store[label])
    days = set.intersection(*[set(store.get(str(n), {})) for n in DIVISIONS]) if all(
        str(n) in store for n in DIVISIONS) else set()
    return {d: sum(DIVISION_WEIGHTS[n] * store[str(n)][d] for n in DIVISIONS)
            / sum(DIVISION_WEIGHTS.values()) for d in days}


def _dated(m: Mapping[str, float]) -> dict[date, float]:
    out: dict[date, float] = {}
    for k, v in m.items():
        try:
            out[date(int(k[:4]), int(k[4:6]), int(k[6:8]))] = float(v)
        except (ValueError, TypeError):
            continue
    return out


def observed_obs(cpc: Mapping[str, Mapping[str, Mapping[str, float]]], today: date,
                 normals_ready: bool) -> list[A.Obs]:
    """Daily observed HDD/CDD (CONUS) and the 7-day anomaly per region. The anomaly is emitted
    only once the history backfill is complete, so its first recorded value already has its full
    normal (a value computed on a partial normal would be the first vintage forever)."""
    out: list[A.Obs] = []
    lo = today - timedelta(days=OBS_EMIT_DAYS)
    for kind in ("hdd", "cdd"):
        by_region = cpc.get(kind) or {}
        regions: dict[str, dict[date, float]] = {
            f"div{n}": _dated(by_region[str(n)]) for n in DIVISIONS if str(n) in by_region}
        conus = _dated(cpc_conus(by_region))
        if conus:
            regions["conus"] = conus
            out.extend(A.Obs(f"conus_{kind}", d, v) for d, v in conus.items() if d >= lo)
        if not normals_ready:
            continue
        for reg, ser in regions.items():
            for d in ser:
                if d < lo:
                    continue
                a = anomaly7(ser, d)
                if a is not None:
                    out.append(A.Obs(f"{reg}_{kind}_anom7", d, round(a, 4)))
    return out


# ============================================================================ hypotheses
@dataclass(frozen=True)
class Hyp:
    store: str
    series: str
    signal: str
    symbol: str
    side: int
    mechanism: str
    falsifier: str


def _hyp_rows(paths: Paths, hyps: Iterable[Hyp], sources: Mapping[str, A.Source],
              points: Mapping[str, Mapping[str, list[dict[str, Any]]]], factory: str,
              state: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]],
                                                             list[dict[str, Any]]]:
    """(rows to donate, held-back with reason). A row is the EXACT_RECIPE shape the compiler
    admits: a registered family, explicit params and a declared symbol."""
    minted = state.setdefault("minted", {})
    rows: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for h in hyps:
        src = sources[h.store]
        lake = A.lake_file(src, h.series)
        cell = f"{h.symbol}.exogenous_conditioner.{lake}.{h.signal}"
        pts = [p for p in (points.get(h.store) or {}).get(h.series, [])
               if p.get(h.signal) is not None]
        if len(pts) < MIN_POINTS:
            held.append({"cell": cell, "why": f"UNMEASURED: {len(pts)} PIT points < {MIN_POINTS}"})
            continue
        if not A.may_mint(h.symbol):
            held.append({"cell": cell, "why": "two-lane order: not a hypothesis-lane instrument"})
            continue
        last = A._t(minted.get(cell))
        if last is not None and now - last < timedelta(days=REMINT_DAYS):
            held.append({"cell": cell, "why": f"already donated {minted[cell]}"})
            continue
        params = {"source": lake, "signal": h.signal, "transform": "level_z", "threshold": 1.0,
                  "side_when_high": int(h.side), "lag_hours": 24, "ttl_bars": A.HORIZON_BARS}
        backfill = sum(1 for p in pts if p.get("pit_quality") == "backfill") / len(pts)
        rows.append({
            "source": ORGAN, "kind": "hypothesis", "symbol": h.symbol, "symbols": [h.symbol],
            "family": "exogenous_conditioner", "params": params, "url": "", "cell": cell,
            "title": f"{factory}: {h.series}.{h.signal} -> {h.symbol} "
                     f"({'+' if h.side > 0 else '-'}, prior)"[:120],
            "available_time": str(pts[-1]["available_time"]),
            "event_time": str(pts[-1]["event_time"]),
            **A._meta(src),
            "mechanism": h.mechanism,
            "prior_sign": int(h.side),
            "falsifier": h.falsifier,
            "evidence": {"n_points": len(pts), "backfill_share": round(backfill, 3),
                         "first": pts[0]["d"], "last": pts[-1]["d"],
                         "tested_here": False,
                         "why": "a declared prior; the gauntlet judges it and charges the trial"},
            "provenance": {"organ": ORGAN, "factory": factory, "store": h.store,
                           "series": h.series, "lake_file": lake}})
    return rows, held


# ============================================================================ factory: weather
WEATHER_OBS = store_source(
    "dfw_weather_obs", "NOAA CPC population-weighted daily degree days (Census divisions)",
    rule=A._lag_rule(1, 18), cadence="daily",
    mechanism=("heating and cooling demand is the weather-sensitive part of US gas and distillate "
               "burn; a week colder than its normal draws storage before the EIA report shows it"),
    payer="gas and distillate holders positioned on the seasonal normal and the last storage print",
    constraint="storage is reported weekly and with a lag; the degree days are daily",
    licence="NOAA/NWS public domain", failure=("fails when the weather surprise was already in the "
                                               "forecast the market traded"))
WEATHER_FCST = store_source(
    "dfw_weather_fcst", "GFS-MOS and NWS NDFD degree-day forecasts, revisions and disagreement",
    rule=A._lag_rule(0, 0), cadence="daily",
    mechanism=("gas prices move on the CHANGE in the week-ahead degree-day forecast; a revision "
               "colder (or hotter in summer) is demand the curve has not priced, and a model "
               "disagreement is the revision the slower model has yet to make"),
    payer="positions sized on yesterday's forecast", constraint=("forecast runs arrive twice a "
                                                                 "day; positions adjust slower"),
    licence="NOAA/NWS public domain", failure="fails when the revision lands in a shoulder season")

WEATHER_HYPS: tuple[Hyp, ...] = (
    *(Hyp("dfw_weather_obs", "conus_hdd_anom7", "value", s, 1,
          "a colder-than-normal week draws heating fuel faster than the seasonal path priced",
          f"z of CONUS 7-day HDD anomaly no longer leads {s} returns over the next 120 H1 bars")
      for s in ("XNGUSD", "XTIUSD", "XBRUSD")),
    Hyp("dfw_weather_obs", "conus_cdd_anom7", "value", "XNGUSD", 1,
        "a hotter-than-normal week lifts power burn of gas",
        "z of CONUS 7-day CDD anomaly no longer leads XNGUSD returns"),
    *(Hyp("dfw_weather_fcst", "conus_hdd_rev_wk", "value", s, 1,
          "an upward revision of week-ahead HDD is demand the curve has not priced",
          f"z of the GFS-MOS week-ahead HDD revision no longer leads {s} returns")
      for s in ("XNGUSD", "XTIUSD", "XBRUSD")),
    Hyp("dfw_weather_fcst", "conus_cdd_rev_wk", "value", "XNGUSD", 1,
        "an upward revision of week-ahead CDD is power-burn demand not yet priced",
        "z of the GFS-MOS week-ahead CDD revision no longer leads XNGUSD returns"),
    Hyp("dfw_weather_fcst", "conus_hdd_dis_wk", "value", "XNGUSD", 1,
        "GFS colder than the NDFD blend is a revision the blend has yet to make",
        "z of GFS-MOS minus NDFD week-ahead HDD no longer leads XNGUSD returns"),
)


def run_weather(paths: Paths, state: dict[str, Any], now: datetime, getter: Getter,
                deadline: float, *, dry_run: bool) -> dict[str, Any]:
    st = state.setdefault("weather", {})
    runs = {sid: preflight(sid) for sid in ("cpc_degree_days", "nws_mex_mos", "nws_api_ndfd")}
    runs["ecmwf_open_data"] = preflight(
        "ecmwf_open_data", parser=False,
        parser_note="ECMWF open data is GRIB2 and no GRIB decoder (eccodes/cfgrib) is installed "
                    "on the base, so the Europe HDD/CDD (base 18 C) region is UNMEASURED")
    runs["open_meteo"] = preflight("open_meteo")

    # -- observed: CPC, current year each pass (6 h refresh), one back-year per pass
    cpc = _read_json(paths.cpc_store, {"hdd": {}, "cdd": {}})
    cr = runs["cpc_degree_days"]
    if runnable(cr):
        years: list[int] = []
        last = A._t(st.get("cpc_current_at"))
        if last is None or now - last >= timedelta(hours=6):
            years.append(now.year)
        back = int(st.get("cpc_back_year") or now.year)
        if back > now.year - CPC_YEARS:
            years.append(back - 1)
        parsed = 0
        for y in years:
            got_year = True
            for kind, label in (("hdd", "Heating"), ("cdd", "Cooling")):
                body = _fetch(cr, Req("cpc_degree_days", CPC_URL.format(year=y, kind=label),
                                      f"cpc_{y}_{label}.txt"), getter, deadline)
                table = parse_cpc(body) if body else {}
                if not table:
                    got_year = False
                    continue
                for reg, vals in table.items():
                    cpc.setdefault(kind, {}).setdefault(reg, {}).update(vals)
                    parsed += len(vals)
            if got_year and y == now.year:
                st["cpc_current_at"] = now.isoformat(timespec="seconds")
            elif got_year:
                st["cpc_back_year"] = y
        _close(cr, parsed)
        if not dry_run:
            _atomic(paths.cpc_store, cpc)
    normals_ready = int(st.get("cpc_back_year") or now.year) <= now.year - CPC_YEARS
    obs = observed_obs(cpc, now.date(), normals_ready)
    merged_obs = merge_into(paths, WEATHER_OBS, obs, now) if obs and not dry_run else {}

    # -- forecasts: every vintage kept
    vint = _read_json(paths.forecast_vintages, {})
    mos = runs["nws_mex_mos"]
    if runnable(mos):
        rows_m: list[dict[str, Any]] = []
        for name in MEX_BULLETINS:
            body = _fetch(mos, Req("nws_mex_mos", MEX_URL.format(name=name), f"{name}.txt"),
                          getter, deadline)
            if body:
                rows_m.extend(r for r in parse_mex(body) if r["station"] in STATIONS)
        merge_forecasts(vint, rows_m, now)
        _close(mos, len(rows_m))
    ndfd = runs["nws_api_ndfd"]
    if runnable(ndfd):
        grids = st.setdefault("nws_grid", {})
        rows_n: list[dict[str, Any]] = []
        hdr = (("Accept", "application/geo+json"),)
        for icao, (_, lat, lon) in STATIONS.items():
            if icao not in grids:
                body = _fetch(ndfd, Req("nws_api_ndfd", NWS_POINTS_URL.format(lat=lat, lon=lon),
                                        f"nws_points_{icao}.json", hdr), getter, deadline)
                g = parse_nws_points(body) if body else None
                if g is None:
                    continue
                grids[icao] = g
            g = grids[icao]
            body = _fetch(ndfd, Req("nws_api_ndfd", NWS_FORECAST_URL.format(**g),
                                    f"nws_forecast_{icao}.json", hdr), getter, deadline)
            if body:
                rows_n.extend(parse_nws_forecast(body, icao))
        merge_forecasts(vint, rows_n, now)
        _close(ndfd, len(rows_n))
    pruned = prune_forecasts(vint, now.date())
    if not dry_run:
        _atomic(paths.forecast_vintages, vint)
    metrics = forecast_metrics(vint, now)
    fobs = [A.Obs(k, now.date(), v, published_at=now) for k, v in sorted(metrics.items())]
    merged_f = merge_into(paths, WEATHER_FCST, fobs, now) if fobs and not dry_run else {}

    points = {s.id: publish(paths, s, now, dry_run=dry_run) for s in (WEATHER_OBS, WEATHER_FCST)}
    rows, held = _hyp_rows(paths, WEATHER_HYPS, {s.id: s for s in (WEATHER_OBS, WEATHER_FCST)},
                           points, "weather", state, now)
    return {"sources": {k: v.as_dict() for k, v in runs.items()},
            "regions": {"us": "conus + Census divisions 1-9 (observed and forecast)",
                        "europe": "UNMEASURED: " + runs["ecmwf_open_data"].why},
            "base": {"F": BASE_F, "C": BASE_C},
            "forecast_vintages": {"rows": len(vint), "pruned": pruned,
                                  "models": sorted({str(r.get("model")) for r in vint.values()})},
            "today": metrics, "normals_ready": normals_ready,
            "merge": {"observed": merged_obs, "forecast": merged_f},
            "series": {sid: {k: len(v) for k, v in sorted(p.items())} for sid, p in points.items()},
            "_rows": rows, "held_back": held}


# ============================================================================ factory: jobs
INDEED_COUNTRIES = ("US", "GB", "CA", "DE", "FR", "AU", "ES", "IT", "NL", "IE")
#: Sector files for the countries whose currency or index the desk trades most.
INDEED_SECTOR_COUNTRIES = ("US", "GB", "CA", "DE", "AU")
INDEED_BASE = "https://raw.githubusercontent.com/hiring-lab/job_postings_tracker/master/{cc}/"
INDEED_AGG = INDEED_BASE + "aggregate_job_postings_{cc}.csv"
INDEED_SECTOR = INDEED_BASE + "job_postings_by_sector_{cc}.csv"
#: Days of daily aggregate history kept, and of weekly (Friday) sector history.
INDEED_KEEP_D = 3 * 365
SECTOR_KEEP_D = 2 * 365
#: A point dated within this many days of the fetch is stamped at the fetch (it is new); older
#: rows are history, stamped by the release rule and flagged backfill by build_points.
FRESH_D = 14
BLS_URL = ("https://api.bls.gov/publicAPI/v2/timeseries/data/{sid}?registrationkey={key}"
           "&startyear={y0}&endyear={y1}")
JOLTS_SERIES: dict[str, str] = {
    "JTS000000000000000JOL": "us_openings_total",
    "JTS100000000000000JOL": "us_openings_private",
    "JTS230000000000000JOL": "us_openings_construction",
    "JTS300000000000000JOL": "us_openings_manufacturing",
    "JTS540099000000000JOL": "us_openings_prof_business",
    "JTS700000000000000JOL": "us_openings_leisure_hospitality",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:48]


def parse_indeed_aggregate(body: bytes, now: datetime) -> list[A.Obs]:
    text = body.decode("utf-8", errors="replace")
    lo = now.date() - timedelta(days=INDEED_KEEP_D)
    out: list[A.Obs] = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            d = date.fromisoformat(str(r["date"]))
            cc = str(r["jobcountry"]).upper()
            v = float(r["indeed_job_postings_index_SA"])
        except (KeyError, TypeError, ValueError):
            continue
        if d < lo or not math.isfinite(v):
            continue
        var = "new" if "new" in str(r.get("variable") or "").lower() else "total"
        out.append(A.Obs(f"{cc}_{var}_sa", d, v, published_at=_fresh(d, now)))
    return out


def parse_indeed_sector(body: bytes, now: datetime) -> list[A.Obs]:
    """Sector index, total postings only, sampled weekly (Fridays) to bound the store."""
    text = body.decode("utf-8", errors="replace")
    lo = now.date() - timedelta(days=SECTOR_KEEP_D)
    out: list[A.Obs] = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            d = date.fromisoformat(str(r["date"]))
            cc = str(r["jobcountry"]).upper()
            v = float(r["indeed_job_postings_index"])
            sector = _slug(str(r["display_name"]))
        except (KeyError, TypeError, ValueError):
            continue
        if (d < lo or d.weekday() != 4 or "new" in str(r.get("variable") or "").lower()
                or not sector or not math.isfinite(v)):
            continue
        out.append(A.Obs(f"{cc}_sector_{sector}", d, v, published_at=_fresh(d, now)))
    return out


def _fresh(d: date, now: datetime) -> datetime | None:
    return now if (now.date() - d).days <= FRESH_D else None


def parse_bls(body: bytes) -> list[A.Obs]:
    try:
        doc = json.loads(body.decode("utf-8"))
    except ValueError:
        return []
    if not isinstance(doc, dict) or doc.get("status") != "REQUEST_SUCCEEDED":
        return []
    out: list[A.Obs] = []
    for s in (doc.get("Results") or {}).get("series") or []:
        name = JOLTS_SERIES.get(str(s.get("seriesID")))
        if not name:
            continue
        for r in s.get("data") or []:
            per = str(r.get("period") or "")
            if not re.fullmatch(r"M(0[1-9]|1[0-2])", per):
                continue
            try:
                v = float(str(r["value"]).replace(",", ""))
                d = A._month_end(int(r["year"]), int(per[1:]))
            except (KeyError, TypeError, ValueError):
                continue
            out.append(A.Obs(name, d, v))
    return out


JOBS_INDEED = store_source(
    "dfj_indeed_postings", "Indeed Hiring Lab job-postings index (country)",
    rule=A._lag_rule(7, 0), transform="anomaly_daily", region="GLOBAL",
    mechanism=("new job postings are labour demand read daily, weeks before payrolls and "
               "unemployment claims; a country whose postings accelerate is a growth surprise "
               "for its index and its currency"),
    payer="index and FX positions waiting for the monthly labour-market prints",
    constraint="payrolls and JOLTS are monthly and revised; the postings index is daily",
    licence="CC BY 4.0 (Indeed Hiring Lab)",
    failure="fails when posting behaviour shifts (platform share) without hiring changing")
JOBS_SECTOR = store_source(
    "dfj_indeed_sector", "Indeed Hiring Lab job-postings index (country x sector, weekly)",
    rule=A._lag_rule(7, 0), transform="anomaly_monthly", region="GLOBAL", cadence="weekly",
    mechanism="sector postings say which part of the economy is hiring",
    payer="sector-tilted index holders", constraint="no official sector series is this fast",
    licence="CC BY 4.0 (Indeed Hiring Lab)", failure="sector labels change")
JOBS_JOLTS = store_source(
    "dfj_bls_jolts", "BLS JOLTS job openings (total and sectors)",
    rule=A._lag_rule(40, 14, weekday=True), transform="mom_monthly", cadence="monthly",
    mechanism="job openings are the demand side of the Fed's labour-market read",
    payer="rates and USD positions priced on the last openings print",
    constraint="the Fed reacts at meetings, not at the print", licence="BLS public domain",
    failure="fails when the JOLTS response rate collapses and revisions dominate")

_IDX = {"US": (("US500", 1), ("US30", 1)), "GB": (("GBPUSD", 1), ("UK100", 1)),
        "CA": (("USDCAD", -1), ("CA60", 1)), "DE": (("GER40", 1), ("EURUSD", 1)),
        "FR": (("FRA40", 1),), "AU": (("AUDUSD", 1), ("AUS200", 1)), "ES": (("E35", 1),),
        "NL": (("NETH25", 1),)}
JOBS_HYPS: tuple[Hyp, ...] = (
    *(Hyp("dfj_indeed_postings", f"{cc}_total_sa", "pace", sym, side,
          f"{cc} postings accelerating against their prior quarter is a growth surprise",
          f"z of {cc} postings pace no longer leads {sym} returns over the next 120 H1 bars")
      for cc, legs in _IDX.items() for sym, side in legs),
    Hyp("dfj_bls_jolts", "us_openings_total", "pace", "US500", 1,
        "rising US openings is labour demand ahead of payrolls",
        "z of the JOLTS openings month-on-month change no longer leads US500 returns"),
    Hyp("dfj_bls_jolts", "us_openings_total", "pace", "USDJPY", 1,
        "rising US openings keeps the Fed path higher than priced",
        "z of the JOLTS openings month-on-month change no longer leads USDJPY returns"),
)


def run_jobs(paths: Paths, state: dict[str, Any], now: datetime, getter: Getter,
             deadline: float, *, dry_run: bool) -> dict[str, Any]:
    st = state.setdefault("jobs", {})
    runs = {"indeed_hiring_lab": preflight("indeed_hiring_lab"),
            "bls_jolts": preflight("bls_jolts", ("BLS_API_KEY",)),
            "usajobs": preflight("usajobs", ("USAJOBS_API_KEY", "USAJOBS_USER_AGENT")),
            "adzuna": preflight("adzuna", ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"))}
    ind = runs["indeed_hiring_lab"]
    if runnable(ind):
        done = st.setdefault("indeed_at", {})
        agg: list[A.Obs] = []
        sec: list[A.Obs] = []
        for cc in INDEED_COUNTRIES:
            last = A._t(done.get(cc))
            if last is not None and now - last < timedelta(hours=12):
                continue
            body = _fetch(ind, Req("indeed_hiring_lab", INDEED_AGG.format(cc=cc),
                                   f"indeed_aggregate_{cc}.csv"), getter, deadline)
            got = parse_indeed_aggregate(body, now) if body else []
            if got:
                agg.extend(got)
                done[cc] = now.isoformat(timespec="seconds")
        for cc in INDEED_SECTOR_COUNTRIES:
            last = A._t(done.get(f"sector_{cc}"))
            if last is not None and now - last < timedelta(hours=24):
                continue
            body = _fetch(ind, Req("indeed_hiring_lab", INDEED_SECTOR.format(cc=cc),
                                   f"indeed_sector_{cc}.csv"), getter, deadline)
            got = parse_indeed_sector(body, now) if body else []
            if got:
                sec.extend(got)
                done[f"sector_{cc}"] = now.isoformat(timespec="seconds")
        if not dry_run:
            if agg:
                merge_into(paths, JOBS_INDEED, agg, now)
            if sec:
                merge_into(paths, JOBS_SECTOR, sec, now)
        _close(ind, len(agg) + len(sec))
    bls = runs["bls_jolts"]
    if runnable(bls):
        last = A._t(st.get("jolts_at"))
        jolts: list[A.Obs] = []
        if last is None or now - last >= timedelta(hours=24):
            key = os.environ.get("BLS_API_KEY", "")
            for sid in JOLTS_SERIES:
                url = BLS_URL.format(sid=sid, key=urllib.parse.quote(key), y0=now.year - 9,
                                     y1=now.year)
                body = _fetch(bls, Req("bls_jolts", url, f"bls_{sid}.json",
                                       key_env="BLS_API_KEY"), getter, deadline)
                jolts.extend(parse_bls(body) if body else [])
            if jolts:
                st["jolts_at"] = now.isoformat(timespec="seconds")
                if not dry_run:
                    merge_into(paths, JOBS_JOLTS, jolts, now)
        _close(bls, len(jolts))
    srcs = (JOBS_INDEED, JOBS_SECTOR, JOBS_JOLTS)
    points = {s.id: publish(paths, s, now, dry_run=dry_run) for s in srcs}
    rows, held = _hyp_rows(paths, JOBS_HYPS, {s.id: s for s in srcs}, points, "jobs", state, now)
    return {"sources": {k: v.as_dict() for k, v in runs.items()},
            "series": {sid: {k: len(v) for k, v in sorted(p.items())} for sid, p in points.items()},
            "_rows": rows, "held_back": held}


# ============================================================================ factory: payments
#: Every payment-statistics source on the base (all parsed by alt_proxies): country -> ids.
PAYMENT_SOURCES: dict[str, tuple[str, ...]] = {
    "US": ("us_oi_card_spend",), "BR": ("br_bcb_payments", "br_cielo_icva"),
    "KR": ("kr_bok_card_spend",), "IN": ("in_npci_upi",), "TR": ("tr_bkm_card",),
    "CN": ("cn_holiday_spend",), "ZA": ("za_beti",)}
#: The component series each permitted source contributes, and the column taken from its points.
PAYMENT_COMPONENT: dict[str, tuple[str, str]] = {
    "us_oi_card_spend": ("spend_all", "pace"),
    "br_bcb_payments": ("retail_payments_value_brl", "pace"),
    "kr_bok_card_spend": ("card_spend", "pace"),
}
PAYMENTS = store_source(
    "dfp_payments", "Payments factory: per-country payment growth (card / instant payments)",
    rule=A._lag_rule(10, 0), cadence="daily", region="GLOBAL",
    mechanism=("payment volumes are consumption settled, read weeks before retail sales and GDP; "
               "a country whose payments accelerate is a demand surprise for its index and FX"),
    payer="index and FX holders waiting for official consumption prints",
    constraint="official consumption data are monthly or quarterly and revised",
    licence="per component (see the factory's source records)",
    failure="fails when price inflation, not volume, moves nominal payments")
PAYMENT_HYPS: tuple[Hyp, ...] = (
    Hyp("dfp_payments", "US_payments", "value", "US500", 1,
        "card spend accelerating is US consumption ahead of retail sales",
        "z of US card-spend pace no longer leads US500 returns"),
    Hyp("dfp_payments", "BR_payments", "value", "USDBRL", -1,
        "Brazilian payments accelerating is domestic demand that firms the real",
        "z of Brazil payments growth no longer leads USDBRL returns"),
    Hyp("dfp_payments", "KR_payments", "value", "USDKRW", -1,
        "Korean card spend accelerating is domestic demand that firms the won",
        "z of Korea card-spend growth no longer leads USDKRW returns"),
)


def payment_obs(alt_points: Mapping[str, Mapping[str, list[dict[str, Any]]]],
                permitted: Iterable[str]) -> list[A.Obs]:
    """One series per country: the permitted component's pace, carried with its own release
    instant (the component's available_time) so the composite is never earlier than its input."""
    out: list[A.Obs] = []
    ok = set(permitted)
    for cc, ids in PAYMENT_SOURCES.items():
        for sid in ids:
            if sid not in ok or sid not in PAYMENT_COMPONENT:
                continue
            series, col = PAYMENT_COMPONENT[sid]
            for p in (alt_points.get(sid) or {}).get(series, []):
                v = p.get(col)
                avail = A._t(p.get("available_time"))
                if v is None or avail is None:
                    continue
                out.append(A.Obs(f"{cc}_payments", date.fromisoformat(str(p["d"])), float(v),
                                 published_at=avail))
            break                             # one component per country: the first permitted
    return out


def run_payments(paths: Paths, state: dict[str, Any], now: datetime, *, dry_run: bool
                 ) -> dict[str, Any]:
    runs: dict[str, SourceRun] = {}
    alt_points: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ids in PAYMENT_SOURCES.values():
        for sid in ids:
            runs[sid] = _alt_run(paths, sid, alt_points)
    permitted = [s for s, r in runs.items() if r.status == FETCHED]
    obs = payment_obs(alt_points, permitted)
    if obs and not dry_run:
        merge_into(paths, PAYMENTS, obs, now)
    points = {PAYMENTS.id: publish(paths, PAYMENTS, now, dry_run=dry_run)}
    rows, held = _hyp_rows(paths, PAYMENT_HYPS, {PAYMENTS.id: PAYMENTS}, points, "payments",
                           state, now)
    return {"sources": {k: v.as_dict() for k, v in runs.items()},
            "fetcher": "none: alt_proxies collects every component; this factory re-reads its "
                       "vintage store",
            "series": {k: len(v) for k, v in sorted(points[PAYMENTS.id].items())},
            "_rows": rows, "held_back": held}


def _alt_run(paths: Paths, sid: str,
             into: dict[str, dict[str, list[dict[str, Any]]]] | None = None) -> SourceRun:
    """A source alt_proxies owns: HELD without a verbatim permitting quote (the factory's own
    record), NEEDS_KEY when alt_proxies' key is absent, FETCHED when its vintage store holds
    points, else UNMEASURED. Nothing is fetched here."""
    t = _alt_terms(sid)
    src = A.BY_ID.get(sid)
    run = SourceRun(sid)
    if src is not None and src.key_env:
        run.key_state = key_state((src.key_env,))
    if src is None or src.terms != "confirmed" or not t.permits:
        run.status, run.why = HELD, (f"alt_proxies terms {src.terms if src else 'absent'}; "
                                     f"factory terms {t.verdict}: never used")
        return run
    if run.key_state.startswith("NEEDS_KEY"):
        run.status, run.why = NEEDS_KEY, f"{run.key_state}: alt_proxies cannot fetch it"
        return run
    store = _read_json(paths.alt.obs_dir / f"{sid}.json", {})
    pts = A.build_points(src, store) if store else {}
    n = sum(len(v) for v in pts.values())
    if into is not None and pts:
        into[sid] = pts
    run.parsed = n
    if n:
        run.status, run.why = FETCHED, f"{n} PIT points in alt_proxies' store (fetched there)"
    else:
        run.why = "alt_proxies' store is empty on this host: live yield UNMEASURED"
    return run


# ============================================================================ factory: ndvi
#: Crop regions: id -> (lat, lon, ((symbol, prior side), ...)). A greener-than-normal season is
#: more supply, so the prior is negative on the crop's CFD.
NDVI_REGIONS: dict[str, tuple[float, float, tuple[tuple[str, int], ...]]] = {
    "us_corn_belt_ia": (42.00, -93.50, (("CORN", -1), ("SOYBEAN", -1))),
    "us_corn_belt_il": (40.50, -89.00, (("CORN", -1), ("SOYBEAN", -1))),
    "us_plains_wheat_ks": (38.50, -98.50, (("WHEAT", -1),)),
    "br_mato_grosso": (-12.50, -55.70, (("SOYBEAN", -1), ("CORN", -1))),
    "br_minas_coffee": (-21.20, -45.00, (("COFARA", -1),)),
    "vn_highlands_coffee": (12.70, 108.10, (("COFROB", -1),)),
    "ci_cocoa_belt": (6.80, -5.30, (("USCOCOA", -1), ("UKCOCOA", -1))),
    "br_sao_paulo_cane": (-21.50, -48.50, (("SUGAR", -1), ("SUGARRAW", -1))),
    "us_texas_cotton": (33.60, -101.80, (("COTTON", -1),)),
    "us_florida_citrus": (27.90, -81.60, (("OJ", -1),)),
}
ORNL_URL = ("https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset?latitude={lat}&longitude={lon}"
            "&band=250m_16_days_NDVI&startDate=A{y0}{d0:03d}&endDate=A{y1}{d1:03d}"
            "&kmAboveBelow=1&kmLeftRight=1")
#: TESViS serves at most ten MODIS dates per /subset request; 144 days holds nine 16-day composites.
ORNL_WINDOW_D = 144
NDVI_BACK_D = 4 * 365
NDVI_FILL = -3000
NDVI_SCALE = 0.0001
NDVI_REQ_PER_PASS = 14
NDVI_ANOM_MIN_YEARS = 2
NDVI_ANOM_YEARS = 5


def _proc_date(s: Any) -> datetime | None:
    """MODIS proc_date 'YYYYDDDHHMMSS' as UTC."""
    s = str(s or "")
    if not re.fullmatch(r"\d{13}", s):
        return None
    try:
        return (datetime(int(s[:4]), 1, 1, tzinfo=UTC) + timedelta(days=int(s[4:7]) - 1,
                                                                   hours=int(s[7:9]),
                                                                   minutes=int(s[9:11])))
    except ValueError:
        return None


def parse_ornl(body: bytes, region: str) -> list[A.Obs]:
    """TESViS subset JSON: per composite, the mean of the valid pixels (fill -3000 dropped,
    -2000..10000 valid) times the scale. The period is the composite's last day; the publication
    instant is its own processing date."""
    try:
        doc = json.loads(body.decode("utf-8"))
    except ValueError:
        return []
    if not isinstance(doc, dict):
        return []
    try:
        scale = float(doc.get("scale") or NDVI_SCALE)
    except (TypeError, ValueError):
        scale = NDVI_SCALE
    out: list[A.Obs] = []
    for c in doc.get("subset") or []:
        if not isinstance(c, dict) or "NDVI" not in str(c.get("band") or "NDVI"):
            continue
        try:
            start = date.fromisoformat(str(c["calendar_date"])[:10])
        except (KeyError, ValueError):
            continue
        vals = [float(v) for v in c.get("data") or []
                if isinstance(v, (int, float)) and v != NDVI_FILL and -2000 <= v <= 10000]
        if not vals:
            continue
        end = start + timedelta(days=15)
        out.append(A.Obs(f"{region}_ndvi", end, round(sum(vals) / len(vals) * scale, 5),
                         published_at=_proc_date(c.get("proc_date"))))
    return out


def ndvi_anomalies(store: Mapping[str, Any]) -> list[A.Obs]:
    """NDVI minus the mean of the same composite window (+-8 days of year) in up to five prior
    years (>= 2 required), carried at the composite's own published instant."""
    by: dict[str, list[tuple[date, float, str]]] = {}
    for r in store.values():
        name = str(r.get("series") or "")
        if name.endswith("_ndvi"):
            by.setdefault(name, []).append((date.fromisoformat(str(r["period"])),
                                            float(r["value_first"]), str(r["published_time"])))
    out: list[A.Obs] = []
    for name, rows in by.items():
        for d, v, pub in rows:
            prior = [pv for pd_, pv, _ in rows
                     if 1 <= d.year - pd_.year <= NDVI_ANOM_YEARS
                     and abs(_doy_gap(d, pd_)) <= 8]
            if len(prior) < NDVI_ANOM_MIN_YEARS:
                continue
            out.append(A.Obs(f"{name}_anom", d, round(v - sum(prior) / len(prior), 5),
                             published_at=A._t(pub)))
    return out


def _doy_gap(a: date, b: date) -> int:
    g = a.timetuple().tm_yday - b.timetuple().tm_yday
    return (g + 182) % 365 - 182


NDVI = store_source(
    "dfn_ndvi", "MODIS MOD13Q1 NDVI per crop region (ORNL DAAC TESViS)",
    rule=A._lag_rule(10, 0), cadence="10-daily", region="GLOBAL",
    mechanism=("vegetation vigour over the growing belt is a supply estimate read from orbit every "
               "16 days, ahead of USDA/CONAB crop reports"),
    payer="softs and grains holders priced on the last official crop estimate",
    constraint="official crop estimates are monthly; the composites are fortnightly",
    licence="NASA ORNL DAAC: openly shared, without restriction",
    failure="fails under persistent cloud and when price is driven by demand, not supply")
NDVI_HYPS: tuple[Hyp, ...] = tuple(
    Hyp("dfn_ndvi", f"{reg}_ndvi_anom", "value", sym, side,
        f"greener-than-normal {reg} is more supply than the last crop report priced",
        f"z of {reg} NDVI anomaly no longer leads {sym} returns over the next 120 H1 bars")
    for reg, (_, _, legs) in NDVI_REGIONS.items() for sym, side in legs)


def run_ndvi(paths: Paths, state: dict[str, Any], now: datetime, getter: Getter,
             deadline: float, *, dry_run: bool) -> dict[str, Any]:
    st = state.setdefault("ndvi", {})
    runs = {"ornl_modis_ndvi": preflight("ornl_modis_ndvi")}
    run = runs["ornl_modis_ndvi"]
    if runnable(run):
        got: list[A.Obs] = []
        budget = NDVI_REQ_PER_PASS
        for reg, (lat, lon, _) in NDVI_REGIONS.items():
            rs = st.setdefault(reg, {})
            windows: list[date] = []
            last = A._t(rs.get("fwd_at"))
            if last is None or now - last >= timedelta(hours=24):
                windows.append(now.date())
            back = date.fromisoformat(rs["back_end"]) if rs.get("back_end") else (
                now.date() - timedelta(days=ORNL_WINDOW_D))
            if back > now.date() - timedelta(days=NDVI_BACK_D):
                windows.append(back)
            for end in windows:
                if budget <= 0:
                    break
                budget -= 1
                start = end - timedelta(days=ORNL_WINDOW_D)
                url = ORNL_URL.format(lat=lat, lon=lon, y0=start.year,
                                      d0=start.timetuple().tm_yday, y1=end.year,
                                      d1=end.timetuple().tm_yday)
                body = _fetch(run, Req("ornl_modis_ndvi", url, f"ornl_{reg}.json",
                                       (("Accept", "application/json"),)), getter, deadline)
                obs = parse_ornl(body, reg) if body else []
                if not obs:
                    continue
                got.extend(obs)
                if end == now.date():
                    rs["fwd_at"] = now.isoformat(timespec="seconds")
                else:
                    rs["back_end"] = (start - timedelta(days=1)).isoformat()
        if got and not dry_run:
            merge_into(paths, NDVI, got, now)
        _close(run, len(got))
    store = _read_json(paths.obs_dir / f"{NDVI.id}.json", {})
    anom = ndvi_anomalies(store)
    if anom and not dry_run:
        merge_into(paths, NDVI, anom, now)
    points = {NDVI.id: publish(paths, NDVI, now, dry_run=dry_run)}
    rows, held = _hyp_rows(paths, NDVI_HYPS, {NDVI.id: NDVI}, points, "ndvi", state, now)
    return {"sources": {k: v.as_dict() for k, v in runs.items()},
            "regions": {k: {"lat": v[0], "lon": v[1], "instruments": dict(v[2])}
                        for k, v in NDVI_REGIONS.items()},
            "series": {k: len(v) for k, v in sorted(points[NDVI.id].items())},
            "_rows": rows, "held_back": held}


# ============================================================================ alt_proxies-backed
#: Domains with a parser already on the base (alt_proxies). Nothing is fetched here; minting
#: stays with alt_proxies.direct_cells (gain-tested, donated only on PASS).
ALT_DOMAINS: dict[str, tuple[str, ...]] = {
    "satellite_facility": ("cn_firms_industrial",),
    "shipping_ais": ("imf_portwatch_ports", "imf_portwatch_chokepoints", "kr_mof_container_teu",
                     "sg_port_throughput"),
    "customs": ("kr_exports_early", "in_gold_imports"),
    "attention": ("wiki_asia_attention", "gdelt_events_country"),
    "spending": ("us_census_marts_ex_autos", "jp_meti_retail", "cn_nbs_retail",
                 "tr_tuik_retail", "mx_inegi_emec"),
}
NO_PARSER_DOMAINS: dict[str, str] = {
    "electricity": "no electricity load/price parser on the base",
    "procurement": "no public-procurement parser on the base",
    "supply_chain_exhaust": "no supply-chain exhaust parser on the base",
    "search_app_attention": "no search-volume or app-ranking parser on the base "
                            "(Wikipedia pageviews and GDELT are the attention row)",
    "customs_microdata": "no customs microdata parser on the base (aggregate customs is a row)",
}


def run_alt_domains(paths: Paths) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for dom, ids in ALT_DOMAINS.items():
        out[dom] = {"sources": {sid: _alt_run(paths, sid).as_dict() for sid in ids},
                    "fetcher": "alt_proxies (this factory fetches nothing for this domain)",
                    "minting": "alt_proxies.direct_cells: exogenous_conditioner cells donated "
                               "only after the placebo gain test PASSES",
                    "lake_files": [A.lake_file(A.BY_ID[sid], s) for sid in ids
                                   if sid in A.BY_ID for s in A.BY_ID[sid].signal_series]}
    return out


# ============================================================================ the pass
def _donate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from research import proposer_common as pc
    path = pc.donate(ORGAN, rows, 0)
    return {**pc.donation_counts(), "path": str(path) if path else None}


def run(paths: Paths = DEFAULT_PATHS, *, budget_s: float = 240.0, fixtures: Path | None = None,
        dry_run: bool = False, donate: bool = True, now: datetime | None = None,
        getter: Getter | None = None,
        donor: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + budget_s * 0.8
    get = getter or (fixture_getter(fixtures) if fixtures is not None else live_getter)
    state = _read_json(paths.state, {})
    factories: dict[str, Any] = {}
    steps: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("weather", lambda: run_weather(paths, state, now, get, deadline, dry_run=dry_run)),
        ("jobs", lambda: run_jobs(paths, state, now, get, deadline, dry_run=dry_run)),
        ("payments", lambda: run_payments(paths, state, now, dry_run=dry_run)),
        ("ndvi", lambda: run_ndvi(paths, state, now, get, deadline, dry_run=dry_run))]
    for name, fn in steps:
        try:
            factories[name] = fn()
        except HeldSource:
            raise
        except Exception as exc:
            factories[name] = {"error": f"{type(exc).__name__}: {str(exc)[:240]}",
                               "sources": {}, "_rows": [], "held_back": []}
    rows = [r for f in factories.values() for r in f.pop("_rows", [])]
    donation: dict[str, Any] = {"donated": 0, "path": None}
    if rows and donate and not dry_run:
        try:
            donation = (donor or _donate)(rows)
        except Exception as exc:
            donation = {"donated": 0, "path": None, "error": f"{type(exc).__name__}: {exc}"}
        if donation.get("path"):
            for r in rows:
                state.setdefault("minted", {})[str(r["cell"])] = now.isoformat(timespec="seconds")
    alt = run_alt_domains(paths)
    statuses: dict[str, int] = dict.fromkeys(STATUSES, 0)
    for f in (*factories.values(), *alt.values()):
        for s in (f.get("sources") or {}).values():
            statuses[s["status"]] = statuses.get(s["status"], 0) + 1
    report = {
        "at": now.isoformat(timespec="seconds"), "organ": ORGAN,
        "mode": "fixtures" if fixtures is not None else "fetch",
        "dry_run": dry_run,
        "requirements": ["DATA-43", "DATA-25"],
        "status_counts": statuses,
        "factories": factories, "domains": alt, "no_parser_domains": NO_PARSER_DOMAINS,
        "hypotheses": {"minted": len(rows), "donation": donation,
                       "cells": [r["cell"] for r in rows][:200],
                       "rule": ("EXACT_RECIPE exogenous_conditioner rows on the factory's lake "
                                "series, a declared prior sign each, minted once the series holds "
                                f">= {MIN_POINTS} PIT points; nothing is tested here "
                                "(tests_run=0) -- the gauntlet judges and charges the trial")},
        "terms_rule": ("a source is fetched only with a PERMITS verdict and a clause quoted "
                       "verbatim from its own terms page (TERMS_RECORDS); everything else is HELD "
                       "and no request is built for it"),
        "live_yield": ("UNMEASURED until the trading box runs this leg: the parsers were built "
                       "against synthetic fixtures because the authoring container cannot reach "
                       "these hosts"),
    }
    state["last_run"] = report["at"]
    if not dry_run:
        _atomic(paths.state, state)
    _atomic(paths.report, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="parse and report, write no store, lake or donation")
    ap.add_argument("--no-donate", action="store_true")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, fixtures=a.fixtures, dry_run=a.dry_run,
              donate=not a.no_donate)
    print(json.dumps({"at": rep["at"], "status_counts": rep["status_counts"],
                      "minted": rep["hypotheses"]["minted"],
                      "report": str(DEFAULT_PATHS.report)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
