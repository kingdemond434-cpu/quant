#!/usr/bin/env python3
"""ERA5 READER -- Copernicus Climate Data Store reanalysis as point-in-time weather series for the
MT5 soft-commodity and gas instruments, fed to all three uses.

WHAT IT READS. ERA5 (ECMWF's global reanalysis, hourly since 1940) at a handful of representative
points in each of SEVEN regions (`data/era5_regions.json`: US Corn Belt, US Plains wheat, Brazil
coffee, Brazil cane, West Africa cocoa, Europe gas demand, US gas demand), through the CDS API's
single-point time series product. Hourly 2 m temperature and total precipitation become daily mean/min/max and
precipitation per point; points become a weighted region day; the region day becomes the fields
in `FIELDS` -- temperature anomaly, heating/cooling degree days and their anomalies, 30-day
precipitation and its anomaly, frost days. An anomaly is against the climatology of PRIOR years
only (the same calendar window, +-7 days), so no value ever leans on its own future.

POINT IN TIME. A day's ERA5 value is published about five days after the day (ERA5T), so every
row carries `event_time` = the valid date and `available_time` = the end of that date plus
`ERA5_LAG_DAYS`, stamped by `libs.data.pit_stamp.available_at` -- a rule that can only be late.
`first_seen_at` is when this box first read the value; the first value seen is kept (a later
ERA5-final revision never overwrites it), and history fetched today is marked `backfill`.
Fetching is incremental: each point keeps a cursor in `data/era5/state.json` and a pass asks
only for the days after it, never a day younger than the release lag.

THE KEY. Read only through `libs.ops.env_keys.read_key` (the Windows machine/user registry, then
process env, so a `setx /M CDSAPI_KEY ...` reaches a resident started before it). The client is
`cdsapi.Client(url=read_key('CDSAPI_URL') or CDS_URL, key=read_key('CDSAPI_KEY'))`, imported
lazily (extra `climate` in pyproject). A missing key is BLOCKED_AUTH, a missing package
UNAVAILABLE -- a named state in the report, never a crash, never invented data. No key value is
ever printed, logged or written; every error text is redacted before it is recorded.

TERMS, FAIL CLOSED (this repo's convention: TERMS / TERMS_EVIDENCE, BLOCKED_ON_TERMS). Nothing is
fetched unless the licence evidence is `confirmed`. The evidence on file off-box is incomplete:
the CDS host was unreachable from the build container (proxy CONNECT 403), so the licence that
binds ERA5 could not be read there. `--confirm-terms` on the box fetches the dataset's own licence
from the CDS catalogue, finds the permitting clause (free, worldwide, use including commercial,
with attribution) and writes it verbatim, with its sha256, to `data/era5/terms_evidence.json`.
Only a stored quote that the matcher re-reads as permitting counts; anything else is
BLOCKED_ON_TERMS. A CDS "licence not accepted" reply is BLOCKED_ON_TERMS:licence_not_accepted.

THE THREE USES (the dataset rule: every dataset feeds cells, conditioners and allocator inputs):
  direct cells     each mapped (region, field, instrument) is gain-tested against a shifted-release
                   placebo (`libs.research.release_gain`), every tested cell is charged as a trial,
                   and PASSING cells are donated as `exogenous_conditioner` recipes through
                   `proposer_common.donate` (the stamped, lane-filtered door). Side = measured IC
                   sign, never the prior.
  conditioning     every field lands in the lake (`data/lake/series/era5_<region>__<field>.csv`, the
                   envelope `mt5desk.family_exogenous_conditioner` reads) and in the axis door
                   (`data/axes/era5_<region>.json`, read by alpha_dsl / world_model /
                   representation_forge).
  allocation       `reports/ERA5_ALLOCATION_INTEL.json`: per instrument, the PIT-available state
                   of every mapped field. Read-only; it sizes nothing.
And the paid-substitute engine: each region's headline field is written as
`psub_era5_<region>` and the library rows `era5_<region>` name it, so the engine judges ERA5 as a
free substitute for paid weather data by its own correlation check (COVERED only at a measured
correlation >= 0.5 to a paid set's public sample; otherwise MATCHED_UNVERIFIED, research lane).

    python research/era5_reader.py --once [--budget-s 600] [--no-fetch] [--dry-run]
    python research/era5_reader.py --confirm-terms
    python research/era5_reader.py --confirm-terms --terms-text <saved licence> --terms-url <url>
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib
import io
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.request
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "era5_reader"
LEG = "era5_reader"
#: The leg's own artifact on the desk (DEFAULT_PATHS.report), declared as a constant so the
#: component registry and the runtime attestation can name it (desks/mt5/ops/components.py).
REPORT = DESK / "reports" / "ERA5_STATUS.json"
UNMEASURED = "UNMEASURED"
KEY_NAME = "CDSAPI_KEY"
URL_NAME = "CDSAPI_URL"
CDS_URL = "https://cds.climate.copernicus.eu/api"
#: ERA5T reaches the CDS about five days behind real time. The stamp may only be late.
ERA5_LAG_DAYS = 5
#: Statuses a pass can end in. Each is a named state in the report; none is a silent skip.
OK = "OK"
BLOCKED_AUTH = "BLOCKED_AUTH"
UNAVAILABLE = "UNAVAILABLE"
BLOCKED_ON_TERMS = "BLOCKED_ON_TERMS"
ERROR = "ERROR"
PARTIAL = "PARTIAL"
#: The aggregates a region publishes. Anything a region config names must be one of these.
FIELDS: tuple[str, ...] = (
    "t2m_c", "t2m_anom_7d", "hdd_7d", "cdd_7d", "hdd_anom_7d", "cdd_anom_7d",
    "precip_30d_mm", "precip_anom_30d", "frost_days_7d")
#: A day is a frost day when the daily minimum 2 m temperature is at or below this (coffee leaf
#: damage starts around 2 C of air temperature; the leaf runs colder than the screen).
FROST_TMIN_C = 2.0
#: Hours a point-day needs before it is a day at all (ERA5 gives 24; a partial day is dropped).
MIN_HOURS = 22
#: The share of a region's point weight that must be present for the region to have that day.
MIN_WEIGHT_SHARE = 0.5
#: Gain test: post-release window in H1 bars (~5 trading days), like the alt-proxies organ.
HORIZON_BARS = 120
#: Days of each mapped field published to the axis door (the lake keeps the whole history).
AXIS_DAYS = 730
#: A field older than this (days since available) no longer describes "now" for allocation intel.
STALE_DAYS = 10
#: The licence matcher lives in `libs.data.licence_evidence` (shared with the paid-substitute
#: engine): only Copernicus/ECMWF hosts count, and a negated or prohibiting clause never
#: confirms.
from libs.data import licence_evidence as _lic  # noqa: E402

CC_BY_GRANT = _lic.CC_BY_GRANT
TERMS_VALUES = ("confirmed", "to_confirm", "refused")

#: THE TERMS GATE, FAIL CLOSED. `confirmed` only from verified evidence. Off-box this reads
#: `to_confirm`: the binding licence text could not be read (see TERMS_EVIDENCE). The box's own
#: evidence file (`--confirm-terms`) is the only thing that can move it.
TERMS: dict[str, tuple[str, str]] = {
    "era5_cds": ("to_confirm",
                 "needs-box-confirmation: ERA5's CDS licence page was unreachable from the build "
                 "container (CONNECT 403); the box fetches and quotes it with --confirm-terms"),
}
_CHK = "2026-10-06"
#: What was verified off-box, verbatim, and what was not. `terms_quote` below is the CC BY 4.0
#: grant clause as published in SPDX's license-list-data (text/CC-BY-4.0.txt, sha256 recorded):
#: it is quoted because it was READ, not because ERA5 is shown to be under it -- that binding is
#: the part the box must confirm from the CDS catalogue's own licence link.
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "era5_cds": {
        "terms_url": "https://cds.climate.copernicus.eu/datasets/"
                     "reanalysis-era5-single-levels-timeseries?tab=download",
        "terms_quote": "(not readable from the build container: cds.climate.copernicus.eu, "
                       "www.copernicus.eu and confluence.ecmwf.int CONNECT 403 through the proxy)",
        "candidate_licence": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "candidate_licence_url": "https://raw.githubusercontent.com/spdx/license-list-data/main/"
                                 "text/CC-BY-4.0.txt",
        "candidate_licence_sha256": "d557539df68e771cc1eedcc91d13f70fca930e508d11eedcafa4b15db49e3744",
        "candidate_grant_quote": (
            "Subject to the terms and conditions of this Public License, the Licensor hereby "
            "grants You a worldwide, royalty-free, non-sublicensable, non-exclusive, irrevocable "
            "license to exercise the Licensed Rights in the Licensed Material to: A. reproduce "
            "and Share the Licensed Material, in whole or in part; and B. produce, reproduce, and "
            "Share Adapted Material."),
        "candidate_attribution_quote": (
            "If You Share the Licensed Material (including in modified form), You must: A. "
            "retain the following if it is supplied by the Licensor with the Licensed Material: "
            "i. identification of the creator(s) of the Licensed Material and any others "
            "designated to receive attribution"),
        "cdsapi_readme_quote": ("Remember to agree to the Terms and Conditions of every dataset "
                                "that you intend to download."),
        "cdsapi_readme_url": "https://raw.githubusercontent.com/ecmwf/cdsapi/master/README.rst",
        "judgement": ("needs-box-confirmation, FAIL CLOSED: that ERA5 is licensed under CC BY 4.0 "
                      "(free, worldwide, commercial use allowed, attribution required) is the "
                      "expected answer but was NOT verified from a Copernicus page; the reader "
                      "fetches nothing until --confirm-terms quotes the CDS licence itself"),
        "robots": "not read (host unreachable)",
        "checked_at": _CHK},
}
#: The attribution every derived artifact carries (CC BY 4.0 / Copernicus licence both require
#: the source to be credited).
ATTRIBUTION = ("Contains modified Copernicus Climate Change Service information (ERA5, "
               "Hersbach et al. 2023, Copernicus Climate Change Service (C3S) Climate Data Store)")


@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def regions(self) -> Path:
        return self.desk / "data" / "era5_regions.json"

    @property
    def state(self) -> Path:
        return self.desk / "data" / "era5" / "state.json"

    @property
    def terms_evidence(self) -> Path:
        return self.desk / "data" / "era5" / "terms_evidence.json"

    @property
    def points(self) -> Path:
        return self.desk / "data" / "lake" / "era5" / "points"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def axes(self) -> Path:
        return self.desk / "data" / "axes"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "ERA5_STATUS.json"

    @property
    def allocation_intel(self) -> Path:
        return self.desk / "reports" / "ERA5_ALLOCATION_INTEL.json"

    @property
    def charges(self) -> Path:
        return self.desk / "data" / "era5" / "trial_charges.json"

    @property
    def null_trials(self) -> Path:
        return self.desk / "data" / "null_pass_trials.jsonl"


DEFAULT_PATHS = Paths(DESK)


# ================================================================================== io
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    for i in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: a held destination is retried
            time.sleep(0.2 * (i + 1))
    path.write_text(tmp.read_text("utf-8"), "utf-8")
    with contextlib.suppress(OSError):
        tmp.unlink()


_UUIDISH = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                      r"[0-9a-fA-F]{12}")


def redact(text: Any, secret: str | None = None) -> str:
    """An error text safe to record: the key (and anything shaped like a CDS token) removed."""
    s = str(text)
    if secret:
        s = s.replace(secret, "<redacted>")
    return _UUIDISH.sub("<redacted>", s)[:300]


# ============================================================================ regions
_ID = re.compile(r"^[a-z0-9_]{1,48}$")


def load_regions(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or DEFAULT_PATHS.regions, {})
    return doc if isinstance(doc, dict) else {}


def region_config_errors(doc: Mapping[str, Any], universe: Iterable[str] | None = None
                         ) -> list[str]:
    """Every defect in a regions document, by name. Empty means usable."""
    errs: list[str] = []
    regions = doc.get("regions")
    if not isinstance(regions, list) or not regions:
        return ["no regions"]
    uni = set(universe) if universe is not None else None
    seen: set[str] = set()
    pseen: set[str] = set()
    for r in regions:
        rid = str((r or {}).get("id") or "")
        if not _ID.match(rid):
            errs.append(f"region id {rid!r} is not a short slug")
        if rid in seen:
            errs.append(f"duplicate region {rid}")
        seen.add(rid)
        pts = r.get("points") or []
        if not pts:
            errs.append(f"{rid}: no points")
        for p in pts:
            pid = str(p.get("id") or "")
            if not _ID.match(pid) or pid in pseen:
                errs.append(f"{rid}: bad or duplicate point id {pid!r}")
            pseen.add(pid)
            try:
                lat, lon, w = float(p["lat"]), float(p["lon"]), float(p["weight"])
            except (KeyError, TypeError, ValueError):
                errs.append(f"{rid}/{pid}: lat, lon and weight must be numbers")
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180) or w <= 0:
                errs.append(f"{rid}/{pid}: out of range")
        inst = r.get("instruments") or {}
        if not inst:
            errs.append(f"{rid}: maps no instrument")
        for field, m in inst.items():
            if field not in FIELDS:
                errs.append(f"{rid}: unknown field {field}")
            for sym, sign in (m or {}).items():
                if sign not in (1, -1):
                    errs.append(f"{rid}: {field}->{sym} prior must be +1 or -1")
                if uni is not None and sym not in uni:
                    errs.append(f"{rid}: {sym} is not in the MT5 universe")
        if r.get("headline") not in FIELDS:
            errs.append(f"{rid}: headline {r.get('headline')!r} is not a field")
        try:
            float(r.get("hdd_base_c"))
        except (TypeError, ValueError):
            errs.append(f"{rid}: hdd_base_c missing")
    return errs


def lag_days(doc: Mapping[str, Any]) -> int:
    """The release lag. A config may make it LONGER, never shorter than ERA5_LAG_DAYS."""
    try:
        return max(ERA5_LAG_DAYS, int(doc.get("release_lag_days") or ERA5_LAG_DAYS))
    except (TypeError, ValueError):
        return ERA5_LAG_DAYS


def lake_id(region_id: str, field: str) -> str:
    return f"era5_{region_id}__{field}"


def substitute_id(region_id: str) -> str:
    """The paid-substitute library row id; the engine's dataset_id is `psub_` + this."""
    return f"era5_{region_id}"


def psub_lake_id(region_id: str) -> str:
    return f"psub_{substitute_id(region_id)}"


# ============================================================================== terms
def permitting_clause(text: str, url: str | None) -> dict[str, str] | None:
    """The permitting clause (free, worldwide, commercial use, attribution) of a licence text
    SERVED BY ``url``, verbatim, or None -- `libs.data.licence_evidence.permitting_clause`. Fail
    closed: a non-Copernicus/ECMWF host, a non-commercial restriction, or a clause that negates
    or prohibits anything is never accepted."""
    return _lic.permitting_clause(text, url)


def clause_holds(kind: str, quote: str, url: str | None) -> bool:
    """Re-read a STORED quote against its URL: does it still say what was accepted?"""
    return _lic.clause_holds(kind, quote, url)


def terms_status(paths: Paths = DEFAULT_PATHS) -> tuple[str, dict[str, Any]]:
    """(verdict, evidence). `confirmed` ONLY when the box's evidence file passes
    `licence_evidence.verified`: an allowed host, a quote that re-reads as permitting with no
    prohibition, a hash and a date. A file that merely says "confirmed" is not evidence."""
    static = TERMS["era5_cds"][0]
    ev = _read_json(paths.terms_evidence, None)
    if not isinstance(ev, dict):
        return static, {"why": TERMS["era5_cds"][1], "evidence": TERMS_EVIDENCE["era5_cds"]}
    verdict = str(ev.get("verdict") or "").lower()
    if verdict == "refused":
        return "refused", ev
    if verdict == "confirmed":
        ok, why = _lic.verified(ev)
        if ok:
            return "confirmed", ev
        return "to_confirm", {**ev, "why": f"evidence file says confirmed but {why}: fail closed"}
    return "to_confirm", ev


def _licence_links(doc: Any) -> list[str]:
    out: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            href = str(x.get("href") or "")
            rel = str(x.get("rel") or "").lower()
            if href.startswith("http") and (rel in ("license", "licence")
                                            or "licen" in href.lower()
                                            or "licen" in str(x.get("title") or "").lower()):
                out.append(href)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(doc)
    return list(dict.fromkeys(out))


def _http_get(url: str, timeout: float = 30.0) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk-era5-reader/1 (terms)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return int(r.status), str(r.headers.get("Content-Type") or ""), r.read(8 * 1024 * 1024)


def _text_of(ctype: str, body: bytes) -> str | None:
    if body[:4] == b"%PDF" or "pdf" in ctype:
        return None
    text = body.decode("utf-8", errors="replace")
    if "json" in ctype or text.lstrip().startswith(("{", "[")):
        with contextlib.suppress(ValueError):
            vals: list[str] = []

            def walk(x: Any) -> None:
                if isinstance(x, dict):
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
                elif isinstance(x, str):
                    vals.append(x)
            walk(json.loads(text))
            return " ".join(vals)
    return re.sub(r"<[^>]+>", " ", text)


def confirm_terms(paths: Paths = DEFAULT_PATHS, *, dataset: str | None = None,
                  get: Callable[[str], tuple[int, str, bytes]] = _http_get,
                  text_file: Path | None = None, text_url: str | None = None,
                  now: datetime | None = None) -> dict[str, Any]:
    """Fetch ERA5's licence from the CDS catalogue (or read a saved copy), find the permitting
    clause, and write the evidence file. Writes `confirmed` only with a verbatim quote."""
    now = now or _now()
    regions = load_regions(paths.regions)
    ds = dataset or str((regions.get("dataset") or {}).get("name") or "")
    tried: list[dict[str, Any]] = []
    bodies: list[tuple[str, bytes, str]] = []
    if text_file is not None:
        if _lic.allowed_url(text_url):
            bodies.append((str(text_url), text_file.read_bytes(), "text"))
        else:
            tried.append({"url": text_url or f"file:{text_file.name}",
                          "rejected": "a saved licence text counts only with --terms-url on a "
                                      "Copernicus/ECMWF https host"})
    else:
        base = CDS_URL
        with contextlib.suppress(Exception):
            from libs.ops.env_keys import read_key
            base = read_key(URL_NAME) or CDS_URL
        coll = f"{base.rstrip('/')}/catalogue/v1/collections/{ds}"
        try:
            st, ct, body = get(coll)
            tried.append({"url": coll, "status": st})
            links = _licence_links(json.loads(body.decode("utf-8", errors="replace")))
        except Exception as exc:
            tried.append({"url": coll, "error": redact(f"{type(exc).__name__}: {exc}")})
            links = []
        for u in links:
            if not _lic.allowed_url(u):
                tried.append({"url": u, "rejected": "not a Copernicus/ECMWF https host"})
                continue
            try:
                st, ct, body = get(u)
                tried.append({"url": u, "status": st, "content_type": ct})
                bodies.append((u, body, ct))
            except Exception as exc:
                tried.append({"url": u, "error": redact(f"{type(exc).__name__}: {exc}")})
    ev: dict[str, Any] = {"dataset": ds, "checked_at": _iso(now), "tried": tried,
                          "verdict": "to_confirm"}
    for url, body, ct in bodies:
        text = _text_of(ct, body)
        if text is None:
            ev.setdefault("unread", []).append({"url": url, "why": "PDF: no text extractor on "
                                                                  "this box; read it by hand"})
            continue
        clause = permitting_clause(text, url)
        if clause:
            ev.update({"verdict": "confirmed", "terms_url": url, "kind": clause["kind"],
                       "terms_quote": clause["quote"],
                       "sha256": hashlib.sha256(body).hexdigest(),
                       "attribution": ATTRIBUTION})
            break
    if ev["verdict"] == "confirmed" and not _lic.verified(ev)[0]:
        ev["verdict"] = "to_confirm"
    if ev["verdict"] != "confirmed":
        ev["why"] = ("no permitting clause (free, worldwide, commercial use, attribution) was "
                     "found in the licence text read: BLOCKED_ON_TERMS until one is")
    _atomic(paths.terms_evidence, ev)
    return ev


# ============================================================================= client
def make_client(*, read: Callable[[str], str | None] | None = None,
                importer: Callable[[str], Any] = importlib.import_module
                ) -> tuple[Any, str, str]:
    """(client, status, why). The key is read through `read_key` only and never echoed."""
    if read is None:
        try:
            from libs.ops.env_keys import read_key as read
        except Exception as exc:
            return None, UNAVAILABLE, f"libs.ops.env_keys unavailable: {type(exc).__name__}"
    try:
        cdsapi = importer("cdsapi")
    except Exception as exc:
        return None, UNAVAILABLE, (f"cdsapi not importable ({type(exc).__name__}); install the "
                                   "pyproject extra `climate`")
    key = read(KEY_NAME)
    if not key:
        return None, BLOCKED_AUTH, f"{KEY_NAME} is not set (process env or machine registry)"
    try:
        client = cdsapi.Client(url=read(URL_NAME) or CDS_URL, key=key, quiet=True,
                               progress=False)
    except TypeError:
        client = cdsapi.Client(url=read(URL_NAME) or CDS_URL, key=key)
    except Exception as exc:
        return None, BLOCKED_AUTH, redact(f"client refused: {type(exc).__name__}: {exc}", key)
    return client, OK, "client ready"


def classify_error(exc: BaseException, key: str | None = None) -> tuple[str, str]:
    msg = redact(f"{type(exc).__name__}: {exc}", key)
    low = msg.lower()
    if "licen" in low or "terms" in low:
        return f"{BLOCKED_ON_TERMS}:licence_not_accepted", msg
    if any(w in low for w in ("401", "403", "unauthor", "authentic", "api key", "token",
                              "forbidden")):
        return BLOCKED_AUTH, msg
    return ERROR, msg


# ============================================================================ parsing
_TIME_COLS = ("valid_time", "time", "date", "datetime", "timestamp")
_T_COLS = ("t2m", "2m_temperature", "2t", "temperature_2m")
_P_COLS = ("tp", "total_precipitation", "precipitation")


def _csv_tables(raw: bytes) -> list[list[dict[str, str]]]:
    if raw[:2] == b"PK":
        out = []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    out.append(list(csv.DictReader(io.StringIO(z.read(n).decode("utf-8-sig")))))
        return out
    return [list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))]


def _col(row: Mapping[str, Any], names: Iterable[str]) -> str | None:
    keys = {k.strip().lower(): k for k in row}
    for n in names:
        if n in keys:
            return keys[n]
    return None


def parse_hourly(raw: bytes) -> dict[datetime, dict[str, float]]:
    """{UTC hour: {"t2m_c", "tp_mm"}} from a CDS time-series CSV (or a zip of them, one per
    variable). Kelvin is detected by magnitude; precipitation metres become millimetres."""
    hours: dict[datetime, dict[str, float]] = {}
    for table in _csv_tables(raw):
        if not table:
            continue
        tc = _col(table[0], _TIME_COLS)
        if tc is None:
            continue
        t_col, p_col = _col(table[0], _T_COLS), _col(table[0], _P_COLS)
        for r in table:
            try:
                ts = datetime.fromisoformat(str(r[tc]).replace("Z", "+00:00"))
            except ValueError:
                continue
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
            e = hours.setdefault(ts, {})
            for col, name in ((t_col, "t2m"), (p_col, "tp")):
                if col is None:
                    continue
                with contextlib.suppress(TypeError, ValueError):
                    v = float(r[col])
                    if math.isfinite(v):
                        e[name] = v
    if not hours:
        return {}
    temps = sorted(e["t2m"] for e in hours.values() if "t2m" in e)
    kelvin = bool(temps) and temps[len(temps) // 2] > 150
    out: dict[datetime, dict[str, float]] = {}
    for ts, e in hours.items():
        row: dict[str, float] = {}
        if "t2m" in e:
            row["t2m_c"] = e["t2m"] - 273.15 if kelvin else e["t2m"]
        if "tp" in e:
            row["tp_mm"] = max(0.0, e["tp"] * 1000.0)
        if row:
            out[ts] = row
    return out


def daily(hours: Mapping[datetime, Mapping[str, float]]) -> dict[date, dict[str, float]]:
    """Complete UTC days only (>= MIN_HOURS hours with a temperature)."""
    by: dict[date, list[Mapping[str, float]]] = {}
    for ts, e in hours.items():
        by.setdefault(ts.date(), []).append(e)
    out: dict[date, dict[str, float]] = {}
    for d, rows in sorted(by.items()):
        t = [r["t2m_c"] for r in rows if "t2m_c" in r]
        p = [r["tp_mm"] for r in rows if "tp_mm" in r]
        if len(t) < MIN_HOURS or len(p) < MIN_HOURS:
            continue
        out[d] = {"t2m_mean": round(sum(t) / len(t), 4), "t2m_min": round(min(t), 4),
                  "t2m_max": round(max(t), 4), "precip_mm": round(sum(p), 4)}
    return out


# ======================================================================= point store
POINT_COLS = ("date", "t2m_mean", "t2m_min", "t2m_max", "precip_mm", "first_seen_at")


def read_point(paths: Paths, pid: str) -> dict[date, dict[str, Any]]:
    p = paths.points / f"{pid}.csv"
    out: dict[date, dict[str, Any]] = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                d = date.fromisoformat(r["date"])
                out[d] = {k: float(r[k]) for k in POINT_COLS[1:5]}
                out[d]["first_seen_at"] = r.get("first_seen_at") or ""
            except (KeyError, ValueError):
                continue
    return out


def merge_point(paths: Paths, pid: str, days: Mapping[date, Mapping[str, float]],
                seen_at: datetime) -> dict[str, int]:
    """Append-only: the first value seen for a day is kept; a revision is counted, not written."""
    have = read_point(paths, pid)
    added = revised = 0
    for d, v in days.items():
        if d in have:
            if any(abs(float(have[d][k]) - float(v[k])) > 1e-6 for k in POINT_COLS[1:5]):
                revised += 1
            continue
        have[d] = {**v, "first_seen_at": _iso(seen_at)}
        added += 1
    if added:
        paths.points.mkdir(parents=True, exist_ok=True)
        tmp = paths.points / f"{pid}.csv.{os.getpid()}.tmp"
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(POINT_COLS)
            for d in sorted(have):
                r = have[d]
                w.writerow([d.isoformat(), *(r[k] for k in POINT_COLS[1:5]), r["first_seen_at"]])
        os.replace(tmp, paths.points / f"{pid}.csv")
    return {"added": added, "revisions_ignored": revised}


# ============================================================================ fetching
def request_for(dataset: Mapping[str, Any], point: Mapping[str, Any], start: date,
                end: date) -> dict[str, Any]:
    return {"variable": list(dataset.get("variables") or ["2m_temperature",
                                                          "total_precipitation"]),
            "location": {"longitude": float(point["lon"]), "latitude": float(point["lat"])},
            "date": [f"{start.isoformat()}/{end.isoformat()}"],
            "data_format": str(dataset.get("data_format") or "csv")}


def last_fetchable_day(now: datetime, lag: int) -> date:
    """The youngest valid date whose release instant (end of day + lag) has passed."""
    return (now - timedelta(days=lag + 1)).date()


def fetch_pass(paths: Paths, client: Any, doc: Mapping[str, Any], state: dict[str, Any], *,
               now: datetime, budget_s: float, key: str | None = None) -> dict[str, Any]:
    """Advance every point's cursor by at most one chunk, oldest cursor first, inside budget."""
    t0 = time.monotonic()
    lag = lag_days(doc)
    end_cap = last_fetchable_day(now, lag)
    start0 = date.fromisoformat(str(doc.get("backfill_start") or "1991-01-01"))
    chunk = max(1, int(doc.get("chunk_days") or 3660))
    dataset = doc.get("dataset") or {}
    name = str(dataset.get("name") or "reanalysis-era5-single-levels-timeseries")
    pstate = state.setdefault("points", {})
    todo = []
    for r in doc.get("regions") or []:
        for p in r.get("points") or []:
            cur = pstate.get(p["id"], {}).get("next")
            nxt = date.fromisoformat(cur) if cur else start0
            if nxt <= end_cap:
                todo.append((nxt, p))
    todo.sort(key=lambda x: x[0])
    res: dict[str, Any] = {"requested": 0, "ok": 0, "days_added": 0, "errors": [],
                           "deferred": 0, "status": OK}
    for nxt, p in todo:
        if time.monotonic() - t0 > budget_s:
            res["deferred"] += 1
            continue
        end = min(end_cap, nxt + timedelta(days=chunk - 1))
        res["requested"] += 1
        tmpdir = Path(tempfile.mkdtemp(prefix="era5_"))
        target = tmpdir / f"{p['id']}.download"
        try:
            client.retrieve(name, request_for(dataset, p, nxt, end), str(target))
            raw = target.read_bytes()
        except Exception as exc:
            status, msg = classify_error(exc, key)
            res["errors"].append({"point": p["id"], "status": status, "error": msg})
            pstate.setdefault(p["id"], {})["last_error"] = msg
            if status != ERROR:
                res["status"] = status   # an auth or licence refusal stops the pass
                break
            continue
        finally:
            with contextlib.suppress(OSError):
                for f in tmpdir.iterdir():
                    f.unlink()
                tmpdir.rmdir()
        days = {d: v for d, v in daily(parse_hourly(raw)).items() if nxt <= d <= end}
        merged = merge_point(paths, p["id"], days, now)
        ps = pstate.setdefault(p["id"], {})
        ps.pop("last_error", None)
        if days:
            last = max(days)
            # A history chunk that returned days advances to its end; a live chunk only past the
            # last complete day it actually returned (ERA5T can trail the nominal lag by a day).
            ps["next"] = (end + timedelta(days=1) if end < end_cap - timedelta(days=10)
                          else last + timedelta(days=1)).isoformat()
            ps["last_day"] = last.isoformat()
            res["ok"] += 1
            res["days_added"] += merged["added"]
            ps["revisions_ignored"] = int(ps.get("revisions_ignored", 0)) + merged[
                "revisions_ignored"]
        else:
            res["errors"].append({"point": p["id"], "status": ERROR,
                                  "error": f"no complete day in {nxt}..{end}"})
        ps["fetched_at"] = _iso(now)
    if res["errors"] and res["status"] == OK and res["ok"] == 0:
        res["status"] = ERROR
    elif res["errors"] and res["status"] == OK:
        res["status"] = PARTIAL
    return res


# ============================================================================== fields
def region_frame(paths: Paths, region: Mapping[str, Any]) -> Any:
    """Weighted region day (DatetimeIndex, UTC midnight): t2m_mean, t2m_min, precip_mm and the
    latest first_seen_at among its points. A day with < MIN_WEIGHT_SHARE of the weight is out."""
    import pandas as pd
    frames = []
    total_w = sum(float(p["weight"]) for p in region.get("points") or [])
    for p in region.get("points") or []:
        rows = read_point(paths, p["id"])
        if not rows:
            continue
        df = pd.DataFrame.from_dict(rows, orient="index")
        df.index = pd.to_datetime([d.isoformat() for d in df.index], utc=True)
        df["w"] = float(p["weight"])
        frames.append(df)
    if not frames or total_w <= 0:
        return None
    big = pd.concat(frames)
    big["first_seen_at"] = pd.to_datetime(big["first_seen_at"], utc=True, errors="coerce")
    g = big.groupby(level=0)
    w = g["w"].sum()
    out = pd.DataFrame({
        c: (big[c] * big["w"]).groupby(level=0).sum() / w for c in ("t2m_mean", "t2m_min",
                                                                    "precip_mm")})
    out["first_seen_at"] = g["first_seen_at"].max()
    out = out[w / total_w >= MIN_WEIGHT_SHARE].sort_index()
    if out.empty:
        return None
    full = pd.date_range(out.index.min(), out.index.max(), freq="D", tz="UTC")
    return out.reindex(full)


def anomaly(s: Any, min_years: int) -> Any:
    """`s` minus the mean of the same calendar window (+-7 days) over PRIOR years only. NaN
    until `min_years` prior years exist for that day of year."""
    import numpy as np
    import pandas as pd
    if s is None or s.dropna().empty:
        return s
    sm = s.rolling(15, center=True, min_periods=8).mean()
    idx = s.index
    leap = idx.is_leap_year & (idx.dayofyear > 59)
    doy = np.where(leap, idx.dayofyear - 1, idx.dayofyear)
    tab = pd.DataFrame({"y": idx.year, "d": doy, "v": sm.to_numpy()}).pivot_table(
        index="y", columns="d", values="v", aggfunc="mean")
    clim = tab.expanding(min_periods=1).mean().shift(1)
    cnt = tab.notna().astype(int).expanding().sum().shift(1)
    clim = clim.where(cnt >= int(min_years))
    lookup = clim.stack()
    keys = pd.MultiIndex.from_arrays([idx.year, doy])
    base = lookup.reindex(keys).to_numpy()
    return pd.Series(s.to_numpy() - base, index=idx)


def region_fields(frame: Any, hdd_base_c: float, min_years: int) -> Any:
    import pandas as pd
    t, tmin, pr = frame["t2m_mean"], frame["t2m_min"], frame["precip_mm"]
    hdd = (hdd_base_c - t).clip(lower=0)
    cdd = (t - hdd_base_c).clip(lower=0)
    hdd7 = hdd.rolling(7, min_periods=7).sum()
    cdd7 = cdd.rolling(7, min_periods=7).sum()
    p30 = pr.rolling(30, min_periods=30).sum()
    frost = (tmin <= FROST_TMIN_C).astype(float).where(tmin.notna())
    return pd.DataFrame({
        "t2m_c": t,
        "t2m_anom_7d": anomaly(t, min_years).rolling(7, min_periods=7).mean(),
        "hdd_7d": hdd7, "cdd_7d": cdd7,
        "hdd_anom_7d": anomaly(hdd7, min_years), "cdd_anom_7d": anomaly(cdd7, min_years),
        "precip_30d_mm": p30, "precip_anom_30d": anomaly(p30, min_years),
        "frost_days_7d": frost.rolling(7, min_periods=7).sum(),
        "first_seen_at": frame["first_seen_at"],
    }, index=frame.index)


def pit_rows(fields: Any, field: str, region_id: str, lag: int) -> list[dict[str, Any]]:
    """One stamped row per valid date: event_time = the date, available_time = end of the date
    + lag via `libs.data.pit_stamp.available_at`, first_seen_at = when this box first held all
    the points that day needed. `backfill` when the box read it after its release instant."""
    from libs.data.pit_stamp import available_at, vintage_id_for
    rows: list[dict[str, Any]] = []
    sid = lake_id(region_id, field)
    for ts, v in fields[field].items():
        if v is None or not math.isfinite(float(v)):
            continue
        d = ts.date()
        avail = available_at(d + timedelta(days=1), lag)
        seen = fields["first_seen_at"].get(ts)
        seen_s = _iso(seen.to_pydatetime()) if seen is not None and str(seen) != "NaT" else ""
        quality = ("backfill" if not seen_s or datetime.fromisoformat(seen_s) > avail
                   + timedelta(days=2) else "live")
        rows.append({"d": d.isoformat(), "event_time": _iso(datetime(d.year, d.month, d.day,
                                                                     tzinfo=UTC)),
                     "available_time": _iso(avail), "published_time": _iso(avail),
                     "retrieval_time": seen_s, "first_seen_at": seen_s, "revision_time": "",
                     "source_id": sid, "vintage_id": vintage_id_for(sid, seen_s or None,
                                                                    f"{float(v):.6g}"),
                     "value": round(float(v), 6), "pit_quality": quality})
    return rows


LAKE_COLS = ("event_time", "available_time", "published_time", "retrieval_time",
             "revision_time", "source_id", "vintage_id", "value", "pit_quality")


def write_lake(paths: Paths, name: str, rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    paths.series.mkdir(parents=True, exist_ok=True)
    target = paths.series / f"{name}.csv"
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(LAKE_COLS)
        for r in rows:
            w.writerow([r[c] for c in LAKE_COLS])
    os.replace(tmp, target)
    return target.name


def axis_doc(region: Mapping[str, Any], per_field: Mapping[str, list[dict[str, Any]]],
             now: datetime) -> dict[str, Any]:
    series = {}
    for f, rows in sorted(per_field.items()):
        keep = [{"d": r["d"], "v": r["value"], "available_time": r["available_time"],
                 "event_time": r["event_time"], "first_seen_at": r["first_seen_at"],
                 "vintage_id": r["vintage_id"], "pit_quality": r["pit_quality"]}
                for r in rows[-AXIS_DAYS:]]
        if keep:
            series[f] = {"what": f"ERA5 {region['label']}: {f}", "n": len(keep),
                         "first": keep[0]["d"], "last": keep[-1]["d"], "points": keep}
    return {"axis": "era5", "id": f"era5_{region['id']}", "source": CDS_URL,
            "at": _iso(now), "region": region["id"], "cadence": "daily",
            "attribution": ATTRIBUTION, "n_series": len(series),
            "pit_fields": ["event_time", "available_time", "first_seen_at", "vintage_id"],
            "shape": "series[<field>].points, joined on available_time; the lake holds the "
                     f"full history, this door the last {AXIS_DAYS} days",
            "series": series}


# ======================================================================== three uses
def _bars_close(paths: Paths, sym: str) -> Any:
    p = paths.universe / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "close" not in df.columns or df.empty:
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    s = pd.Series(df["close"].to_numpy(dtype=float), index=idx)
    return s[s.index.notna()].sort_index()


def may_mint(sym: str, family: str = "exogenous_conditioner") -> bool:
    """The two-lane order by asset class (`universe_policy`): share CFDs never mint here."""
    try:
        from research import universe_policy
        return bool(universe_policy.may_hypothesise(sym, family))
    except Exception:
        return False


def mapped_cells(doc: Mapping[str, Any]) -> list[tuple[str, str, str, int]]:
    out = []
    for r in doc.get("regions") or []:
        for field, m in sorted((r.get("instruments") or {}).items()):
            for sym, sign in sorted((m or {}).items()):
                out.append((str(r["id"]), field, sym, int(sign)))
    return out


def gain_tests(paths: Paths, doc: Mapping[str, Any],
               rows: Mapping[tuple[str, str], list[dict[str, Any]]],
               mint: Callable[[str], bool] = may_mint) -> dict[str, dict[str, Any]]:
    """Every mapped (region, field, instrument) cell with a series, tested once, charged
    together (`n_cells`). A cell with no bars on this box is UNMEASURED, never a fail."""
    from libs.research.release_gain import release_gain
    cells = [(rid, f, s) for rid, f, s, _ in mapped_cells(doc) if rows.get((rid, f)) and mint(s)]
    out: dict[str, dict[str, Any]] = {}
    closes: dict[str, Any] = {}
    for rid, f, sym in cells:
        if sym not in closes:
            closes[sym] = _bars_close(paths, sym)
        key = f"{rid}|{f}|{sym}"
        if closes[sym] is None:
            out[key] = {"verdict": UNMEASURED, "why": f"no {sym}_H1 bars on this box"}
            continue
        ev = [(r["available_time"], float(r["value"])) for r in rows[(rid, f)]]
        res = release_gain(ev, closes[sym], horizon_bars=HORIZON_BARS,
                           n_cells=len(cells)).as_dict()
        res["backfill_share"] = round(sum(1 for r in rows[(rid, f)] if r["pit_quality"]
                                          == "backfill") / len(rows[(rid, f)]), 3)
        out[key] = res
    return out


#: Bump when the gain test or the cell recipe changes meaning: every cell is then re-charged.
CELL_SPEC_VERSION = "era5-cell/1"


def cell_charge_key(doc: Mapping[str, Any], key: str,
                    rows: Mapping[tuple[str, str], list[dict[str, Any]]]) -> str:
    """What a trial charge is FOR: (cell id, spec hash, data fingerprint). A cell is charged once
    per key and re-charged only when its spec or its ERA5 data (last valid date, row count)
    changes -- never because another hourly pass re-ran the same test (zuck's trial rule)."""
    rid, field, sym = key.split("|")
    prior = next((sg for r, f, s_, sg in mapped_cells(doc) if (r, f, s_) == (rid, field, sym)),
                 None)
    spec = {"v": CELL_SPEC_VERSION, "family": "exogenous_conditioner", "horizon": HORIZON_BARS,
            "transform": "level_z", "threshold": 1.0, "lag_hours": 24, "prior": prior,
            "lag_days": lag_days(doc)}
    spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
    rs = rows.get((rid, field)) or []
    last = max((str(r.get("d") or r.get("event_time") or "") for r in rs), default="")
    return f"{key}#{spec_hash}#{last}|{len(rs)}"


def fresh_charges(paths: Paths, doc: Mapping[str, Any],
                  gains: Mapping[str, Mapping[str, Any]],
                  rows: Mapping[tuple[str, str], list[dict[str, Any]]]) -> dict[str, str]:
    """Tested cells (verdict not UNMEASURED) whose charge key is not the one already charged."""
    led = _read_json(paths.charges, {}) or {}
    charged = led.get("cells") if isinstance(led.get("cells"), dict) else {}
    out: dict[str, str] = {}
    for key, g in sorted(gains.items()):
        if g.get("verdict") == UNMEASURED:
            continue
        ck = cell_charge_key(doc, key, rows)
        if charged.get(key) != ck:
            out[key] = ck
    return out


def record_charges(paths: Paths, fresh: Mapping[str, str], now: datetime) -> None:
    led = _read_json(paths.charges, {}) or {}
    cells = dict(led.get("cells") or {}) if isinstance(led.get("cells"), dict) else {}
    cells.update(fresh)
    _atomic(paths.charges, {"schema": "era5_trial_charges/1", "updated_at": _iso(now),
                            "rule": "one charge per (cell, spec hash, data fingerprint)",
                            "cells": dict(sorted(cells.items()))})


def direct_cells(doc: Mapping[str, Any], gains: Mapping[str, Mapping[str, Any]],
                 now: datetime, mint: Callable[[str], bool] = may_mint) -> list[dict[str, Any]]:
    """PASSING cells only, as `exogenous_conditioner` recipes on the lake series. The side is the
    MEASURED IC sign; the declared prior rides along as provenance."""
    regions = {str(r["id"]): r for r in doc.get("regions") or []}
    out: list[dict[str, Any]] = []
    for key, g in sorted(gains.items()):
        if g.get("verdict") != "PASS" or not g.get("ic"):
            continue
        rid, field, sym = key.split("|")
        if not mint(sym) or rid not in regions:
            continue
        r = regions[rid]
        side = 1 if float(g["ic"]) > 0 else -1
        src = lake_id(rid, field)
        params = {"source": src, "signal": "value", "transform": "level_z", "threshold": 1.0,
                  "side_when_high": side, "lag_hours": 24, "ttl_bars": HORIZON_BARS}
        out.append({
            "source": SOURCE, "kind": "hypothesis", "symbol": sym, "symbols": [sym],
            "family": "exogenous_conditioner", "params": params, "url": CDS_URL,
            "cell": f"{sym}.exogenous_conditioner.{src}",
            "title": f"ERA5 {r['label']}: {field} -> {sym} ({'+' if side > 0 else '-'})"[:120],
            "available_time": _iso(now), "event_time": _iso(now),
            "mechanism": r.get("mechanism", ""), "participant_structure": ["physical_flow"],
            "prior_sign": (r.get("instruments") or {}).get(field, {}).get(sym),
            "falsifier": (f"IC of ERA5 {field} ({rid}) on {sym} {HORIZON_BARS}-bar post-release "
                          "returns no longer beats the shifted-release placebo at p<=0.05"),
            "evidence": {k: g.get(k) for k in ("ic", "n", "t", "p_t", "p_placebo",
                                               "placebo_abs_ic_p95", "backfill_share",
                                               "horizon_bars", "min_detectable_ic", "why")},
            "provenance": {"organ": SOURCE, "use": "direct_cells", "dataset": "era5",
                           "region": rid, "field": field, "lake_id": src,
                           "attribution": ATTRIBUTION}})
    return out


def donate(paths: Paths, cands: list[dict[str, Any]], tests_run: int, now: datetime
           ) -> dict[str, Any]:
    """Donate the passing cells; charge every tested cell either way (discovery file, else the
    null-trials side ledger -- exactly one carries the pass's trials)."""
    res: dict[str, Any] = {"donated": 0, "path": None}
    if cands:
        try:
            from research import proposer_common as pc
            path = pc.donate(SOURCE, cands, max(1, tests_run))
            res = {**pc.donation_counts(), "path": str(path) if path else None}
        except Exception as exc:
            res = {"donated": 0, "path": None,
                   "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    if tests_run > 0 and not res.get("path"):
        row = {"at": _iso(now), "source": SOURCE, "tests_run": int(tests_run),
               "by_family": {"exogenous_conditioner": int(tests_run)},
               "why": "tested cells charged; no discovery file carried them this pass"}
        try:
            paths.null_trials.parent.mkdir(parents=True, exist_ok=True)
            with paths.null_trials.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            res["null_trials_charged"] = int(tests_run)
        except OSError as exc:
            res["null_trials_error"] = str(exc)[:160]
    return res


def allocation_intel(doc: Mapping[str, Any],
                     rows: Mapping[tuple[str, str], list[dict[str, Any]]],
                     gains: Mapping[str, Mapping[str, Any]], now: datetime) -> dict[str, Any]:
    """Per instrument: the latest PIT-available z of every mapped field (z over the trailing
    250 available values), signed by the measured IC when its test passed, else the prior."""
    inst: dict[str, list[dict[str, Any]]] = {}
    for rid, field, sym, prior in mapped_cells(doc):
        series = [r for r in rows.get((rid, field)) or []
                  if datetime.fromisoformat(r["available_time"]) <= now]
        if len(series) < 30:
            continue
        last = series[-1]
        age = (now - datetime.fromisoformat(last["available_time"])).days
        vals = [float(r["value"]) for r in series[-250:]]
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
        z = (vals[-1] - mu) / sd if sd > 0 else 0.0
        g = gains.get(f"{rid}|{field}|{sym}") or {}
        measured = g.get("verdict") == "PASS" and g.get("ic")
        sign = (1 if float(g["ic"]) > 0 else -1) if measured else prior
        inst.setdefault(sym, []).append({
            "region": rid, "field": field, "value": last["value"], "z": round(z, 3),
            "signed_z": round(sign * max(-3.0, min(3.0, z)), 3), "sign": sign,
            "sign_basis": "measured_ic" if measured else "prior", "period": last["d"],
            "available_time": last["available_time"], "stale": age > STALE_DAYS,
            "gain_verdict": g.get("verdict", UNMEASURED)})
    out = {}
    for sym, comps in sorted(inst.items()):
        live = [c["signed_z"] for c in comps if not c["stale"]]
        out[sym] = {"tilt": round(sum(live) / len(live), 4) if live else None,
                    "components": comps}
    return {"generated_at": _iso(now), "use": "allocation_intel", "source": SOURCE,
            "attribution": ATTRIBUTION,
            "rule": ("read-only PIT summary: tilt = mean(sign * clip(z, +-3)) over the mapped "
                     "ERA5 fields released and not stale; it sizes nothing"),
            "instruments": out}


# ================================================================================== run
def _universe(paths: Paths) -> set[str] | None:
    doc = _read_json(paths.universe / "universe.json", None)
    return set(doc) if isinstance(doc, dict) else None


def run(paths: Paths = DEFAULT_PATHS, *, now: datetime | None = None, budget_s: float = 600.0,
        fetch: bool = True, dry_run: bool = False,
        client_factory: Callable[[], tuple[Any, str, str]] = make_client,
        key_reader: Callable[[str], str | None] | None = None,
        mint: Callable[[str], bool] = may_mint,
        donor: Callable[..., dict[str, Any]] = donate) -> dict[str, Any]:
    now = now or _now()
    doc = load_regions(paths.regions)
    errs = region_config_errors(doc, _universe(paths))
    state = _read_json(paths.state, {}) or {}
    terms, terms_ev = terms_status(paths)
    rep: dict[str, Any] = {"generated_at": _iso(now), "leg": LEG, "attribution": ATTRIBUTION,
                           "terms": terms, "terms_evidence": terms_ev, "config_errors": errs,
                           "lag_days": lag_days(doc), "status": OK, "box_steps": []}
    if errs:
        rep["status"] = ERROR
        rep["why"] = "region config invalid"
        _finish(paths, rep, dry_run)
        return rep
    if terms != "confirmed":
        rep["status"] = f"{BLOCKED_ON_TERMS}:{terms}"
        rep["why"] = "terms evidence is not confirmed: nothing is fetched or published"
        rep["box_steps"].append("python desks/mt5/research/era5_reader.py --confirm-terms "
                                "(fetches and quotes ERA5's CDS licence)")
        _finish(paths, rep, dry_run)
        return rep
    fetch_res: dict[str, Any] = {"status": "SKIPPED (--no-fetch)"}
    if fetch:
        client, cstat, why = client_factory()
        rep["client"] = {"status": cstat, "why": why}
        if client is None:
            rep["status"] = cstat
            rep["box_steps"].append(
                f"setx /M {KEY_NAME} <your CDS personal access token>" if cstat == BLOCKED_AUTH
                else 'pip install "cdsapi>=0.7.7,<1"  (pyproject extra: climate)')
        else:
            key = None
            with contextlib.suppress(Exception):
                if key_reader is None:
                    from libs.ops.env_keys import read_key as key_reader
                key = key_reader(KEY_NAME)
            fetch_res = fetch_pass(paths, client, doc, state, now=now, budget_s=budget_s,
                                   key=key)
            if str(fetch_res["status"]).startswith(BLOCKED_ON_TERMS):
                rep["box_steps"].append("accept the ERA5 dataset licence on the CDS web page "
                                        "(Download tab, 'Terms of use') with the account whose "
                                        "token is CDSAPI_KEY")
            rep["status"] = fetch_res["status"]
    rep["fetch"] = fetch_res
    _publish(paths, doc, rep, now=now, dry_run=dry_run, mint=mint, donor=donor)
    if not dry_run:
        state["updated_at"] = _iso(now)
        _atomic(paths.state, state)
    rep["cursors"] = {k: v.get("next") for k, v in sorted((state.get("points") or {}).items())}
    _finish(paths, rep, dry_run)
    return rep


def _publish(paths: Paths, doc: Mapping[str, Any], rep: dict[str, Any], *, now: datetime,
             dry_run: bool, mint: Callable[[str], bool], donor: Callable[..., dict[str, Any]]
             ) -> None:
    lag = lag_days(doc)
    min_years = int(doc.get("climatology_min_years") or 3)
    rows: dict[tuple[str, str], list[dict[str, Any]]] = {}
    regions_rep: dict[str, Any] = {}
    lake: list[str] = []
    for r in doc.get("regions") or []:
        rid = str(r["id"])
        frame = region_frame(paths, r)
        if frame is None:
            regions_rep[rid] = {"days": 0, "status": UNMEASURED, "why": "no point data yet"}
            continue
        fields = region_fields(frame, float(r["hdd_base_c"]), min_years)
        per: dict[str, list[dict[str, Any]]] = {}
        for f in FIELDS:
            per[f] = pit_rows(fields, f, rid, lag)
            rows[(rid, f)] = per[f]
        headline = per.get(str(r["headline"])) or []
        regions_rep[rid] = {"days": int(frame["t2m_mean"].notna().sum()),
                            "first": per["t2m_c"][0]["d"] if per["t2m_c"] else None,
                            "last": per["t2m_c"][-1]["d"] if per["t2m_c"] else None,
                            "last_available": (per["t2m_c"][-1]["available_time"]
                                               if per["t2m_c"] else None),
                            "fields": {f: len(v) for f, v in per.items()}}
        if dry_run:
            continue
        for f, frs in per.items():
            n = write_lake(paths, lake_id(rid, f), frs)
            if n:
                lake.append(n)
        n = write_lake(paths, psub_lake_id(rid), headline)
        if n:
            lake.append(n)
        mapped = {f: per[f] for f in (r.get("instruments") or {})}
        _atomic(paths.axes / f"era5_{rid}.json", axis_doc(r, mapped, now))
    rep["regions"] = regions_rep
    rep["lake_files"] = lake
    gains = gain_tests(paths, doc, rows, mint=mint) if rows else {}
    tested = sum(1 for g in gains.values() if g.get("verdict") != UNMEASURED)
    cells = direct_cells(doc, gains, now, mint=mint)
    rep["gains"] = {"tested": tested, "cells_mapped": len(mapped_cells(doc)),
                    "passed": len(cells),
                    "verdicts": {k: g.get("verdict") for k, g in sorted(gains.items())}}
    rep["direct_cells"] = [c["cell"] for c in cells]
    # ONE CHARGE PER (cell, spec, data). An unchanged cell re-tested this pass is neither
    # re-charged nor re-donated; its earlier charge stands.
    fresh = fresh_charges(paths, doc, gains, rows)
    new_cells = [c for c in cells
                 if f"{c['provenance']['region']}|{c['provenance']['field']}|{c['symbol']}"
                 in fresh]
    rep["gains"]["charged"] = len(fresh)
    rep["gains"]["unchanged_not_recharged"] = tested - len(fresh)
    if not dry_run:
        if fresh:
            rep["donation"] = donor(paths, new_cells, len(fresh), now)
            if not (isinstance(rep["donation"], dict) and rep["donation"].get("error")):
                record_charges(paths, fresh, now)
        else:
            rep["donation"] = {"donated": 0, "path": None,
                               "why": "no cell's spec or data changed: nothing re-charged"}
        _atomic(paths.allocation_intel, allocation_intel(doc, rows, gains, now))
    rep["uses"] = {"direct_cells": len(cells), "conditioning_series": len(lake),
                   "axes": len(regions_rep) - sum(1 for v in regions_rep.values()
                                                  if v.get("status") == UNMEASURED),
                   "allocation_intel": str(paths.allocation_intel.relative_to(paths.desk))}


def _finish(paths: Paths, rep: dict[str, Any], dry_run: bool) -> None:
    if not dry_run:
        _atomic(paths.report, rep)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--no-fetch", action="store_true", help="publish from stored points only")
    ap.add_argument("--dry-run", action="store_true", help="measure, write nothing")
    ap.add_argument("--confirm-terms", action="store_true",
                    help="fetch and quote ERA5's licence into data/era5/terms_evidence.json")
    ap.add_argument("--terms-text", type=Path, default=None,
                    help="with --confirm-terms: a saved copy of the licence text")
    ap.add_argument("--terms-url", default=None, help="where --terms-text was saved from")
    a = ap.parse_args(argv)
    if a.confirm_terms:
        ev = confirm_terms(text_file=a.terms_text, text_url=a.terms_url)
        print(json.dumps({"verdict": ev["verdict"], "terms_url": ev.get("terms_url"),
                          "kind": ev.get("kind"), "why": ev.get("why")}))
        return 0
    rep = run(budget_s=a.budget_s, fetch=not a.no_fetch, dry_run=a.dry_run)
    print(json.dumps({k: rep.get(k) for k in ("status", "terms", "why", "box_steps")}
                     | {"regions": {k: v.get("days") for k, v in (rep.get("regions") or {})
                                    .items()},
                        "direct_cells": len(rep.get("direct_cells") or [])}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
