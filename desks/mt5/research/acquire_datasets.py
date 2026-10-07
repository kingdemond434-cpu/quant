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
import hashlib
import io
import json
import os
import re
import sys
import time
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

from libs.data import terms_fence as _tf  # noqa: E402
from libs.data.pit_certificate import certify  # noqa: E402
from libs.data.pit_certificate import write as write_certificate  # noqa: E402
from libs.research import country_lab as country_lab  # noqa: E402

WORLD = DESK / "data" / "intelligence" / "world"
STORE = DESK / "data" / "acquired"
REGISTRY = STORE / "registry.json"
REPORT = DESK / "reports" / "dataset_acquisition.json"

#: An HONEST UA that names the desk, never a browser string. The default urllib agent draws 403s
#: from some statistics sites; a named agent is the polite answer to that, a disguise is not. A
#: site that refuses it is recorded as refusing, which is the truth.
_UA = "quant-desk-dataset-acquirer/1.0 (public statistical data; internal research use)"

FETCH_TIMEOUT_S = 25
MAX_BYTES = 60 * 1024 * 1024          #: real statistical archives are tens of MB
MAX_PER_RUN = 40                      #: bounded so one run cannot saturate the box's disk or hour
MIN_ROWS = 200                        #: below this a series cannot support a rolling rank
#: ACQUISITION IS NOT PROMOTION (principal, 2026-10-06). `MIN_ROWS` is a RESEARCH bar -- the
#: rolling rank `build_primitives` computes needs it -- and it used to be the RETENTION bar too,
#: so ten years of a correctly dated monthly series (120 rows) was refused before anything could
#: accumulate it forward. Retention now needs only enough dated points to be a series at all;
#: a shorter one is kept, stamped INSUFFICIENT_HISTORY and withheld from the cell vocabulary
#: until its own forward accumulation carries it over `MIN_ROWS`.
MIN_DATED_ROWS = 8
#: Columns persisted per file per run. NOT a cap: the remainder is a cursor the next run resumes
#: (the old `len(out) >= 6: break` silently discarded every column after the sixth).
COLUMNS_PER_RUN = 64
#: Archive members parsed per file per run, resumed by cursor like the columns.
MEMBERS_PER_RUN = 16
#: Decompressed bytes one archive window may read in total. The per-member cap is MAX_BYTES and is
#: enforced on the bytes actually inflated, never on the size the archive declares.
WINDOW_BYTES = 2 * MAX_BYTES
REFRESH_AFTER_S = 3600                #: an hourly owner must revisit changing public series
REFUSED_RETRY_S = 24 * 3600           #: bad pages yield their seat to the rest of the world

#: Column names that are plausibly a DATE. Checked in order; the first that parses wins.
_DATE_COLS = ("date", "DATE", "Date", "time", "TIME", "Time", "timestamp", "TIMESTAMP",
              "datetime", "DATETIME", "period", "PERIOD", "obs_date", "ref_date", "week",
              "as_of", "asof", "report_date", "TIME_PERIOD")

#: Anything matching this needs a credential. It is never fetched keyless, and it is never a lost
#: discovery either: `_access_states` routes it to the adapter that holds its key or names the
#: missing key as an explicit access state.
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
    # THE TERMS FENCE, BEFORE ANY REQUEST (principal 2026-09-30: no Reddit, StockTwits or X at
    # all). A fenced URL is never requested and a 30x INTO a fenced host is never followed
    # (`guarded_urlopen`); either comes back as `terms_fenced:<platform>`, which `acquire` counts.
    platform = _tf.platform_of_url(url)
    if platform:
        return None, f"terms_fenced:{platform}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with _tf.guarded_urlopen(req, timeout=FETCH_TIMEOUT_S) as r:
            ctype = str(r.headers.get("Content-Type") or "").lower()
            if "html" in ctype:
                return None, "html"
            return r.read(MAX_BYTES + 1), ctype
    except _tf.TermsFenced as exc:
        return None, f"terms_fenced:{exc.platform}"
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
            # `_parse` keeps its one-frame contract (the largest member); `_tables` is what the
            # acquirer calls, and it enumerates EVERY member.
            members = _archive_members(raw)
            body = _read_member(raw, members[0]) if members else None
            if body is None:
                return None
            raw = body
        elif raw[:2] == b"\x1f\x8b":
            body = _gunzip(raw)
            if body is None:
                return None
            raw = body
        # SEPARATOR SNIFFED, NOT ASSUMED. European statistical offices ship semicolon CSV, and
        # reading it as comma yields one column and a silent refusal downstream.
        sample = raw[:8192].decode("utf-8", errors="replace")
        sep = max((",", ";", "\t", "|"), key=sample.count)
        return pd.read_csv(io.BytesIO(raw), sep=sep, low_memory=False,
                           on_bad_lines="skip", encoding_errors="replace")
    except Exception:
        return None


_TABULAR_MEMBER = (".csv", ".txt", ".tsv", ".json", ".xls")


def _archive_members(raw: bytes) -> list[str]:
    """Every tabular member NAME of a zip archive, largest first, each bounded by `MAX_BYTES`.

    The former reader kept only the single largest member, so a statistical bulk archive that
    ships one file per table (BIS, Eurostat, JPX) silently became one dataset. Only the central
    directory is read here: member bytes are read lazily, for the cursor's window alone, so an
    archive of many large members never sits in memory whole. A member larger than the per-file
    cap is skipped by name.
    """
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = [i for i in z.infolist()
                     if not i.is_dir() and i.filename.lower().endswith(_TABULAR_MEMBER)
                     and i.file_size <= MAX_BYTES]
    except (zipfile.BadZipFile, OSError, ValueError):
        return []
    return [i.filename for i in sorted(infos, key=lambda i: (-i.file_size, i.filename))]


def _read_member(raw: bytes, name: str, limit: int = MAX_BYTES) -> bytes | None:
    """The member's bytes, inflated in chunks and abandoned the moment they pass `limit`. The
    declared `file_size` is the archive's claim, and a zip bomb lies in it."""
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z, z.open(name) as fh:
            buf = bytearray()
            while chunk := fh.read(1 << 20):
                buf += chunk
                if len(buf) > limit:
                    return None
            return bytes(buf)
    except (zipfile.BadZipFile, OSError, ValueError, KeyError, EOFError):
        return None


def _tables(raw: bytes, url: str, *, start: int = 0, budget: int = MEMBERS_PER_RUN
            ) -> tuple[list[tuple[str, pd.DataFrame]], int, int]:
    """(member, frame) for every parseable table in `raw`, the next member cursor, and how many
    members remain after this window.

    A plain file is one table with member ``""``. An archive yields one table per tabular member
    from `start`, at most `budget` of them; the acquirer records the cursor so the next run
    resumes rather than re-reading.
    """
    if raw[:2] != b"PK":
        df = _parse(raw, url)
        return ([("", df)] if df is not None and not df.empty else []), 0, 0
    members = _archive_members(raw)
    window = members[start:start + max(budget, 1)]
    out: list[tuple[str, pd.DataFrame]] = []
    spent = 0
    read = 0
    for name in window:
        if spent >= WINDOW_BYTES:
            break                       # the cursor stops here; the next run resumes at `name`
        limit = min(MAX_BYTES, WINDOW_BYTES - spent)
        body = _read_member(raw, name, limit)
        if body is None and limit < MAX_BYTES:
            break                       # too big for what is left of this window, not too big
        read += 1
        if body is None:
            continue
        spent += len(body)
        df = _parse(body, f"{url}#{name}")
        if df is not None and not df.empty:
            out.append((name, df))
    nxt = start + read
    return out, nxt, max(len(members) - nxt, 0)


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
            in_range = int(numeric.between(20_000, 80_000).sum())
            # Most of the column, not a fixed count: a 120-row monthly workbook is as much an
            # Excel-dated column as a 5,000-row daily one.
            plausible_excel = (in_range >= MIN_DATED_ROWS
                               and in_range >= 0.8 * max(int(raw.notna().sum()), 1))
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
        if idx.notna().sum() < MIN_DATED_ROWS:
            continue
        out = df.loc[idx.notna()].copy()
        out.index = pd.DatetimeIndex(idx[idx.notna()])
        return out.sort_index()
    return None


def _numeric_series(df: pd.DataFrame, stem: str) -> dict[str, pd.Series]:
    """EVERY numeric column as its own series -- no column cap.

    The vocabulary is protected where it is consumed, not by discarding fields here: the former
    `len(out) >= 6: break` dropped every later column of a wide statistical table on every run,
    which is a silent truncation, not a budget. The acquirer persists these through a resumable
    column cursor (`COLUMNS_PER_RUN`), and `acquired_series` admits to the cell vocabulary only
    what clears PIT authority and research history.
    """
    out: dict[str, pd.Series] = {}
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce")
        n = int(s.notna().sum())
        # Distinct values scale with length: a 12-point monthly series with 9 distinct prints is
        # a series; a 5,000-row column with 9 distinct values is a code list.
        if n < MIN_DATED_ROWS or s.nunique() < min(10, max(3, n // 3)):
            continue
        name = re.sub(r"[^A-Za-z0-9]+", "_", f"{stem}_{col}").strip("_")[:48]
        base, k = name, 2
        while name in out:                          # two columns sanitising to one name
            name = f"{base[:44]}_{k}"
            k += 1
        out[name] = s[s.notna()]
    return out


def _gunzip(raw: bytes, limit: int = MAX_BYTES) -> bytes | None:
    """A gzip body inflated to at most `limit` bytes, or None when it would inflate past it.

    `gzip.decompress` has no ceiling: a 0.5 MB member that inflates a thousandfold would sit in
    memory whole before anything could refuse it. Inflating through a bounded decompressor
    stops at the limit, the same rule `_read_member` applies to zip members.
    """
    import zlib
    d = zlib.decompressobj(wbits=31)
    try:
        out = d.decompress(raw, limit + 1)
    except zlib.error:
        return None
    if len(out) > limit or d.unconsumed_tail:
        return None
    return out


#: Terms evidence for catalogue-discovered endpoints (catalog_routes/terms_evidence.json): a
#: discovered URL takes a seat only on a host whose own terms page was read, quoted and permits.
_TERMS_PERMITTED: frozenset[str] | None = None


def _terms_permitted() -> frozenset[str]:
    global _TERMS_PERMITTED
    if _TERMS_PERMITTED is None:
        try:
            here = str(Path(__file__).resolve().parent)
            if here not in sys.path:
                sys.path.insert(0, here)
            import catalog_routes as _cr
            _TERMS_PERMITTED = _cr.permitted_hosts(_cr.load_terms_evidence())
        except Exception:                      # unreadable evidence admits nothing
            _TERMS_PERMITTED = frozenset()
    return _TERMS_PERMITTED


def _terms_unverified(url: str) -> bool:
    """True (and counted) when a discovered URL's host has no quoted permitting terms."""
    host = (urllib.parse.urlparse(str(url)).hostname or "").lower().rstrip(".")
    if host and any(host == h or host.endswith("." + h) for h in _terms_permitted()):
        return False
    _ENDPOINT_FENCED["TERMS_UNVERIFIED"] = _ENDPOINT_FENCED.get("TERMS_UNVERIFIED", 0) + 1
    return True


#: Endpoints the last `_endpoints` pass left unselected because they sit on a terms-fenced
#: platform, by platform. A fenced URL never takes an hourly seat, and the count says so.
_ENDPOINT_FENCED: dict[str, int] = {}


def _fenced_pick(url: str) -> bool:
    """True (and counted) when `url` is on a terms-fenced platform: it is never selected."""
    p = _tf.platform_of_url(url)
    if p:
        _ENDPOINT_FENCED[p] = _ENDPOINT_FENCED.get(p, 0) + 1
    return bool(p)


#: Statuses that mean "this endpoint answered with data": revisited on the hourly refresh clock.
#: Anything else yields its seat for a day. PARTIAL and UNCHANGED used to fall into the second
#: group, so an endpoint that delivered data and lost one parquet write was parked for 24 hours.
_HEALTHY = frozenset({"SUCCESS", "PARTIAL", "UNCHANGED"})


def _endpoints(limit: int, *, now: datetime | None = None,
               keyed: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """(url, host) from seeds/crawls, excluding only URLs refreshed within this hour.

    The former implementation excluded every URL that had *ever* been acquired.  A successful
    first fetch therefore disabled updates forever and made an hourly acquisition clock a one-shot
    initializer.  Durable identity prevents duplicate series; recency must decide refetching.

    RESUMABLE WORK GOES FIRST. An endpoint whose last pass left a column or archive-member cursor
    open is due immediately, ahead of the seeds: its remainder is owed work, not a new fetch.

    KEYED URLS ARE COLLECTED, NOT DROPPED. When `keyed` is given, every URL skipped for needing
    a credential is appended to it so `_access_states` can route or name it.
    """
    fresh: set[str] = set()
    resume: list[tuple[str, str]] = []
    _ENDPOINT_FENCED.clear()
    now = now or datetime.now(UTC)
    if REGISTRY.exists():
        try:
            previous = json.loads(REGISTRY.read_text("utf-8")).get("by_url") or {}
            for url, meta in previous.items():
                meta = meta or {}
                if meta.get("cursor_open"):
                    resume.append((str(url), str(meta.get("host") or "")))
                    continue
                try:
                    at = datetime.fromisoformat(str(meta.get("at") or ""))
                    if at.tzinfo is None:
                        at = at.replace(tzinfo=UTC)
                    retry_s = (REFRESH_AFTER_S if str(meta.get("status") or "SUCCESS")
                               in _HEALTHY else REFUSED_RETRY_S)
                    if (now - at.astimezone(UTC)).total_seconds() < retry_s:
                        fresh.add(str(url))
                except (TypeError, ValueError):
                    continue
        except (OSError, ValueError):
            fresh, resume = set(), []
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for u, h in sorted(resume):
        seen.add(u)
        if _fenced_pick(u):
            continue
        out.append((u, h or urllib.parse.urlparse(u).netloc))
        if len(out) >= limit:
            return out
    # Seeds first: they are known to be dated, keyless and relevant, so a run never spends its
    # whole budget on discovered pages that turn out to be markup.
    for u in _SEED_ENDPOINTS:
        if u in fresh or u in seen:
            continue
        seen.add(u)
        if _fenced_pick(u):
            continue
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
            if _KEYED.search(url):
                if keyed is not None:
                    keyed.append((url, code))
                continue
            if url in seen or url in fresh:
                continue
            seen.add(url)
            if _fenced_pick(url):
                continue
            buckets[region].append((url, urllib.parse.urlparse(url).netloc or code))
    # DISCOVERED ENDPOINTS HOLD A RESERVED SHARE. The crawler, the deep forest and the catalog
    # routes (CKAN/DCAT/SDMX/STAC/Common Crawl) resolve real data URLs into
    # `discoveries_*.json`; read only after ~170 country packs, they almost never reached a seat
    # in a 40-endpoint pass. A quarter of the pass is theirs whenever they have work; packs keep
    # the rest, and either side's unused share flows to the other.
    found: list[tuple[str, str]] = []
    for f in sorted(glob.glob(str(WORLD / "discoveries_*.json")), reverse=True):
        try:
            rows = json.loads(Path(f).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            for u in (r.get("endpoints") or []):
                if _KEYED.search(str(u)):
                    if keyed is not None:
                        keyed.append((str(u), str(r.get("host") or "")))
                    continue
                if u in seen or u in fresh:
                    continue
                seen.add(u)
                if _fenced_pick(u) or _terms_unverified(str(u)):
                    continue
                found.append((u, str(r.get("host") or "")))
    room = limit - len(out)
    reserve = min(len(found), max(room // 4, 1 if room > 0 else 0))
    active = deque(sorted(region for region, rows in buckets.items() if rows))
    while active and len(out) < limit - reserve:
        region = active.popleft()
        out.append(buckets[region].popleft())
        if buckets[region]:
            active.append(region)
    for item in found:
        if len(out) >= limit:
            break
        out.append(item)
    while active and len(out) < limit:
        region = active.popleft()
        out.append(buckets[region].popleft())
        if buckets[region]:
            active.append(region)
    return out

ASIA_SOURCES = DESK / "data" / "asia_sources.json"


_CREDENTIAL_PARAM = re.compile(
    r"(?i)((?:api[_-]?key|apikey|token|access_key|client_id|client_secret|subscription[_-]?key"
    r"|key|secret|password|sig|signature)=)[^&#]*")


def _redact(url: str) -> str:
    return _CREDENTIAL_PARAM.sub(r"\1REDACTED", url)


def _access_states(keyed: list[tuple[str, str]],
                   environ: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """An explicit access state for every credentialed URL the frontier reached.

    The acquirer is keyless by doctrine, and it used to express that by DROPPING every keyed URL
    from the frontier with no record -- a lost discovery. Now each one is matched by host to the
    desk's keyed adapter rows (`asia_sources.json`, read by `asia_collector`, which holds the
    key-reading code): ROUTED when that adapter's key is set on this box, BLOCKED_ON_KEY:<ENV>
    when it is not, NEEDS_KEY_UNDECLARED when no adapter declares the host at all (the access
    or budget decision is now visible instead of silent). Only key PRESENCE is read; no key
    value is ever touched, logged or written.
    """
    env = os.environ if environ is None else environ
    by_host: dict[str, dict[str, Any]] = {}
    try:
        rows = json.loads(ASIA_SOURCES.read_text("utf-8")).get("sources") or []
    except (OSError, ValueError, AttributeError):
        rows = []
    for row in rows:
        if isinstance(row, dict) and row.get("key_env") and row.get("url"):
            host = urllib.parse.urlparse(str(row["url"])).netloc.lower()
            by_host.setdefault(host, row)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for url, origin in keyed:
        if url in seen:
            continue
        seen.add(url)
        host = urllib.parse.urlparse(url).netloc.lower()
        row = by_host.get(host)
        if row is None:
            state, adapter = "NEEDS_KEY_UNDECLARED", None
        else:
            key_env = str(row["key_env"])
            adapter = f"asia_collector:{row.get('id')}"
            state = f"ROUTED:{adapter}" if env.get(key_env) else f"BLOCKED_ON_KEY:{key_env}"
        # A discovered URL can carry a live credential: every credential-shaped parameter VALUE
        # is replaced before the URL is stored, so the discovery is named and the secret is not.
        safe = _redact(url)
        out.append({"url": safe, "host": host, "origin": origin, "state": state,
                    "adapter": adapter})
    return out


def _stem(host: str, url: str, member: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", f"{host}_{Path(url).stem}").strip("_")[:40]
    if not member:
        return base                    # unchanged for single-file endpoints: names stay stable
    tag = hashlib.sha256(member.encode("utf-8")).hexdigest()[:6]
    mstem = re.sub(r"[^A-Za-z0-9]+", "_", Path(member).stem).strip("_")[:10]
    return f"{base[:26]}_{mstem}_{tag}".strip("_")


#: Intermediate prints `_accumulate` saw this pass, written by the caller beside the series in
#: the same guarded persist step (a failure there is a counted refusal, never swallowed).
_PENDING_REVISIONS: dict[str, pd.DataFrame] = {}


def _write_revisions(path: Path) -> None:
    log = _PENDING_REVISIONS.pop(str(path), None)
    if log is None:
        return
    rev_path = path.with_name(path.stem + ".revisions.parquet")
    if rev_path.exists():
        log = pd.concat([pd.read_parquet(rev_path), log], ignore_index=True)
    log.to_parquet(rev_path)


def _accumulate(path: Path, s: pd.Series, seen_at: str,
                prior_seen_at: str | None) -> tuple[pd.DataFrame, int, int]:
    """Fold a freshly fetched series into what the store already holds, FIRST VALUE WINS.

    Returns (frame, revisions observed this pass, new points this pass). The stored `value` for
    a date is the value this desk first saw; a different later print is counted as a revision
    and carried in `value_latest`, never written over the first. `first_seen_at` per point is
    the vintage: a point first seen near its own date is live point-in-time evidence, and a
    point backfilled from a publisher's history is stamped with when it was backfilled. This is
    what lets a short or revision-prone series ACCUMULATE forward honestly instead of being
    re-downloaded as one restated block every hour.

    A series whose index repeats (a long panel such as one row per market per week) is stored
    whole, as before: folding it by date would mix its members.
    """
    fresh = s.rename("value").to_frame()
    fresh["value_latest"] = fresh["value"]
    fresh["first_seen_at"] = seen_at
    if not s.index.is_unique or not path.exists():
        return fresh, 0, len(fresh)
    try:
        old = pd.read_parquet(path)
    except Exception:                                                   # noqa: BLE001
        return fresh, 0, len(fresh)
    if "value" not in old.columns or not old.index.is_unique:
        return fresh, 0, len(fresh)
    if "first_seen_at" not in old.columns:
        old["first_seen_at"] = prior_seen_at
    if "value_latest" not in old.columns:
        old["value_latest"] = old["value"]
    common = old.index.intersection(fresh.index)
    a = old.loc[common, "value"].astype(float)
    b = fresh.loc[common, "value"].astype(float)
    revised = int(((a - b).abs() > 1e-9 * (1.0 + a.abs())).sum())
    # EVERY PRINT IS KEPT, not only the first and the latest: a print that differs from the
    # current `value_latest` is appended to the series' revision log before it is overwritten,
    # so an intermediate vintage (first -> second -> third estimate) is never lost.
    prev_latest = pd.to_numeric(old.loc[common, "value_latest"], errors="coerce").astype(float)
    moved = (prev_latest - b).abs() > 1e-9 * (1.0 + prev_latest.abs())
    if bool(moved.any()):
        _PENDING_REVISIONS[str(path)] = pd.DataFrame({"period": common[moved.to_numpy()],
                                                      "value": b[moved].to_numpy(),
                                                      "seen_at": seen_at})
    old.loc[common, "value_latest"] = b
    added = fresh.loc[fresh.index.difference(old.index)]
    merged = pd.concat([old, added]).sort_index()
    return merged, revised, len(added)


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

    tried = kept = unchanged = 0
    refusals: dict[str, int] = {}
    terms_fenced: dict[str, int] = {}
    new_series: list[str] = []
    keyed: list[tuple[str, str]] = []

    def _refuse(why: str) -> None:
        refusals[why] = refusals.get(why, 0) + 1

    try:
        frontier = _endpoints(limit, keyed=keyed)
    except TypeError:                     # a caller-supplied frontier without the keyed collector
        frontier = _endpoints(limit)
    for url, host in frontier:
        tried += 1
        attempt_at = datetime.now(UTC).isoformat(timespec="seconds")
        prev = dict(reg["by_url"].get(url) or {})

        def _refuse_url(why: str) -> None:
            _refuse(why)
            reg["by_url"][url] = {"host": host, "series": [], "at": attempt_at,
                                  "status": "REFUSED", "refusal": why, **cost}

        t_fetch = time.monotonic()
        raw, ctype = _fetch(url)
        # THE DATA COST, measured per visit, so the use census can price information per cost.
        took = time.monotonic() - t_fetch
        cost = {"bytes": len(raw) if raw is not None else 0, "fetch_s": round(took, 3),
                "visits": int(prev.get("visits") or 0) + 1,
                "fetch_s_total": round(float(prev.get("fetch_s_total") or 0.0) + took, 3)}
        if raw is None:
            if ctype.startswith("terms_fenced:"):
                terms_fenced[ctype.split(":", 1)[1]] = \
                    terms_fenced.get(ctype.split(":", 1)[1], 0) + 1
                _refuse_url(f"terms fence ({ctype.split(':', 1)[1]}): never requested")
                continue
            _refuse_url("served HTML, not data" if ctype == "html" else "unreachable")
            continue
        if len(raw) > MAX_BYTES:
            _refuse_url("larger than the per-file cap")
            continue
        digest = hashlib.sha256(raw).hexdigest()
        same_bytes = digest == prev.get("sha256")
        # NEVER RE-PARSE UNCHANGED BYTES. Identical content with no open cursor has nothing new
        # to give; the visit is recorded so the refresh clock still advances.
        if same_bytes and not prev.get("cursor_open") and prev.get("status") in _HEALTHY:
            reg["by_url"][url] = {**prev, "at": attempt_at, "status": "UNCHANGED", **cost}
            unchanged += 1
            continue
        # A cursor is only meaningful against the bytes it was opened on.
        m0 = int(prev.get("member_cursor") or 0) if same_bytes else 0
        c0 = int(prev.get("column_cursor") or 0) if same_bytes else 0
        tables, m_next, members_after = _tables(raw, url, start=m0)
        if not tables:
            _refuse_url("unparseable as a supported workbook, archive, delimited file or JSON")
            continue
        units: list[tuple[str, pd.Series, str]] = []
        no_date = 0
        for member, df in tables:
            dated = _dated(df)
            if dated is None:
                no_date += 1
                continue
            for name, ser in _numeric_series(dated, _stem(host, url, member)).items():
                units.append((name, ser, member))
        if not units:
            _refuse_url("no usable date column -- refused rather than stamped with now"
                        if no_date == len(tables) else "no numeric column with enough history")
            continue
        window = units[c0:c0 + COLUMNS_PER_RUN]
        cols_after = max(len(units) - c0 - len(window), 0)

        persisted: list[str] = []
        failed_series: list[str] = []
        for name, s, member in window:
            path = STORE / f"{name}.parquet"
            prior = reg["series"].get(name) or {}
            seen_at = datetime.now(UTC).isoformat(timespec="seconds")
            frame, revised, added = _accumulate(path, s, seen_at, prior.get("acquired_at"))
            try:
                _write_revisions(path)      # the log first: a series never outruns its history
                frame.to_parquet(path)
            except Exception:
                _refuse("could not persist")
                failed_series.append(name)
                continue
            # EVERY ACQUIRED SERIES IS CERTIFIED, at the only moment the desk holds both the
            # frame and what the acquirer knows about it. `authority: false` is not a refusal to
            # STORE -- the series stays, priced honestly -- it is a refusal of PROMOTION
            # authority, and `acquired_series` is what enforces that downstream.
            try:
                cert = certify({"dataset": name, "url": url, "host": host, "provider": host,
                                "selection": _SELECTION.get(url),
                                "revised": _REVISED.get(url),
                                "publication_lag_s": _PUBLICATION_LAG_S.get(url),
                                "history_starts": prior.get("first"),
                                "schema_hash": prior.get("schema_hash")},
                               frame[["value"]], now=datetime.now(UTC))
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
            rows = int(frame["value"].notna().sum())
            reg["series"][name] = {
                "path": str(path), "url": url, "host": host, "member": member or None,
                "rows": rows,
                "first": str(frame.index.min()), "last": str(frame.index.max()),
                "acquired_at": prior.get("acquired_at") or seen_at,
                "refreshed_at": seen_at,
                # RETENTION, RESEARCH AND PRODUCTION ARE SEPARATE PERMISSIONS.
                "history_status": ("RESEARCH_READY" if rows >= MIN_ROWS
                                   else "INSUFFICIENT_HISTORY"),
                "research_eligible": rows >= MIN_ROWS,
                "points_added_last": added,
                "revisions_seen": int(prior.get("revisions_seen") or 0) + revised,
                "schema_hash": schema_hash,
                "pit_certificate": cert_id,
                "pit_authority": authority,
                "pit_blocking": blocking,
            }
            new_series.append(name)
            persisted.append(name)
        if cols_after:
            next_m, next_c, cursor_open = m0, c0 + len(window), True
        elif members_after:
            next_m, next_c, cursor_open = m_next, 0, True
        else:
            next_m, next_c, cursor_open = 0, 0, False
        prior_series = [n for n in (prev.get("series") or []) if same_bytes and n not in persisted]
        reg["by_url"][url] = {"host": host, "series": [*prior_series, *persisted],
                              "failed_series": failed_series,
                              "at": datetime.now(UTC).isoformat(timespec="seconds"),
                              "status": ("PARTIAL" if failed_series else "SUCCESS")
                              if persisted else "REFUSED",
                              "refusal": "could not persist" if failed_series else None,
                              "sha256": digest,
                              "member_cursor": next_m, "column_cursor": next_c,
                              "cursor_open": cursor_open,
                              "columns_remaining": cols_after,
                              "members_remaining": members_after, **cost}
        kept += int(bool(persisted))

    access = _access_states(keyed)
    reg["access"] = {row["url"]: row for row in access}
    reg["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), encoding="utf-8")

    series_meta = [m for m in reg["series"].values() if isinstance(m, dict)]
    open_cursors = [u for u, m in reg["by_url"].items() if (m or {}).get("cursor_open")]
    access_counts: dict[str, int] = {}
    for row in access:
        key = str(row["state"]).split(":", 1)[0]
        access_counts[key] = access_counts.get(key, 0) + 1
    report = {
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "endpoints_tried": tried, "datasets_kept": kept, "unchanged": unchanged,
        "new_series": new_series, "total_series": len(reg["series"]),
        "acquired": len(new_series),
        "research_ready": sum(1 for m in series_meta if m.get("research_eligible") is True),
        "insufficient_history": sum(1 for m in series_meta
                                    if m.get("history_status") == "INSUFFICIENT_HISTORY"),
        "pit_authority": sum(1 for m in series_meta if m.get("pit_authority") is True),
        "cursors_open": len(open_cursors),
        "columns_remaining": sum(int((reg["by_url"][u] or {}).get("columns_remaining") or 0)
                                 for u in open_cursors),
        "members_remaining": sum(int((reg["by_url"][u] or {}).get("members_remaining") or 0)
                                 for u in open_cursors),
        "access_states": access_counts,
        "refusals": refusals,
        # FENCED ENDPOINTS, COUNTED (libs/data/terms_fence.py): refused before any request.
        "terms_fenced": {"by_platform": terms_fenced, "total": sum(terms_fenced.values()),
                         "endpoints_skipped_at_selection": dict(_ENDPOINT_FENCED)},
        "rule": ("point-in-time or nothing: a frame with no usable date column is refused rather "
                 "than stamped with now, because backfilling today's value across history "
                 "manufactures an edge that never existed. Retention, research eligibility and "
                 "PIT authority are separate verdicts: a short series is kept and accumulated "
                 "forward (first value wins, revisions counted), not refused"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


def main() -> int:
    """The hourly_discovery calling convention ("main"). The module had none, so that roster's
    `acquire_datasets` organ raised AttributeError every pass it was scheduled."""
    r = acquire()
    print(f"acquisition: {r['endpoints_tried']} endpoint(s) tried, {r['datasets_kept']} kept, "
          f"{r['unchanged']} unchanged, {len(r['new_series'])} series written, "
          f"{r['total_series']} total ({r['research_ready']} research-ready, "
          f"{r['insufficient_history']} accumulating), {r['cursors_open']} cursor(s) open")
    for why, n in sorted(r["refusals"].items(), key=lambda kv: -kv[1])[:12]:
        print(f"   refused {n:3d}: {why[:140]}")
    for state, n in sorted(r["access_states"].items()):
        print(f"   access  {n:3d}: {state}")
    print("YIELD " + json.dumps({"acquired": r["acquired"], "endpoints": r["endpoints_tried"]}))
    return 0


def acquired_series(index: pd.Index | None = None, *,
                    require_authority: bool = True,
                    min_rows: int = MIN_ROWS,
                    consumer: str | None = None,
                    use: str = "new_hypotheses") -> dict[str, pd.Series]:
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
    versions: dict[str, str] = {}
    for name, meta in (reg.get("series") or {}).items():
        # NO CERTIFICATE -> NO PROMOTION AUTHORITY (principal 2026-09-05). A series without one
        # is still on disk and still in the registry; it is simply not in the vocabulary a cell
        # can be built from. Series acquired before certification existed carry no flag and are
        # therefore withheld until the next acquisition run certifies them -- which is the
        # fail-closed direction, and the reason the registry keeps `pit_blocking` per series.
        if require_authority and meta.get("pit_authority") is not True:
            continue
        # RESEARCH ELIGIBILITY is its own gate: a retained series still accumulating toward
        # `min_rows` is not in the vocabulary (its rolling rank would be computed on nothing).
        try:
            if int(meta.get("rows") or 0) < min_rows:
                continue
        except (TypeError, ValueError):
            continue
        try:
            df = pd.read_parquet(meta["path"])
            s = df["value"].astype(float)
            # FORWARD-FILL ONLY. A macro series is knowable from its publication date onward and
            # never before; interpolating backwards is leakage wearing the shape of tidiness.
            out[name] = s.reindex(index).ffill() if index is not None else s
            versions[name] = str(meta.get("refreshed_at") or meta.get("acquired_at") or "")
        except Exception:
            continue
    if consumer and versions:
        # A READ IS RECORDED WHERE IT HAPPENS, with the version it saw (libs.data.dataset_use).
        from libs.data.dataset_use import record_reads
        record_reads(consumer, {f"acquired:{k}": v for k, v in versions.items()}, use=use)
    return out


if __name__ == "__main__":
    sys.exit(main())
