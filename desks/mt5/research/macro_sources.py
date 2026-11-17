"""WHERE macro_desk READS EACH MACRO SERIES -- primary publishers only, keyed by name, fail closed.

WHY THIS MODULE EXISTS (2026-11-17). `macro_desk` read every series from FRED/ALFRED
(`fredgraph.csv`) and the cross-asset anchors from Yahoo. FRED, ALFRED and every
`stlouisfed.org` host are refused for automated use (Governance ruling 2026-11-13), and so are
Yahoo, Cboe and ICE. So no route here touches them: each series the desk used to ask FRED for
is either

  * SOURCED from its primary publisher, through a route that already exists in this repository
    (the builder/parser in `libs.data.keyed_sources`, the BIFF8 reader in
    `libs.data.xls_reader`), with the publisher's terms read from a record already in the repo,
    or
  * BLOCKED_ON_TERMS, with the reason and a missed_growth line, and reads UNMEASURED.

THREE FENCES, ALL BEFORE A SOCKET OPENS.
  1. TERMS. A keyless route is fetched only when `libs.research.equivalence_ontology
     .terms_verdict(url)` is PERMITTED (a verbatim permitting clause on file). The BLS API is
     fetched only while its roster row in `data/source_rosters/keyed_sources.json` carries
     `machine_use_allowed: true` -- the same fence the keyed_sources leg applies.
  2. ROBOTS. `asia_collector._robots_allows` (the 2026-11-13 ruling: obeyed, fail closed,
     401/403/429/451 stop the host).
  3. HARD STOP. A 401/403/429/451 answer halts that host for HALT_S, persisted in
     `data/macro_sources/halt.json`; nothing retries around it.

KEYS. Read only through `research.keyed_sources.resolve_keys` (registry names via
`libs.data.credentials.accepted_names`, values via `libs.ops.env_keys.read_key`), by NAME
(`BLS_API_KEY`). The value goes into the request body only; the transport is
`research.keyed_sources.http`, which scrubs it from anything it returns. No key is logged,
cached or written; a missing key is BLOCKED_AUTH:BLS_API_KEY, never a zero.

CACHE. `data/macro_sources/<route>.json` (gitignored: raw publisher series stay on the box) is
re-used until the route is due again, so an hourly loop asks BLS for one POST every DUE_S.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CACHE = DESK / "data" / "macro_sources"
HALT_F = CACHE / "halt.json"
ROSTER = DESK / "data" / "source_rosters" / "keyed_sources.json"
AGENT = "quant-desk-keyed-sources/1.0"

BLOCKED_ON_TERMS = "BLOCKED_ON_TERMS"
UNMEASURED = "UNMEASURED"
#: Answers that stop a host: authentication, rate limit, legal. Never retried around.
HARD_STOP = (401, 403, 429, 451)
HALT_S = 24 * 3600

ECB_HICP = ("https://data-api.ecb.europa.eu/service/data/ICP/"
            "M.U2.N.000000.4.INX?format=csvdata")
EIA_WTI_XLS = "https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls"

#: Route -> seconds before it is fetched again. The data underneath is daily or monthly.
DUE_S: dict[str, int] = {"bls": 6 * 3600, "eia_xls": 6 * 3600, "ecb_sdmx": 12 * 3600}

#: THE MAP: macro_desk's series id -> the primary publisher route that serves it. The ids stay
#: the desk's historic names (readers key on them); `native` is the publisher's own id.
SOURCED: dict[str, dict[str, str]] = {
    "PAYEMS": {"route": "bls", "native": "CES0000000001", "publisher": "US BLS (CES)"},
    "UNRATE": {"route": "bls", "native": "LNS14000000", "publisher": "US BLS (CPS)"},
    "CPIAUCSL": {"route": "bls", "native": "CUSR0000SA0", "publisher": "US BLS (CPI-U SA)"},
    "CPILFESL": {"route": "bls", "native": "CUSR0000SA0L1E",
                 "publisher": "US BLS (CPI-U core SA)"},
    "DCOILWTICO": {"route": "eia_xls", "native": "RWTC", "url": EIA_WTI_XLS,
                   "publisher": "US EIA (Cushing WTI spot, daily)"},
    "CP0000EZ19M086NEST": {"route": "ecb_sdmx", "native": "ICP.M.U2.N.000000.4.INX",
                           "url": ECB_HICP, "publisher": "Eurostat HICP via ECB Data Portal"},
}

_TREASURY = ("the FRED route is refused; the primary publisher, home.treasury.gov, is HELD in "
             "libs/research/equivalence_ontology.TERMS_EVIDENCE (its site policies carry no "
             "reuse clause, read 2026-10-06)")
_NYFED = ("the FRED route is refused; the primary publisher (NY Fed markets API) has no terms "
          "evidence on file, so it is HELD (fail closed, never inferred)")
_FEDBOARD = ("the FRED route is refused; the primary publisher (Federal Reserve Board data "
             "download) has no reader and no terms evidence in this repo")
_MG_RATES = ("missed_growth: the US rates/curve/breakeven legs of POLICY_STATE, "
             "CURVE_T10Y2Y and INFLATION_STATE are UNMEASURED; gold/USD/index cells "
             "conditioned on them see no state (a gap, not a neutral reading)")
_MG_POLICY = ("missed_growth: POLICY_RATE, EFF_RATE, POLICY_STATE and LIQUIDITY_STATE are "
              "UNMEASURED; the policy-path tilt is absent, not neutral")

#: Every other id the desk used to read from FRED: BLOCKED_ON_TERMS, why, and what it costs.
BLOCKED: dict[str, dict[str, str]] = {
    **{sid: {"why": _TREASURY, "missed_growth": _MG_RATES}
       for sid in ("DGS2", "DGS10", "T10Y2Y", "T10YIE", "T5YIE")},
    **{sid: {"why": _NYFED, "missed_growth": _MG_POLICY}
       for sid in ("DFEDTARU", "DFF", "SOFR", "RRPONTSYD")},
    "WALCL": {"why": _FEDBOARD + " (H.4.1)", "missed_growth": _MG_POLICY},
    "INDPRO": {"why": _FEDBOARD + " (G.17)",
               "missed_growth": "missed_growth: GROWTH_STATE runs without industrial output"},
    "DTWEXBGS": {"why": _FEDBOARD + " (H.10)",
                 "missed_growth": "missed_growth: DOLLAR_STATE is UNMEASURED; USD-leg tilts "
                                  "are absent"},
    "UMCSENT": {"why": ("the FRED route is refused; the University of Michigan survey has no "
                        "reader and no terms evidence in this repo"),
                "missed_growth": "missed_growth: GROWTH_STATE runs without consumer sentiment"},
    "RSAFS": {"why": ("the FRED route is refused; the primary publisher (Census MARTS) has no "
                      "reader and no terms evidence in this repo"),
                    "missed_growth": "missed_growth: GROWTH_STATE runs without retail sales"},
    "BAMLH0A0HYM2": {"why": ("the FRED route is refused, and the index owner (ICE) refuses "
                             "automated collection of its data"),
                     "missed_growth": "missed_growth: RISK_STATE runs without HY credit spread"},
    "VIXCLS": {"why": ("the FRED route is refused, and Cboe refuses automated collection "
                       "of its data"),
               "missed_growth": "missed_growth: RISK_STATE runs without implied vol"},
    "JPNCPIALLMINMEI": {"why": ("the FRED route is refused; no national-CPI reader for the "
                                "primary publisher (e-Stat) exists in this repo"),
                        "missed_growth": "missed_growth: US_MINUS_JP_CPI_YOY is UNMEASURED"},
}
#: Routes macro_desk used outside the series map, now refused in full.
BLOCKED_ROUTES: dict[str, dict[str, str]] = {
    "alfred_vintages": {
        "why": "ALFRED (alfred.stlouisfed.org) is refused for automated use (ruling 2026-11-13)",
        "missed_growth": ("missed_growth: no new point-in-time vintages of PAYEMS/CPIAUCSL/"
                          "DGS10; data/macro_pointintime keeps what it holds and grows no "
                          "further")},
    "yahoo_anchors": {
        "why": "Yahoo's terms forbid automated collection (ruling 2026-11-13)",
        "missed_growth": ("missed_growth: anchors DXY/VIX/TNX/GC/CL/SPX stop advancing; their "
                          "history in cross_asset_anchors.pkl is kept, never erased")},
}


@dataclass
class Fetched:
    """One series as one pass read it: data or the reason it has none."""
    series: str
    data: dict[str, float] | None = None
    status: str = UNMEASURED
    reason: str = ""
    route: str = ""
    native: str = ""
    publisher: str = ""
    fetched_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def entry(self) -> dict[str, Any]:
        return {"route": self.route, "native": self.native, "publisher": self.publisher,
                "status": self.status, "reason": self.reason, "fetched_at": self.fetched_at}


class HardStop(Exception):
    """A host answered 401/403/429/451."""


# ------------------------------------------------------------------------------- fences -----
def terms_verdict(route: str, url: str) -> tuple[bool, str]:
    """(permitted, why) from a terms record already in this repo. Unclear fails closed."""
    if route == "bls":
        row = bls_roster_row()
        if row is None:
            return False, "no bls_components row in the keyed-sources roster: terms unread"
        if row.get("machine_use_allowed") is not True:
            return False, "keyed-sources roster row bls_components is not machine_use_allowed"
        return True, f"roster bls_components: {row.get('licence') or 'machine_use_allowed'}"
    try:
        from libs.research.equivalence_ontology import PERMITTED, terms_why
        from libs.research.equivalence_ontology import terms_verdict as tv
    except Exception as exc:          # the evidence table is unreadable: nothing is permitted
        return False, f"terms evidence unreadable ({type(exc).__name__})"
    if tv(url) == PERMITTED:
        return True, terms_why(url)
    return False, terms_why(url)


def robots_allows(url: str) -> tuple[bool, str]:
    try:
        from research.asia_collector import _robots_allows
    except ModuleNotFoundError:
        from asia_collector import (  # type: ignore[no-redef,import-not-found,unused-ignore]
            _robots_allows,
        )
    ok, why = _robots_allows(url, agent=AGENT)
    return bool(ok), str(why)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), "utf-8")
    os.replace(tmp, path)


def halted(host: str, now: datetime, path: Path | None = None) -> str | None:
    doc = _read_json(path or HALT_F) or {}
    row = doc.get(host) if isinstance(doc, dict) else None
    if not isinstance(row, dict):
        return None
    try:
        until = datetime.fromisoformat(str(row.get("until")))
    except ValueError:
        return None
    if until > now:
        return f"halted until {until.isoformat()} after HTTP {row.get('code')}"
    return None


def record_halt(host: str, code: int, now: datetime, path: Path | None = None) -> None:
    p = path or HALT_F
    doc = _read_json(p)
    doc = doc if isinstance(doc, dict) else {}
    doc[host] = {"code": int(code), "at": now.isoformat(),
                 "until": (now + timedelta(seconds=HALT_S)).isoformat()}
    _write_json(p, doc)


def bls_roster_row(path: Path | None = None) -> dict[str, Any] | None:
    doc = _read_json(path or ROSTER)
    rows = doc.get("sources") if isinstance(doc, dict) else doc
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("id") == "bls_components":
            return r
    return None


# ------------------------------------------------------------------------------ parsing -----
_EXCEL_EPOCH = date(1899, 12, 30)


def parse_eia_xls(body: bytes) -> dict[str, float]:
    """EIA `hist_xls` workbook -> {iso_date: value}: the rows whose first cell is a date (an
    Excel serial, a date or an ISO string) and whose second is a number. Notes rows drop out."""
    from libs.data.xls_reader import read_xls
    out: dict[str, float] = {}
    for sheet in read_xls(body):
        for row in sheet.rows():
            if len(row) < 2:
                continue
            d = _cell_date(row[0])
            v = row[1]
            if d is None or isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            out[d.isoformat()] = float(v)
        if out:
            break
    return out


def _cell_date(cell: object) -> date | None:
    if isinstance(cell, datetime):
        return cell.date()
    if isinstance(cell, date):
        return cell
    if isinstance(cell, (int, float)) and not isinstance(cell, bool) and 20000 < cell < 80000:
        return _EXCEL_EPOCH + timedelta(days=int(cell))
    if isinstance(cell, str):
        try:
            return date.fromisoformat(cell.strip()[:10])
        except ValueError:
            return None
    return None


def _obs_to_series(obs: list[Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for o in obs:
        out.setdefault(str(o.series), {})[o.period.isoformat()] = float(o.value)
    return out


# ----------------------------------------------------------------------------- fetching -----
Getter = Callable[[Any], bytes]


def _http() -> Getter:
    try:
        from research.keyed_sources import http
    except ModuleNotFoundError:
        from keyed_sources import (  # type: ignore[no-redef,import-not-found,unused-ignore]
            http,
        )
    return http


def _resolve_bls_key(environ: Mapping[str, str] | None) -> str:
    try:
        from research.keyed_sources import Blocked, resolve_keys
    except ModuleNotFoundError:
        from keyed_sources import (  # type: ignore[no-redef,import-not-found,unused-ignore]
            Blocked,
            resolve_keys,
        )
    try:
        return resolve_keys({"key_env": ["BLS_API_KEY"]}, environ)["BLS_API_KEY"]
    except Blocked:
        return ""


def _fetch_route(route: str, ids: list[str], now: datetime, get: Getter,
                 environ: Mapping[str, str] | None) -> dict[str, dict[str, float]]:
    """Raw fetch of one route: {macro id: {iso_date: value}}. Raises HardStop / PermissionError
    / OSError with a message that carries no key."""
    from libs.data import keyed_sources as ks
    if route == "bls":
        key = _resolve_bls_key(environ)
        if not key:
            raise PermissionError("BLOCKED_AUTH:BLS_API_KEY (no value under any registered name)")
        row = {"series": {sid: {"code": SOURCED[sid]["native"]} for sid in ids}}
        out: dict[str, dict[str, float]] = {}
        for req in ks.bls_requests(row, key, None):
            req.secrets = (key,)
            out.update(_obs_to_series(ks.parse_bls(_guarded(req, get, now), row)))
        if not out:
            raise OSError("BLS answered without REQUEST_SUCCEEDED data")
        return out
    if route == "eia_xls":
        req = ks.Request(SOURCED["DCOILWTICO"]["url"])
        data = parse_eia_xls(_guarded(req, get, now))
        if not data:
            raise OSError("EIA workbook parsed to no dated rows")
        return {"DCOILWTICO": data}
    if route == "ecb_sdmx":
        sid = "CP0000EZ19M086NEST"
        req = ks.Request(SOURCED[sid]["url"], headers={"Accept": "text/csv"}, part=sid)
        series = _obs_to_series(ks.parse_sdmx_csv(_guarded(req, get, now), {}, part=sid))
        if not series.get(sid):
            raise OSError("ECB SDMX-CSV parsed to no observations")
        return series
    raise ValueError(f"unknown route {route!r}")


def _guarded(req: Any, get: Getter, now: datetime) -> bytes:
    host = (urlsplit(req.url).hostname or "").lower()
    why = halted(host, now)
    if why:
        raise HardStop(f"{host} {why}")
    try:
        return get(req)
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        exc.close()
        if code in HARD_STOP:
            record_halt(host, code, now)
            raise HardStop(f"{host} answered HTTP {code}: hard stop for {HALT_S // 3600}h") \
                from None
        raise OSError(f"{host} answered HTTP {code}") from None


def _route_url(route: str) -> str:
    from libs.data import keyed_sources as ks
    return {"bls": ks.BLS_URL, "eia_xls": EIA_WTI_XLS, "ecb_sdmx": ECB_HICP}[route]


def collect(now: datetime | None = None, *, get: Getter | None = None,
            environ: Mapping[str, str] | None = None, fetch: bool = True,
            robots: Callable[[str], tuple[bool, str]] | None = None) -> dict[str, Fetched]:
    """Every macro id -> Fetched. Sourced ids go through terms, robots and the hard stop; a
    route not due re-uses its cache; a failed fetch falls back to the cache with the failure
    named. Blocked ids come back BLOCKED_ON_TERMS with no data."""
    now = now or datetime.now(UTC)
    get = get or _http()
    robots = robots or robots_allows
    out: dict[str, Fetched] = {}
    for sid, b in BLOCKED.items():
        out[sid] = Fetched(sid, status=BLOCKED_ON_TERMS, route="none",
                           reason=f"{b['why']}. {b['missed_growth']}")
    by_route: dict[str, list[str]] = {}
    for sid, spec in SOURCED.items():
        by_route.setdefault(spec["route"], []).append(sid)
    for route, ids in by_route.items():
        cache_f = CACHE / f"{route}.json"
        cached = _read_json(cache_f)
        cached = cached if isinstance(cached, dict) else {}
        raw_series = cached.get("series")
        series: dict[str, Any] = raw_series if isinstance(raw_series, dict) else {}
        fetched_at = cached.get("fetched_at")
        status, reason = "MEASURED", "cache"
        url = _route_url(route)
        due = True
        try:
            age = (now - datetime.fromisoformat(str(fetched_at))).total_seconds()
            due = age >= DUE_S[route]
        except (TypeError, ValueError):
            due = True
        if due and fetch:
            permitted, terms_why = terms_verdict(route, url)
            if not permitted:
                status, reason = BLOCKED_ON_TERMS, terms_why
                series = {}
            else:
                ok, rwhy = robots(url)
                if not ok:
                    status, reason = UNMEASURED, f"robots: {rwhy}"
                else:
                    try:
                        series = _fetch_route(route, ids, now, get, environ)
                        fetched_at = now.isoformat()
                        status, reason = "MEASURED", f"fetched; terms: {terms_why[:160]}"
                        _write_json(cache_f, {"fetched_at": fetched_at, "series": series})
                    except PermissionError as exc:
                        status, reason = "BLOCKED_AUTH", str(exc)
                    except HardStop as exc:
                        status, reason = "HARD_STOP", str(exc)
                    except Exception as exc:
                        status, reason = UNMEASURED, f"{type(exc).__name__}: {str(exc)[:200]}"
                    if status != "MEASURED" and series:
                        reason += f" (serving the cache fetched {fetched_at})"
        for sid in ids:
            spec = SOURCED[sid]
            data = series.get(sid) or None
            out[sid] = Fetched(sid, data=data, status=status if data or status != "MEASURED"
                               else UNMEASURED,
                               reason=reason if data else (reason or "no observations"),
                               route=route, native=spec["native"],
                               publisher=spec["publisher"], fetched_at=fetched_at)
    return out


def routes_report(got: Mapping[str, Fetched]) -> dict[str, Any]:
    """Per route: its status and reason once (the artifact's `sources` block)."""
    rep: dict[str, Any] = {}
    for f in got.values():
        if f.route and f.route != "none":
            rep.setdefault(f.route, {"status": f.status, "reason": f.reason,
                                     "fetched_at": f.fetched_at, "series": []})
            rep[f.route]["series"].append(f.series)
    for name, b in BLOCKED_ROUTES.items():
        rep[name] = {"status": BLOCKED_ON_TERMS, "reason": b["why"],
                     "missed_growth": b["missed_growth"], "series": []}
    return rep
