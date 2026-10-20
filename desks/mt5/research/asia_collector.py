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
    BLOCKED_BY_ROBOTS
                    a HOLD, not a drop (LAWS 5e, AMENDED 2026-10-14 07:35Z by the principal,
                    decision card cmsg_012XFUfE12Rvggnu86fDb8pr5ze7a7HLob52jUdGwu28JR). The host's
                    robots.txt, read at the exact scheme://host:port under the User-Agent this
                    collector actually sends, disallows the path -- or could not be read in a way
                    RFC 9309 lets a crawler treat as consent -- so the page is NOT fetched. The
                    row is still written with `hold_cause`, `robots`, `robots_disallows` and
                    `terms_note`, so the source stays visible in every census. 404 on robots.txt
                    means allow; 5xx or unreachable means disallow FOR NOW and the source is
                    re-checked after ROBOTS_RECHECK_S; a 401/403/429 on robots.txt is a
                    PERSON-RELEASED hold (`site:<host>` in the collector state; zero requests to
                    that host until `--release-host HOST --released-by NAME`). A robots.txt that
                    was read is re-read at most once per 24h per origin.
    HARD_STOP       a HOLD, not a drop: the PAGE itself (or robots.txt) answered 401, 403 or 429,
                    or a WAF challenge (a `cf-mitigated: challenge` header, or a 403/503 whose body
                    carries Cloudflare's "Just a moment..." title -- never text on a 200 page).
                    Recorded as `site:<host>` with verdict HARD_STOP and the status; the host gets
                    zero requests until a person releases it. A plain 5xx stays HTTP_ERROR.

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
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
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
#: THE User-Agent the desk SENDS on every page fetch, and therefore the one robots.txt is read
#: under. Reading robots for one agent and fetching as another would obey a rule nobody wrote for
#: us. Robots groups are matched on the product token `ROBOTS_PRODUCT_TOKEN` (RFC 9309 2.2.1).
DESK_UA = ("quant-mt5-research-desk/1.0 (+https://github.com/kingdemond434-cpu/quant/issues; "
           "internal research; honours robots.txt)")
ROBOTS_PRODUCT_TOKEN = DESK_UA.split("/", 1)[0]          # "quant-mt5-research-desk"
#: Kept as an alias: older callers and tests read `USER_AGENT`.
USER_AGENT = DESK_UA
#: Seconds before a TIMED robots hold (robots.txt 5xx or unreachable) is re-read. RFC 9309
#: 2.3.1.4: an unreachable robots.txt is a complete disallow FOR NOW -- not a refusal.
ROBOTS_RECHECK_S = 3600.0
#: A robots.txt that was READ (200, or a 4xx that means "no rules") is re-read at most once per
#: this many seconds per origin (RFC 9309 2.4: caching up to 24 hours).
ROBOTS_CACHE_S = 24 * 3600.0
#: HTTP statuses on robots.txt that put a host under a PERSON-RELEASED hold (auditor's ruling
#: 2026-10-14): no timer releases it, and the host gets ZERO requests until `release_site_hold`.
PERSON_HOLD_STATUSES: frozenset[int] = frozenset({401, 403, 429})
#: Verdicts a site-hold record may carry. Both are active while `released_by` is null.
SITE_HOLD_VERDICTS: tuple[str, ...] = ("ROBOTS_HOLD", "HARD_STOP")
#: Bytes of robots.txt parsed. RFC 9309 2.5 asks a crawler to parse at least 500 KiB.
ROBOTS_MAX_BYTES = 512 * 1024
#: The per-origin robots.txt cache (gitignored lake, beside the collector state).
ROBOTS_CACHE = BASE / "data" / "lake" / "robots_cache.json"
#: Serialises read-modify-write of STATE / ROBOTS_CACHE across the collector's worker threads.
_STATE_LOCK = threading.Lock()


def _now() -> float:
    """The clock, one seam so tests can move it."""
    return time.time()


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


@dataclass(frozen=True)
class RobotsVerdict:
    """What robots.txt said about ONE url for ONE user agent, and what the desk does with it.

    `cause` is the named reason, so a hold is never a silent drop:
      allowed             robots.txt was read and permits this path for this agent
      robots_absent       robots.txt answered 404/410 (or another 4xx RFC 9309 reads as "no
                          rules", other than 401/403/429): allow
      disallow            robots.txt was read and DISALLOWS this path for this agent: no fetch
      robots_5xx          robots.txt answered 5xx: disallow for now, timed re-check
      robots_unreachable  robots.txt could not be reached at all: disallow for now, timed re-check
      person_hold         robots.txt answered 401/403/429, or the host already carries an
                          unreleased site hold: ZERO requests until a person releases it
    """

    allowed: bool
    cause: str
    why: str
    robots_url: str
    recheck: bool = False
    #: The site-hold record (see `site_hold_record`) when cause is person_hold.
    hold: dict[str, Any] | None = None


def _host(url: str) -> str:
    return urllib.parse.urlsplit(str(url or "")).netloc.lower()


def site_hold_record(host: str, url: str, status: int | None, verdict: str = "ROBOTS_HOLD",
                     at: float | None = None) -> dict[str, Any]:
    """The agreed record shape (with Global data), one row per refusing host."""
    if verdict not in SITE_HOLD_VERDICTS:
        raise ValueError(f"site hold verdict must be one of {SITE_HOLD_VERDICTS}: {verdict!r}")
    return {"key": f"site:{host}", "verdict": verdict, "status": status, "host": host,
            "url": str(url or "")[:300], "held_at": float(_now() if at is None else at),
            "released_by": None, "released_at": None}


def active_site_hold(host: str) -> dict[str, Any] | None:
    """The host's unreleased site hold, or None. Read from the collector STATE file."""
    row = (_read(STATE, {}) or {}).get(f"site:{host.lower()}")
    if isinstance(row, dict) and row.get("verdict") in SITE_HOLD_VERDICTS \
            and row.get("released_by") is None:
        return row
    return None


def _record_site_hold(rec: dict[str, Any]) -> None:
    with _STATE_LOCK:
        state = _read(STATE, {}) or {}
        state[str(rec["key"])] = rec
        _write_atomic(STATE, json.dumps(state, indent=1))


#: Cloudflare's interstitial title. Matched ONLY on a 403/503 body -- never on a 200 page, where
#: forum text quoting it has false-positived before.
_CHALLENGE_TITLE = re.compile(rb"<title>\s*just a moment\.\.\.\s*</title>", re.IGNORECASE)


def is_challenge(code: int | None, headers: Any, body: bytes | None) -> bool:
    """A WAF / bot challenge: a `cf-mitigated: challenge` header on any response, or a 403/503
    whose body carries Cloudflare's "Just a moment..." title. Plain body text on a 200 page is
    never read as a challenge."""
    try:
        mitigated = str((headers.get("cf-mitigated") if headers is not None else "") or "")
    except Exception:
        mitigated = ""
    if mitigated.strip().lower() == "challenge":
        return True
    return code in (403, 503) and bool(body) and bool(_CHALLENGE_TITLE.search(body or b""))


def hard_stop_for(url: str, code: int | None, headers: Any = None,
                  body: bytes | None = None) -> dict[str, Any] | None:
    """THE PRINCIPAL'S STANDING RULE: a 401, 403 or 429 on a PAGE, or a WAF challenge, is a HARD
    STOP. Records `site:<host>` (verdict HARD_STOP, status recorded) and returns the record; the
    host then gets zero requests until `release_site_hold`. A plain 5xx returns None -- it stays
    an ordinary error."""
    if not (code in PERSON_HOLD_STATUSES or is_challenge(code, headers, body)):
        return None
    rec = site_hold_record(_host(url), url, code, "HARD_STOP")
    _record_site_hold(rec)
    return rec


def _error_body(e: urllib.error.HTTPError, limit: int = 65536) -> bytes:
    try:
        return bytes(e.read(limit) or b"")
    except Exception:
        return b""


def fetch_bytes(url: str, *, agent: str = DESK_UA, max_bytes: int = MAX_BYTES,
                timeout: float = 25.0, reject_html: bool = False) -> tuple[bytes | None, str]:
    """One GET through the hold rules: (body, content-type) or (None, reason).

    The reason is `held:<verdict>` when the host already carries an unreleased site hold (no
    request is sent), `hard_stop:<status>` when this response put it under one, `html` when
    `reject_html` and the header says HTML, else `unreachable`. Robots is NOT read here -- the
    caller does that first (`robots_verdict`), exactly as `collect_one` does."""
    held = active_site_hold(_host(url))
    if held is not None:
        return None, f"held:{held.get('verdict')}"
    req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_TLS) as r:
            code = int(getattr(r, "status", 0) or 0)
            ctype = str(r.headers.get("Content-Type") or "").lower()
            if hard_stop_for(url, code, r.headers, None) is not None:
                return None, f"hard_stop:{code}"
            if reject_html and "html" in ctype:
                return None, "html"
            return r.read(max_bytes), ctype
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        if hard_stop_for(url, code, getattr(e, "headers", None), _error_body(e)) is not None:
            return None, f"hard_stop:{code}"
        return None, "unreachable"
    except (urllib.error.URLError, OSError, ValueError):
        return None, "unreachable"


def release_site_hold(host: str, released_by: str, at: float | None = None) -> dict[str, Any]:
    """THE ONLY WAY A SITE HOLD ENDS: a named person releases it. No timer ever does.

    Also drops the host's cached robots.txt, so the next pass reads it fresh."""
    who = str(released_by or "").strip()
    if not who:
        raise ValueError("a site hold is released by a named person; released_by is empty")
    host = host.lower()
    with _STATE_LOCK:
        state = _read(STATE, {}) or {}
        row = state.get(f"site:{host}")
        if not isinstance(row, dict):
            raise KeyError(f"no site hold recorded for {host!r}")
        row = {**row, "released_by": who,
               "released_at": float(_now() if at is None else at)}
        state[f"site:{host}"] = row
        _write_atomic(STATE, json.dumps(state, indent=1))
        cache = _read(ROBOTS_CACHE, {}) or {}
        for k in [k for k in cache if _host(k) == host]:
            del cache[k]
        _write_atomic(ROBOTS_CACHE, json.dumps(cache, indent=1))
    return row


def _cached_robots(origin: str, now: float) -> dict[str, Any] | None:
    row = (_read(ROBOTS_CACHE, {}) or {}).get(origin)
    if isinstance(row, dict) and isinstance(row.get("fetched_at"), (int, float)) \
            and now - float(row["fetched_at"]) < ROBOTS_CACHE_S:
        return row
    return None


def _cache_robots(origin: str, row: dict[str, Any]) -> None:
    with _STATE_LOCK:
        cache = _read(ROBOTS_CACHE, {}) or {}
        cache[origin] = row
        _write_atomic(ROBOTS_CACHE, json.dumps(cache, indent=1))


def robots_verdict(url: str, agent: str = DESK_UA) -> RobotsVerdict:
    """Read the host's robots.txt and decide whether `url` may be fetched (RFC 9309).

    LAWS 5e, AMENDED 2026-10-14 07:35Z by the principal (decision card
    cmsg_012XFUfE12Rvggnu86fDb8pr5ze7a7HLob52jUdGwu28JR): a robots.txt Disallow is RESPECTED AT
    FETCH TIME. A disallowed page is not fetched, and the caller logs the skip as a hold with
    this verdict's named cause. Everything else in 5e stands: labels never stop mining, there is
    no quarantine, and content about the page obtained lawfully by other means is still mined.

    Semantics: robots.txt is read at the EXACT origin (scheme, host and port) of the url, under
    the SAME agent string the page fetch sends, groups matched on its product token, and a read
    robots.txt is re-read at most once per 24h per origin. 404 means allow. 5xx or unreachable
    means a complete disallow FOR NOW, re-read on a timer -- not a refusal. A 401/403/429 on
    robots.txt is a PERSON-RELEASED hold (auditor's ruling 2026-10-14): the host is recorded as
    `site:<host>` and gets zero requests until `release_site_hold` names who released it.
    """
    from urllib.robotparser import RobotFileParser
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower()
    origin = f"{parts.scheme}://{parts.netloc}"
    robots = f"{origin}/robots.txt"
    held = active_site_hold(host)
    if held is not None:
        return RobotsVerdict(False, "person_hold",
                             f"{host} carries an unreleased {held.get('verdict')} (HTTP "
                             f"{held.get('status')}) since {held.get('held_at')}: zero requests "
                             f"until a person releases it", robots, hold=held)
    now = _now()
    cached = _cached_robots(origin, now)
    body: bytes | None = None
    if cached is not None:
        if cached.get("absent"):
            return RobotsVerdict(True, "robots_absent",
                                 f"{robots} answered HTTP {cached.get('status')} (cached): no "
                                 f"rules, allow", robots)
        body = str(cached.get("body") or "").encode("utf-8")
    else:
        req = urllib.request.Request(robots, headers={"User-Agent": agent})
        try:
            with urllib.request.urlopen(req, timeout=12, context=_TLS) as r:
                if is_challenge(int(getattr(r, "status", 0) or 0), r.headers, None):
                    rec = site_hold_record(host, url, int(getattr(r, "status", 0) or 0),
                                           "HARD_STOP", at=now)
                    _record_site_hold(rec)
                    return RobotsVerdict(False, "person_hold",
                                         f"{robots} carried cf-mitigated: challenge: HARD_STOP on "
                                         f"{host}, zero requests until a person releases it",
                                         robots, hold=rec)
                body = r.read(ROBOTS_MAX_BYTES)
        except urllib.error.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            if is_challenge(code, getattr(e, "headers", None), _error_body(e)):
                rec = site_hold_record(host, url, code, "HARD_STOP", at=now)
                _record_site_hold(rec)
                return RobotsVerdict(False, "person_hold",
                                     f"{robots} answered a WAF challenge (HTTP {code}): HARD_STOP "
                                     f"on {host}, zero requests until a person releases it",
                                     robots, hold=rec)
            if code in PERSON_HOLD_STATUSES:
                rec = site_hold_record(host, url, code, "ROBOTS_HOLD", at=now)
                _record_site_hold(rec)
                return RobotsVerdict(False, "person_hold",
                                     f"{robots} answered HTTP {code}: ROBOTS_HOLD on {host}, "
                                     f"zero requests until a person releases it", robots,
                                     hold=rec)
            if code >= 500:
                return RobotsVerdict(False, "robots_5xx",
                                     f"{robots} answered HTTP {code}: treated as disallow for "
                                     f"now (RFC 9309 2.3.1.4), re-checked later", robots,
                                     recheck=True)
            _cache_robots(origin, {"fetched_at": now, "status": code, "absent": True})
            return RobotsVerdict(True, "robots_absent",
                                 f"{robots} answered HTTP {code}: no rules, allow "
                                 f"(RFC 9309 2.3.1.3)", robots)
        except Exception as exc:
            return RobotsVerdict(False, "robots_unreachable",
                                 f"{robots} unreachable ({type(exc).__name__}): treated as "
                                 f"disallow for now (RFC 9309 2.3.1.4), re-checked later",
                                 robots, recheck=True)
        _cache_robots(origin, {"fetched_at": now, "status": 200,
                               "body": body.decode("utf-8", errors="replace")})
    token = agent.split("/")[0].strip() or agent
    rp = RobotFileParser()
    rp.parse(body.decode("utf-8", errors="replace").splitlines())
    if rp.can_fetch(token, url):
        return RobotsVerdict(True, "allowed", f"{robots} consulted: allowed for {token!r}",
                             robots)
    return RobotsVerdict(False, "disallow", f"{robots} disallows this path for {token!r}", robots)


def _robots_allows(url: str, agent: str = DESK_UA) -> tuple[bool, str]:
    """(allowed, why) -- the tuple shape older callers read. See `robots_verdict`."""
    v = robots_verdict(url, agent)
    return v.allowed, v.why


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
    # A ROUTE THE FIXER REPAIRED WINS OVER THE REGISTERED ONE (2026-09-16). `source_fixer`
    # writes `url_override` when a webmaster's variant of a dead URL answers in the declared
    # shape; the registered url stays as written so the repair is auditable and revertible.
    url = str(src.get("url_override") or src.get("url") or "")
    if "{" not in url:
        return url
    lag = src.get("url_lag_days")
    # UTC, not local: an exchange file is published against a calendar day, and a box in a
    # different timezone must not ask for tomorrow's session or re-fetch yesterday's twice.
    days = int(lag) if isinstance(lag, (int, float)) else 1
    d = (datetime.now(UTC) - timedelta(days=days)).date()
    return (url.replace("{yyyymm}", f"{d:%Y%m}").replace("{yyyy-mm-dd}", f"{d:%Y-%m-%d}")
               .replace("{yyyy}", f"{d:%Y}").replace("{mm}", f"{d:%m}").replace("{dd}", f"{d:%d}"))


#: Date tokens a source may write into its `form` values. The vocabulary is the one `_resolve_url`
#: already uses, plus the two a WINDOWED endpoint needs: a start and an end that move with the
#: clock. Sized by the source's own declared `window_days_back` / `window_days_fwd`.
def _window_dates(src: dict[str, Any]) -> tuple[str, str]:
    from datetime import timedelta
    back = src.get("window_days_back")
    fwd = src.get("window_days_fwd")
    back_d = int(back) if isinstance(back, (int, float)) else 30
    fwd_d = int(fwd) if isinstance(fwd, (int, float)) else 1
    today = datetime.now(UTC).date()
    return ((today - timedelta(days=back_d)).isoformat(),
            (today + timedelta(days=fwd_d)).isoformat())


def _resolve_token(text: str, src: dict[str, Any]) -> str:
    """Date placeholders inside a DECLARED form value. Same vocabulary as `_resolve_url`."""
    if "{" not in text:
        return text
    from datetime import timedelta
    lag = src.get("url_lag_days")
    days = int(lag) if isinstance(lag, (int, float)) else 1
    d = (datetime.now(UTC) - timedelta(days=days)).date()
    start, end = _window_dates(src)
    return (text.replace("{from_date}", start).replace("{to_date}", end)
                .replace("{yyyymm}", f"{d:%Y%m}").replace("{yyyy-mm-dd}", f"{d:%Y-%m-%d}")
                .replace("{yyyy}", f"{d:%Y}").replace("{mm}", f"{d:%m}")
                .replace("{dd}", f"{d:%d}"))


def _declared_form(src: dict[str, Any]) -> bytes | None:
    """The POST body a source DECLARES, or None -- and None is every source written before this.

    SOME PUBLIC ENDPOINTS ARE POST-ONLY AND THAT IS NOT A WALL. MetaQuotes' own economic calendar
    -- the one the MT5 terminal renders, fully public, no login, no paywall, no credential --
    answers `POST /en/economic-calendar/content` with a form naming the window, and answers 404
    to the same query as GET. A GET-only collector reads it as a dead route, which is exactly the
    false verdict this file exists to prevent: the endpoint is reachable and carrying data.

    The body is DECLARED, never guessed: a source names every field in `form`, and the only
    expansion is the date vocabulary above. Nothing is sent that the registry did not write.
    This is not an access control being bypassed -- there is no credential, no session and no
    paywall in a form that says which dates to return (hard boundary 2 is untouched).
    """
    form = src.get("form")
    if not isinstance(form, dict) or not form:
        return None
    return urllib.parse.urlencode(
        {str(k): _resolve_token(str(v), src) for k, v in form.items()}).encode()


def _declared_headers(src: dict[str, Any]) -> dict[str, str]:
    """Extra request headers a source DECLARES. Never a credential: `Authorization`, `Cookie` and
    friends are refused here, so a registry row can name a content-negotiation header (the
    `X-Requested-With` an endpoint's own page sends) and can never smuggle a secret."""
    hdr = src.get("request_headers")
    if not isinstance(hdr, dict):
        return {}
    banned = {"authorization", "cookie", "proxy-authorization", "x-api-key", "api-key"}
    return {str(k): _resolve_token(str(v), src) for k, v in hdr.items()
            if str(k).lower() not in banned}


def _hard_stop_row(rec: dict[str, Any], stop: dict[str, Any]) -> dict[str, Any]:
    """The visible row for a page that answered 401/403/429 or a WAF challenge."""
    rec.update({"status": "HARD_STOP", "http": stop.get("status"),
                "hold_cause": f"hard_stop:{stop.get('status')}", "site_hold": stop,
                "why": (f"HOLD, not a drop: HTTP {stop.get('status')} or a WAF challenge on "
                        f"{stop.get('host')} -- HARD_STOP, zero requests to that host until a "
                        f"person releases it (release_site_hold)")})
    return rec


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

    # ROBOTS IS RESPECTED AT FETCH TIME (LAWS 5e, AMENDED 2026-10-14 07:35Z, decision card
    # cmsg_012XFUfE12Rvggnu86fDb8pr5ze7a7HLob52jUdGwu28JR). Read under the agent this fetch sends;
    # a Disallow, or a robots.txt RFC 9309 does not let us read as consent, means NO FETCH. The
    # skip is a HOLD with a named cause, written on the row like every other verdict, never a
    # silent drop.
    rv = robots_verdict(url, DESK_UA)
    rec["robots"] = rv.why
    rec["robots_disallows"] = not rv.allowed
    if not rv.allowed:
        hard = bool(rv.hold and rv.hold.get("verdict") == "HARD_STOP")
        rec.update({
            "status": "HARD_STOP" if hard else "BLOCKED_BY_ROBOTS",
            "hold_cause": (f"hard_stop:{rv.hold.get('status')}" if hard and rv.hold
                           else f"robots:{rv.cause}"),
            "robots_recheck": rv.recheck, "site_hold": rv.hold,
            "terms_note": (f"robots.txt hold ({rv.cause}): this page is not fetched (LAWS 5e, "
                           f"amended 2026-10-14); content about it obtained lawfully by other "
                           f"means is still labelled and mined"),
            "why": (f"HOLD, not a drop: {rv.why}"
                    + ("; re-checked next pass" if rv.recheck else "")
                    + ("; released only by a person (release_site_hold)" if rv.hold else ""))})
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
    headers = {"User-Agent": DESK_UA, "Accept": "*/*"}
    if isinstance(validators, dict):
        if validators.get("etag"):
            headers["If-None-Match"] = str(validators["etag"])
        if validators.get("last_modified"):
            headers["If-Modified-Since"] = str(validators["last_modified"])
    headers.update(_declared_headers(src))
    body_out = _declared_form(src)
    req = urllib.request.Request(url, data=body_out, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_TLS) as r:
            status = int(getattr(r, "status", 0) or 0)
            ctype = str(r.headers.get("Content-Type") or "").lower()
            etag = r.headers.get("ETag")
            last_mod = r.headers.get("Last-Modified")
            stop = hard_stop_for(url, status, r.headers, None)
            body = b"" if stop is not None else r.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        code = int(getattr(e, "code", 0) or 0)
        stop = hard_stop_for(url, code, getattr(e, "headers", None), _error_body(e))
        if stop is not None:
            return _hard_stop_row(rec, stop)
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

    if stop is not None:
        return _hard_stop_row(rec, stop)
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


FOUND = BASE / "data" / "intelligence" / "asia_endpoints"
MAX_DERIVED = int(os.environ.get("ASIA_COLLECTOR_MAX_DERIVED", "150"))


def _derived_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The data files index pages POINT AT, as sources of their own.

    `asia_parser` reads an index page, finds the csv/xlsx/json/xml/zip links on it and hands
    them back in `data/intelligence/asia_endpoints/endpoints_*.json` -- and until 2026-09-16
    nothing read that file, so nine INDEX_PAGE sources handed back their payloads every hour to
    nobody. Each address becomes a derived source: the parent's plane, pit block and targets, a
    daily cadence, an id of `<parent>__ep<hash>` so the vault, the parser and the fixer all
    treat it as the parent's child. Capped, newest first, so a runaway index cannot flood a pass.
    """
    import hashlib
    by_id = {str(r.get("id")): r for r in sources if isinstance(r, dict)}
    seen = {str(r.get("url_override") or r.get("url")) for r in sources if isinstance(r, dict)}
    out: list[dict[str, Any]] = []
    if not FOUND.is_dir():
        return out
    for f in sorted(FOUND.glob("endpoints_*.json"), reverse=True)[:6]:
        for row in _read(f, []) or []:
            if not isinstance(row, dict) or row.get("kind") != "address":
                continue
            url = str(row.get("url") or "")
            parent = str(row.get("route") or "").split(":")[-1]
            src = by_id.get(parent)
            if not url or src is None or url in seen:
                continue
            seen.add(url)
            low = url.lower().split("?")[0]
            expect = ("json" if low.endswith(".json") else "csv" if low.endswith(".csv")
                      else "xml" if low.endswith(".xml") else "binary"
                      if low.endswith((".xlsx", ".xls", ".zip")) else "any")
            out.append({"id": f"{parent}__ep{hashlib.sha1(url.encode()).hexdigest()[:8]}",
                        "plane": src.get("plane"), "name": f"{src.get('name')} :: {low[-60:]}",
                        "url": url, "expect": expect, "access": src.get("access") or "public",
                        "cadence": "daily", "pit": src.get("pit"), "targets": src.get("targets"),
                        "derived_from": parent, "role": "derived"})
            if len(out) >= MAX_DERIVED:
                return out
    return out


def due(src: dict[str, Any], state: dict[str, Any], now: float) -> bool:
    row = state.get(str(src.get("id"))) or {}
    last = row.get("last_attempt_epoch")
    if not isinstance(last, (int, float)):
        return True
    # A ROBOTS HOLD THAT IS NOT A SERVED DISALLOW (robots.txt 5xx, unreachable, 401/403) is a
    # "not now", so it comes back on its own short clock, not the source's cadence.
    recheck = row.get("recheck_after_epoch")
    if isinstance(recheck, (int, float)) and now >= float(recheck):
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
    ap.add_argument("--release-host", metavar="HOST",
                    help="release a person-held site hold (site:<HOST>) and exit")
    ap.add_argument("--released-by", metavar="NAME", help="who releases it (required)")
    args = ap.parse_args(argv)
    if args.release_host:
        row = release_site_hold(args.release_host, args.released_by or "")
        print(f"asia collector: released {row['key']} ({row['verdict']}, HTTP {row['status']}) "
              f"by {row['released_by']}")
        return 0

    registry = _read(REGISTRY, {})
    sources = [s for s in (registry.get("sources") or []) if isinstance(s, dict)]
    derived = _derived_sources(sources)
    if derived:
        print(f"asia collector: {len(derived)} endpoint(s) handed back by the parser "
              f"join this pass")
    sources = [*sources, *derived]
    if args.id:
        want = set(args.id)
        sources = [s for s in sources if str(s.get("id")) in want]
    state = _read(STATE, {})
    now = time.time()
    # A TRANSPORT CARRIES OTHER SOURCES AND HAS NO ENDPOINT OF ITS OWN TO COLLECT.
    todo = [s for s in sources
            if str(s.get("role") or "mechanism") != "transport" and (args.id or due(s, state, now))]
    # FETCH IN EXPECTED-INFORMATION-GAIN ORDER (Tier-1 B14). The pass budget is spent in registry
    # order otherwise, so whichever sources sat late in a hand-written file were the ones deferred
    # every hour. `source_evig` prices each source BEFORE it is fetched -- prior uncertainty on the
    # instruments it declares, the share of those no collected source already covers, its own
    # usable rate, its publication lag, over its measured cost -- and this sorts by that price.
    # Nothing is dropped or refused: an unpriced source keeps its place after the priced ones, and
    # a missing artifact leaves the order exactly as it was.
    try:
        from research.source_evig import fetch_order
        _rank = {sid: i for i, sid in enumerate(fetch_order([str(s.get("id")) for s in todo]))}
        todo.sort(key=lambda s: _rank.get(str(s.get("id")), 10**6))
    except Exception:                                          # absence is never a demotion
        pass

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
        if rec.get("robots_recheck"):
            keep["recheck_after_epoch"] = time.time() + ROBOTS_RECHECK_S
            keep["hold_cause"] = rec.get("hold_cause")
        # A 304 keeps the OLD validators: they are what proved the page unchanged, and replacing
        # them with nothing would make the next pass unconditional for no reason.
        keep["validators"] = (rec.get("validators")
                              or (prev.get("validators") if isinstance(prev, dict) else None) or {})
        with guard:
            state[str(s.get("id"))] = keep

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(lambda t: _one(*t), list(enumerate(todo))))
    rows = [r for r in rows if r is not None]

    # SITE HOLDS LIVE ON DISK, NOT IN THIS PASS'S COPY: `robots_verdict` records them and
    # `release_site_hold` releases them while a pass may be running, so the file's `site:` rows
    # win over the copy loaded at the start of the pass.
    with _STATE_LOCK:
        disk = _read(STATE, {}) or {}
        state = {k: v for k, v in state.items() if not str(k).startswith("site:")}
        state.update({k: v for k, v in disk.items() if str(k).startswith("site:")})
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
               "UNCONFIGURED", "BLOCKED_BY_ROBOTS", "HARD_STOP"):
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
