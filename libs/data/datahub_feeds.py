"""THE LIVE FEEDS BEHIND THE DATAHUB: the free-terminal contracts, OpenBB as a second provider.

The Fincept/OpenBB pattern, rebuilt rather than copied (2026-11-13). One contract per
dataset, and several providers behind each: the desk's own recorder first, OpenBB's
provider extension second. OpenBB V5 is Apache-2.0 (repository LICENSE, read 2026-11-13),
so it may be imported. Fincept Terminal is AGPL-3.0-or-later, so its concepts are rebuilt
here and none of its code is copied.

WHICH OPENBB PROVIDERS. Only those whose upstream terms read `confirmed` on 2026-11-13. The
report is /mnt/project-files/reports/terms_reads/free_terminal_terms_2026-11-13.md:

    fred (St. Louis Fed's own series), sec, federal_reserve (Board), cftc (COT),
    government_us (FiscalData, USDA), us_eia, oecd (terms confirmed; robots read on the box)

IMF, Cboe, FINRA, Nasdaq, TMX, yfinance, Tiingo, FMP, Intrinio and Polygon read `refused`.
ECB, BLS, JODI, Fama-French and the regional Fed banks read `to_confirm`. None of them is
wired. A provider that is not in OPENBB_CONFIRMED raises before it is called.

OpenBB is never required. When `openbb` does not import, its provider raises, and
`DataHub.get` records the error and moves to the next provider. A contract whose only
provider is OpenBB then raises LookupError, which leaves the answer UNMEASURED; it never
becomes zero.

    from libs.data.datahub_feeds import live_hub
    live_hub().get("tanker.port_calls")              -> daily frame, Kystverket NLOD
    live_hub().get("macro.fred_series", series_id="DGS10")
"""
from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from libs.data.datahub import DESK, Contract, DataHub, Provider, desk_hub

AIS_LAKE = DESK / "data" / "lake" / "ais" / "norway"
AIS_SERIES = DESK / "data" / "lake" / "series" / "ais_norway.parquet"
ALFRED = DESK / "data" / "lake" / "alfred"

#: OpenBB V5 provider names whose upstream terms read `confirmed` on 2026-11-13.
OPENBB_CONFIRMED: frozenset[str] = frozenset({
    "fred", "sec", "federal_reserve", "cftc", "government_us", "us_eia", "oecd"})


# --------------------------------------------------------------------------- AIS (Kystverket)
def _ais_frame(columns: tuple[str, ...] | None = None) -> Any:
    if not AIS_SERIES.exists():
        return None
    import pandas as pd
    df = pd.read_parquet(AIS_SERIES)
    if columns:
        keep = [c for c in df.columns if c in columns or c == "windows"]
        df = df[keep]
    return df if len(df) else None


def ais_port_calls() -> Any:
    """Mean distinct tankers per window, per terminal zone, per complete UTC day."""
    return _ais_frame(("hammerfest_lng_tankers", "mongstad_sture_tankers", "karsto_tankers",
                       "north_cape_tankers", "hammerfest_lng_mean_draught",
                       "mongstad_sture_mean_draught", "karsto_mean_draught",
                       "north_cape_mean_draught"))


def ais_floating_storage() -> Any:
    """Tankers idling (< 0.5 kn) outside the terminal boxes, mean per window per day."""
    return _ais_frame(("stationary_offport_tankers", "coverage_tankers"))


def ais_positions(days: int = 1) -> list[dict[str, Any]] | None:
    """The last `days` UTC days of tanker positions, one row per tanker per window."""
    rows: list[dict[str, Any]] = []
    today = datetime.now(UTC).date()
    for k in range(days):
        p = AIS_LAKE / f"tankers_{(today - timedelta(days=k)).isoformat()}.jsonl"
        with contextlib.suppress(OSError):
            for ln in p.read_text("utf-8").splitlines():
                with contextlib.suppress(ValueError):
                    rows.append(json.loads(ln))
    return rows or None


# --------------------------------------------------------------------------- OpenBB
#: The upstream path each OpenBB provider requests. robots.txt is read for it BEFORE OpenBB is
#: called, because OpenBB itself never reads robots.
OPENBB_UPSTREAM: dict[str, str] = {
    "fred": "https://api.stlouisfed.org/fred/series/observations",
    "oecd": "https://sdmx.oecd.org/public/rest/data/",
    "cftc": "https://publicreporting.cftc.gov/resource/",
    "sec": "https://data.sec.gov/api/xbrl/",
    "federal_reserve": "https://www.federalreserve.gov/datadownload/",
    "government_us": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/",
    "us_eia": "https://api.eia.gov/v2/",
}
UA = "quant-desk-datahub/1.0 (research; robots-respecting)"
_ROBOTS: dict[str, str | None] = {}


def robots_refusal(url: str, agent: str = "") -> str | None:
    """None when robots.txt allows `url`, else why not. FAIL CLOSED (Governance 2026-11-10):
    404/410 means no rules; 401/403/429/451 is a hard stop; anything unreadable, a 5xx, or an
    HTML body in place of robots rules refuses. `agent` is the User-Agent the fetch will send;
    robots is read and evaluated under that same agent (datahub's own UA by default)."""
    import urllib.error
    import urllib.parse
    import urllib.request
    import urllib.robotparser
    parts = urllib.parse.urlsplit(url)
    ua = agent or UA
    key = f"{ua}|{parts.scheme}://{parts.netloc}{parts.path}"
    if key in _ROBOTS:
        return _ROBOTS[key]
    rp = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(f"{parts.scheme}://{parts.netloc}/robots.txt",
                                 headers={"User-Agent": ua})
    out: str | None
    try:
        with urllib.request.urlopen(req, timeout=15.0) as r:
            body = r.read(500_000).decode("utf-8", errors="replace")
        if body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
            out = "robots.txt answered HTML"
        else:
            rp.parse(body.splitlines())
            out = None if rp.can_fetch(ua, url) else "robots.txt disallows this path"
    except urllib.error.HTTPError as e:
        out = None if e.code in (404, 410) else f"robots.txt HTTP {e.code}"
    except Exception as e:
        out = f"robots.txt unreadable ({type(e).__name__})"
    _ROBOTS[key] = out
    return out


def openbb_call(provider: str, route: str, **kw: Any) -> Any:
    """Call one OpenBB route through a terms-confirmed provider; the result as a DataFrame."""
    if provider not in OPENBB_CONFIRMED:
        raise PermissionError(f"openbb provider {provider!r} is not terms-confirmed")
    refused = robots_refusal(OPENBB_UPSTREAM[provider])
    if refused:
        raise PermissionError(f"openbb provider {provider!r}: {refused}")
    from openbb import obb  # type: ignore[import-not-found]
    fn: Any = obb
    for part in route.split("."):
        fn = getattr(fn, part)
    return fn(provider=provider, **kw).to_dataframe()


def _fred_lake(series_id: str) -> Any:
    p = ALFRED / f"{series_id}.parquet"
    if not p.exists():
        return None
    import pandas as pd
    return pd.read_parquet(p)


def _fred_openbb(series_id: str) -> Any:
    return openbb_call("fred", "economy.fred_series", symbol=series_id)


def _cot_desk(code: str) -> Any:
    from libs.data.cot_source import fetch_net_spec
    s = fetch_net_spec(code)
    return s if len(s) else None


def _cot_openbb(code: str) -> Any:
    return openbb_call("cftc", "regulators.cftc.cot", id=code)


def _oecd_cli_openbb(country: str = "all") -> Any:
    return openbb_call("oecd", "economy.composite_leading_indicator", country=country)


def _official_events() -> Any:
    """The robots-gated publisher calendar (libs/data/event_calendar.py), as written."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "data" / "event_calendar.json"
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or "coverage" not in doc:
        return None
    return doc.get("events") or None


def live_hub() -> DataHub:
    """`desk_hub()` plus the free-terminal contracts."""
    hub = desk_hub()
    nlod = "Kystverket open AIS, NLOD 2.0"
    hub.register(Contract("tanker.port_calls", "frame",
                          description=f"tankers per terminal zone per day ({nlod})",
                          providers=[Provider("ais_norway", lambda: ais_port_calls(), "free")]))
    hub.register(Contract("tanker.floating_storage", "frame",
                          description=f"stationary off-port tankers per day ({nlod})",
                          providers=[Provider("ais_norway",
                                              lambda: ais_floating_storage(), "free")]))
    hub.register(Contract("ais.positions", "rows",
                          description=f"tanker positions per sampling window ({nlod})",
                          providers=[Provider("ais_norway", ais_positions, "free")]))
    hub.register(Contract("macro.fred_series", "frame",
                          description="FRED/ALFRED series (St. Louis Fed's own series)",
                          providers=[Provider("alfred_lake", _fred_lake, "primary"),
                                     Provider("openbb.fred", _fred_openbb, "backup",
                                              version="openbb-v5")]))
    hub.register(Contract("cot.net_spec", "frame",
                          description="CFTC COT net non-commercial share of open interest",
                          providers=[Provider("cftc_socrata", _cot_desk, "primary"),
                                     Provider("openbb.cftc", _cot_openbb, "backup",
                                              version="openbb-v5")]))
    hub.register(Contract("macro.oecd_cli", "frame",
                          description="OECD composite leading indicators (OECD terms: any "
                                      "purpose incl. commercial, credit the OECD)",
                          providers=[Provider("openbb.oecd", _oecd_cli_openbb, "free",
                                              version="openbb-v5")]))
    hub.register(Contract("calendar.official_events", "rows",
                          description="scheduled releases from the Fed, BLS, BEA, ECB, BoE, "
                                      "BoJ, SNB and BoC pages, UTC (event_calendar_refresh)",
                          providers=[Provider("publisher_pages", _official_events, "free")]))
    return hub


def census() -> dict[str, Any]:
    """Which live contracts answer on this box right now -- measured, never asserted."""
    hub = live_hub()
    probes: dict[str, dict[str, Any]] = {
        "tanker.port_calls": {}, "tanker.floating_storage": {}, "ais.positions": {},
        "macro.fred_series": {"series_id": "DGS10"}, "macro.oecd_cli": {},
        "calendar.official_events": {}}
    out: dict[str, Any] = {}
    for name, kw in probes.items():
        try:
            got = hub.get(name, **kw)
            out[name] = {"status": "ANSWERED", "provider": got["provider"]}
        except LookupError as exc:
            out[name] = {"status": "UNMEASURED", "why": str(exc)[:300]}
    return out
