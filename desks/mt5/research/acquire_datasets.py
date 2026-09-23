"""Fetch the endpoints the crawler found, turn them into series, register them as primitives.

THE STEP THAT WAS MISSING, AND WHY IT COST EVERYTHING. The crawler now finds real data endpoints
-- 391 across the last six crawls -- and `world_crawler` still converts at 0 candidates from 34
rows. An endpoint is a URL to a CSV. The compiler's rule is "exact recipe or structured causal
data only", and a POINTER to data is neither: nothing fetched it, parsed it, or turned it into a
series anything could condition on. So the crawler stopped one move short of the gauntlet in
exactly the way the six prose sources did, one layer further along.

This is that move. Fetch, parse, date-check, register. After it, an acquired series is an
`ext_<name>` primitive through `build_primitives` -- which means the anomaly miner can rank
conditions on it AND `family_discovered` can execute them, because both resolve features through
the same function. That shared vocabulary is the whole reason this converts where prose cannot.

POINT-IN-TIME OR NOTHING. A series without a usable date column is REFUSED, not timestamped with
"now". A dataset whose values are revised after publication and carries no vintage is refused
too. Backfilling today's value across history is the single easiest way to manufacture an edge
that cannot exist, and this desk has already paid for revision leakage once.

FREE AND KEYLESS ONLY. Anything demanding a credential is skipped and named. The desk's mandate
is that its improvement rate must not depend on a key.

BOUNDED BY CONSTRUCTION. Per-file size cap, per-run count cap, a hard timeout and a real user
agent -- measured previously on this box, a default urllib UA gets 403s that read as dead sources.
Nothing here retries forever or downloads something it has not measured first.
"""
from __future__ import annotations

import glob
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
_ROOT = DESK.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.pit_certificate import certify  # noqa: E402
from libs.data.pit_certificate import write as write_certificate  # noqa: E402

WORLD = DESK / "data" / "intelligence" / "world"
STORE = DESK / "data" / "acquired"
REGISTRY = STORE / "registry.json"
REPORT = DESK / "reports" / "dataset_acquisition.json"

#: A real browser UA. Measured on this box: the default urllib agent draws 403s from several
#: statistics sites, which read downstream as dead sources rather than as a rejected header.
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36")

FETCH_TIMEOUT_S = 25
MAX_BYTES = 60 * 1024 * 1024          #: real statistical archives are tens of MB
MAX_PER_RUN = 40                      #: bounded so one run cannot saturate the box's disk or hour
MIN_ROWS = 200                        #: below this a series cannot support a rolling rank

#: Column names that are plausibly a DATE. Checked in order; the first that parses wins.
_DATE_COLS = ("date", "DATE", "Date", "time", "TIME", "Time", "timestamp", "TIMESTAMP",
              "datetime", "DATETIME", "period", "PERIOD", "obs_date", "ref_date", "week",
              "as_of", "asof", "report_date", "TIME_PERIOD")

#: Anything matching this needs a credential and is skipped rather than retried.
_KEYED = re.compile(r"(api[_-]?key|apikey|token=|access_key|client_id|subscription)", re.I)


#: KNOWN-GOOD DIRECT ENDPOINTS, PROBED FROM THIS BOX rather than assumed.
#:
#: The crawler finds pages ABOUT data far more often than data -- measured 2026-09-03, 23 of 40
#: discovered endpoints served HTML and none produced a series. That is not a crawler bug;
#: statistical sites genuinely put downloads behind forms and scripts. But it left the acquirer
#: with nothing to acquire, so the desk needs a floor of endpoints it knows are real.
#:
#: EVERY ONE OF THESE WAS PROBED, and the list is what survived. The first draft seeded 28 FRED
#: series on the reasonable assumption that fredgraph.csv is the canonical keyless source; every
#: one TIMED OUT from this box. That is exactly the failure mode already recorded in the desk's
#: free-data findings -- a healthy source looking dead for a transport reason -- and assuming
#: instead of probing would have shipped an acquirer that could never acquire anything, reported
#: 29 "unreachable" every run, and looked like a network problem rather than a wrong list.
#: Also refused on probe: bankofengland (HTML), stooq (HTML), cftc/deacot.txt (404).
#:
#: Chosen for RELEVANCE TO THE MT5 UNIVERSE: positioning drives the crosses, ECB reference rates
#: are the EUR legs, the Treasury curve and policy rates drive gold and indices, oil drives the
#: energy symbols. Each becomes an `ext_<name>` primitive that BOTH the miner and
#: `family_discovered` resolve through `build_primitives` -- the shared vocabulary prose lacked.
#:
#: A SEED, NEVER A LIMIT. Crawler-found endpoints are acquired alongside these.
_ECB_CROSSES = ("USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD", "SEK", "NOK",
                "PLN", "HUF", "TRY", "ZAR", "MXN", "CNY", "SGD", "HKD", "CZK", "DKK")

#: What the acquirer KNOWS about a source. Anything absent reads UNMEASURED in the certificate
#: rather than being guessed at: a crawler-found URL has told the desk nothing about how its rows
#: were selected or whether its publisher restates them, and UNMEASURED is not authority.
_SELECTION: dict[str, str] = {}
#: The CFTC restates prior weeks. Declared so the revision check FAILS a series carrying no
#: vintage column -- which is the correct verdict, not a defect in the acquirer.
_REVISED: dict[str, bool] = {}
_PUBLICATION_LAG_S: dict[str, int] = {}

_SEED_ENDPOINTS: tuple[str, ...] = (
    # CFTC positioning -- weekly, dated, the only free source of who is actually long what.
    "https://www.cftc.gov/dea/newcot/FinFutWk.txt",
    # US Treasury curve -- daily, every tenor, drives gold and the index symbols.
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value=2026&_format=csv",
    # BIS central bank policy rates -- zipped CSV, the global rate-differential ground.
    "https://data.bis.org/static/bulk/WS_CBPOL_csv_col.zip",
    # EIA WTI spot -- the energy leg.
    "https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls",
) + tuple(
    f"https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A?format=csvdata"
    for ccy in _ECB_CROSSES
)


def _fetch(url: str) -> tuple[bytes | None, str]:
    """Bytes and content-type. HTML is rejected AT THE HEADER rather than parsed and refused.

    Measured: 25 of 40 endpoints in the first run were unparseable, and almost all were HTML
    landing pages. Reading the header costs nothing and turns a confusing parse failure into an
    accurate one -- "this was a web page" rather than "this data was malformed".
    """
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as r:
            ctype = str(r.headers.get("Content-Type") or "").lower()
            if "html" in ctype:
                return None, "html"
            return r.read(MAX_BYTES + 1), ctype
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None, "unreachable"


def _parse(raw: bytes, url: str) -> pd.DataFrame | None:
    """CSV or JSON into a frame, or None. Never guesses a format it did not detect."""
    head = raw[:4096].lstrip()
    try:
        if head.startswith((b"{", b"[")):
            obj = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(obj, dict):
                for v in obj.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        return pd.DataFrame(v)
                return None
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                return pd.DataFrame(obj)
            return None
        if head.startswith(b"<"):
            return None                      # markup, not a series
        # ARCHIVES ARE THE NORMAL SHAPE for statistical bulk data -- CFTC, ECB and JPX all ship
        # zipped CSV, and refusing them would refuse the very sources most worth having.
        if raw[:2] == b"PK":
            import zipfile
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = [n for n in z.namelist()
                         if n.lower().endswith((".csv", ".txt", ".tsv"))]
                if not names:
                    return None
                raw = z.read(sorted(names, key=lambda n: -z.getinfo(n).file_size)[0])
        elif raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
        # SEPARATOR SNIFFED, NOT ASSUMED. European statistical offices ship semicolon CSV, and
        # reading it as comma yields one column and a silent refusal downstream.
        sample = raw[:8192].decode("utf-8", errors="replace")
        sep = max((",", ";", "\t", "|"), key=sample.count)
        return pd.read_csv(io.BytesIO(raw), sep=sep, low_memory=False,
                           on_bad_lines="skip", encoding_errors="replace")
    except Exception:
        return None


def _dated(df: pd.DataFrame) -> pd.DataFrame | None:
    """Index the frame on a real date column, or refuse.

    NO DATE, NO DATASET (L1.28a). Stamping rows with "now" would make every historical value look
    knowable today, which manufactures an edge that never existed. A frame the desk cannot place
    in time is not a weaker dataset; it is not a dataset.
    """
    for col in _DATE_COLS:
        if col not in df.columns:
            continue
        try:
            idx = pd.to_datetime(df[col], utc=True, errors="coerce")
        except Exception:
            continue
        if idx.notna().sum() < MIN_ROWS:
            continue
        out = df.loc[idx.notna()].copy()
        out.index = pd.DatetimeIndex(idx[idx.notna()])
        return out.sort_index()
    return None


def _numeric_series(df: pd.DataFrame, stem: str) -> dict[str, pd.Series]:
    """Every numeric column as its own series, capped so one file cannot flood the vocabulary."""
    out: dict[str, pd.Series] = {}
    for col in df.columns:
        if len(out) >= 6:
            break
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() < MIN_ROWS or s.nunique() < 10:
            continue
        name = re.sub(r"[^A-Za-z0-9]+", "_", f"{stem}_{col}").strip("_")[:48]
        out[name] = s[s.notna()]
    return out


def _endpoints(limit: int) -> list[tuple[str, str]]:
    """(url, host) from the newest crawl files, deduped against what is already acquired."""
    known: set[str] = set()
    if REGISTRY.exists():
        try:
            known = set(json.loads(REGISTRY.read_text("utf-8")).get("by_url") or {})
        except (OSError, ValueError):
            known = set()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    # Seeds first: they are known to be dated, keyless and relevant, so a run never spends its
    # whole budget on discovered pages that turn out to be markup.
    for u in _SEED_ENDPOINTS:
        if u in known or u in seen:
            continue
        seen.add(u)
        out.append((u, urllib.parse.urlparse(u).netloc or "seed"))
        if len(out) >= limit:
            return out
    for f in sorted(glob.glob(str(WORLD / "discoveries_*.json")), reverse=True):
        try:
            rows = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for r in rows:
            for u in (r.get("endpoints") or []):
                if u in seen or u in known or _KEYED.search(u):
                    continue
                seen.add(u)
                out.append((u, str(r.get("host") or "")))
                if len(out) >= limit:
                    return out
    return out


def acquire(limit: int = MAX_PER_RUN) -> dict[str, Any]:
    STORE.mkdir(parents=True, exist_ok=True)
    reg: dict[str, Any] = {"by_url": {}, "series": {}}
    if REGISTRY.exists():
        try:
            reg = json.loads(REGISTRY.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    reg.setdefault("by_url", {})
    reg.setdefault("series", {})

    tried = kept = 0
    refusals: dict[str, int] = {}
    new_series: list[str] = []

    def _refuse(why: str) -> None:
        refusals[why] = refusals.get(why, 0) + 1

    for url, host in _endpoints(limit):
        tried += 1
        raw, ctype = _fetch(url)
        if raw is None:
            _refuse("served HTML, not data" if ctype == "html" else "unreachable")
            continue
        if len(raw) > MAX_BYTES:
            _refuse("larger than the per-file cap")
            continue
        df = _parse(raw, url)
        if df is None or df.empty:
            _refuse("unparseable as CSV or JSON")
            continue
        dated = _dated(df)
        if dated is None:
            _refuse("no usable date column -- refused rather than stamped with now")
            continue
        stem = re.sub(r"[^A-Za-z0-9]+", "_", f"{host}_{Path(url).stem}").strip("_")[:40]
        series = _numeric_series(dated, stem)
        if not series:
            _refuse("no numeric column with enough history")
            continue

        for name, s in series.items():
            path = STORE / f"{name}.parquet"
            try:
                s.rename("value").to_frame().to_parquet(path)
            except Exception:
                _refuse("could not persist")
                continue
            # EVERY ACQUIRED SERIES IS CERTIFIED, at the only moment the desk holds both the
            # frame and what the acquirer knows about it. `authority: false` is not a refusal to
            # STORE -- the series stays, priced honestly -- it is a refusal of PROMOTION
            # authority, and `acquired_series` is what enforces that downstream.
            prior = reg["series"].get(name) or {}
            try:
                cert = certify({"dataset": name, "url": url, "host": host, "provider": host,
                                "selection": _SELECTION.get(url),
                                "revised": _REVISED.get(url),
                                "publication_lag_s": _PUBLICATION_LAG_S.get(url),
                                "history_starts": prior.get("first"),
                                "schema_hash": prior.get("schema_hash")},
                               s.rename("value").to_frame(), now=datetime.now(UTC))
                write_certificate(cert)
                blocking = sorted(set(cert.failures()) | set(cert.unmeasured()))
                authority, cert_id = bool(cert.authority), cert.certificate_id
                schema_hash = cert.span.get("schema_hash")
            except Exception as exc:                                        # noqa: BLE001
                # A certifier that cannot run withholds authority; it never grants it.
                blocking = [f"certify failed: {type(exc).__name__}: {exc}"]
                authority, cert_id, schema_hash = False, "", prior.get("schema_hash")
            if not authority:
                _refuse("no PIT authority: " + ", ".join(blocking))
            reg["series"][name] = {
                "path": str(path), "url": url, "host": host,
                "rows": int(s.notna().sum()),
                "first": str(s.index.min()), "last": str(s.index.max()),
                "acquired_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "schema_hash": schema_hash,
                "pit_certificate": cert_id,
                "pit_authority": authority,
                "pit_blocking": blocking,
            }
            new_series.append(name)
        reg["by_url"][url] = {"host": host, "series": list(series),
                              "at": datetime.now(UTC).isoformat(timespec="seconds")}
        kept += 1

    reg["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), encoding="utf-8")

    report = {
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "endpoints_tried": tried, "datasets_kept": kept,
        "new_series": new_series, "total_series": len(reg["series"]),
        "refusals": refusals,
        "rule": ("point-in-time or nothing: a frame with no usable date column is refused rather "
                 "than stamped with now, because backfilling today's value across history "
                 "manufactures an edge that never existed"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


def acquired_series(index: pd.Index | None = None, *,
                    require_authority: bool = True) -> dict[str, pd.Series]:
    """Every acquired series, for `build_primitives(extra=...)`.

    THE SHARED VOCABULARY IS THE POINT. The miner ranks conditions on `ext_<name>` and
    `family_discovered` resolves the same `ext_<name>` through the same function, so an anomaly
    found here is executable there by construction. That is precisely what the crawler's rows
    never had, and why they converted at zero.
    """
    if not REGISTRY.exists():
        return {}
    try:
        reg = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, pd.Series] = {}
    for name, meta in (reg.get("series") or {}).items():
        # NO CERTIFICATE -> NO PROMOTION AUTHORITY (principal 2026-09-05). A series without one
        # is still on disk and still in the registry; it is simply not in the vocabulary a cell
        # can be built from. Series acquired before certification existed carry no flag and are
        # therefore withheld until the next acquisition run certifies them -- which is the
        # fail-closed direction, and the reason the registry keeps `pit_blocking` per series.
        if require_authority and not meta.get("pit_authority"):
            continue
        try:
            df = pd.read_parquet(meta["path"])
            s = df["value"].astype(float)
            # FORWARD-FILL ONLY. A macro series is knowable from its publication date onward and
            # never before; interpolating backwards is leakage wearing the shape of tidiness.
            out[name] = s.reindex(index).ffill() if index is not None else s
        except Exception:
            continue
    return out


if __name__ == "__main__":
    r = acquire()
    print(f"acquisition: {r['endpoints_tried']} endpoint(s) tried, {r['datasets_kept']} kept, "
          f"{len(r['new_series'])} new series, {r['total_series']} total")
    for why, n in sorted(r["refusals"].items(), key=lambda kv: -kv[1]):
        print(f"   refused {n:3d}: {why}")
    for n in r["new_series"][:10]:
        print(f"   + {n}")
    sys.exit(0)
