"""ONE GENERIC COLLECTOR FOR EVERY REGISTERED SOURCE. No source is ever blocked for want of one.

THE LAW (principal, 2026-09-15): if any declared data is ever blocked because nobody wrote a
collector for it, that is a FLAW. Collectors are permanent and universal, not per-source
favours.

WHY THAT IS AN ARCHITECTURE STATEMENT AND NOT A WORK ITEM. The registry holds 89 sources and 774
cells, and 750 of those cells were BLOCKED_ON_DATA -- each waiting on a bespoke fetcher nobody had
written. Writing 89 fetchers would take weeks, rot at 89 different rates, and guarantee that the
90th source is blocked again on the day it is added. The registry already declares everything a
fetch needs: the address, the SHAPE the body should have, the cadence, and what needs a key. So
the collector is DRIVEN BY THE REGISTRY and a new source is collected the moment it is declared.

WHAT IT REFUSES TO DO, because a collector that invents data is worse than none:

    ROUTE_CHANGED   HTTP 200 with the wrong SHAPE -- HTML where JSON or CSV was declared. This is
                    the NOAA failure this desk already paid for: `CurrentSummaries.json` was
                    renamed, the old path answered 200 with an error page, the miner parsed it,
                    found no storm records and reported NO ACTIVE STORMS with four hurricanes
                    live. Absence is a verdict, never an empty series.
    UNCONFIGURED    the source declares `access: key` or `paid` and no key is present. NOT a
                    failure and NOT a silent skip: a named state, so a missing subscription can
                    never be mistaken for a dead endpoint.
    BLOCKED_BY_ROBOTS  the host's robots.txt disallows the path. Refused and recorded. Public
                    or licensed only is a hard line, not a preference.

EVERYTHING IS VAULTED POINT-IN-TIME. The raw bytes are written under their own content hash and
never overwritten, so a claim made today can be re-read against exactly what the page said when
it said it. A parse that improves later can be re-run over the vault without re-fetching, and a
source that silently changes shape leaves both versions on disk to be diffed.

THIS DOES NOT PARSE EVERY SOURCE INTO A SERIES, AND SAYS SO. A CSV or JSON endpoint yields a
frame; an HTML statistics portal yields vaulted bytes and `NEEDS_PARSER`, which is a named, ranked
backlog item rather than an invisible gap. The distinction is the whole point: NEEDS_PARSER means
the bytes are on disk and the work is downstream; BLOCKED_ON_DATA meant nothing had ever been
fetched at all.

    python desks/mt5/research/asia_collector.py                 # collect every due public source
    python desks/mt5/research/asia_collector.py --id sge_benchmark
    python desks/mt5/research/asia_collector.py --dry-run
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = BASE / "data" / "asia_sources.json"
VAULT = BASE / "data" / "lake" / "vault"
SERIES = BASE / "data" / "lake" / "series"
STATE = BASE / "data" / "lake" / "collector_state.json"
OUT = BASE / "reports" / "ASIA_COLLECTOR.json"

#: Bytes read per fetch. Generous enough for a daily statistics file, small enough that a
#: misconfigured source cannot fill the disk before the next pass notices.
MAX_BYTES = 8 * 1024 * 1024
#: Seconds between fetches of the SAME HOST. Politeness is not optional on public endpoints, and
#: a collector that hammers a government portal gets the desk blocked from it permanently.
HOST_DELAY_S = 2.0
#: Hosts fetched at once. Politeness is per HOST and is preserved exactly by a per-host lock, so
#: workers only ever overlap DIFFERENT servers. Eight hides the timeouts without making this desk
#: a nuisance to a dozen government sites at once.
WORKERS = int(os.environ.get("ASIA_COLLECTOR_WORKERS", "8"))
#: Cadence -> seconds before a source is due again. A daily statistic fetched hourly is twenty-
#: three wasted requests and one rate-limit away from a ban.
DUE_AFTER = {
    "daily": 20 * 3600, "weekly": 6 * 24 * 3600, "monthly": 20 * 24 * 3600,
    "10-daily": 8 * 24 * 3600, "fortnightly": 12 * 24 * 3600, "hourly": 3000,
    "on demand": 24 * 3600, "on change": 7 * 24 * 3600, "scheduled": 24 * 3600,
    "weekly, on a published calendar": 6 * 24 * 3600,
    "fortnightly, on a published calendar": 12 * 24 * 3600,
    "monthly announcement, daily execution": 20 * 3600,
}
DEFAULT_DUE_S = 24 * 3600

#: Built once: a CA bundle lookup per fetch is wasted work on an 85-source pass.
_TLS = None

_ACCEPT = {
    "json": ("json", "javascript"),
    "csv": ("csv", "text/plain", "octet-stream"),
    "xml": ("xml",),
    "binary": ("octet-stream", "excel", "spreadsheet", "zip", "pdf"),
    "any": (),
}


def _tls_context():
    """A verified TLS context using certifi's CA bundle, or None to keep the default.

    THIS IS NOT A VERIFICATION BYPASS AND MUST NEVER BECOME ONE. Measured 2026-09-15: 26 of 85
    sources -- every Chinese government host among them -- failed with
    `CERTIFICATE_VERIFY_FAILED: self-signed certificate`. A self-signed chain on safe.gov.cn is
    not a broken government site; it is TLS interception on this host's egress path, and the
    system trust store simply does not carry the intercepting CA's roots for those chains.

    With certifi's bundle the same request completes and returns an honest HTTP 404 -- which is
    a REAL verdict about a URL that needs correcting, where UNREACHABLE was a verdict about the
    network. Turning verification off would have produced the same 404 and thrown away the
    guarantee that the bytes came from who they claim to; this keeps the guarantee and changes
    only which roots are trusted.
    """
    try:
        import ssl

        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def _key_present(src: dict[str, Any]) -> bool:
    import os
    env = str(src.get("key_env") or "")
    return bool(env and os.environ.get(env))


def _robots_allows(url: str, agent: str = "quant-desk-collector") -> tuple[bool, str]:
    """Ask the host's robots.txt. A host that cannot be asked is treated as ALLOWING.

    Deliberately permissive on failure and deliberately strict on a real DISALLOW: an unreachable
    robots.txt is a network fact, not a prohibition, while a served DISALLOW is the host stating
    its terms and this desk does not work around a stated term.
    """
    try:
        from urllib.robotparser import RobotFileParser
        parts = urllib.parse.urlsplit(url)
        rp = RobotFileParser()
        robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
        req = urllib.request.Request(robots, headers={"User-Agent": agent})
        with urllib.request.urlopen(req, timeout=12, context=_TLS) as r:
            rp.parse(r.read(200_000).decode("utf-8", errors="replace").splitlines())
        return (bool(rp.can_fetch(agent, url)), "robots.txt consulted")
    except Exception as exc:
        return True, f"robots.txt unreadable ({type(exc).__name__}); treated as allowing"


def _vault(source_id: str, body: bytes, url: str, ctype: str) -> dict[str, Any]:
    """Write the raw bytes under their content hash. Never overwrites, never deletes."""
    digest = hashlib.sha256(body).hexdigest()
    d = VAULT / source_id
    d.mkdir(parents=True, exist_ok=True)
    blob = d / f"{digest[:16]}.gz"
    fresh = not blob.exists()
    if fresh:
        blob.write_bytes(gzip.compress(body))
        _write_atomic(blob.with_suffix(".meta.json"), json.dumps({
            "source_id": source_id, "url": url, "content_type": ctype,
            "sha256": digest, "bytes": len(body),
            "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }, indent=1))
    return {"sha256": digest, "blob": str(blob), "bytes": len(body), "new_content": fresh}


def _parse(body: bytes, expect: str, source_id: str) -> dict[str, Any]:
    """Body -> a stored frame where the declared shape allows one, else NEEDS_PARSER.

    NO SHAPE IS GUESSED. A declared `json` that does not parse as JSON is a route change, not a
    parser problem, and calling it one would hide the NOAA failure all over again.
    """
    if expect == "json":
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError as exc:
            return {"parsed": False, "why": f"declared json and did not parse: {exc}"}
        SERIES.mkdir(parents=True, exist_ok=True)
        _write_atomic(SERIES / f"{source_id}.json", json.dumps(doc, indent=1)[:4_000_000])
        n = len(doc) if isinstance(doc, (list, dict)) else 1
        return {"parsed": True, "kind": "json", "n": n,
                "path": str(SERIES / f"{source_id}.json")}
    if expect == "csv":
        try:
            import io

            import pandas as pd
            df = pd.read_csv(io.BytesIO(body))
        except Exception as exc:
            return {"parsed": False, "why": f"declared csv and did not parse: {type(exc).__name__}"}
        if df.empty:
            return {"parsed": False, "why": "csv parsed to zero rows"}
        SERIES.mkdir(parents=True, exist_ok=True)
        out = SERIES / f"{source_id}.parquet"
        try:
            df.to_parquet(out)
        except Exception:
            out = SERIES / f"{source_id}.csv"
            df.to_csv(out, index=False)
        return {"parsed": True, "kind": "csv", "n": len(df),
                "columns": [str(c) for c in df.columns][:20], "path": str(out)}
    # HTML portals, XML statistics pages, PDFs: the bytes are vaulted and the parser is a NAMED
    # backlog item. This is the honest half of "no source is ever blocked" -- the fetch is never
    # the thing missing again, and what remains is downstream work with the data already on disk.
    return {"parsed": False, "kind": expect,
            "why": ("vaulted, and this shape needs a source-specific parser. The BYTES ARE ON "
                    "DISK, so this is downstream work and not a missing fetch -- which is the "
                    "whole difference between NEEDS_PARSER and BLOCKED_ON_DATA")}


def _parses_as(body: bytes, expect: str) -> bool:
    """Does a small body parse as its declared type? Used only to spare valid tiny payloads."""
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return False
    if expect == "json":
        try:
            json.loads(text)
        except ValueError:
            return False
        return True
    if expect == "xml":
        return text.startswith("<")
    if expect == "csv":
        return "," in text or '\n' in text
    return len(text) > 8


def _resolve_url(src: dict[str, Any]) -> str:
    """Expand date placeholders in a source's url.

    EXCHANGE ENDPOINTS ARE DATED, AND A STATIC REGISTRY CANNOT SAY SO. CFFEX publishes each
    session at `/sj/hqsj/rtj/<YYYYMM>/<DD>/index.xml`; SHFE, DCE and INE are the same shape. A
    registry holding one frozen URL can only ever fetch one day, so these read as NO_TABLE
    forever while their data sits one path segment away.

    Placeholders are `{yyyymm}`, `{yyyy}`, `{mm}`, `{dd}` and `{yyyy-mm-dd}`, resolved against
    today minus `url_lag_days` (default 1, because a session's file appears after it closes).
    A url with no placeholder is returned untouched, so nothing existing changes.
    """
    from datetime import timedelta
    url = str(src.get("url") or "")
    if "{" not in url:
        return url
    lag = src.get("url_lag_days")
    # UTC, not local: an exchange file is published against a calendar day, and a box in a
    # different timezone must not ask for tomorrow's session or re-fetch yesterday's twice.
    days = int(lag) if isinstance(lag, (int, float)) else 1
    d = (datetime.now(UTC) - timedelta(days=days)).date()
    return (url.replace("{yyyymm}", f"{d:%Y%m}").replace("{yyyy-mm-dd}", f"{d:%Y-%m-%d}")
               .replace("{yyyy}", f"{d:%Y}").replace("{mm}", f"{d:%m}").replace("{dd}", f"{d:%d}"))


def collect_one(src: dict[str, Any], timeout: float = 25.0,
                validators: dict[str, str] | None = None) -> dict[str, Any]:
    """One source, one verdict. Never raises: an unfetched source is named, never assumed empty."""
    sid = str(src.get("id") or "")
    url = _resolve_url(src)
    expect = str(src.get("expect") or "any")
    access = str(src.get("access") or "public")
    rec: dict[str, Any] = {"id": sid, "plane": src.get("plane"), "url": url, "expect": expect,
                           "access": access,
                           "collected_utc": datetime.now(UTC).isoformat(timespec="seconds")}

    if access in ("key", "paid") and not _key_present(src):
        rec.update({"status": "UNCONFIGURED", "key_env": src.get("key_env"),
                    "why": (f"declares {access} access and {src.get('key_env') or 'no key env'} "
                            f"is not set. A named state, never a failure and never a silent "
                            f"skip: a missing subscription must not read as a dead endpoint")})
        return rec

    allowed, why_robots = _robots_allows(url)
    rec["robots"] = why_robots
    if not allowed:
        rec.update({"status": "BLOCKED_BY_ROBOTS",
                    "why": "the host's robots.txt disallows this path; public or licensed only "
                           "is a hard line and this desk does not work around a stated term"})
        return rec

    # CONDITIONAL GET. A 304 costs a round trip and no body, and most of these sources publish
    # daily or monthly against a pass that may run hourly -- so the default behaviour is to
    # re-download an unchanged page over and over. The validators come from the LAST successful
    # fetch of this exact source, stored beside its cadence in collector_state.
    #
    # A 304 IS A RESULT, NOT A MISS: it says the vault's newest blob is still current, which is
    # exactly what a point-in-time store wants to hear. It is recorded as UNCHANGED so a reader
    # can tell "nothing new" from "nothing fetched", which is the same distinction this file
    # draws everywhere else.
    headers = {"User-Agent": "quant-desk-collector/1.0 (+public data collection)",
               "Accept": "*/*"}
    if isinstance(validators, dict):
        if validators.get("etag"):
            headers["If-None-Match"] = str(validators["etag"])
        if validators.get("last_modified"):
            headers["If-Modified-Since"] = str(validators["last_modified"])
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_TLS) as r:
            status = int(getattr(r, "status", 0) or 0)
            ctype = str(r.headers.get("Content-Type") or "").lower()
            etag = r.headers.get("ETag")
            last_mod = r.headers.get("Last-Modified")
            body = r.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        if code == 304:
            rec.update({"status": "UNCHANGED", "http": 304,
                        "why": ("the source has not changed since the last fetch (conditional "
                                "GET). The vault's newest blob is still current -- nothing new, "
                                "which is not the same as nothing fetched.")})
            return rec
        rec.update({"status": "HTTP_ERROR", "http": code,
                    "why": (f"HTTP {code}" if code not in (401, 403)
                            else f"HTTP {code}: authentication or access control, not a route "
                                 f"change")})
        return rec
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        rec.update({"status": "UNREACHABLE", "why": f"{type(e).__name__}: {str(e)[:90]}"})
        return rec
    except Exception as e:
        rec.update({"status": "UNMEASURED", "why": f"{type(e).__name__}: {str(e)[:90]}"})
        return rec

    rec.update({"http": status, "content_type": ctype, "bytes": len(body)})
    accept = _ACCEPT.get(expect, ())
    looks_html = ("html" in ctype) or body[:200].lstrip().lower().startswith(
        (b"<!doctype html", b"<html"))
    if accept and looks_html:
        rec.update({"status": "ROUTE_CHANGED",
                    "why": (f"HTTP 200 with an HTML body where {expect} was declared. This is the "
                            f"NOAA shape: an error or landing page a parser reads as NO DATA. "
                            f"Absence is a verdict, never an empty series")})
        return rec
    if accept and not any(a in ctype for a in accept):
        rec.update({"status": "ROUTE_CHANGED",
                    "why": f"content-type {ctype!r} does not match declared {expect!r}"})
        return rec
    # SIZE IS NOT THE TEST -- SHAPE IS. The 64-byte floor exists to catch an endpoint that answers
    # 200 with nothing, and it wrongly condemned a valid one: Riksbank's latest-observation route
    # returns `{"date":"2026-09-14","value":9.76625}`, which is 37 bytes of perfectly good data
    # and was marked ROUTE_CHANGED -- the same class of false verdict this collector exists to
    # prevent, committed by the guard itself. A body that PARSES as its declared type is data at
    # any size; only an unparseable tiny body is empty.
    if len(body) < 64 and not _parses_as(body, expect):
        rec.update({"status": "ROUTE_CHANGED",
                    "why": (f"only {len(body)} bytes and it does not parse as {expect}: "
                            f"reachable and carrying nothing")})
        return rec

    # Stored for the NEXT pass's conditional GET. Absent headers simply mean no validator, and
    # the next fetch is unconditional -- correct, and never a silent skip.
    rec["validators"] = {k: v for k, v in
                         (("etag", etag), ("last_modified", last_mod)) if v}
    rec["vault"] = _vault(sid, body, url, ctype)
    parsed = _parse(body, expect, sid)
    rec["parse"] = parsed
    rec["status"] = "COLLECTED" if parsed.get("parsed") else "NEEDS_PARSER"
    return rec


def due(src: dict[str, Any], state: dict[str, Any], now: float) -> bool:
    last = (state.get(str(src.get("id"))) or {}).get("last_attempt_epoch")
    if not isinstance(last, (int, float)):
        return True
    window = DUE_AFTER.get(str(src.get("cadence") or ""), DEFAULT_DUE_S)
    return (now - float(last)) >= window


def main(argv: list[str] | None = None) -> int:
    global _TLS
    _TLS = _tls_context()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", action="append", help="collect only these source ids")
    ap.add_argument("--timeout", type=float, default=25.0)
    ap.add_argument("--budget", type=float, default=600.0, help="seconds for the whole pass")
    ap.add_argument("--dry-run", action="store_true", help="list what is due and fetch nothing")
    args = ap.parse_args(argv)

    registry = _read(REGISTRY, {})
    sources = [s for s in (registry.get("sources") or []) if isinstance(s, dict)]
    if args.id:
        want = set(args.id)
        sources = [s for s in sources if str(s.get("id")) in want]
    state = _read(STATE, {})
    now = time.time()
    # A TRANSPORT CARRIES OTHER SOURCES AND HAS NO ENDPOINT OF ITS OWN TO COLLECT.
    todo = [s for s in sources
            if str(s.get("role") or "mechanism") != "transport" and (args.id or due(s, state, now))]

    if args.dry_run:
        print(f"asia collector: {len(todo)} of {len(sources)} source(s) due")
        for s in todo[:40]:
            print(f"  {s.get('id')!s:24} {s.get('cadence') or ''!s:12} "
                  f"{s.get('access')!s:8} {str(s.get('url'))[:60]}")
        return 0

    # CONCURRENT ACROSS HOSTS, STRICTLY SERIAL WITHIN ONE.
    #
    # The serial loop this replaces was the reason a pass could not finish. Eighty-five sources at
    # up to 25s of timeout each is thirty-five minutes of WALL CLOCK in the worst case, against a
    # budget of ten -- so whichever sources happened to sit behind the slow ones were DEFERRED
    # every pass, forever, exactly the starvation the gauntlet's build order suffers from. And the
    # sources most likely to be slow are government portals, which is most of this registry.
    #
    # Politeness is per HOST, not global, and that is the whole reason this is safe: HOST_DELAY_S
    # exists so one server is not hammered, and it is preserved exactly -- a per-host lock plus
    # the same gap. Two different hosts were never in contention, and waiting two seconds between
    # safe.gov.cn and rba.gov.au bought nothing but wall clock.
    #
    # WORKERS ARE FEW ON PURPOSE. Eight is enough to hide the timeouts and small enough that the
    # box's memory and this desk's reputation with a dozen government sites both survive it.
    started = time.monotonic()
    rows: list[Any] = [None] * len(todo)
    host_locks: dict[str, threading.Lock] = {}
    host_last: dict[str, float] = {}
    guard = threading.Lock()

    def _slot(host: str) -> threading.Lock:
        with guard:
            return host_locks.setdefault(host, threading.Lock())

    def _one(i: int, s: dict[str, Any]) -> None:
        if time.monotonic() - started > args.budget:
            rows[i] = {"id": s.get("id"), "status": "DEFERRED",
                       "why": "pass budget exhausted; due again next pass"}
            return
        host = urllib.parse.urlsplit(str(s.get("url") or "")).netloc
        with _slot(host):
            wait = HOST_DELAY_S - (time.monotonic() - host_last.get(host, -1e9))
            if wait > 0:
                time.sleep(min(wait, HOST_DELAY_S))
            host_last[host] = time.monotonic()
            prev = state.get(str(s.get("id"))) or {}
            rec = collect_one(s, timeout=args.timeout,
                              validators=prev.get("validators") if isinstance(prev, dict) else None)
        rows[i] = rec
        keep = {"last_attempt_epoch": time.time(), "last_status": rec.get("status")}
        # A 304 keeps the OLD validators: they are what proved the page unchanged, and replacing
        # them with nothing would make the next pass unconditional for no reason.
        keep["validators"] = (rec.get("validators")
                              or (prev.get("validators") if isinstance(prev, dict) else None) or {})
        with guard:
            state[str(s.get("id"))] = keep

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(lambda t: _one(*t), list(enumerate(todo))))
    rows = [r for r in rows if r is not None]

    _write_atomic(STATE, json.dumps(state, indent=1))
    census = Counter(str(r.get("status")) for r in rows)
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("NO SOURCE IS EVER BLOCKED FOR WANT OF A COLLECTOR. One generic collector is "
                "driven by the registry, so a source is collected the moment it is declared and "
                "the 90th source is not blocked on the day it is added."),
        "n_sources": len(sources), "n_attempted": len(rows),
        "census": dict(census),
        "series_written": [r["parse"]["path"] for r in rows
                           if isinstance(r.get("parse"), dict) and r["parse"].get("path")],
        "rows": rows,
    }
    _write_atomic(OUT, json.dumps(doc, indent=1))

    print(f"asia collector: {len(rows)} attempted of {len(sources)} -> {dict(census)}")
    for st in ("COLLECTED", "NEEDS_PARSER", "ROUTE_CHANGED", "HTTP_ERROR", "UNREACHABLE",
               "UNCONFIGURED", "BLOCKED_BY_ROBOTS"):
        rs = [r for r in rows if r.get("status") == st]
        if not rs:
            continue
        print(f"  {st} {len(rs)}:")
        for r in rs[:8]:
            extra = ""
            if st == "COLLECTED" and isinstance(r.get("parse"), dict):
                extra = f"  n={r['parse'].get('n')}"
            print(f"    {r.get('id')!s:24} {str(r.get('why') or '')[:58]}{extra}")
    print(f"  -> {OUT}")
    # ROUTE_CHANGED is the only fatal verdict: it is the one that silently becomes "no data".
    return 1 if census.get("ROUTE_CHANGED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
