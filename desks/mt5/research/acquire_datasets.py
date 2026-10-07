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

import contextlib
import glob
import io
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
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
from libs.research import country_lab as country_lab  # noqa: E402

WORLD = DESK / "data" / "intelligence" / "world"
STORE = DESK / "data" / "acquired"
REGISTRY = STORE / "registry.json"
#: FIRST-SEEN VINTAGES (ARCH-26, 2026-10-07): one append-only parquet per series, every row the
#: acquirer ever saw for the first time or saw CHANGED, with the UTC time it was captured.
VINTAGES = STORE / "vintages"
UNMEASURED = "UNMEASURED"
REPORT = DESK / "reports" / "dataset_acquisition.json"

#: A real browser UA. Measured on this box: the default urllib agent draws 403s from several
#: statistics sites, which read downstream as dead sources rather than as a rejected header.
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36")

FETCH_TIMEOUT_S = 25
MAX_BYTES = 60 * 1024 * 1024          #: real statistical archives are tens of MB
MAX_PER_RUN = 40                      #: bounded so one run cannot saturate the box's disk or hour
MIN_ROWS = 200                        #: below this a series cannot support a rolling rank
REFRESH_AFTER_S = 3600                #: an hourly owner must revisit changing public series
REFUSED_RETRY_S = 24 * 3600           #: bad pages yield their seat to the rest of the world

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

#: WHAT THE DESK ACTUALLY KNOWS ABOUT ITS OWN SEEDS, DECLARED (ARCH-26, 2026-10-07). The three
#: maps above were declared and left EMPTY, so `revision`, `availability` and `survivorship` read
#: UNMEASURED for every series ever acquired and `pit_authority` was unreachable by construction:
#: not one acquired series could enter the `ext_` vocabulary, however honest it was. Declared
#: here only where the source's own publication rules answer the question:
#:
#:   ECB euro foreign-exchange REFERENCE RATES (EXR D.*.EUR.SP00.A). The full daily series as the
#:   ECB publishes it (no row is selected by anything later than its own date); fixed once at
#:   the daily concertation and never restated; published around 16:00 CET on the reference day.
#:   The row is dated at that day's 00:00 UTC, so the declared lag is a FULL DAY -- the value is
#:   joined from the next UTC midnight, never the morning before it was published. That costs
#:   about nine hours of freshness and buys certainty; `acquired_series` applies it.
#:   CFTC TFF positioning: the CFTC restates prior weeks (see `_REVISED` above), declared so the
#:   revision check FAILS a series with no vintage -- the correct verdict.
#:
#:   The Treasury par curve, BIS policy rates and EIA WTI spot are declared below, each from its
#:   publisher's own release documentation (read 2026-10-07). All three come out REVISED with no
#:   vintage column, so the revision check FAILS and authority is withheld honestly; their lag
#:   and selection are declared anyway, so the day a vintage-carrying feed replaces them the only
#:   thing left to prove is the vintage.
#:
#: Every crawler-found URL stays undeclared and therefore UNMEASURED: nobody has read its
#: revision policy, and a guess is not a declaration.
_ECB_REFERENCE_LAG_S = 24 * 3600
for _ccy in _ECB_CROSSES:
    _u = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{_ccy}.EUR.SP00.A?format=csvdata"
    _SELECTION[_u] = "all_rows_as_published"
    _REVISED[_u] = False
    _PUBLICATION_LAG_S[_u] = _ECB_REFERENCE_LAG_S
_REVISED["https://www.cftc.gov/dea/newcot/FinFutWk.txt"] = True

def _seed(fragment: str) -> str:
    """The one seed URL containing `fragment`. Looked up, never indexed, so reordering the seeds
    cannot attach one publisher's declaration to another's URL; a missing seed fails at import."""
    (url,) = [u for u in _SEED_ENDPOINTS if fragment in u]
    return url


#: US TREASURY DAILY PAR YIELD CURVE. Source: Treasury, "Treasury Yield Curve Methodology"
#: (home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/
#: treasury-yield-curve-methodology): inputs are bid-side quotations taken "at or near 3:30 PM
#: each trading day", and "Yield curve rates are usually available at Treasury's interest rate
#: website by 6:00 PM Eastern Time each trading day, but may be delayed due to system problems
#: or other issues."
#:   selection  every trading day's curve as published; no row is kept or dropped on anything
#:              later than its own date.
#:   revised    TRUE. The same page: "Treasury reserves the option to make changes to the yield
#:              curve as appropriate and in its sole discretion", and the Federal Reserve's H.15
#:              notice "Corrections to several historical Treasury rates"
#:              (federalreserve.gov/releases/h15/historical-data-correction.htm) records
#:              Treasury-sourced history corrected after publication. The CSV carries no vintage.
#:   lag        TWO days. 6:00 PM ET is 22:00-23:00 UTC on a row stamped 00:00 UTC, so the next
#:              midnight clears the usual release by an hour at most; the second day covers the
#:              "may be delayed" Treasury itself documents.
TREASURY_CURVE = _seed("home.treasury.gov/")
_SELECTION[TREASURY_CURVE] = "all_rows_as_published"
_REVISED[TREASURY_CURVE] = True
_PUBLICATION_LAG_S[TREASURY_CURVE] = 2 * 24 * 3600

#: BIS CENTRAL BANK POLICY RATES (WS_CBPOL). Source: BIS, "Central bank policy rates"
#: documentation (bis.org/statistics/cbpol/cbpol_doc.pdf) and the data portal's topic page
#: (data.bis.org/topics/CBPOL): "Daily data are reported directly to the BIS by the member
#: central banks" and "Daily data are released around mid-week"; the series "show the sequence
#: of policy instruments used to conduct monetary policy in consecutive periods", with breaks
#: identified per country.
#:   selection  each central bank's full daily history as published (the panel is the central
#:              banks that worked with the BIS on it, not one filtered on later survival).
#:   revised    TRUE. The BIS documents no revision policy and no vintage; the bulk file is the
#:              current compilation of a spliced, central-bank-reported series whose instrument
#:              sequence the BIS amends per country. A compiled series nobody has documented as
#:              final-at-publication is not declared final here.
#:   lag        NINE days. A weekly mid-week release means a value can wait a full week for the
#:              next one; "around mid-week" can slip a day, and the row is stamped at 00:00 UTC.
BIS_POLICY_RATES = _seed("data.bis.org/static/bulk/WS_CBPOL")
_SELECTION[BIS_POLICY_RATES] = "all_rows_as_published"
_REVISED[BIS_POLICY_RATES] = True
_PUBLICATION_LAG_S[BIS_POLICY_RATES] = 9 * 24 * 3600

#: EIA CUSHING WTI SPOT (RWTCd). Source: EIA, "Spot Prices for Crude Oil and Petroleum Products"
#: (eia.gov/dnav/pet/pet_pri_spt_s1_d.htm): a WEEKLY release -- the table read 2026-10-07 showed
#: "Release Date: 9/30/2026", "Next Release Date: 10/7/2026", latest data 09/29/26 -- and its
#: Definitions, Sources & Notes (eia.gov/dnav/pet/TblDefs/pet_pri_spt_tbldef2.asp) name the
#: source as "Refinitiv, an LSEG business".
#:   selection  the full daily history as published.
#:   revised    TRUE. EIA republishes a licensed vendor price, documents no revision policy for
#:              it and keeps no vintage; nothing the publisher says makes it final-at-publication.
#:   lag        NINE days. Wednesday's release covers through Tuesday, so Wednesday's price waits
#:              seven days for the next one; a holiday-shifted release and the release's own
#:              time of day are the other two.
EIA_WTI_SPOT = _seed("www.eia.gov/dnav/pet/hist_xls/RWTCd")
_SELECTION[EIA_WTI_SPOT] = "all_rows_as_published"
_REVISED[EIA_WTI_SPOT] = True
_PUBLICATION_LAG_S[EIA_WTI_SPOT] = 9 * 24 * 3600


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
    """A detected tabular format into a frame, or ``None``.

    Legacy government workbooks are a first-class input.  In particular the seeded EIA WTI
    endpoint is BIFF8 ``.xls``; sending those bytes through the delimited-text reader produced a
    plausible one-column frame and silently stranded the energy lane.  The repository already
    has a dependency-free, structurally validating BIFF8 reader, so use that rather than adding
    another parser or requiring ``xlrd`` on production.
    """
    head = raw[:4096].lstrip()
    try:
        if raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            from libs.data.xls_reader import read_xls

            sheets = read_xls(raw)
            grids = [sheet.rows() for sheet in sheets]
            grids = [rows for rows in grids if rows]
            if not grids:
                return None
            # Statistical publishers normally put notes in small tabs and observations in the
            # largest.  Selecting by populated cells is deterministic and prevents a cover sheet
            # from becoming the dataset merely because it is tab zero.
            rows = max(grids, key=lambda values: sum(len(r) for r in values))
            header_i = next((i for i, row in enumerate(rows)
                             if sum(v not in (None, "") for v in row) >= 2), None)
            if header_i is None:
                return None
            width = max(len(row) for row in rows[header_i:])
            header = [str(v).strip() if v not in (None, "") else f"column_{i}"
                      for i, v in enumerate(rows[header_i] + [None] * width)][:width]
            body = [(row + [None] * width)[:width] for row in rows[header_i + 1:]]
            return pd.DataFrame(body, columns=header)
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
            raw = df[col]
            numeric = pd.to_numeric(raw, errors="coerce")
            plausible_excel = numeric.between(20_000, 80_000).sum() >= MIN_ROWS
            if plausible_excel:
                # Excel's 1900 date system, including its historical leap-year compatibility
                # offset.  Numeric values must never be handed to ``to_datetime`` unqualified:
                # pandas otherwise reads them as nanoseconds after 1970.
                idx = pd.to_datetime(numeric, unit="D", origin="1899-12-30",
                                     utc=True, errors="coerce")
            else:
                idx = pd.to_datetime(raw, utc=True, errors="coerce")
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


def _endpoints(limit: int, *, now: datetime | None = None) -> list[tuple[str, str]]:
    """(url, host) from seeds/crawls, excluding only URLs refreshed within this hour.

    The former implementation excluded every URL that had *ever* been acquired.  A successful
    first fetch therefore disabled updates forever and made an hourly acquisition clock a one-shot
    initializer.  Durable identity prevents duplicate series; recency must decide refetching.
    """
    fresh: set[str] = set()
    now = now or datetime.now(UTC)
    if REGISTRY.exists():
        try:
            previous = json.loads(REGISTRY.read_text("utf-8")).get("by_url") or {}
            for url, meta in previous.items():
                try:
                    at = datetime.fromisoformat(str((meta or {}).get("at") or ""))
                    if at.tzinfo is None:
                        at = at.replace(tzinfo=UTC)
                    retry_s = (REFRESH_AFTER_S if str((meta or {}).get("status") or "SUCCESS")
                               == "SUCCESS" else REFUSED_RETRY_S)
                    if (now - at.astimezone(UTC)).total_seconds() < retry_s:
                        fresh.add(str(url))
                except (TypeError, ValueError):
                    continue
        except (OSError, ValueError):
            fresh = set()
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    # Seeds first: they are known to be dated, keyless and relevant, so a run never spends its
    # whole budget on discovered pages that turn out to be markup.
    for u in _SEED_ENDPOINTS:
        if u in fresh or u in seen:
            continue
        seen.add(u)
        out.append((u, urllib.parse.urlparse(u).netloc or "seed"))
        if len(out) >= limit:
            return out
    # EVERY COUNTRY PACK, FAIRLY BY REGION. Declaring sources in 170+ native-market packs while
    # the acquirer reads only crawler output is declaration theatre: none of those sources can
    # ever reach a parser. Interleave regions so alphabetical country order cannot spend every
    # hourly seat on one continent; recent-attempt suppression advances the frontier next hour.
    buckets: dict[str, deque[tuple[str, str]]] = defaultdict(deque)
    packs = DESK / "research" / "countries"
    for pack_py in sorted(packs.glob("*/pack.py")):
        code = pack_py.parent.name
        if code.startswith("_") or code in {"global", "institutional", "jp"}:
            continue
        pack = country_lab.resolve_pack(code)
        if pack is None:
            continue
        region = str(pack.region_command or "UNMEASURED")
        urls: list[str] = []
        for dataset in pack.datasets:
            urls.extend(str(value) for value in (dataset.how_to_fetch, dataset.source)
                        if str(value).startswith(("http://", "https://")))
        for source in country_lab.source_rows(pack):
            if not source.absent_reason:
                urls.extend(str(value) for value in source.roots
                            if str(value).startswith(("http://", "https://")))
        for url in urls:
            if url in seen or url in fresh or _KEYED.search(url):
                continue
            seen.add(url)
            buckets[region].append((url, urllib.parse.urlparse(url).netloc or code))
    active = deque(sorted(region for region, rows in buckets.items() if rows))
    while active and len(out) < limit:
        region = active.popleft()
        out.append(buckets[region].popleft())
        if buckets[region]:
            active.append(region)
    if len(out) >= limit:
        return out
    for f in sorted(glob.glob(str(WORLD / "discoveries_*.json")), reverse=True):
        try:
            rows = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for r in rows:
            for u in (r.get("endpoints") or []):
                if u in seen or u in fresh or _KEYED.search(u):
                    continue
                seen.add(u)
                out.append((u, str(r.get("host") or "")))
                if len(out) >= limit:
                    return out
    return out


# ------------------------------------------------------------------ first-seen vintage capture
#: A publisher that restates history and keeps no vintage cannot be read point-in-time from its
#: own file: the file only ever shows today's opinion of the past. What the desk CAN know is what
#: the file said each time the desk read it. So every acquisition appends each row it has never
#: seen, or has seen with a different value, to `VINTAGES/<series>.parquet` stamped with the UTC
#: capture time -- and never rewrites an earlier row. The point-in-time view built from that store:
#:
#:   * a value is usable from max(its capture time, event time + declared publication lag);
#:   * a later revision is a NEW vintage, usable only from its own capture time, so it can never
#:     reach a bar that the earlier value was already serving;
#:   * before the series' first capture there is nothing -- UNMEASURED, never a backfill. History
#:     the desk first saw today becomes usable today, all of it at once, and no earlier.
#:
#: That view carries its vintage on the row (`vintage`, `available_time`), so the certifier grades
#: `revision` PASS for it -- and only for it: the as-published file of a revised source still FAILS.
VINTAGE_COLUMNS = ("event_time", "value", "captured_at", "source")


def vintage_path(name: str) -> Path:
    """Resolved against STORE at call time, so a run (or a test) pointed at another store never
    writes vintages into this one."""
    return STORE / VINTAGES.name / f"{name}.parquet"


def _utc_index(idx: Any) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(idx, utc=True, errors="coerce"))


def read_vintages(path: Path) -> pd.DataFrame:
    """The store as written: event_time, value, captured_at (both clocks UTC), in append order."""
    if not path.exists():
        return pd.DataFrame({"event_time": pd.DatetimeIndex([], tz="UTC"),
                             "value": pd.Series([], dtype=float),
                             "captured_at": pd.DatetimeIndex([], tz="UTC"),
                             "source": pd.Series([], dtype=str)})
    v = pd.read_parquet(path)
    v["event_time"] = pd.to_datetime(v["event_time"], utc=True)
    v["captured_at"] = pd.to_datetime(v["captured_at"], utc=True)
    v["value"] = v["value"].astype(float)
    if "source" not in v.columns:
        v["source"] = "capture"
    return v[list(VINTAGE_COLUMNS)].reset_index(drop=True)


def _append(path: Path, old: pd.DataFrame, new: pd.DataFrame) -> int:
    """Old rows exactly as they were, then the new ones. The ONLY writer of the store."""
    out = pd.concat([old, new], ignore_index=True) if len(old) else new
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.stem}.tmp.parquet")   # ignored like the store itself
    out.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return len(out)


def _same(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or a == b or math.isclose(a, b, rel_tol=1e-12,
                                                                       abs_tol=0.0)


def capture_vintages(path: Path, series: pd.Series, captured_at: datetime) -> dict[str, Any]:
    """Append every new or changed row of `series` to the store at `path`. NEVER rewrites: the
    file written is the old rows byte-for-byte in their order, then the new ones. A capture
    clock that has gone backwards is held at the last capture, so vintages stay ordered."""
    old = read_vintages(path)
    now = pd.Timestamp(captured_at).tz_convert("UTC") if pd.Timestamp(captured_at).tzinfo \
        else pd.Timestamp(captured_at, tz="UTC")
    live = old[old["source"] == "capture"]
    if len(live):
        now = max(now, live["captured_at"].max())
    known: dict[pd.Timestamp, float] = {}
    # the LATEST CAPTURED vintage of each event is what a re-read is compared against -- by
    # capture time, not file order, because archival (ALFRED) rows are appended with past times
    hist = old.sort_values("captured_at", kind="stable")
    for e, val in zip(hist["event_time"], hist["value"], strict=True):
        known[e] = float(val)
    s = series.astype(float)
    idx = _utc_index(s.index)
    rows: list[tuple[pd.Timestamp, float]] = []
    revisions = 0
    for e, val in zip(idx, s.to_numpy(), strict=True):
        if pd.isna(e) or not math.isfinite(float(val)):
            continue                              # an unplaceable or empty cell is no observation
        prior = known.get(e)
        if prior is None or not _same(prior, float(val)):
            revisions += int(prior is not None)
            rows.append((e, float(val)))
            known[e] = float(val)
    first = live["captured_at"].min() if len(live) else (now if rows else None)
    if rows:
        new = pd.DataFrame({"event_time": pd.DatetimeIndex([r[0] for r in rows]),
                            "value": [r[1] for r in rows],
                            "captured_at": pd.DatetimeIndex([now] * len(rows)),
                            "source": ["capture"] * len(rows)})
        total = _append(path, old, new)
    else:
        total = len(old)
    return {"appended": len(rows), "revisions": revisions, "rows": total,
            "first_capture": first.isoformat() if first is not None else None,
            "captured_at": now.isoformat()}


def vintage_frame(v: pd.DataFrame, lag_s: float | None,
                  now: datetime | None = None) -> pd.DataFrame:
    """The vintage view to certify: indexed by event time, one row per vintage, with `vintage`
    (capture time) and `available_time` = max(capture, event + lag). With `now`, only rows the
    desk could already use are kept -- a row not yet usable is not yet part of the record."""
    lag = pd.Timedelta(seconds=float(lag_s or 0.0))
    f = pd.DataFrame({"value": v["value"].to_numpy(dtype=float),
                      "vintage": pd.DatetimeIndex(v["captured_at"]),
                      "available_time": pd.DatetimeIndex(
                          [max(c, e + lag) for c, e in zip(v["captured_at"], v["event_time"],
                                                           strict=True)])},
                     index=pd.DatetimeIndex(v["event_time"], name="event_time"))
    if now is not None:
        f = f[f["available_time"] <= pd.Timestamp(now).tz_convert("UTC")]
    return f.sort_values(["event_time", "vintage"], kind="stable")


def vintage_view(frame: pd.DataFrame) -> pd.Series:
    """What the desk could read at each instant: indexed by availability time, the value of the
    latest event it knew of, in the latest vintage it had captured by then. A revision moves the
    reading only from its own availability onward; it never rewrites an earlier reading."""
    if frame.empty:
        return pd.Series([], dtype=float, index=pd.DatetimeIndex([], tz="UTC"), name="value")
    rows = sorted(zip(frame["available_time"], frame["vintage"], frame.index,
                      frame["value"], strict=True), key=lambda r: (r[0], r[1]))
    known: dict[pd.Timestamp, float] = {}
    top: pd.Timestamp | None = None
    times: list[pd.Timestamp] = []
    vals: list[float] = []
    for avail, _cap, ev, val in rows:
        known[ev] = float(val)
        top = ev if top is None or ev > top else top
        if times and times[-1] == avail:
            vals[-1] = known[top]
        else:
            times.append(avail)
            vals.append(known[top])
    return pd.Series(vals, index=pd.DatetimeIndex(times), name="value")


def _join(s: pd.Series, index: pd.Index | None) -> pd.Series:
    """As-of join, FORWARD ONLY: each bar reads the last value available at or before it, and a
    bar before the first availability reads NaN -- UNMEASURED, never a backfill."""
    if index is None:
        return s
    bars = pd.DatetimeIndex(index)
    src = s.copy()
    src.index = pd.DatetimeIndex(src.index)
    if bars.tz is None and src.index.tz is not None:
        src.index = src.index.tz_convert("UTC").tz_localize(None)
    elif bars.tz is not None and src.index.tz is None:
        src.index = src.index.tz_localize("UTC")
    src = src[~src.index.duplicated(keep="last")].sort_index()
    return src.reindex(src.index.union(bars)).ffill().reindex(bars)


def as_of(name: str, at: datetime) -> float | str:
    """One series' point-in-time reading at `at`, or UNMEASURED (before its first capture, for a
    vintage-served series; unknown series; no authority)."""
    got = acquired_series(pd.DatetimeIndex([pd.Timestamp(at)]))
    s = got.get(name)
    if s is None or s.empty or pd.isna(s.iloc[0]):
        return UNMEASURED
    return float(s.iloc[0])


# ------------------------------------------------------------- archival vintages from ALFRED
#: HONEST DEPTH, NOT BACKFILL. A live capture can only start today. Where an ARCHIVE recorded
#: what was published and when, its vintages are real point-in-time history: ALFRED (FRED's
#: vintage archive) gives every observation's `realtime_start`, the date that value first
#: appeared. Each archival vintage enters the store as source="alfred" with
#:     captured_at = realtime_start at 00:00 America/New_York, in UTC, + the declared lag
#: so it is never usable before the archive says it existed, and a later archival vintage is
#: usable only from its own realtime_start -- the same no-backwards rule as a live capture.
#:
#: Mapped only where FRED carries THE SAME numbers as the publisher's file:
#:   Treasury par curve  -> DGS* (H.15's constant maturities are read off this curve)
#:   EIA Cushing WTI     -> DCOILWTICO (FRED republishes EIA's RWTC)
#:   BIS policy rates    -> none: FRED's policy-rate series come from other compilers, so a
#:                          match would be coincidence, not identity.
#: and accepted only after a cross-check against the publisher's own values (ALFRED_MIN_MATCH of
#: at least ALFRED_MIN_OVERLAP overlapping dates within the tolerance); mismatched dates are
#: excluded and recorded. FRED's copyrighted series stay HELD: VIX *CLS and BAML by name, and any
#: series whose own FRED notes carry a copyright notice.
ALFRED_OBSERVATIONS = "https://api.stlouisfed.org/fred/series/observations"
ALFRED_SERIES = "https://api.stlouisfed.org/fred/series"
_TREASURY_TENORS = {"1_Mo": "DGS1MO", "3_Mo": "DGS3MO", "6_Mo": "DGS6MO", "1_Yr": "DGS1",
                    "2_Yr": "DGS2", "3_Yr": "DGS3", "5_Yr": "DGS5", "7_Yr": "DGS7",
                    "10_Yr": "DGS10", "20_Yr": "DGS20", "30_Yr": "DGS30"}
#: Both publishers quote two decimals; anything past half a cent / half a basis point is not the
#: same number.
ALFRED_TOLERANCE = {TREASURY_CURVE: 0.0051, EIA_WTI_SPOT: 0.0051}
ALFRED_MIN_MATCH = 0.99
ALFRED_MIN_OVERLAP = 20
ALFRED_RETRY_S = 7 * 24 * 3600
_ALFRED_HELD = re.compile(r"^(VIX\w*CLS|BAML\w*)$", re.IGNORECASE)
_ET = "America/New_York"


def alfred_id(url: str, name: str) -> str | None:
    """The FRED series carrying the same numbers as this acquired series, or None."""
    if url == EIA_WTI_SPOT:
        return "DCOILWTICO"
    if url == TREASURY_CURVE:
        for col, sid in _TREASURY_TENORS.items():
            if name.endswith("_" + col):
                return sid
    return None


def alfred_held(series_id: str, notes: str | None) -> str | None:
    """Why a FRED series may not be used, or None. Held by name (VIX *CLS, BAML) whatever its
    notes say; held when its notes carry a copyright notice; held when the notes could not be
    read (an unread licence is not a cleared one)."""
    if _ALFRED_HELD.match(series_id):
        return f"{series_id}: held by project policy (FRED copyrighted family)"
    if notes is None:
        return f"{series_id}: FRED notes unreadable -- copyright not cleared"
    if re.search(r"copyright|\u00a9|\(c\)\s*\d{4}", notes, re.IGNORECASE):
        return f"{series_id}: FRED notes carry a copyright notice"
    return None


def _alfred_key() -> str | None:
    """The FRED key, from the places the repo's FRED readers already use: FRED_API_KEY, then
    `secrets/fred_api_key` (fetch_alfred.api_key), then `data/secrets/fred.json` {"key": ...}
    (scripts/collect_fred_macro.py). Read here rather than by importing fetch_alfred, whose import
    creates its lake directory. The key goes to the request and nowhere else -- never logged,
    never written to the registry or a report."""
    env = os.environ.get("FRED_API_KEY", "").strip()
    if env:
        return env
    repo = DESK.parents[1]
    for path in (repo / "secrets" / "fred_api_key", DESK / "secrets" / "fred_api_key"):
        with contextlib.suppress(OSError):
            k = path.read_text("utf-8").strip()
            if k:
                return k
    with contextlib.suppress(OSError, ValueError, AttributeError):
        k = str(json.loads((repo / "data" / "secrets" / "fred.json").read_text("utf-8"))
                .get("key") or "").strip()
        if k:
            return k
    return None


def _alfred_notes(series_id: str, key: str) -> str | None:
    import requests
    r = requests.get(ALFRED_SERIES, params={"series_id": series_id, "api_key": key,
                                            "file_type": "json"}, timeout=60)
    if r.status_code != 200:
        return None
    rows = r.json().get("seriess") or []
    return str(rows[0].get("notes") or "") if rows else None


def _alfred_fetch(series_id: str, key: str) -> pd.DataFrame:
    """Every vintage, one row per (observation, vintage): output_type=1 with the FULL realtime
    span -- omitting the span returns only today's revised vintage with a 200 (see
    fetch_alfred.fetch_vintages). Paged; a daily series is tens of thousands of rows."""
    import requests
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        r = requests.get(ALFRED_OBSERVATIONS, params={
            "series_id": series_id, "api_key": key, "file_type": "json", "output_type": 1,
            "realtime_start": "1776-07-04", "realtime_end": "9999-12-31",
            "limit": 100000, "offset": offset}, timeout=120)
        r.raise_for_status()
        doc = r.json()
        page = doc.get("observations") or []
        rows.extend(page)
        offset += len(page)
        if not page or offset >= int(doc.get("count") or 0):
            break
    return alfred_frame(rows)


def alfred_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """ALFRED rows -> observation_date, realtime_start, value. FRED's "." (no value) is dropped."""
    df = pd.DataFrame(rows, columns=["realtime_start", "date", "value"])
    df = df[df["value"].astype(str) != "."]
    out = pd.DataFrame({
        "observation_date": pd.to_datetime(df["date"], errors="coerce", utc=True),
        "realtime_start": pd.to_datetime(df["realtime_start"], errors="coerce"),
        "value": pd.to_numeric(df["value"], errors="coerce")})
    return out.dropna().reset_index(drop=True)


def alfred_capture_time(realtime_start: Any, lag_s: float | None) -> pd.Timestamp:
    """00:00 America/New_York on the vintage date, in UTC, plus the declared publication lag."""
    day = pd.Timestamp(realtime_start).normalize()
    if day.tzinfo is not None:
        day = day.tz_localize(None)
    return day.tz_localize(_ET).tz_convert("UTC") + pd.Timedelta(seconds=float(lag_s or 0))


def ingest_alfred(path: Path, publisher: pd.Series, vint: pd.DataFrame, lag_s: float | None,
                  tol: float, series_id: str) -> dict[str, Any]:
    """Cross-check ALFRED against the publisher, then append its vintages as source="alfred".
    Append-only, idempotent (an (event, capture) pair already stored is not stored again)."""
    pub = publisher.astype(float)
    pub.index = _utc_index(pub.index).normalize()
    pub = pub[~pub.index.duplicated(keep="last")]
    v = vint.copy()
    v["observation_date"] = _utc_index(v["observation_date"]).normalize()
    current = v.sort_values("realtime_start").groupby("observation_date")["value"].last()
    both = current.index.intersection(pub.index)
    diff = (current.loc[both] - pub.loc[both]).abs()
    bad = diff[diff > tol]
    rep: dict[str, Any] = {"series_id": series_id, "overlap": len(both),
                           "verified": int(len(both) - len(bad)), "mismatches": len(bad),
                           "mismatch_sample": [
                               {"date": str(d.date()), "alfred": float(current.loc[d]),
                                "publisher": float(pub.loc[d])} for d in bad.index[:5]],
                           "tolerance": tol}
    share = (rep["verified"] / len(both)) if len(both) else 0.0
    rep["match_share"] = round(share, 6)
    if len(both) < ALFRED_MIN_OVERLAP or share < ALFRED_MIN_MATCH:
        rep["status"] = "REJECTED"
        rep["why"] = (f"{len(both)} overlapping date(s), {share:.2%} within {tol}: needs "
                      f">= {ALFRED_MIN_OVERLAP} and >= {ALFRED_MIN_MATCH:.0%} -- not the same "
                      "series, so none of its history is taken")
        return rep
    keep = v[~v["observation_date"].isin(bad.index)]
    rep["unverified_outside_publisher_span"] = int(
        (~keep["observation_date"].isin(pub.index)).groupby(keep["observation_date"]).any().sum())
    cap = pd.DatetimeIndex([alfred_capture_time(t, lag_s) for t in keep["realtime_start"]])
    new = pd.DataFrame({"event_time": pd.DatetimeIndex(keep["observation_date"]),
                        "value": keep["value"].astype(float).round(6).to_numpy(),
                        "captured_at": cap, "source": ["alfred"] * len(keep)})
    old = read_vintages(path)
    seen = set(zip(old.loc[old["source"] == "alfred", "event_time"],
                   old.loc[old["source"] == "alfred", "captured_at"], strict=True))
    new = new[[(e, c) not in seen for e, c in zip(new["event_time"], new["captured_at"],
                                                   strict=True)]]
    rep["appended"] = len(new)
    if len(new):
        _append(path, old, new.reset_index(drop=True))
    rep["first_realtime"] = str(keep["realtime_start"].min().date()) if len(keep) else None
    rep["status"] = "INGESTED"
    return rep


def alfred_step(url: str, name: str, s: pd.Series, prior: dict[str, Any],
                run_at: datetime) -> dict[str, Any] | None:
    """One series' archival ingest, at most once a week until it lands. Never raises."""
    sid = alfred_id(url, name)
    if sid is None:
        return None
    last = prior.get("alfred") if isinstance(prior.get("alfred"), dict) else {}
    if last.get("status") == "INGESTED":
        return last
    # a REJECTED, HELD or unreachable answer is re-asked weekly; a missing key every run, so the
    # day a key is installed is the day the archive is read
    if last.get("retry_after"):
        if pd.Timestamp(run_at) < pd.Timestamp(str(last["retry_after"])):
            return last
    out: dict[str, Any] = {"series_id": sid, "at": run_at.isoformat(timespec="seconds")}
    key = _alfred_key()
    if not key:
        return {**out, "status": UNMEASURED, "why": "no FRED key (FRED_API_KEY or secrets/)"}
    retry = {"retry_after": (pd.Timestamp(run_at) + pd.Timedelta(seconds=ALFRED_RETRY_S))
             .isoformat()}
    try:
        held = alfred_held(sid, _alfred_notes(sid, key))
        if held:
            return {**out, **retry, "status": "HELD", "why": held}
        rep = ingest_alfred(vintage_path(name), s, _alfred_fetch(sid, key),
                            _PUBLICATION_LAG_S.get(url), ALFRED_TOLERANCE.get(url, 0.0051), sid)
        return {**out, **rep, **(retry if rep.get("status") != "INGESTED" else {})}
    except Exception as exc:                                                # noqa: BLE001
        # the message is the exception's type only: a requests error can echo the URL, key
        return {**out, **retry, "status": UNMEASURED,
                "why": f"ALFRED unreachable: {type(exc).__name__}"}


def acquire(limit: int = MAX_PER_RUN, *, now: datetime | None = None) -> dict[str, Any]:
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
        attempt_at = datetime.now(UTC).isoformat(timespec="seconds")

        def _refuse_url(why: str) -> None:
            _refuse(why)
            reg["by_url"][url] = {"host": host, "series": [], "at": attempt_at,
                                  "status": "REFUSED", "refusal": why}

        raw, ctype = _fetch(url)
        if raw is None:
            _refuse_url("served HTML, not data" if ctype == "html" else "unreachable")
            continue
        if len(raw) > MAX_BYTES:
            _refuse_url("larger than the per-file cap")
            continue
        df = _parse(raw, url)
        if df is None or df.empty:
            _refuse_url("unparseable as a supported workbook, archive, delimited file or JSON")
            continue
        dated = _dated(df)
        if dated is None:
            _refuse_url("no usable date column -- refused rather than stamped with now")
            continue
        stem = re.sub(r"[^A-Za-z0-9]+", "_", f"{host}_{Path(url).stem}").strip("_")[:40]
        series = _numeric_series(dated, stem)
        if not series:
            _refuse_url("no numeric column with enough history")
            continue

        persisted: list[str] = []
        failed_series: list[str] = []
        for name, s in series.items():
            path = STORE / f"{name}.parquet"
            try:
                s.rename("value").to_frame().to_parquet(path)
            except Exception:
                _refuse("could not persist")
                failed_series.append(name)
                continue
            # EVERY ACQUIRED SERIES IS CERTIFIED, at the only moment the desk holds both the
            # frame and what the acquirer knows about it. `authority: false` is not a refusal to
            # STORE -- the series stays, priced honestly -- it is a refusal of PROMOTION
            # authority, and `acquired_series` is what enforces that downstream.
            prior = reg["series"].get(name) or {}
            run_at = now or datetime.now(UTC)
            # EVERY SERIES' ROWS ARE CAPTURED AS VINTAGES, revised or not: the store costs a few
            # rows a day and is the only record of what the file said when the desk read it.
            vin: dict[str, Any] = {}
            try:
                vin = capture_vintages(vintage_path(name), s, run_at)
            except Exception as exc:                                        # noqa: BLE001
                vin = {"error": f"{type(exc).__name__}: {exc}"}
                _refuse("vintage not captured")
            served_vintage = _REVISED.get(url) is True and "error" not in vin
            alfred = alfred_step(url, name, s, prior, run_at) if served_vintage else None
            lag_decl = _PUBLICATION_LAG_S.get(url)
            vin_obs = 0
            try:
                if served_vintage:
                    # A REVISED SOURCE IS CERTIFIED ON ITS VINTAGE VIEW, never its file: that is
                    # the frame that carries the vintage on the row, so revision grades PASS for
                    # it and for nothing else. Its schema is tracked under its own hash.
                    vf = vintage_frame(read_vintages(vintage_path(name)), lag_decl, run_at)
                    vin_obs = int(vf["available_time"].nunique())
                    frame: pd.DataFrame = vf
                    prior_hash = prior.get("vintage_schema_hash")
                else:
                    frame = s.rename("value").to_frame()
                    prior_hash = prior.get("schema_hash")
                cert = certify({"dataset": name, "url": url, "host": host, "provider": host,
                                "selection": _SELECTION.get(url),
                                "revised": _REVISED.get(url),
                                "publication_lag_s": lag_decl,
                                "history_starts": prior.get("first"),
                                "schema_hash": prior_hash},
                               frame, now=run_at)
                write_certificate(cert)
                blocking = sorted(set(cert.failures()) | set(cert.unmeasured()))
                authority, cert_id = bool(cert.authority), cert.certificate_id
                new_hash = cert.span.get("schema_hash")
                if served_vintage and vin_obs < MIN_ROWS:
                    # THE FLOOR IS POINT-IN-TIME OBSERVATIONS: distinct instants at which the
                    # vintage view's reading could change. History first seen in one capture is
                    # ONE such instant however many rows it holds -- it earns no backtest depth.
                    blocking.append(f"vintage_floor: {vin_obs} of {MIN_ROWS} point-in-time "
                                    "observations")
                    authority = False
            except Exception as exc:                                        # noqa: BLE001
                # A certifier that cannot run withholds authority; it never grants it.
                blocking = [f"certify failed: {type(exc).__name__}: {exc}"]
                authority, cert_id = False, ""
                new_hash = prior.get("vintage_schema_hash" if served_vintage else "schema_hash")
            schema_hash = new_hash if not served_vintage else prior.get("schema_hash")
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
                "publication_lag_s": _PUBLICATION_LAG_S.get(url),
                "pit_blocking": blocking,
                "pit_view": "vintage" if served_vintage else "as_published",
                "vintage_path": str(vintage_path(name)),
                "vintage_rows": vin.get("rows"),
                "vintage_appended": vin.get("appended"),
                "revisions_captured": vin.get("revisions"),
                "first_capture": vin.get("first_capture"),
                "vintage_observations": vin_obs if served_vintage else None,
                "vintage_schema_hash": (new_hash if served_vintage
                                        else prior.get("vintage_schema_hash")),
                "vintage_error": vin.get("error"),
                "alfred": alfred,
            }
            new_series.append(name)
            persisted.append(name)
        reg["by_url"][url] = {"host": host, "series": persisted,
                              "failed_series": failed_series,
                              "at": datetime.now(UTC).isoformat(timespec="seconds"),
                              "status": ("PARTIAL" if failed_series else "SUCCESS")
                              if persisted else "REFUSED",
                              "refusal": "could not persist" if failed_series else None}
        kept += int(bool(persisted))

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
        if require_authority and meta.get("pit_authority") is not True:
            continue
        # AVAILABILITY TIME, NOT EVENT TIME. A certificate's `availability` check passes on a
        # declared publication lag "that a joiner applies uniformly to the event time" -- and
        # this is that joiner. Without the shift a value dated at its reference day's midnight
        # would be read by every bar of a day it had not yet been published on. An authorised
        # series whose lag was not recorded cannot be placed in time, so it is withheld.
        lag = meta.get("publication_lag_s")
        if require_authority and (isinstance(lag, bool) or not isinstance(lag, (int, float))
                                  or lag < 0):
            continue
        try:
            if meta.get("pit_view") == "vintage":
                # A REVISED SOURCE IS SERVED FROM ITS VINTAGES: what the desk had captured by each
                # instant, never the publisher's current opinion of the past. Before the first
                # capture the reading is NaN -- UNMEASURED -- and nothing is backfilled.
                vp = Path(str(meta.get("vintage_path") or vintage_path(name)))
                frame = vintage_frame(read_vintages(vp), lag if isinstance(lag, (int, float))
                                      and not isinstance(lag, bool) else None,
                                      datetime.now(UTC))
                s = vintage_view(frame)
            else:
                df = pd.read_parquet(meta["path"])
                s = df["value"].astype(float)
                if isinstance(lag, (int, float)) and not isinstance(lag, bool) and lag > 0:
                    s.index = pd.DatetimeIndex(s.index) + pd.Timedelta(seconds=float(lag))
            # FORWARD-FILL ONLY. A macro series is knowable from its publication date onward and
            # never before; interpolating backwards is leakage wearing the shape of tidiness.
            out[name] = _join(s, index)
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
