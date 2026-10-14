#!/usr/bin/env python3
"""GEOINT HAZARDS: public natural-hazard notices as point-in-time events (N3), the chokepoint
transit lane's status (N4), and the GEOINT source ledger (FIRMS, PortWatch, Sentinel-5P).

WHY THIS ORGAN, checked first. `research/alt_proxies.py` owns the periodic GEOINT SERIES (FIRMS
industrial heat, PortWatch ports and chokepoints) and stays their only fetcher: N4 is a widening
of its `imf_portwatch_chokepoints` row, not a second reader. What alt_proxies cannot hold is an
EVENT -- a magnitude-6 earthquake or a storm cone has no period and no release calendar, only a
publication instant -- and nothing on the tree read USGS or NHC. This organ is that reader.

N3  NATURAL-HAZARD SHOCKS, executed by `mt5desk.family_hazard_shock`:
      quake_jp / quake_tw / quake_cl   USGS M6+ inside declared boxes around Japan, Taiwan, Chile
      storm_gulf                      an NHC Atlantic-basin forecast cone touching the Gulf of
                                      Mexico production box (first advisory per storm)
    Targets: USDJPY, JPN225 (JP, TW), XCUUSD (CL), XTIUSD, XNGUSD, USDMXN (Gulf).
    PIT: `available_time` = USGS origin + PUBLICATION_SLACK (late-biased: USGS posts M6+ within
    ~20 min), or the cone's own advisory `issuance`. `first_seen_at` = when this box read it.
N4  CHOKEPOINT TRANSIT ANOMALY: alt_proxies' chokepoint transit series (7-day vs 90-day anomaly,
    its surprise_z) now map to XTIUSD, XBRUSD, XAUUSD and USDJPY; alt_proxies' release-gain test
    and direct cells do the rest. Reported here, not re-fetched.

TERMS (read 2026-10-14, quoted in TERMS_RECORD). USGS: public domain, and the GeoJSON feed "is
intended to be used as a programatic interface for applications". NWS/NHC: public domain, "may be
used without charge for any lawful purpose", with refresh-frequency guidance this organ follows
(one CurrentStorms read and at most one cone per Atlantic storm per pass). PortWatch and FIRMS
keep the terms evidence alt_proxies already records. Sentinel-5P: NEEDS_KEY (see S5P_STATUS).

TRIALS. Cells are donated through `proposer_common.donate` only for (kind, target) pairs whose
event count reaches MIN_EVENTS, with tests_run = 0: nothing here screened a cell on returns, so
nothing here is a trial. The judge charges what it judges, as for every donated cell.

    python desks/mt5/research/geoint_hazards.py --once [--dry-run] [--no-fetch] [--fixtures DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "GEOINT_HAZARDS.json"
STATE = DESK / "data" / "geoint_hazards" / "state.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
SERIES_FILE = "natural_hazard_events.csv"
SOURCE = "geoint_hazards"
UNMEASURED = "UNMEASURED"
UA = "quant-desk-geoint-hazards/1.0 (+public hazard feeds research)"
TIMEOUT = 30.0
MAX_BYTES = 16 * 1024 * 1024
#: USGS posts an M6+ solution within ~20 minutes; an hour can only be late.
PUBLICATION_SLACK = timedelta(hours=1)
MIN_MAGNITUDE = 6.0
MIN_EVENTS = 8
BACKFILL_START = "2010-01-01"

USGS_LIVE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
USGS_FDSN = "https://earthquake.usgs.gov/fdsnws/event/1/query"
NHC_CURRENT = "https://www.nhc.noaa.gov/CurrentStorms.json"

#: (min_lat, max_lat, min_lon, max_lon). Declared boxes; an event outside every box is dropped.
QUAKE_BOXES: dict[str, tuple[float, float, float, float]] = {
    "quake_jp": (24.0, 46.0, 122.0, 150.0),
    "quake_tw": (21.0, 26.5, 119.0, 123.5),
    "quake_cl": (-56.0, -17.0, -76.0, -66.0),
}
#: The Gulf of Mexico production and refining box (platforms, Louisiana/Texas refineries).
GULF_BOX = (18.0, 31.0, -98.0, -81.0)

#: Declared prior direction of each target after each kind (+1 = the instrument rises). The
#: family trades `side` x this; the mirror cell (side -1) is in the grid, so the prior is tested,
#: never assumed.
TARGETS: dict[str, dict[str, int]] = {
    "quake_jp": {"USDJPY": -1, "JPN225": -1},
    "quake_tw": {"JPN225": -1, "USDJPY": -1},
    "quake_cl": {"XCUUSD": 1},
    "storm_gulf": {"XTIUSD": 1, "XNGUSD": 1, "USDMXN": 1},
}
GRID = {"mode": ("drift", "fade"), "hold_bars": (24, 72), "side": (1, -1)}

TERMS_RECORD: dict[str, dict[str, str]] = {
    "usgs_earthquakes": {
        "verdict": "CONFIRMED",
        "terms_url": "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
        "terms_quote": ("USGS-authored or produced data and information are considered to be in "
                        "the U.S. Public Domain."),
        "credit_quote": ("When using information from USGS information products, publications, "
                         "or websites, we ask that proper credit be given."),
        "automation_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php",
        "automation_quote": ("GeoJSON is intended to be used as a programatic interface for "
                             "applications."),
        "credit": "Source: U.S. Geological Survey, Earthquake Hazards Program",
        "checked_at": "2026-10-14"},
    "nhc_current_storms": {
        "verdict": "CONFIRMED",
        "terms_url": "https://www.weather.gov/disclaimer",
        "terms_quote": ("in the public domain, unless specifically noted otherwise [...] may be "
                        "used without charge for any lawful purpose so long as you do not: claim "
                        "it is your own; use it in a manner that implies an endorsement or "
                        "affiliation with NOAA/NWS; modify its content and then present it as "
                        "official government material"),
        "automation_quote": ("Know your data refresh frequency / Request only the data that you "
                             "need / If a Web Service isn't available users should limit the "
                             "number of retries to 1 minute intervals."),
        "robots": "www.nhc.noaa.gov/robots.txt: User-agent: * / Disallow: (empty -- allowed)",
        "credit": "Source: NOAA National Hurricane Center (not subject to copyright protection)",
        "checked_at": "2026-10-14"},
}

#: Copernicus Sentinel-5P (asia_sources row `copernicus_s5p`, key_env CDSE_TOKEN). The box holds
#: CDSAPI_KEY, which is the ECMWF Climate Data Store's personal access token -- a different
#: identity system. CDSE issues its token from its own Keycloak realm against a CDSE account.
S5P_STATUS: dict[str, str] = {
    "status": "NEEDS_KEY",
    "needs": "CDSE_TOKEN (a Copernicus Data Space Ecosystem account's OAuth token)",
    "cdsapi_key_grants_cdse": "NO",
    "evidence_url": "https://documentation.dataspace.copernicus.eu/APIs/Token.html",
    "evidence_quote": ("replace “<username>” and “<password>” with your "
                       "Copernicus Data Space Ecosystem login credentials"),
    "token_endpoint": ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/"
                       "openid-connect/token"),
    "why": ("CDSAPI_KEY authenticates cds.climate.copernicus.eu (ECMWF CDS); the CDSE token page "
            "names only CDSE username/password credentials and never the CDS key"),
    "checked_at": "2026-10-14",
}


# ------------------------------------------------------------------------------- parsing
def _iso(ms: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _in(box: tuple[float, float, float, float], lat: float, lon: float) -> bool:
    return box[0] <= lat <= box[1] and box[2] <= lon <= box[3]


def parse_usgs(body: bytes, first_seen: datetime) -> list[dict[str, Any]]:
    """USGS GeoJSON (the live summary feed or an FDSN query): M6+ inside a declared box."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    out: list[dict[str, Any]] = []
    for f in doc.get("features") or [] if isinstance(doc, dict) else []:
        if not isinstance(f, dict):
            continue
        p = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or []
        try:
            mag = float(p.get("mag") or "nan")
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError, IndexError):
            continue
        origin = _iso(p.get("time"))
        if origin is None or not mag >= MIN_MAGNITUDE or str(p.get("type") or "earthquake") != \
                "earthquake":
            continue
        kind = next((k for k, box in QUAKE_BOXES.items() if _in(box, lat, lon)), None)
        if kind is None:
            continue
        avail = origin + PUBLICATION_SLACK
        out.append({"event_id": f"usgs:{f.get('id')}", "kind": kind, "region": kind[-2:].upper(),
                    "magnitude": round(mag, 2), "lat": lat, "lon": lon,
                    "event_time": origin.isoformat(timespec="seconds"),
                    "available_time": avail.isoformat(timespec="seconds"),
                    "pit_basis": "origin+publication_slack",
                    "first_seen_at": first_seen.isoformat(timespec="seconds"),
                    "source_id": "usgs_earthquakes"})
    return out


def parse_nhc_current(body: bytes) -> list[dict[str, Any]]:
    """CurrentStorms.json -> Atlantic-basin storms with a cone product (id, name, kt, cone)."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    out = []
    for s in (doc.get("activeStorms") or []) if isinstance(doc, dict) else []:
        if not isinstance(s, dict) or not str(s.get("id") or "").lower().startswith("al"):
            continue
        cone = s.get("trackCone") or {}
        if not isinstance(cone, dict) or not (cone.get("kmzFile") or cone.get("url")):
            continue
        out.append({"id": str(s["id"]).lower(), "name": s.get("name"),
                    "intensity_kt": s.get("intensity"), "classification": s.get("classification"),
                    "adv": str(cone.get("advNum") or ""), "issuance": cone.get("issuance"),
                    "kmz": cone.get("kmzFile") or cone.get("url")})
    return out


_COORDS = re.compile(r"<coordinates>(.*?)</coordinates>", re.S)


def cone_points(body: bytes) -> list[tuple[float, float]]:
    """(lat, lon) vertices of every polygon in a cone KMZ (or a bare KML)."""
    raw = body
    if raw[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                name = next((n for n in z.namelist() if n.lower().endswith(".kml")), None)
                raw = z.read(name) if name else b""
        except (zipfile.BadZipFile, KeyError, OSError):
            return []
    pts: list[tuple[float, float]] = []
    for block in _COORDS.findall(raw.decode("utf-8", errors="replace")):
        for tok in block.split():
            parts = tok.split(",")
            try:
                pts.append((float(parts[1]), float(parts[0])))
            except (IndexError, ValueError):
                continue
    return pts


def _issued(raw: Any, fallback: datetime) -> tuple[datetime, str]:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return (t if t.tzinfo else t.replace(tzinfo=UTC)), "advisory_issuance"
    except (TypeError, ValueError):
        return fallback, "first_seen (issuance unreadable)"


def storm_event(storm: dict[str, Any], cone: bytes, first_seen: datetime) -> dict[str, Any] | None:
    """A storm_gulf event when the cone touches the Gulf box; None otherwise."""
    pts = cone_points(cone)
    if not any(_in(GULF_BOX, lat, lon) for lat, lon in pts):
        return None
    issued, basis = _issued(storm.get("issuance"), first_seen)
    return {"event_id": f"nhc:{storm['id']}", "kind": "storm_gulf", "region": "GULF",
            "magnitude": float(storm.get("intensity_kt") or 0.0), "lat": None, "lon": None,
            "event_time": issued.isoformat(timespec="seconds"),
            "available_time": issued.isoformat(timespec="seconds"),
            "pit_basis": basis, "first_seen_at": first_seen.isoformat(timespec="seconds"),
            "source_id": "nhc_current_storms", "advisory": storm.get("adv")}


# ------------------------------------------------------------------------------- the store
def merge(store: dict[str, dict[str, Any]], rows: list[dict[str, Any]]) -> int:
    """Append-only by event_id: the FIRST sighting is kept (a storm's first Gulf cone is the
    event; later advisories are not new events)."""
    added = 0
    for r in rows:
        if r["event_id"] not in store:
            store[r["event_id"]] = r
            added += 1
    return added


def write_series(store: dict[str, dict[str, Any]], series_dir: Path = SERIES_DIR) -> str | None:
    if not store:
        return None
    import pandas as pd
    series_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(store.values(), key=lambda r: r["available_time"])
    df = pd.DataFrame([{**r, "published_time": r["available_time"],
                        "retrieval_time": r["first_seen_at"], "revision_time": None,
                        "vintage_id": hashlib.sha1(r["event_id"].encode()).hexdigest()[:16]}
                       for r in rows])
    target = series_dir / SERIES_FILE
    tmp = target.with_suffix(f".tmp{os.getpid()}")
    df.to_csv(tmp, index=False)
    os.replace(tmp, target)
    return target.name


# ------------------------------------------------------------------------------- fetching
def _tls() -> Any:
    try:
        from research import asia_collector
        make: Any = asia_collector._tls_context
        return make()
    except Exception:
        return None


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_tls()) as r:
        body: bytes = r.read(MAX_BYTES)
        return body


def fdsn_url(kind: str, start: str, end: str) -> str:
    lo_lat, hi_lat, lo_lon, hi_lon = QUAKE_BOXES[kind]
    q = {"format": "geojson", "starttime": start, "endtime": end,
         "minmagnitude": MIN_MAGNITUDE, "minlatitude": lo_lat, "maxlatitude": hi_lat,
         "minlongitude": lo_lon, "maxlongitude": hi_lon, "orderby": "time-asc"}
    return f"{USGS_FDSN}?{urllib.parse.urlencode(q)}"


def collect(store: dict[str, dict[str, Any]], state: dict[str, Any], now: datetime, *,
            fetch: bool, fixtures: Path | None, deadline: float,
            getter: Any = http_get) -> dict[str, Any]:
    """One pass: the live USGS feed, a one-time FDSN backfill per box, the NHC storms."""
    rec: dict[str, Any] = {"requests": 0, "errors": [], "added": 0}

    def get(url: str, fixture: str) -> bytes | None:
        if time.monotonic() > deadline:
            rec["errors"].append("budget reached: owed to the next pass")
            return None
        if fixtures is not None:
            p = fixtures / fixture
            return p.read_bytes() if p.exists() else None
        if not fetch:
            return None
        rec["requests"] += 1
        try:
            return bytes(getter(url))
        except Exception as exc:
            rec["errors"].append(f"{fixture}: {type(exc).__name__}: {str(exc)[:100]}")
            return None

    body = get(USGS_LIVE, "usgs_4.5_day.geojson")
    if body:
        rec["added"] += merge(store, parse_usgs(body, now))
    done = state.setdefault("backfilled", {})
    for kind in QUAKE_BOXES:
        if done.get(kind):
            continue
        body = get(fdsn_url(kind, BACKFILL_START, now.date().isoformat()),
                   f"usgs_fdsn_{kind}.geojson")
        if body is None:
            continue
        rec["added"] += merge(store, parse_usgs(body, now))
        if fixtures is None and fetch:
            done[kind] = now.isoformat(timespec="seconds")
    body = get(NHC_CURRENT, "nhc_current_storms.json")
    storms = parse_nhc_current(body) if body else []
    rec["atlantic_storms"] = len(storms)
    for s in storms:
        if f"nhc:{s['id']}" in store:
            continue                                   # first Gulf cone already recorded
        cone = get(str(s["kmz"]), f"nhc_cone_{s['id']}.kmz")
        if cone is None:
            continue
        ev = storm_event(s, cone, now)
        if ev is not None:
            rec["added"] += merge(store, [ev])
    return rec


# ------------------------------------------------------------------------------- cells
def counts(store: dict[str, dict[str, Any]]) -> dict[str, int]:
    out = dict.fromkeys(TARGETS, 0)
    for r in store.values():
        out[r["kind"]] = out.get(r["kind"], 0) + 1
    return out


def n3_cells(store: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    n = counts(store)
    out: list[dict[str, Any]] = []
    for kind, targets in TARGETS.items():
        for sym, prior in targets.items():
            for mode in GRID["mode"]:
                for hold in GRID["hold_bars"]:
                    for side in GRID["side"]:
                        params = {"symbol": sym, "kind": kind, "prior_side": prior,
                                  "mode": mode, "hold_bars": hold, "side": side,
                                  "clock": "utc"}
                        cid = hashlib.sha1(json.dumps(params, sort_keys=True).encode()
                                           ).hexdigest()[:12]
                        out.append({
                            "source": SOURCE, "kind": "hypothesis", "symbol": sym,
                            "symbols": [sym], "family": "hazard_shock", "params": params,
                            "cell": f"{sym}.hazard_shock.{cid}", "url": "",
                            "title": f"{kind} notice -> {sym} {mode} {hold}h side {side:+d}",
                            "available_time": now.isoformat(timespec="seconds"),
                            "event_time": now.isoformat(timespec="seconds"),
                            "n_events": n.get(kind, 0),
                            "status": "DONATABLE" if n.get(kind, 0) >= MIN_EVENTS
                            else f"OWED: {n.get(kind, 0)} < {MIN_EVENTS} events",
                            "mechanism": ("a public hazard notice forces holders of the named "
                                          "physical exposure to hedge before damage is measured"),
                            "falsifier": (f"{mode} returns on {sym} over {hold} bars after "
                                          f"{kind} notices are indistinguishable from the same "
                                          "bars at shifted dates")})
    return out


#: N4: what alt_proxies now maps the chokepoint transit anomaly to.
def n4_status() -> dict[str, Any]:
    try:
        import research.alt_proxies as ap
    except Exception as exc:
        return {"status": f"{UNMEASURED}: alt_proxies import failed ({type(exc).__name__})"}
    src = ap.BY_ID.get("imf_portwatch_chokepoints")
    if src is None:
        return {"status": f"{UNMEASURED}: imf_portwatch_chokepoints absent"}
    ev = ap.TERMS_EVIDENCE.get(src.id) or {}
    return {"organ": "desks/mt5/research/alt_proxies.py (source imf_portwatch_chokepoints)",
            "status": ap.status_of(src), "terms": src.terms,
            "terms_url": ev.get("terms_url"), "terms_quote": ev.get("terms_quote"),
            "instruments": src.instruments, "signal_series": list(src.signal_series),
            "transform": src.transform,
            "cells": "alt_proxies.direct_cells: exogenous_conditioner on surprise_z (level_z, "
                     "|z| >= 1), side = the measured IC sign, after the release-gain test"}


def geoint_sources() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        import research.alt_proxies as ap
        for sid in ("cn_firms_industrial", "imf_portwatch_ports", "imf_portwatch_chokepoints"):
            s = ap.BY_ID[sid]
            ev = ap.TERMS_EVIDENCE.get(sid) or {}
            out[sid] = {"status": ap.status_of(s), "terms": s.terms,
                        "terms_quote": ev.get("terms_quote") or ap.TERMS.get(sid, ("", ""))[1],
                        "key_env": s.key_env,
                        "key_present": (bool(os.environ.get(s.key_env)) if s.key_env else None),
                        "clock": "hourly_cycle:alt_proxies"}
    except Exception as exc:
        out["alt_proxies"] = f"{UNMEASURED}: {type(exc).__name__}"
    out["copernicus_s5p"] = S5P_STATUS
    return out


# ------------------------------------------------------------------------------- the pass
def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, p)


def run(*, budget_s: float = 120.0, fetch: bool = True, fixtures: Path | None = None,
        dry_run: bool = False, donate: bool = True, now: datetime | None = None,
        report: Path = REPORT, state_path: Path = STATE, series_dir: Path = SERIES_DIR,
        style_novelty_path: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + budget_s * 0.7
    state = _read(state_path, {})
    store: dict[str, dict[str, Any]] = state.setdefault("events", {})
    rec = collect(store, state, now, fetch=fetch, fixtures=fixtures, deadline=deadline)
    cells = n3_cells(store, now)
    donatable = [c for c in cells if c["status"] == "DONATABLE"]
    donation: dict[str, Any] = {"donated": 0}
    if donate and not dry_run and fixtures is None and donatable:
        from research import proposer_common
        path = proposer_common.donate(SOURCE, donatable, tests_run=0)
        donation = {"donated": len(donatable) if path else 0, "path": str(path or "")}
    written = None if dry_run else write_series(store, series_dir)
    from research.novel_style_lanes import STYLE_NOVELTY, novelty
    nov = novelty(style_novelty_path or STYLE_NOVELTY, declared=DECLARED)
    doc = {
        "at": now.isoformat(timespec="seconds"), "organ": SOURCE,
        "mode": "fixtures" if fixtures is not None else ("fetch" if fetch else "no_fetch"),
        "terms": TERMS_RECORD, "collect": rec,
        "N3": {"name": "natural-hazard shock lane (USGS M6+ JP/TW/CL, NHC Gulf cones)",
               "family": "hazard_shock",
               "family_module": "desks/mt5/mt5desk/family_hazard_shock.py",
               "events_by_kind": counts(store), "n_events": len(store),
               "lake_written": written, "n_cells": len(cells),
               "n_donatable": len(donatable), "donation": donation,
               "cells_preview": cells[:8], "trials_charged_here": 0,
               "nhc_backfill": ("UNMEASURED: CurrentStorms.json is live-only; storm history "
                                "accrues forward from the first pass")},
        "N4": {"name": "chokepoint transit anomaly -> oil, gold, USDJPY", **n4_status()},
        "geoint_sources": geoint_sources(),
        "novelty": nov,
        "live_yield": ("UNMEASURED until the trading box runs this leg: the authoring container's "
                       "proxy refuses earthquake.usgs.gov and www.nhc.noaa.gov"),
    }
    if not dry_run:
        _atomic(state_path, state)
        _atomic(report, doc)
    return doc


#: N3/N4 declared closest known styles, for `novel_style_lanes.novelty`.
DECLARED: dict[str, dict[str, Any]] = {
    "N3": {"family": "hazard_shock", "closest_styles": ["abs_window", "reversal_1bar"],
           "why": ("drift trades a declared direction after an exogenous notice (no price "
                   "window chooses it); fade is a post-shock reversal, the nearest known style")},
    "N4": {"family": "exogenous_conditioner", "closest_styles": ["trend_20d"],
           "why": ("a slow physical-flow anomaly held for days: if its sign tracks the trailing "
                   "month it is trend in disguise")},
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--budget-s", type=float, default=120.0)
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, fetch=not a.no_fetch, fixtures=a.fixtures, dry_run=a.dry_run)
    print(json.dumps({"events": doc["N3"]["events_by_kind"], "cells": doc["N3"]["n_cells"],
                      "donatable": doc["N3"]["n_donatable"], "errors": doc["collect"]["errors"],
                      "N4": doc["N4"].get("status"),
                      "novelty": {k: v.get("verdict")
                                  for k, v in doc["novelty"]["lanes"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
