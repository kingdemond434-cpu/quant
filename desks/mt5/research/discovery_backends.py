"""LAWFUL DISCOVERY: machine-readable indexes in place of scraping search engines.

THE FAILURE THIS REPLACES (measured 2026-11-03, `reports/ALT_DATA_YIELD.json`). Of 537 named
alt-data vectors, 256 were BLOCKED and 139 of those failed one way: "bing returned no parseable
results (an anti-bot shell)", with DuckDuckGo failing the same way behind it. Discovery ran by
scraping two search engines that refuse automated clients. That is a METHOD failure, not an
empty forest, and the desk never bypasses anti-bot pages, logins, CAPTCHAs or paywalls -- so the
method changes instead of the rail.

THE BACKENDS, every one free, keyless and BUILT for machine use:

    site_feeds       the ground's OWN declared URL set: `Sitemap:` lines in its robots.txt,
                     /sitemap.xml (and one level of sitemap index), /feed and /rss.xml (RSS 1.0,
                     RSS 2.0 or Atom). One to four requests per site, cached for the run.
    gdelt_doc        the GDELT DOC 2.0 API: dated news articles in 65 languages from every
                     country, `domain:<site>` for a site ground, keywords + `sourcecountry` +
                     `sourcelang` otherwise. Cross-process spacing (GDELT asks for one request
                     per five seconds).
    commoncrawl_cdx  the Common Crawl URL index (index.commoncrawl.org): every URL the latest
                     crawl holds for a host, in one request. The current index id is read from
                     collinfo.json, never hard-coded, so a rotated crawl is not a 404.
    wayback_cdx      the Internet Archive's CDX server: every archived URL for a host, which also
                     reaches grounds that have since gone dark.
    (last resort)    bing / duckduckgo, ONLY when every lawful backend came back without rows,
                     ONLY through the same robots check (both engines Disallow their result paths
                     to `*`, so on the real box this is a recorded robots refusal, never a fetch),
                     and NEVER counted against the vector once a lawful backend has run.

THE RAILS, applied to every request a backend makes -- the index host and the site alike:

* HONEST USER-AGENT. `DESK_UA` names the desk and what it does. No browser disguise.
* ROBOTS.TXT IS RESPECTED for these requests (RFC 9309): a 2xx file is parsed and a Disallow
  for our token means NO FETCH; a 404/410 means no rules; a 5xx or a transport failure means the
  file could not be read and the fetch does not happen this pass (an unreadable robots.txt is
  not consent). This governs the DISCOVERY REQUESTS this module makes; it never deletes a ground
  or a claim -- a ground whose own host refuses is still discovered through the index backends,
  which read the archives rather than the host. RELATION TO LAWS 5e: 5e makes robots a label on
  what the desk READS and TESTS; it never stops a ground. Nothing here changes that: the page
  reads in `deep_forest_miner` (`_Run.page`) are untouched, and every ground stays scheduled and
  mined. What this module adds is manners for its own automated index and feed requests, which
  the operator ordered for this backend (2026-11-03) -- a refusal here is a BLOCKED record on one
  backend, and the next backend still discovers the ground.
* 401 / 403 / 429 IS A PERSON-RELEASED HARD STOP. The host is written to `HOLDS` with the status,
  url and time, and NOTHING here fetches from it again until a person releases it (sets
  `released_by` on the entry, or deletes it). No retry, no backoff-and-try-again, no rotation.
* PER-HOST POLITENESS. Every request waits on `libs.data.polite_fetch.GATE` (process-wide per
  host spacing); hosts with a published rate get a cross-process slot as well.
* A RECORD PER BACKEND PER CALL: backend, status (YIELDED / EMPTY / BLOCKED / SKIPPED), rows,
  requests and why. `STATS` accumulates them per backend so a leg can publish its yield.

UNMEASURED IS NEVER ZERO. A backend that did not run (budget, hold not yet released) is SKIPPED
with its reason; it is not EMPTY and it is not counted as an attempt.

No network is touched at import. `transport` is injectable, so every path is testable offline.
"""
from __future__ import annotations

import contextlib
import html as _html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.robotparser
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

DESK = Path(__file__).resolve().parents[1]

#: The honest desk User-Agent. Its first token is what robots.txt groups are matched against.
DESK_UA_PRODUCT = "quant-desk-discovery"
DESK_UA = (f"{DESK_UA_PRODUCT}/1.0 (+research; reads public indexes, sitemaps and feeds; "
           "honours robots.txt; stops on 401/403/429)")
DESK_HEADERS = {"User-Agent": DESK_UA,
                "Accept": "application/json,application/xml,text/xml,text/plain,text/html;q=0.8,"
                          "*/*;q=0.5"}
#: Box-local, person-released hard stops. Gitignored state, one file per box.
HOLDS = DESK / "data" / "discovery_host_holds.json"
#: Statuses that stop a host until a person releases it.
HARD_STOP_STATUS: frozenset[int] = frozenset({401, 403, 429})
YIELDED, EMPTY, BLOCKED, SKIPPED = "YIELDED", "EMPTY", "BLOCKED", "SKIPPED"
UNMEASURED = "UNMEASURED"
#: The lawful chain, in the order it is tried. Rows stop accumulating at ENOUGH_ROWS.
LAWFUL_BACKENDS: tuple[str, ...] = ("site_feeds", "gdelt_doc", "commoncrawl_cdx", "wayback_cdx")
LAST_RESORT: tuple[str, ...] = ("bing", "duckduckgo")
ENOUGH_ROWS = 40
ROWS_PER_BACKEND = 200
#: Common Crawl's index list; the newest id is first. The constant is only the fallback.
CC_COLLINFO = "https://index.commoncrawl.org/collinfo.json"
CC_INDEX_FALLBACK = "CC-MAIN-2026-30"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"
#: HOSTS THIS MODULE NEVER CONTACTS, whatever a ground or a redirect names (desk mandate,
#: 2026-11-14). Matched on the host and every parent domain. A request to one is refused before
#: robots.txt is read, with the reason on the backend's record -- disabled and said, never
#: silently dropped.
_NO_YOUTUBE = "no YouTube contact from the trading box; video ids come from the indexes"
_TERMS = "terms-refused source"
_OI = "terms-refused exchange options-OI host"
_OFF_LIMITS = "off-limits ground (WeChat/Baidu)"
NEVER_CONTACT: dict[str, str] = {
    "youtube.com": _NO_YOUTUBE, "youtu.be": _NO_YOUTUBE, "googlevideo.com": _NO_YOUTUBE,
    "fred.stlouisfed.org": f"{_TERMS} (FRED)", "alfred.stlouisfed.org": f"{_TERMS} (ALFRED)",
    "yahoo.com": f"{_TERMS} (Yahoo)",
    "cboe.com": f"{_OI} (Cboe)", "cmegroup.com": f"{_OI} (CME)",
    "nasdaq.com": f"{_OI} (Nasdaq)", "theocc.com": f"{_OI} (OCC)",
    "miaxglobal.com": f"{_OI} (MIAX)", "m-x.ca": f"{_OI} (Montreal Exchange)",
    "asx.com.au": f"{_OI} (ASX)",
    "eurex.com": "terms unread, and an unread term is a refusal (Eurex)",
    "comtrade.un.org": f"{_TERMS} (UN Comtrade: licence s.5 refuses automated use, 2026-11-14)",
    "comtradeplus.un.org": f"{_TERMS} (UN Comtrade)",
    "comtradeapi.un.org": f"{_TERMS} (UN Comtrade)",
    "weixin.qq.com": _OFF_LIMITS, "wechat.com": _OFF_LIMITS, "baidu.com": _OFF_LIMITS,
}
#: Of those, the hosts whose URLs are not even TAKEN from an index: a discovered row is followed
#: and read by the miner, so harvesting it would be contact by the back door. YouTube rows stay
#: (the video id is all the miner uses, and transcripts go through the keyless mirrors).
NEVER_DISCOVER: frozenset[str] = frozenset(h for h, why in NEVER_CONTACT.items()
                                           if why != _NO_YOUTUBE)


def _match(host: str, table: Iterable[str]) -> str:
    h = (host or "").lower().split(":")[0].rstrip(".")
    for dom in table:
        if h == dom or h.endswith(f".{dom}"):
            return dom
    return ""


def never_contact(url_or_host: str) -> str:
    """The reason this module refuses to contact the host, or "" when it may."""
    h = urlparse(url_or_host).netloc if "://" in url_or_host else url_or_host
    dom = _match(h, NEVER_CONTACT)
    return f"REFUSED: {NEVER_CONTACT[dom]} ({dom})" if dom else ""


#: Hosts whose operator publishes a rate. These are spaced ACROSS PROCESSES (the eleven forest
#: legs run this miner concurrently), on top of polite_fetch's in-process gate.
CROSS_PROCESS_INTERVAL_S: dict[str, float] = {"api.gdeltproject.org": 6.0}
MAX_SLOT_WAIT_S = 30.0

#: ISO 3166 alpha-2 (the grounds file's `region`) -> FIPS 10-4, which GDELT's `sourcecountry`
#: takes. A vocabulary of country codes, not a symbol list.
ISO_TO_FIPS: dict[str, str] = {
    "cn": "CH", "jp": "JA", "kr": "KS", "tw": "TW", "hk": "HK", "sg": "SN", "vn": "VM",
    "th": "TH", "id": "ID", "my": "MY", "ph": "RP", "in": "IN", "pk": "PK", "bd": "BG",
    "lk": "CE", "au": "AS", "nz": "NZ", "sa": "SA", "ae": "AE", "qa": "QA", "tr": "TU",
    "il": "IS", "eg": "EG", "za": "SF", "ng": "NI", "ke": "KE", "ma": "MO", "us": "US",
    "gb": "UK", "ca": "CA", "de": "GM", "fr": "FR", "it": "IT", "es": "SP", "nl": "NL",
    "se": "SW", "dk": "DA", "no": "NO", "fi": "FI", "pl": "PL", "cz": "EZ", "hu": "HU",
    "ua": "UP", "ru": "RS", "br": "BR", "mx": "MX", "cl": "CI", "co": "CO", "pe": "PE",
    "ar": "AR",
}
#: The grounds file's language codes -> GDELT `sourcelang` names.
LANG_TO_GDELT: dict[str, str] = {
    "zh": "chinese", "zh-Hant": "chinese", "ja": "japanese", "ko": "korean", "ru": "russian",
    "uk": "ukrainian", "vi": "vietnamese", "th": "thai", "id": "indonesian", "ms": "malay",
    "hi": "hindi", "en": "english", "de": "german", "fr": "french", "it": "italian",
    "es": "spanish", "pt": "portuguese", "ar": "arabic", "tr": "turkish", "he": "hebrew",
    "pl": "polish", "nl": "dutch", "sv": "swedish", "da": "danish", "no": "norwegian",
    "fi": "finnish", "sw": "swahili", "cs": "czech", "hu": "hungarian",
}


# --------------------------------------------------------------------------- transport
_HTTP_STATUS = re.compile(r"^HTTP \d{3}$")
_TYPE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def safe_error(error: object) -> str:
    """`HTTP <status>`, or the exception type name before any `: message`, or "transport_error".
    Never the free text of the message."""
    e = str(error or "").strip()
    if not e:
        return ""
    if _HTTP_STATUS.match(e):
        return e
    head = e.split(":", 1)[0].strip()
    return head if _TYPE_NAME.match(head) else "transport_error"


@dataclass
class Fetched:
    """What one GET came back with. `status` is None for a transport failure."""

    url: str
    status: int | None
    text: str = ""
    error: str = ""
    #: The URL that actually answered, after redirects ("" = the url asked for).
    final_url: str = ""

    def __post_init__(self) -> None:
        # Only an exception TYPE name or `HTTP <status>` is ever carried (Auditor MF2 on #1168):
        # a transport message can hold a host, a path or a key, and this field reaches records,
        # errors() and the leg's stdout.
        self.error = safe_error(self.error)

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300


Transport = Callable[[str], Fetched]


def recording_opener(meta: dict[str, str]) -> Callable[..., Any]:
    """An opener for `polite_fetch.get(opener=...)` that records WHICH URL refused when an HTTP
    error comes back through a redirect -- `polite_fetch` keeps only the status, and the hold must
    land on the host that answered, not on the host that was asked."""
    import urllib.request

    def _open(req: Any, **kw: Any) -> Any:
        try:
            return urllib.request.urlopen(req, **kw)
        except urllib.error.HTTPError as exc:
            meta["final_url"] = str(getattr(exc, "url", "") or exc.geturl() or "")
            raise
    return _open


def default_transport(url: str) -> Fetched:
    """`libs.data.polite_fetch.get` with the desk's honest headers and NO retry: a 429 is a hard
    stop here, never something to back off from and try again."""
    from libs.data import polite_fetch as pf
    meta: dict[str, str] = {}
    r = pf.get(url, headers=DESK_HEADERS, timeout=25.0, retries=0, leg="lawful_discovery",
               max_bytes=4_000_000, opener=recording_opener(meta))
    final = meta.get("final_url") or r.final_url or ""
    return Fetched(url=url, status=r.status, text=r.text if r.ok else "",
                   error="" if r.ok else (r.error or f"HTTP {r.status}"),
                   final_url="" if final == url else final)


def _host(url: str) -> str:
    return urlparse(url).netloc.lower()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- hard stops
UNMEASURED_HOLDS = "UNMEASURED_HOLDS"


class HoldWriteError(RuntimeError):
    """A hold could not be persisted. Never swallowed: the caller records it on the backend's
    record and in `hold_errors()`, and the process-local hold still stands."""


#: Every hold-write failure this process saw, for the leg's report.
_HOLD_ERRORS: list[str] = []


def hold_errors() -> list[str]:
    with _STATS_LOCK:
        return list(_HOLD_ERRORS)


class HostHolds:
    """401/403/429 -> the host is held until a PERSON releases it. Persisted, box-local.

    A release is a person's act on the file: set `released_by` (and optionally `released_at`) on
    the host's entry, or delete the entry. Code here only ever ADDS holds.

    FAIL CLOSED. Only a MISSING file means "no holds". A file that exists but cannot be read or
    parsed means EVERY host is held (`UNMEASURED_HOLDS`, with the reason) and nothing is written
    over it -- rewriting it would erase holds a person has not released. A hold is first recorded
    in a PROCESS-LOCAL set, so the rest of this process's backends stop for that host at once,
    and then merged into the file under a cross-process lock (`.job_locks`, the forest legs'
    pattern): load, add this one host, write -- never overwrite what another leg wrote.
    """

    def __init__(self, path: Path | None = None, *, lock_dir: Path | None = None,
                 lock_timeout_s: float = 30.0) -> None:
        self.path = Path(path) if path is not None else HOLDS
        self.lock_dir = Path(lock_dir) if lock_dir is not None else self.path.parent / \
            ".job_locks"
        self.lock_timeout_s = float(lock_timeout_s)
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._local: dict[str, dict[str, Any]] = {}

    def _load(self) -> tuple[dict[str, Any], str]:
        """(hosts, why the file is unusable). Only FileNotFoundError is "no holds"."""
        try:
            text = self.path.read_text("utf-8")
        except FileNotFoundError:
            return {}, ""
        except OSError as exc:
            return {}, f"{self.path.name} exists but cannot be read ({type(exc).__name__})"
        try:
            doc = json.loads(text)
        except ValueError as exc:
            return {}, f"{self.path.name} does not parse ({type(exc).__name__})"
        hosts = doc.get("hosts") if isinstance(doc, dict) else None
        if not isinstance(hosts, dict):
            return {}, f"{self.path.name} has no `hosts` table"
        return hosts, ""

    def status(self) -> str:
        """"" when the file is usable, else `UNMEASURED_HOLDS: <why>`."""
        _h, bad = self._load()
        return f"{UNMEASURED_HOLDS}: {bad}" if bad else ""

    def held(self, host: str) -> str:
        """Why `host` must not be fetched, or ""."""
        h = host.lower()
        with self._lock:
            local = self._local.get(h)
        if local is not None:
            return (f"HARD STOP: {host} answered HTTP {local.get('status')} at {local.get('at')} "
                    "in this process; held until a person releases it")
        hosts, bad = self._load()
        if bad:
            return (f"{UNMEASURED_HOLDS}: {bad}; every host is held until a person repairs "
                    "the holds file")
        e = hosts.get(h)
        if not isinstance(e, dict) or e.get("released_by"):
            return ""
        return (f"HARD STOP: {host} answered HTTP {e.get('status')} at {e.get('at')} "
                f"({e.get('url')}); held until a person releases it in {self.path.name}")

    def hold(self, host: str, status: int, url: str, via: str) -> None:
        """Hold `host` in this process now, then merge it into the file. Raises HoldWriteError
        when the merge could not be written (the local hold stands either way)."""
        from libs.ops.win_write import replace_resilient
        from libs.research import artifact_chain as ac
        h = host.lower()
        entry = {"status": int(status), "url": url[:300], "at": _now(), "via": via,
                 "released_by": None,
                 "how_to_release": "a person sets released_by to their name, or deletes this entry"}
        with self._lock:
            self._local[h] = entry
        try:
            self.lock_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HoldWriteError(f"hold on {h} not persisted: lock dir: "
                                 f"{type(exc).__name__}") from exc
        with self._write_lock, ac._locked(self.lock_dir / "discovery_host_holds",
                                    timeout_s=self.lock_timeout_s) as got:
            if not got:
                raise HoldWriteError(f"hold on {h} not persisted: the cross-process lock was not "
                                     f"taken in {self.lock_timeout_s:.0f}s")
            hosts, bad = self._load()
            if bad:
                raise HoldWriteError(f"hold on {h} not persisted: {UNMEASURED_HOLDS}: {bad} "
                                     "(the file is left exactly as it is)")
            prev = hosts.get(h) if isinstance(hosts.get(h), dict) else {}
            hosts[h] = {**entry, "times_held": int(prev.get("times_held") or 0) + 1}
            doc = {"rule": ("401/403/429 from a discovery request is a HARD STOP. Code never "
                            "releases a hold; a person does."), "updated": _now(),
                   "hosts": hosts}
            tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
            try:
                tmp.write_text(json.dumps(doc, indent=1), "utf-8")
                replace_resilient(tmp, self.path)
            except OSError as exc:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise HoldWriteError(f"hold on {h} not persisted: "
                                     f"{type(exc).__name__}") from exc


# --------------------------------------------------------------------------- robots
@dataclass
class RobotsVerdict:
    allowed: bool
    why: str
    sitemaps: list[str] = field(default_factory=list)
    hard_stop: int | None = None
    transport_ok: bool = True


class Robots:
    """RFC 9309 robots.txt for the desk's token, one read per host per run."""

    def __init__(self, transport: Transport, token: str = DESK_UA_PRODUCT,
                 before_fetch: Callable[[str], str] | None = None) -> None:
        self.transport = transport
        self.token = token
        #: Called with the robots.txt URL before it is fetched; a non-empty answer (a hold, no
        #: cross-process slot) means it is NOT fetched and nothing is cached.
        self.before_fetch = before_fetch
        self._cache: dict[str, tuple[Any, list[str], str, int | None, bool]] = {}
        self._lock = threading.Lock()

    def _read(self, scheme: str, host: str) -> tuple[Any, list[str], str, int | None, bool]:
        key = f"{scheme}://{host}"
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        if self.before_fetch is not None:
            refused = self.before_fetch(f"{key}/robots.txt")
            if refused:
                return False, [], f"robots.txt not fetched: {refused}", None, False
        r = self.transport(f"{key}/robots.txt")
        parser: Any
        sitemaps: list[str] = []
        stop: int | None = None
        if r.status is not None and r.status in HARD_STOP_STATUS:
            parser, why, stop = False, f"robots.txt answered HTTP {r.status}", r.status
        elif r.ok:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            parser, why = rp, "robots.txt read"
            sitemaps = [ln.split(":", 1)[1].strip() for ln in r.text.splitlines()
                        if ln.strip().lower().startswith("sitemap:")]
        elif r.status is not None and 400 <= r.status < 500:
            parser, why = True, f"robots.txt HTTP {r.status}: no rules (RFC 9309)"
        else:
            parser = False
            why = (f"robots.txt unreadable ({r.error or r.status}): not consent, no fetch "
                   "this pass")
        got = (parser, sitemaps, why, stop, r.status is not None)
        with self._lock:
            self._cache[key] = got
        return got

    def check(self, url: str) -> RobotsVerdict:
        p = urlparse(url)
        parser, sitemaps, why, stop, tok = self._read(p.scheme or "https", p.netloc.lower())
        if parser is True:
            return RobotsVerdict(True, why, sitemaps, transport_ok=tok)
        if parser is False:
            return RobotsVerdict(False, why, sitemaps, hard_stop=stop, transport_ok=tok)
        ok = bool(parser.can_fetch(self.token, url))
        return RobotsVerdict(ok, "robots allows" if ok else
                             f"robots.txt Disallows this path for {self.token}: not fetched",
                             sitemaps, transport_ok=tok)

    def sitemaps(self, host: str, scheme: str = "https") -> list[str]:
        return list(self._read(scheme, host.lower())[1])


# --------------------------------------------------------------------------- cross-process slot
def _cross_process_slot(host: str, lock_dir: Path, sleep: Callable[[float], None]) -> bool:
    """Wait for `host`'s next slot shared by every process on this box. False when the slot
    could not be had inside MAX_SLOT_WAIT_S (the caller then SKIPS, it never fetches early).

    FAIL CLOSED: only a held lock (FileExistsError) is waited on, and only a lock older than a
    minute (a crashed holder) is broken. Any other OSError -- no lock dir, a slot file that cannot
    be read or written -- refuses the slot for this pass."""
    interval = CROSS_PROCESS_INTERVAL_S.get(host)
    if not interval:
        return True
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    lock = lock_dir / f".{host}.slot.lock"
    slot = lock_dir / f".{host}.slot"
    t_end = time.monotonic() + MAX_SLOT_WAIT_S
    while time.monotonic() < t_end:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > 60
            except FileNotFoundError:
                continue                          # released between the two calls: retry
            except OSError:
                return False
            if stale:
                try:
                    lock.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    return False
                continue
            sleep(0.2)
            continue
        except OSError:
            return False
        try:
            try:
                nxt = float(slot.read_text("utf-8").strip() or 0)
            except FileNotFoundError:
                nxt = 0.0
            except ValueError:
                nxt = 0.0                         # a torn number: the interval still applies
            except OSError:
                return False
            wait = nxt - time.time()
            if wait > MAX_SLOT_WAIT_S:
                return False
            if wait > 0:
                sleep(wait)
            try:
                slot.write_text(f"{time.time() + interval:.3f}", "utf-8")
            except OSError:
                return False
            return True
        finally:
            os.close(fd)
            with contextlib.suppress(OSError):
                lock.unlink()
    return False


# --------------------------------------------------------------------------- parsers
def parse_cdx_ndjson(text: str) -> list[dict[str, str]]:
    """Common Crawl's CDX answer (`output=json`): one JSON object per line."""
    out: list[dict[str, str]] = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        u = str(row.get("url") or "")
        if not u:
            continue
        status = str(row.get("status") or "")
        if status and status != "200":
            continue
        out.append({"url": u, "timestamp": str(row.get("timestamp") or ""),
                    "mime": str(row.get("mime") or row.get("mime-detected") or "")})
    return out


def parse_wayback_cdx(text: str) -> list[dict[str, str]]:
    """The Wayback CDX server's `output=json`: a header row, then one list per capture."""
    try:
        doc = json.loads(text or "")
    except ValueError:
        return []
    if not isinstance(doc, list) or not doc or not isinstance(doc[0], list):
        return []
    head = [str(h) for h in doc[0]]
    out: list[dict[str, str]] = []
    for row in doc[1:]:
        if not isinstance(row, list):
            continue
        rec = dict(zip(head, (str(x) for x in row), strict=False))
        u = rec.get("original") or ""
        if not u:
            continue
        if rec.get("statuscode") not in (None, "", "200", "-"):
            continue
        out.append({"url": u, "timestamp": rec.get("timestamp", ""),
                    "mime": rec.get("mimetype", "")})
    return out


def parse_gdelt_doc(text: str) -> tuple[list[dict[str, str]], str]:
    """GDELT DOC 2.0 ArtList JSON -> rows, plus GDELT's own message when it refused the query
    (it answers 200 with a plain-text explanation, which is an answer, not a block)."""
    t = (text or "").strip()
    if not t:
        return [], "empty body"
    if not t.startswith("{"):
        return [], f"gdelt answered without JSON: {t[:120]}"
    try:
        doc = json.loads(t)
    except ValueError:
        return [], "gdelt JSON did not parse"
    rows: list[dict[str, str]] = []
    for a in doc.get("articles") or []:
        if not isinstance(a, dict) or not a.get("url"):
            continue
        rows.append({"url": str(a["url"]), "title": str(a.get("title") or "")[:300],
                     "published": str(a.get("seendate") or ""),
                     "language": str(a.get("language") or ""),
                     "country": str(a.get("sourcecountry") or ""),
                     "domain": str(a.get("domain") or "")})
    return rows, ""


_LOC = re.compile(r"(?is)<loc>\s*(.*?)\s*</loc>")


def parse_sitemap(text: str) -> tuple[list[str], list[str]]:
    """(page urls, child sitemap urls) of a sitemap or a sitemap index."""
    t = text or ""
    locs = [_html.unescape(re.sub(r"(?s)<!\[CDATA\[(.*?)\]\]>", r"\1", m)).strip()
            for m in _LOC.findall(t)]
    if re.search(r"(?i)<sitemapindex\b", t):
        return [], [u for u in locs if u]
    if re.search(r"(?i)<urlset\b", t):
        return [u for u in locs if u], []
    return [], []


def is_feed(text: str) -> bool:
    return bool(re.search(r"(?i)<(rss|feed|rdf:RDF)\b", (text or "")[:4000]))


def _parse_feed(text: str) -> list[dict[str, str]]:
    try:
        from research.deep_forest_miner import parse_feed
    except ImportError:                                     # pragma: no cover - path set up
        from deep_forest_miner import parse_feed  # type: ignore[import-not-found,no-redef]
    return parse_feed(text)


# --------------------------------------------------------------------------- results
@dataclass
class BackendRecord:
    backend: str
    status: str
    rows: int = 0
    requests: int = 0
    why: str = ""
    lawful: bool = True
    transport_ok: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"backend": self.backend, "status": self.status, "rows": self.rows,
                "requests": self.requests, "why": self.why[:200], "lawful": self.lawful}


@dataclass
class Discovery:
    rows: list[dict[str, str]]
    records: list[BackendRecord]

    @property
    def status(self) -> str:
        """YIELDED / EMPTY / BLOCKED / SKIPPED for the vector. A last-resort engine's refusal is
        not counted once a lawful backend has actually run."""
        if self.rows:
            return YIELDED
        lawful_ran = [r for r in self.records if r.lawful and r.status != SKIPPED]
        pool = lawful_ran or [r for r in self.records if r.status != SKIPPED]
        if any(r.status == EMPTY for r in pool):
            return EMPTY
        if any(r.status == BLOCKED for r in pool):
            return BLOCKED
        return SKIPPED

    @property
    def yielded_via(self) -> list[str]:
        return [r.backend for r in self.records if r.status == YIELDED]

    @property
    def answered(self) -> int:
        return sum(1 for r in self.records if r.status in (YIELDED, EMPTY))

    @property
    def transport_ok(self) -> bool:
        return any(r.transport_ok for r in self.records)

    def errors(self) -> list[str]:
        """What to record against the vector: lawful refusals always; a last-resort engine's
        refusal only when no lawful backend ran at all."""
        lawful_ran = any(r.lawful and r.status != SKIPPED for r in self.records)
        return [f"{r.backend}: {r.why}" for r in self.records
                if r.status == BLOCKED and (r.lawful or not lawful_ran)]


#: Process-wide per-backend accounting, published by the leg that ran the chain.
_STATS: dict[str, dict[str, int]] = {}
_STATS_LOCK = threading.Lock()


def _stat(rec: BackendRecord) -> None:
    with _STATS_LOCK:
        s = _STATS.setdefault(rec.backend, {"calls": 0, YIELDED: 0, EMPTY: 0, BLOCKED: 0,
                                            SKIPPED: 0, "rows": 0, "requests": 0})
        s["calls"] += 1
        s[rec.status] = s.get(rec.status, 0) + 1
        s["rows"] += rec.rows
        s["requests"] += rec.requests


def stats() -> dict[str, dict[str, int]]:
    with _STATS_LOCK:
        return {k: dict(v) for k, v in _STATS.items()}


def reset_stats() -> None:
    with _STATS_LOCK:
        _STATS.clear()


def _tokens(query: str) -> list[str]:
    q = unquote(query or "").lower()
    toks = [t for t in re.split(r"[\s,;:/|+\-_.()\"']+", q) if len(t) >= 2]
    return toks


def rank(rows: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    """Stable: rows whose url or title carries more of the query's tokens first."""
    toks = _tokens(query)
    if not toks:
        return rows

    def score(r: dict[str, str]) -> int:
        hay = (unquote(r.get("url", "")) + " " + r.get("title", "")).lower()
        return sum(1 for t in toks if t in hay)
    return sorted(rows, key=lambda r: -score(r))


_ASSET = re.compile(r"(?i)\.(css|js|png|jpe?g|gif|svg|ico|woff2?|ttf|mp4|webp|zip)(\?|$)")


def _page_like(u: str) -> bool:
    return u.startswith(("http://", "https://")) and not _ASSET.search(u)


def _site_host(site: str) -> str:
    s = re.sub(r"^https?://", "", str(site or "").strip()).split("/")[0].lower()
    return s


# --------------------------------------------------------------------------- the chain
class LawfulDiscovery:
    """One instance per run, shared by every worker thread: caches, holds and robots."""

    def __init__(self, transport: Transport | None = None, *, holds: Path | None = None,
                 lock_dir: Path | None = None,
                 last_resort: Iterable[tuple[str, Callable[..., str],
                                             Callable[[str], list[dict[str, str]]]]] = (),
                 sleep: Callable[[float], None] = time.sleep,
                 backends: Iterable[str] = LAWFUL_BACKENDS) -> None:
        self.transport = transport or default_transport
        hp = Path(holds) if holds is not None else HOLDS
        self.lock_dir = Path(lock_dir) if lock_dir is not None else hp.parent / ".job_locks"
        self.holds = HostHolds(hp, lock_dir=self.lock_dir)
        self.robots = Robots(self.transport, before_fetch=self._admit)
        self.last_resort = list(last_resort)
        self.sleep = sleep
        self.backends = tuple(backends)
        self._cache: dict[tuple[str, ...], tuple[BackendRecord, list[dict[str, str]]]] = {}
        self._lock = threading.Lock()
        self._cc_api: str | None = None

    # ---------------------------------------------------------------- one guarded GET
    def _admit(self, url: str) -> str:
        """Hold and cross-process slot for ANY request, robots.txt included. "" = may fetch."""
        host = _host(url)
        refused = never_contact(url)
        if refused:
            return refused
        why = self.holds.held(host)
        if why:
            return why
        if not _cross_process_slot(host, self.lock_dir, self.sleep):
            return f"no cross-process slot for {host} inside {MAX_SLOT_WAIT_S:.0f}s"
        return ""

    def _hold(self, host: str, status: int, url: str, rec: BackendRecord) -> None:
        try:
            self.holds.hold(host, status, url, rec.backend)
        except HoldWriteError as exc:
            with _STATS_LOCK:
                _HOLD_ERRORS.append(f"{_now()} {type(exc).__name__}")
            rec.why = f"{rec.why}; HOLD WRITE FAILED: {type(exc).__name__}".strip("; ")

    def get(self, url: str, rec: BackendRecord) -> Fetched | None:
        """Hold -> robots -> slot -> GET -> (redirect target: hold + robots again) -> hold the
        ANSWERING host on 401/403/429. None when not fetched or not usable, with the reason on
        `rec`."""
        host = _host(url)
        refused = never_contact(url)
        if refused:
            rec.why = refused
            return None
        why = self.holds.held(host)
        if why:
            rec.why = why
            return None
        v = self.robots.check(url)
        rec.transport_ok = rec.transport_ok or v.transport_ok
        if v.hard_stop is not None:
            rec.why = f"HARD STOP: robots.txt answered HTTP {v.hard_stop}"
            self._hold(host, v.hard_stop, f"{urlparse(url).scheme}://{host}/robots.txt", rec)
            return None
        if not v.allowed:
            rec.why = v.why
            return None
        if not _cross_process_slot(host, self.lock_dir, self.sleep):
            rec.why = f"no cross-process slot for {host} inside {MAX_SLOT_WAIT_S:.0f}s"
            return None
        rec.requests += 1
        r = self.transport(url)
        if r.status is not None:
            rec.transport_ok = True
        answered_by = r.final_url or url
        ahost = _host(answered_by) or host
        if r.status is not None and r.status in HARD_STOP_STATUS:
            rec.why = f"HARD STOP: HTTP {r.status} from {ahost}; held for a person to release"
            self._hold(ahost, r.status, answered_by, rec)
            return None
        if ahost != host and never_contact(answered_by):
            rec.why = f"redirected to {ahost}: {never_contact(answered_by)}; body discarded"
            return None
        if ahost != host:
            # A REDIRECT TO ANOTHER HOST is a request to that host: its hold and its robots.txt
            # decide whether the body may be used. (urllib has already followed it; a refused
            # target's body is discarded, never parsed.)
            why = self.holds.held(ahost)
            if why:
                rec.why = f"redirected to {ahost}: {why}"
                return None
            v2 = self.robots.check(answered_by)
            if v2.hard_stop is not None:
                rec.why = f"redirected to {ahost}: HARD STOP: robots.txt HTTP {v2.hard_stop}"
                self._hold(ahost, v2.hard_stop, f"https://{ahost}/robots.txt", rec)
                return None
            if not v2.allowed:
                rec.why = f"redirected to {ahost}: {v2.why}; body discarded"
                return None
        return r

    # ---------------------------------------------------------------- backends
    def _site_feeds(self, q: _Query, rec: BackendRecord) -> list[dict[str, str]] | None:
        if not q.host:
            rec.status, rec.why = SKIPPED, "no site to read a sitemap or feed from"
            return None
        refused = never_contact(q.host)
        if refused:
            rec.status, rec.why = SKIPPED, refused
            return None
        base = f"https://{q.host}"
        found: list[dict[str, str]] = []
        answered = False
        first = self.get(f"{base}/sitemap.xml", rec)
        declared = self.robots.sitemaps(q.host)
        cands = [*[d for d in declared if d.rstrip("/") != f"{base}/sitemap.xml"][:2],
                 "__first__", f"{base}/feed", f"{base}/rss.xml"]
        children: list[str] = []
        for c in cands:
            if len(found) >= ROWS_PER_BACKEND:
                break
            r = first if c == "__first__" else self.get(c, rec)
            if r is None:
                continue
            if r.status is not None and r.status < 500:
                answered = True               # a 404 is an answer; a 5xx is not
            if not r.ok:
                if r.status is not None and r.status >= 500:
                    rec.why = f"HTTP {r.status} from {_host(r.final_url or c)}"
                continue
            pages, kids = parse_sitemap(r.text)
            children.extend(kids)
            found.extend({"url": u, "title": ""} for u in pages if _page_like(u))
            if is_feed(r.text):
                found.extend({"url": it["url"], "title": it.get("title", ""),
                              "snippet": it.get("summary", "")[:400],
                              "published": it.get("published", "")}
                             for it in _parse_feed(r.text) if it.get("url"))

        def _kid_order(u: str) -> int:
            return 0 if re.search(r"(?i)post|news|article|blog|forum|thread", u) else 1
        for kid in sorted(dict.fromkeys(children), key=_kid_order)[:2]:
            r = self.get(kid, rec)
            if r is not None and r.ok:
                answered = True
                pages, _ = parse_sitemap(r.text)
                found.extend({"url": u, "title": ""} for u in pages if _page_like(u))
        if not answered and not found:
            return None
        return found

    def _gdelt(self, q: _Query, rec: BackendRecord) -> list[dict[str, str]] | None:
        if q.host:
            expr = f"domain:{q.host}"
        else:
            kw = " ".join(t for t in (q.query or "").split() if t)
            if not kw:
                rec.status, rec.why = SKIPPED, "no query and no site"
                return None
            expr = f"({kw})" if " " in kw else kw
            fips = ISO_TO_FIPS.get((q.region or "").lower())
            if fips:
                expr += f" sourcecountry:{fips}"
            lang = LANG_TO_GDELT.get(q.lang or "")
            if lang:
                expr += f" sourcelang:{lang}"
        url = (f"{GDELT_DOC}?query={quote(expr)}&mode=artlist&format=json"
               f"&maxrecords=75&sort=datedesc&timespan=3months")
        r = self.get(url, rec)
        if r is None:
            return None
        if not r.ok:
            rec.why = f"HTTP {r.status}" if r.status else r.error
            return [] if r.status is not None and r.status < 500 else None
        rows, msg = parse_gdelt_doc(r.text)
        if msg:
            rec.why = msg
        return rows

    def _cc_endpoint(self, rec: BackendRecord) -> str:
        with self._lock:
            if self._cc_api:
                return self._cc_api
        api = f"https://index.commoncrawl.org/{CC_INDEX_FALLBACK}-index"
        r = self.get(CC_COLLINFO, rec)
        if r is not None and r.ok:
            with contextlib.suppress(ValueError, TypeError, IndexError, AttributeError):
                info = json.loads(r.text)
                api = str(info[0].get("cdx-api") or api)
        with self._lock:
            self._cc_api = api
        return api

    def _commoncrawl(self, q: _Query, rec: BackendRecord) -> list[dict[str, str]] | None:
        if not q.host:
            rec.status, rec.why = SKIPPED, "the URL index answers per host; no site given"
            return None
        api = self._cc_endpoint(rec)
        url = (f"{api}?url={quote(f'{q.host}/*', safe='')}&output=json"
               f"&limit={ROWS_PER_BACKEND}&filter=status:200&fl=url,timestamp,mime,status")
        r = self.get(url, rec)
        if r is None:
            return None
        if r.status == 404:                  # CC's own "No Captures found": an answer
            rec.why = "no captures for this host in the current crawl"
            return []
        if not r.ok:
            rec.why = f"HTTP {r.status}" if r.status else r.error
            return None
        # A capture time is NOT a publication time: it is carried as `captured`, never as
        # `published`, so no claim inherits a PIT stamp it does not have.
        return [{"url": x["url"], "title": "", "captured": x["timestamp"]}
                for x in parse_cdx_ndjson(r.text) if _page_like(x["url"])]

    def _wayback(self, q: _Query, rec: BackendRecord) -> list[dict[str, str]] | None:
        if not q.host:
            rec.status, rec.why = SKIPPED, "the archive index answers per host; no site given"
            return None
        url = (f"{WAYBACK_CDX}?url={quote(f'{q.host}/*', safe='')}&output=json"
               f"&limit={ROWS_PER_BACKEND}&filter=statuscode:200&collapse=urlkey"
               "&fl=original,timestamp,mimetype,statuscode")
        r = self.get(url, rec)
        if r is None:
            return None
        if not r.ok:
            rec.why = f"HTTP {r.status}" if r.status else r.error
            return None
        # A capture time is NOT a publication time: it is carried as `captured`, never as
        # `published`, so no claim inherits a PIT stamp it does not have.
        return [{"url": x["url"], "title": "", "captured": x["timestamp"]}
                for x in parse_wayback_cdx(r.text) if _page_like(x["url"])]

    def _engine(self, name: str, build: Callable[..., str],
                parse: Callable[[str], list[dict[str, str]]], q: _Query,
                rec: BackendRecord) -> list[dict[str, str]] | None:
        url = build(q.query, q.site, q.lang, q.market)
        r = self.get(url, rec)
        if r is None:
            return None
        if not r.ok:
            rec.why = f"HTTP {r.status}" if r.status else r.error
            return None
        rows = parse(r.text)
        if not rows:
            rec.why = f"{name} returned no parseable results ({len(r.text)} bytes)"
            return None                      # a shell is a refusal, never an empty forest
        return rows

    # ---------------------------------------------------------------- the public call
    def discover(self, query: str, *, site: str = "", lang: str = "en", market: str = "",
                 region: str = "", deadline: float | None = None) -> Discovery:
        q = _Query(query=str(query or ""), site=str(site or ""), host=_site_host(site),
                   lang=str(lang or "en"), market=str(market or ""),
                   region=str(region or market or "").lower())
        off = _match(q.host, NEVER_DISCOVER)
        if off:
            why = f"REFUSED: {NEVER_CONTACT[off]} ({off}): not discovered on any backend"
            return Discovery(rows=[], records=[BackendRecord(n, SKIPPED, why=why)
                                               for n in self.backends])
        fns = {"site_feeds": self._site_feeds, "gdelt_doc": self._gdelt,
               "commoncrawl_cdx": self._commoncrawl, "wayback_cdx": self._wayback}
        rows: list[dict[str, str]] = []
        records: list[BackendRecord] = []
        seen: set[str] = set()
        for name in self.backends:
            if len(rows) >= ENOUGH_ROWS:
                break
            per_host = name != "gdelt_doc" or bool(q.host)
            key = (name, q.host) if per_host and q.host else (name, q.query, q.region, q.lang)
            with self._lock:
                cached = self._cache.get(key)
            if cached is not None:
                rec, got = cached
                rec = BackendRecord(**{**rec.__dict__, "requests": 0})
            else:
                if deadline is not None and time.monotonic() >= deadline:
                    records.append(BackendRecord(name, SKIPPED, why="ground budget spent"))
                    continue
                rec = BackendRecord(name, "")
                try:
                    out = fns[name](q, rec)
                except Exception as exc:              # a parser bug is recorded, never raised
                    out, rec.why = None, f"{type(exc).__name__}"
                if out is not None:
                    rec.status = YIELDED if out else EMPTY
                elif rec.status != SKIPPED:
                    rec.status = BLOCKED
                got = rank(out or [], q.query)[:ROWS_PER_BACKEND]
                rec.rows = len(got)
                with self._lock:
                    self._cache[key] = (rec, got)
                _stat(rec)
            records.append(rec)
            for r in got:
                u = r.get("url", "")
                if u and u not in seen and not _match(_host(u), NEVER_DISCOVER):
                    seen.add(u)
                    rows.append({**r, "backend": name})
        if not rows and self.last_resort:
            for name, build, parse in self.last_resort:
                rec = BackendRecord(name, "", lawful=False)
                if deadline is not None and time.monotonic() >= deadline:
                    rec.status, rec.why = SKIPPED, "ground budget spent"
                    records.append(rec)
                    continue
                try:
                    out = self._engine(name, build, parse, q, rec)
                except Exception as exc:
                    out, rec.why = None, f"{type(exc).__name__}"
                rec.status = BLOCKED if out is None else (YIELDED if out else EMPTY)
                rec.rows = len(out or [])
                _stat(rec)
                records.append(rec)
                for r in out or []:
                    u = r.get("url", "")
                    if u and u not in seen and not _match(_host(u), NEVER_DISCOVER):
                        seen.add(u)
                        rows.append({**r, "backend": name})
                if rows:
                    break
        return Discovery(rows=rank(rows, q.query), records=records)


@dataclass
class _Query:
    query: str
    site: str
    host: str
    lang: str
    market: str
    region: str


def http_error_to_fetched(url: str, exc: BaseException) -> Fetched:
    """Adapter for callers whose transport raises (urllib's HTTPError / OSError)."""
    if isinstance(exc, urllib.error.HTTPError):
        final = str(getattr(exc, "filename", "") or "")
        return Fetched(url=url, status=int(exc.code), error=f"HTTP {exc.code}",
                       final_url="" if final in ("", url) else final)
    return Fetched(url=url, status=None, error=f"{type(exc).__name__}")
