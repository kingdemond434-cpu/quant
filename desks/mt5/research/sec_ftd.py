"""SEC FAILS-TO-DELIVER -- the half-month files, collected point-in-time and mapped to MT5 CFDs.

WHY. The flow factory's `fails_and_borrow` family stood UNWIRED: its source was permitted
(2026-10-13 ruling; the SEC's own page: "We allow scripted access to sec.gov content [...] Please
declare your user agent in request headers [...] Note that our current maximum access rate is 10
requests per second.") and nothing collected it. This organ is that collector.

ACCESS. Every request declares the User-Agent held in the environment as QUANT_EDGAR_UA (the box
already carries it for the EDGAR organs). It is read, sent and never printed, logged or written.
Absent, the organ fetches nothing and reports NEEDS_KEY. Requests are spaced at least
MIN_INTERVAL_S apart (<= 2 per second, a fifth of the SEC's stated ceiling), and a pass fetches at
most `max_files` files, newest missing first, so history fills across passes.

THE FILES. The listing page names them `cnsfails<YYYYMM><a|b>[_n].zip`: `a` covers the first half
of the month, `b` the second. Each holds one pipe-delimited table: SETTLEMENT DATE | CUSIP | SYMBOL
| QUANTITY (FAILS) | DESCRIPTION | PRICE (the previous day's close; "." when unavailable). Only the
listing's own hrefs are fetched; no URL is constructed.

POINT IN TIME. The page states the schedule: "The first half of a month is posted at the end of
that month. The second half is posted around the 15th of the following month." A file is
therefore AVAILABLE no earlier than a conservative bound on that schedule -- the 5th of the
following month for `a`, the 20th for `b`, 00:00 UTC -- and no earlier than the server's own
Last-Modified stamp when that stamp is a plausible first posting (within LATE_POSTING_DAYS of the
bound; a stamp later than that is a re-upload of an old file and would erase its history, so the
bound stands and the record says so). `available_time = max(bound, plausible Last-Modified)`, and
the consuming families add their own publication-day lag on top. Each file is stored once, as
fetched, under data/lake/sec_ftd/ and never rewritten: the store is a vintage. A re-uploaded file
(`_0` suffix) is a separate vintage; a period's FIRST vintage is the one the series reads.

THE MAPPING. ETFs map to the index, metal and energy CFDs they track (ETF_CFD, a fact table);
single names map to their share CFD through `libs.data.free_stack.TICKER_CFD`. Which rows reach
an instrument is decided against the broker registry at run time. Share-CFD series are written
for the event lane; whether a cell may be MINTED on one is the two-lane policy's decision, taken
by the factory, not here.

THE SERIES. data/lake/series/ftd_<MT5SYMBOL>.parquet, one row per half-month period:
`event_time` (the period's last settlement date), `published_time`, `available_time`,
`retrieval_time`, `source_id`, `vintage_id`, and the signals `ftd_value_usd` (sum of fails x
previous close across the mapped tickers and settlement days), `ftd_value_log` (log1p of it),
`ftd_shares` and `ftd_days`. It is a derived view of the vintage store, rebuilt each pass.

NOTHING HERE PROMOTES, SIZES OR CONDITIONS CAPITAL.

    python desks/mt5/research/sec_ftd.py --once [--dry-run] [--max-files N]
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
STORE = DATA / "lake" / "sec_ftd"
SERIES_DIR = DATA / "lake" / "series"
UNIVERSE_JSON = DATA / "universe" / "universe.json"

LISTING_URL = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
UA_ENV = "QUANT_EDGAR_UA"
#: Seconds between any two requests: at most two a second.
MIN_INTERVAL_S = 0.5
DEFAULT_MAX_FILES = 24
MAX_BYTES = 64 * 1024 * 1024
TIMEOUT_S = 30
#: A Last-Modified later than the schedule bound by more than this is a re-upload, not a posting.
LATE_POSTING_DAYS = 45
SOURCE_ID = "sec_ftd"
SERIES_PREFIX = "ftd_"

FILE_RE = re.compile(r"cnsfails(\d{4})(\d{2})([ab])(?:_(\d+))?\.zip", re.IGNORECASE)
HREF_RE = re.compile(r"""href=["']([^"']*cnsfails\d{6}[ab](?:_\d+)?\.zip)["']""", re.IGNORECASE)

#: ETF -> the MT5 CFD it tracks. A FACT TABLE; the registry decides at run time which rows reach
#: an instrument this broker lists.
ETF_CFD: dict[str, str] = {
    "SPY": "US500", "IVV": "US500", "VOO": "US500", "QQQ": "NAS100", "DIA": "US30",
    "IWM": "US2000", "GLD": "XAUUSD", "IAU": "XAUUSD", "SLV": "XAGUSD", "PPLT": "XPTUSD",
    "PALL": "XPDUSD", "CPER": "XCUUSD", "USO": "XTIUSD", "BNO": "XBRUSD", "UNG": "XNGUSD",
    "EWJ": "JPN225", "EWG": "GER40", "EWU": "UK100", "EWH": "HK50", "EWA": "AUS200",
    "EWQ": "FRA40", "EWP": "E35", "EWN": "NETH25", "EWC": "CA60", "FEZ": "EUSTX50",
}

Fetch = Callable[[str, str], tuple[bytes, dict[str, str]]]


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def user_agent() -> str | None:
    """The declared User-Agent, or None. Never printed: callers only test it for presence."""
    ua = os.environ.get(UA_ENV, "").strip()
    return ua or None


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, path)
    except PermissionError:
        # legal on POSIX, WinError 5 on the box when the destination is read-only
        path.chmod(0o644)
        os.replace(tmp, path)


# ----------------------------------------------------------------------------- the network
class Throttled:
    """urllib with a declared User-Agent and a floor between requests. Never logs the agent."""

    def __init__(self, ua: str, *, min_interval_s: float = MIN_INTERVAL_S) -> None:
        self._ua = ua
        self._gap = max(MIN_INTERVAL_S, float(min_interval_s))
        self._last = 0.0
        self.requests = 0

    def __call__(self, url: str, accept: str) -> tuple[bytes, dict[str, str]]:
        wait = self._last + self._gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua, "Accept": accept,
                                                   "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                body = r.read(MAX_BYTES + 1)
                headers = {k.lower(): v for k, v in r.headers.items()}
        finally:
            self._last = time.monotonic()
            self.requests += 1
        if len(body) > MAX_BYTES:
            raise ValueError(f"response over {MAX_BYTES} bytes")
        return body, headers


def listing(html: str) -> list[dict[str, Any]]:
    """Every FTD file the listing page links, as {name, url, period, half, vintage}. Only hrefs
    the page itself carries; a name the pattern does not parse is skipped."""
    out: dict[str, dict[str, Any]] = {}
    for href in HREF_RE.findall(html):
        url = urllib.parse.urljoin(LISTING_URL, href)
        if not url.startswith("https://www.sec.gov/"):
            continue
        name = url.rsplit("/", 1)[-1]
        m = FILE_RE.fullmatch(name)
        if not m:
            continue
        out[name.lower()] = {"name": name.lower(), "url": url,
                             "period": f"{m.group(1)}{m.group(2)}{m.group(3).lower()}",
                             "year": int(m.group(1)), "month": int(m.group(2)),
                             "half": m.group(3).lower(), "vintage": int(m.group(4) or -1)}
    return sorted(out.values(), key=lambda r: (r["period"], r["vintage"]))


# ----------------------------------------------------------------------------- point in time
def schedule_bound(year: int, month: int, half: str) -> datetime:
    """The earliest instant the SEC's stated schedule allows the file to be public, padded."""
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return datetime(ny, nm, 5 if half == "a" else 20, tzinfo=UTC)


def available_time(year: int, month: int, half: str,
                   last_modified: str | None) -> tuple[datetime, str]:
    """(available_time, basis). max(schedule bound, a plausible Last-Modified)."""
    bound = schedule_bound(year, month, half)
    lm: datetime | None = None
    if last_modified:
        try:
            from email.utils import parsedate_to_datetime
            lm = parsedate_to_datetime(last_modified).astimezone(UTC)
        except (TypeError, ValueError, IndexError):
            lm = None
    if lm is None:
        return bound, "schedule bound (no Last-Modified)"
    if lm <= bound:
        return bound, "schedule bound (Last-Modified earlier)"
    if lm - bound <= timedelta(days=LATE_POSTING_DAYS):
        return lm, "Last-Modified (a late posting)"
    return bound, (f"schedule bound (Last-Modified {lm.date()} is over {LATE_POSTING_DAYS} days "
                   "late: a re-upload, not the first posting)")


# ----------------------------------------------------------------------------- the file
def parse_ftd(zip_bytes: bytes) -> pd.DataFrame:
    """The table inside one FTD zip. Header, trailer and malformed lines are skipped."""
    rows: list[tuple[str, str, str, float, str, float]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for member in z.namelist():
            if member.endswith("/"):
                continue
            text = z.read(member).decode("latin-1", errors="replace")
            for line in text.splitlines():
                parts = line.split("|")
                if len(parts) < 6 or not re.fullmatch(r"\d{8}", parts[0].strip()):
                    continue
                try:
                    qty = float(parts[3].strip())
                except ValueError:
                    continue
                px_raw = parts[5].strip()
                try:
                    px = float(px_raw) if px_raw not in ("", ".") else math.nan
                except ValueError:
                    px = math.nan
                rows.append((parts[0].strip(), parts[1].strip(), parts[2].strip().upper(), qty,
                             parts[4].strip(), px))
    f = pd.DataFrame(rows, columns=["settlement_date", "cusip", "symbol", "quantity",
                                    "description", "price"])
    f["settlement_date"] = pd.to_datetime(f["settlement_date"], format="%Y%m%d", errors="coerce",
                                          utc=True)
    return f.dropna(subset=["settlement_date"])


def ticker_map(registry: Mapping[str, Any]) -> dict[str, str]:
    """US ticker -> the MT5 CFD this broker lists. ETFs first, then share CFDs."""
    reg = {k for k, v in registry.items() if isinstance(v, dict)}
    out = {t: c for t, c in ETF_CFD.items() if c in reg}
    try:
        from libs.data.free_stack import TICKER_CFD
    except Exception:                                    # pragma: no cover - import on the box
        TICKER_CFD = {}
    for t, c in TICKER_CFD.items():
        if c in reg:
            out.setdefault(t.upper(), c)
    return out


# ----------------------------------------------------------------------------- the store
def stored(store: Path) -> dict[str, dict[str, Any]]:
    """{file name: its stamp record} for every vintage already held."""
    out: dict[str, dict[str, Any]] = {}
    for meta in sorted(store.glob("cnsfails*.json")):
        try:
            rec = json.loads(meta.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and (store / f"{meta.stem}.parquet").exists():
            out[meta.stem] = rec
    return out


def store_file(store: Path, item: Mapping[str, Any], frame: pd.DataFrame,
               headers: Mapping[str, str], retrieved: datetime) -> dict[str, Any]:
    """Write one vintage, once. An existing vintage is never rewritten."""
    stem = Path(str(item["name"])).stem
    pq, meta = store / f"{stem}.parquet", store / f"{stem}.json"
    if pq.exists() and meta.exists():
        return json.loads(meta.read_text("utf-8"))
    at, basis = available_time(int(item["year"]), int(item["month"]), str(item["half"]),
                               headers.get("last-modified"))
    rec = {"name": item["name"], "url": item["url"], "period": item["period"],
           "vintage": item["vintage"], "rows": len(frame),
           "settlement_first": str(frame["settlement_date"].min().date()) if len(frame) else None,
           "settlement_last": str(frame["settlement_date"].max().date()) if len(frame) else None,
           "last_modified": headers.get("last-modified"),
           "available_time": at.isoformat(), "available_basis": basis,
           "retrieval_time": retrieved.isoformat(timespec="seconds"), "source_id": SOURCE_ID}
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    _atomic_bytes(pq, buf.getvalue())
    _atomic_bytes(meta, json.dumps(rec, indent=1).encode())
    return rec


def collect(*, store: Path = STORE, fetch: Fetch | None = None, max_files: int = DEFAULT_MAX_FILES,
            dry_run: bool = False, deadline: float | None = None) -> dict[str, Any]:
    """One pass: read the listing, fetch the newest missing files up to `max_files`."""
    if fetch is None:
        ua = user_agent()
        if ua is None:
            return {"status": "NEEDS_KEY", "fetched": 0,
                    "why": (f"no {UA_ENV} in this environment: the SEC requires a declared "
                            "User-Agent, so nothing was fetched")}
        fetch = Throttled(ua)
    try:
        html, _ = fetch(LISTING_URL, "text/html")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "fetched": 0,
                "why": f"listing unreachable: {type(exc).__name__}"}
    files = listing(html.decode("utf-8", errors="replace"))
    held = stored(store)
    missing = [f for f in files if Path(f["name"]).stem not in held]
    missing.sort(key=lambda r: (r["period"], r["vintage"]), reverse=True)     # newest first
    todo = missing[:max(0, int(max_files))]
    out: dict[str, Any] = {"status": "COLLECTING", "listed": len(files), "held": len(held),
                           "missing": len(missing), "planned": [f["name"] for f in todo],
                           "fetched": 0, "errors": []}
    if dry_run:
        out["status"] = "DRY_RUN"
        return out
    for item in todo:
        if deadline is not None and time.monotonic() > deadline:
            out["errors"].append({"file": item["name"], "why": "budget spent; next pass"})
            break
        try:
            body, headers = fetch(item["url"], "application/zip")
            frame = parse_ftd(body)
        except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as exc:
            out["errors"].append({"file": item["name"], "why": type(exc).__name__})
            continue
        store_file(store, item, frame, headers, now_utc())
        out["fetched"] += 1
    out["held"] = len(stored(store))
    return out


# ----------------------------------------------------------------------------- the series
def build_series(*, store: Path = STORE, series_dir: Path = SERIES_DIR,
                 registry: Mapping[str, Any] | None = None, write: bool = True
                 ) -> dict[str, dict[str, Any]]:
    """Fold the vintage store into one PIT series per mapped MT5 CFD.

    Returns {MT5 symbol: {"periods", "first", "last", "tickers"}} -- a summary, never a frame."""
    if registry is None:
        try:
            registry = json.loads(UNIVERSE_JSON.read_text("utf-8"))
        except (OSError, ValueError):
            registry = {}
    tmap = ticker_map(registry or {})
    held = stored(store)
    first_vintage: dict[str, tuple[str, dict[str, Any]]] = {}
    for stem, rec in sorted(held.items(), key=lambda kv: int(kv[1].get("vintage", -1))):
        first_vintage.setdefault(str(rec.get("period")), (stem, rec))
    per_sym: dict[str, list[dict[str, Any]]] = {}
    tickers: dict[str, set[str]] = {}
    for period, (stem, rec) in sorted(first_vintage.items()):
        try:
            f = pd.read_parquet(store / f"{stem}.parquet")
        except Exception:
            continue
        f = f[f["symbol"].isin(list(tmap))]
        if f.empty:
            continue
        f = f.assign(cfd=f["symbol"].map(tmap),
                     value=pd.to_numeric(f["quantity"], errors="coerce")
                     * pd.to_numeric(f["price"], errors="coerce"))
        for cfd, g in f.groupby("cfd"):
            value = float(g["value"].fillna(0.0).sum())
            per_sym.setdefault(str(cfd), []).append({
                "event_time": pd.Timestamp(g["settlement_date"].max()),
                "published_time": rec.get("last_modified"),
                "available_time": pd.Timestamp(rec["available_time"]),
                "retrieval_time": pd.Timestamp(rec["retrieval_time"]),
                "source_id": SOURCE_ID, "vintage_id": stem, "period": period,
                "ftd_value_usd": value, "ftd_value_log": math.log1p(max(value, 0.0)),
                "ftd_shares": float(pd.to_numeric(g["quantity"], errors="coerce").sum()),
                "ftd_days": int(g["settlement_date"].nunique())})
            tickers.setdefault(str(cfd), set()).update(str(s) for s in g["symbol"].unique())
    summary: dict[str, dict[str, Any]] = {}
    for cfd, rows in sorted(per_sym.items()):
        frame = pd.DataFrame(rows).sort_values("available_time").reset_index(drop=True)
        if write:
            buf = io.BytesIO()
            frame.to_parquet(buf, index=False)
            _atomic_bytes(series_dir / f"{SERIES_PREFIX}{cfd}.parquet", buf.getvalue())
        summary[cfd] = {"periods": len(frame), "first": str(frame["event_time"].min().date()),
                        "last": str(frame["event_time"].max().date()),
                        "last_available": str(frame["available_time"].max()),
                        "tickers": sorted(tickers.get(cfd, set()))}
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="read the listing only; write nothing")
    ap.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    a = ap.parse_args(argv)
    c = collect(max_files=a.max_files, dry_run=a.dry_run)
    s = build_series(write=not a.dry_run) if not a.dry_run else {}
    print(f"sec_ftd: {c['status']} listed={c.get('listed')} held={c.get('held')} "
          f"fetched={c.get('fetched')} series={len(s)}")
    if c.get("why"):
        print(f"  why: {c['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
