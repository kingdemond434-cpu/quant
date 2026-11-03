"""One polite, concurrent, measured HTTP GET for every alt-data miner.

WHY THIS EXISTS (measured 2026-09-30 on the trading box). The alt-data miners fetched one URL at a
time with ad-hoc sleeps and no retry, so their wall time was mostly spent waiting, and every
transient failure was booked as a verdict about the source:

* `readitrades_africa` lost 217 of 217 attempts to `SSLError` -- a trust-store problem on the
  Windows Python build, not a closed source. `ssl_context()` loads certifi's bundle ON TOP of the
  system store, so a chain either knows is accepted.
* `share4you`, `hfm_pamm`, `followme_cn`, `minfx_jp` were booked `HTTPError` on the first answer.
  A 5xx is a request to come back later; `get()` does, with exponential backoff and the server's
  own `Retry-After` (capped), inside a hard deadline. A 404 is deterministic and is NOT retried.
* Chinese and Japanese grounds serve GBK / Shift_JIS. Decoding every body as UTF-8 with
  `errors="replace"` turned their text into U+FFFD soup that no claim extractor can read.
  `decode_body()` honours the header charset, then the page's own `<meta charset>`.

POLITENESS IS PER HOST, NOT PER MINER. `HostGate` spaces requests to one host by a minimum
interval shared by every thread in the process, so a miner can run many fetches at once against
MANY hosts without ever sending one host more than it did when it ran sequentially. That is how
concurrency buys coverage per second without buying a ban.

MEASURED, NEVER ASSUMED. `STATS` counts fetches, successes, HTTP and transport failures, bytes
and seconds per `leg` label, so a miner can publish its own fetches/second.

HONEST, AND ROBOTS DECIDES (auditor ruling 2026-10-14). Every request carries `DESK_UA`; a
caller-supplied User-Agent that looks like a browser or another company's crawler is REPLACED by
it (`honest_headers`), so no caller can make this module impersonate one. Before every request --
the URL and each redirect hop -- `HostAccess.permits` reads the exact origin's robots.txt (24h
cache) against the `DESK_UA_PRODUCT` token: unreadable robots (network error, 5xx) means no
fetch; a 4xx other than 401/403/429, or an HTML soft-404, means allow (RFC 9309). 401
(NEEDS_KEY), 403 and 429 (METHOD_BLOCKED), and a challenge recognised by markup, header or status
(a Cloudflare 503 included), are a HARD STOP for the whole site: no retry, no sibling host, no
other route, recorded in the shared access state as a PERSON-HELD hold that no clock
releases (`release`, `--release site:<site> --by <name>`). There is no IP, egress or User-Agent
rotation anywhere in this module. `HostAccess` is the ONE implementation: the world crawler
subclasses it.

No secret is read or sent. Stdlib only (certifi is optional).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

#: THE DESK'S HONEST USER-AGENT (auditor ruling 2026-10-14: browser impersonation is forbidden).
#: The project's name plus a contact path a site operator can reach, and no "Mozilla", engine or
#: browser token. A fetcher that reads the open web on its own initiative (a crawler, a frontier,
#: a ground it found itself) identifies itself with THIS, and robots.txt is matched against its
#: product token `DESK_UA_PRODUCT`. One definition: import it, never copy it.
DESK_UA_PRODUCT = "quant-mt5-research-desk"
DESK_UA = (f"{DESK_UA_PRODUCT}/1.0 (+https://github.com/kingdemond434-cpu/quant/issues; "
           "internal research; honours robots.txt)")
#: The default request headers. There is no browser variant: `BROWSER_UA` / `BROWSER_HEADERS`
#: were deleted with the ruling, and `honest_headers` replaces any browser-looking UA a caller
#: passes.
DESK_HEADERS: dict[str, str] = {
    "User-Agent": DESK_UA,
    "Accept": ("text/html,application/xhtml+xml,application/json,application/xml;q=0.9,"
               "*/*;q=0.8"),
    "Accept-Encoding": "gzip, deflate",
}
#: Tokens that only a browser -- or a NAMED CRAWLER (a search engine's, an ad network's) -- puts in
#: its User-Agent. Sending either is impersonation: a desk fetcher is neither a person's browser
#: nor another company's crawler, and a robots.txt rule written for that crawler is not addressed
#: to it. This tuple is the ONE list; `tests/data/test_no_browser_ua.py` allow-lists exactly it.
IMPERSONATION_UA_TOKENS: tuple[str, ...] = (
    # browsers and engines
    "mozilla/", "chrome/", "chromium/", "crios/", "safari/", "applewebkit", "gecko/", "edg/",
    "edge/", "opr/", "opera/", "opera mini", "presto/", "msie ", "trident/", "firefox/",
    # other companies' crawlers
    "googlebot", "adsbot-google", "mediapartners-google", "google-inspectiontool", "bingbot",
    "slurp", "baiduspider", "yandexbot", "duckduckbot", "applebot", "facebookexternalhit",
    "twitterbot", "petalbot", "sogou web spider", "360spider", "bytespider", "yeti/",
)
#: Back-compatible name for importers that read the old browser-only list.
BROWSER_UA_TOKENS: tuple[str, ...] = IMPERSONATION_UA_TOKENS


def looks_like_browser(ua: str) -> bool:
    """True when `ua` carries a browser OR a named-crawler token: either is impersonation."""
    low = str(ua or "").lower()
    return any(t in low for t in IMPERSONATION_UA_TOKENS)


looks_impersonating = looks_like_browser


def honest_headers(headers: Mapping[str, str] | None = None) -> dict[str, str]:
    """DESK_HEADERS overlaid with the caller's, with exactly one User-Agent that impersonates
    nobody. A caller's own honest UA (the SEC's declared-contact UA, say) is kept; a browser- or
    named-crawler-looking one is replaced by DESK_UA, whatever case its header name was spelled
    in."""
    out = dict(DESK_HEADERS)
    caller_ua = ""
    for k, v in (headers or {}).items():
        if k.lower() == "user-agent":
            caller_ua = str(v)
            continue
        out[k] = str(v)
    if caller_ua.strip() and not looks_like_browser(caller_ua):
        out["User-Agent"] = caller_ua.strip()
    return out


#: Statuses that mean "come back later", and the only ones retried. 429 is NOT here: it is a
#: refusal (`BLOCK_STATUS`), a hard stop recorded for the site.
RETRY_STATUS: frozenset[int] = frozenset({408, 425, 500, 502, 503, 504, 520, 521, 522,
                                          523, 524})
#: Default spacing between two requests to ONE host, process-wide.
DEFAULT_HOST_INTERVAL_S = 1.1
#: Hosts that answer for many grounds at once (search engines) get a wider spacing, so running
#: grounds concurrently never raises the rate any one of them sees.
HOST_INTERVAL_S: dict[str, float] = {
    "www.bing.com": 2.0, "bing.com": 2.0, "html.duckduckgo.com": 2.5,
    "duckduckgo.com": 2.5, "lite.duckduckgo.com": 2.5, "www.google.com": 3.0,
}
MAX_RETRY_AFTER_S = 30.0
MAX_BYTES = 2_000_000


# --------------------------------------------------------------------------- TLS
_CTX: ssl.SSLContext | None = None
_CTX_LOCK = threading.Lock()


def ssl_context() -> ssl.SSLContext:
    """The system trust store PLUS certifi's bundle when it is installed. Verification stays on:
    a chain that neither store knows is a real failure and is reported as one."""
    global _CTX
    with _CTX_LOCK:
        if _CTX is None:
            ctx = ssl.create_default_context()
            try:
                import certifi  # type: ignore[import-not-found,unused-ignore]
                ctx.load_verify_locations(cafile=certifi.where())
            except Exception:
                pass
            _CTX = ctx
        return _CTX


# --------------------------------------------------------------------------- per-host gate
class HostGate:
    """Process-wide minimum spacing between requests to one host. Thread-safe; the sleep happens
    OUTSIDE the lock, so waiting on one host never blocks a fetch to another."""

    def __init__(self, default_s: float = DEFAULT_HOST_INTERVAL_S,
                 per_host: Mapping[str, float] | None = None) -> None:
        self.default_s = float(default_s)
        self.per_host = dict(per_host or {})
        self._next: dict[str, float] = {}
        self._lock = threading.Lock()

    def interval(self, host: str) -> float:
        return float(self.per_host.get(host, self.default_s))

    def reserve(self, host: str, at_least: float = 0.0) -> float:
        """Book the next slot for `host`; returns how long the caller must wait for it. The
        spacing after this slot is max(the host's interval, `at_least`) -- robots Crawl-delay."""
        now = time.monotonic()
        with self._lock:
            slot = max(now, self._next.get(host, 0.0))
            self._next[host] = slot + max(self.interval(host), float(at_least or 0.0))
        return max(0.0, slot - now)

    def penalise(self, host: str, seconds: float) -> None:
        """A 429/503 pushes the host's next slot out for every thread, not only the one that saw
        it."""
        with self._lock:
            self._next[host] = max(self._next.get(host, 0.0), time.monotonic() + seconds)

    def wait(self, host: str, sleep: Callable[[float], None] = time.sleep,
             at_least: float = 0.0) -> None:
        w = self.reserve(host, at_least)
        if w > 0:
            sleep(w)


GATE = HostGate(per_host=HOST_INTERVAL_S)


# --------------------------------------------------------------------------- robots + refusals
#: The per-host access record every polite fetcher shares: robots.txt read per origin and the sites
#: that refused. Box-written state, NOT under `intelligence/` (the compiler reads every JSON there
#: as a donation). The world crawler wrote it first and keeps the same file, so a site that
#: refused the crawler is held for every miner too.
ACCESS_STATE = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data"
                / "world_crawler_access.json")
#: robots.txt is re-read at most this often per scheme://host[:port].
ROBOTS_TTL_S = 24 * 3600
#: EVERY HOLD WAITS FOR A PERSON (auditor ruling 2026-10-14, GD_LANDING_TRAIN_6eb7a91b4 MF1).
#: A 401, 403, 429 or WAF/challenge page holds the site until a person releases it
#: (`release(key, by)`, or `python -m libs.data.polite_fetch --release site:<site> --by <name>`).
#: There is no recheck clock: a row is active while `released_by` is null, and a legacy row that
#: still carries a `recheck_after_ts` is active too -- time never releases a hold.
#: Redirect hops followed per fetch; every hop passes the hold and robots checks again.
MAX_REDIRECTS = 5
MAX_ROBOTS_BYTES = 512_000
ROBOTS_TIMEOUT_S = 12.0
REDIRECT_STATUS: frozenset[int] = frozenset({301, 302, 303, 307, 308})
#: The verdict each refusal status is recorded as. A hard stop: never retried, never routed around.
BLOCK_STATUS: dict[int, str] = {401: "NEEDS_KEY", 403: "METHOD_BLOCKED", 429: "METHOD_BLOCKED"}

#: The Public Suffix List, VENDORED (snapshot 2025-12-28, MPL-2.0, from publicsuffix.org): no
#: network at runtime and no new dependency. ICANN and PRIVATE sections both apply, so github.io,
#: blogspot.com and k12.ca.us tenants are separate sites. Refresh by replacing the file.
PSL_PATH = Path(__file__).with_name("public_suffix_list.dat")
_PSL: tuple[frozenset[str], frozenset[str], frozenset[str]] | None = None
_PSL_LOCK = threading.Lock()


def _idna(label: str) -> str:
    try:
        return label.encode("idna").decode("ascii")
    except UnicodeError:
        return label


def _psl() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """(plain rules, wildcard parents, exception rules), each in both Unicode and IDNA form."""
    global _PSL
    with _PSL_LOCK:
        if _PSL is None:
            plain: set[str] = set()
            wild: set[str] = set()
            exc: set[str] = set()
            try:
                lines = PSL_PATH.read_text("utf-8").splitlines()
            except OSError:
                lines = []
            for ln in lines:
                rule = ln.strip().split(" ")[0].lower()
                if not rule or rule.startswith("//"):
                    continue
                forms = {rule, ".".join(_idna(x) if x not in ("*", "!") else x
                                        for x in rule.lstrip("!").split("."))}
                for r in forms:
                    if rule.startswith("!"):
                        exc.add(r.lstrip("!"))
                    elif r.startswith("*."):
                        wild.add(r[2:])
                    else:
                        plain.add(r)
            _PSL = (frozenset(plain), frozenset(wild), frozenset(exc))
        return _PSL


def _is_ip(host: str) -> bool:
    import ipaddress
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def ascii_url(url: str) -> str:
    """Percent-encode a URL's non-ASCII parts (IDNA for the host); urllib raises without this."""
    try:
        url.encode("ascii")
    except UnicodeEncodeError:
        parts = urlsplit(url)
        netloc = parts.netloc
        with contextlib.suppress(UnicodeError):
            netloc = parts.netloc.encode("idna").decode("ascii")
        return urlunsplit((parts.scheme, netloc, quote(parts.path, safe="/%"),
                           quote(parts.query, safe="=&%?"), quote(parts.fragment, safe="%")))
    return url


def origin_of(url: str) -> str:
    """scheme://host[:port], lower-cased. robots.txt belongs to exactly this, never to a parent."""
    parts = urlsplit(url)
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def hostname_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def site_of(host: str) -> str:
    """The registrable site a host belongs to, by the Public Suffix List. A refusal holds the whole
    site, so a 403 on www.example.org is never answered by asking old.example.org or example.org
    instead -- and a.github.io's refusal never holds b.github.io. A bare IP is its own site."""
    host = host.lower().strip(".")
    if not host or _is_ip(host):
        return host
    labels = [x for x in host.split(".") if x]
    plain, wild, exc = _psl()
    suffix_len = 1                                   # the default rule "*"
    for i in range(len(labels)):
        cand = ".".join(labels[i:])
        if cand in exc:                              # an exception rule: its parent is the suffix
            suffix_len = len(labels) - i - 1
            break
        if cand in plain:
            suffix_len = max(suffix_len, len(labels) - i)
        if i >= 1 and cand in wild:
            suffix_len = max(suffix_len, len(labels) - i + 1)
    if suffix_len >= len(labels):
        return host                                  # the host IS a public suffix
    return ".".join(labels[-(suffix_len + 1):])


#: Anti-bot interstitials, recognised by MARKUP, HEADER or STATUS -- never by prose. A forum post
#: that says "Just a moment..." or "checking your browser" is content; holding a whole site on
#: words a person can type is a mining cut (P6). What a challenge page carries and an ordinary
#: page does not is the vendor's own machinery:
#:   * strong markup (any status): Cloudflare's challenge bootstrap and form, Imperva/Incapsula's
#:     resource path, DataDome's and PerimeterX's block-page hooks, AWS WAF's challenge loader.
#:   * a header: `cf-mitigated: challenge` is Cloudflare saying so outright.
#:   * weak markup ONLY WITH a refusal status (403/429/503): `challenge-platform` and `cf-chl-`
#:     also appear on ORDINARY 200 pages (Cloudflare's passive bot-detection script, a Turnstile
#:     widget on a comment form), so on a 200 they prove nothing.
CHALLENGE_MARKUP: tuple[str, ...] = (
    "_cf_chl_opt", "__cf_chl_", "challenge-platform/h/", "/chl_page", 'id="challenge-form"',
    "id='challenge-form'", "cf-browser-verification", "_incapsula_resource",
    "captcha-delivery.com", 'id="px-captcha"', "awswafcookiedomainlist")
CHALLENGE_MARKUP_WITH_STATUS: tuple[str, ...] = ("challenge-platform", "cf-chl-", "cf_chl_")
CHALLENGE_STATUS: frozenset[int] = frozenset({403, 429, 503})
#: Back-compatible name: the markers `looks_challenged` matches on any status.
CHALLENGE_MARKERS: tuple[str, ...] = CHALLENGE_MARKUP


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    try:
        v = headers.get(name)
    except Exception:
        return ""
    if v is None and isinstance(headers, Mapping):
        for k, vv in headers.items():
            if str(k).lower() == name.lower():
                v = vv
                break
    return str(v or "")


def looks_challenged(body: str | bytes, headers: Any = None, status: int | None = None) -> str:
    """What marks this response as an anti-bot challenge, or ''. A challenge is a block, not
    content. Decided by markup, header or status -- never by body prose (see CHALLENGE_MARKUP)."""
    if _header(headers, "cf-mitigated").strip().lower() == "challenge":
        return "cf-mitigated: challenge"
    if isinstance(body, bytes):
        body = body[:16000].decode("utf-8", errors="replace")
    low = str(body or "")[:16000].lower()
    for marker in CHALLENGE_MARKUP:
        if marker in low:
            return marker
    if status in CHALLENGE_STATUS:
        for marker in CHALLENGE_MARKUP_WITH_STATUS:
            if marker in low:
                return f"{marker} with HTTP {status}"
        if "ddos-guard" in _header(headers, "Server").lower():
            return f"server: ddos-guard with HTTP {status}"
    return ""


def looks_like_html(body: str | bytes) -> bool:
    if isinstance(body, bytes):
        body = body[:2000].decode("utf-8", errors="replace")
    head = str(body or "")[:2000].lstrip().lower()
    return head.startswith(("<!doctype", "<html", "<head", "<body", "<?xml")) or "<html" in head


#: The missed-growth line every hold carries (GROWTH GOVERNANCE): the gain forgone by not reading
#: the site is UNMEASURED, never zero, and the line says why.
def hold_missed_growth(site: str, verdict: str, status: int | str, cause: str) -> dict[str, Any]:
    return {"source": site, "kind": "access_hold", "status": verdict, "http_status": status,
            "delta_elogw": "UNMEASURED",
            "cause": (f"{cause}; nothing from {site} is read while the hold stands, and no "
                      "conversion of its pages is on record here, so the growth forgone is "
                      "UNMEASURED, never zero")}


def _held_at(row: Mapping[str, Any]) -> float:
    for k in ("held_at", "since_ts"):
        try:
            return float(row.get(k) or 0)
        except (TypeError, ValueError):
            continue
    return 0.0


def person_held(row: Any) -> bool:
    """Is this hold row in force? Active while `released_by` is null -- whatever any timestamp
    says. A legacy row with `recheck_after_ts` is still active: time never releases a hold."""
    return isinstance(row, Mapping) and not row.get("released_by")


def hold_record(site: str, url: str, verdict: str, status: int | str | None, now: float, *,
                missed_growth: dict[str, Any] | None = None) -> dict[str, Any]:
    """THE SHARED PERSON-HELD RECORD (agreed with `research/hard_stop.py` and
    `research/source_fixer.py` so they cannot drift): key, verdict, status, host, url (300 chars),
    held_at (unix), released_by / released_at null. No recheck_after_ts: no clock releases it."""
    host = hostname_of(url) or site
    return {"key": f"site:{site}", "verdict": verdict,
            "status": status if isinstance(status, int) else (status or None),
            "host": host, "url": url[:300], "held_at": now,
            "released_by": None, "released_at": None,
            "since_utc": datetime.fromtimestamp(now, tz=UTC).isoformat(timespec="seconds"),
            "waits_for": "a person",
            "missed_growth": missed_growth or hold_missed_growth(
                site, verdict, status if status is not None else "", f"{verdict} from {host}")}


class ReleaseNotSaved(OSError):
    """A person's release that could not be written to the shared ledger (unreadable ledger,
    lock timeout, write failure): the hold still stands on disk, so the release is not done."""


def release(key: str, by: str, path: Path | None = None) -> dict[str, Any]:
    """A PERSON releases one hold: the only way a hold ever ends. `key` is `site:<site>` (or the
    bare site). Sets released_by / released_at on disk and in the process-wide record; the row
    stays as the audit trail. KeyError when no such hold exists; ValueError without a name;
    ReleaseNotSaved when the ledger refused the save (nothing in memory is changed then)."""
    who = str(by or "").strip()
    if not who:
        raise ValueError("a release names the person releasing the hold (--by <name>)")
    site = key[5:] if key.startswith("site:") else key
    target = path or ACCESS_STATE
    acc = HostAccess.load(target)
    with acc._lock:
        row = acc.blocked.get(site)
        if not isinstance(row, dict):
            raise KeyError(key)
        row = {**row, "key": f"site:{site}", "released_by": who, "released_at": time.time()}
        acc.blocked[site] = row
    if not acc.save():
        why = acc.save_refusals[-1]["why"] if acc.save_refusals else "save refused"
        raise ReleaseNotSaved(f"release of {key} by {who} was NOT saved: {why}")
    live = _ACCESS
    if live is not None and (live.path or ACCESS_STATE) == target:
        with live._lock:
            live.blocked[site] = dict(row)
    return dict(row)


def person_hold(url: str, access: HostAccess | None = None) -> str:
    """The verdict of the person-held hold on `url`'s site, or ''. For callers that do not fetch
    through `get` (Google Trends' readers, the fetch door): they ask before every request."""
    return (access if access is not None else default_access()).hold(url)


def hold_site(url: str, status: int | str, cause: str = "",
              access: HostAccess | None = None, *,
              mirror: Mapping[str, Any] | None = None) -> str:
    """Record a person-held hold on `url`'s site (a 401/403/429 or "WAF") and save it at once.
    `mirror` names the other register's hold this one was placed with ({key, held_at}), so a
    person's release of THAT hold is recognised as covering this one (`adopt_release`)."""
    extra = ({"mirror_key": str(mirror.get("key") or ""), "mirror_held_at": mirror.get("held_at")}
             if mirror else None)
    return (access if access is not None else default_access()).block(url, status, cause=cause,
                                                                      extra=extra)


def adopt_release(url: str, by: Any, released_at: Any, key: str = "",
                  access: HostAccess | None = None) -> bool:
    """A PERSON'S release recorded in another person-held register (research/hard_stop's, for
    the same site) releases this record's hold on `url`'s site too -- but only a hold placed AT
    OR BEFORE that release: a refusal after it is a new hold the release never covered. A hold
    placed WITH that register's hold (`mirror_key` == `key`) is dated by the mirrored hold's
    `held_at`, on that register's clock. Nothing is released without a named person; no
    timestamp alone releases anything. True if released."""
    who = str(by or "").strip()
    try:
        at = float(released_at)
    except (TypeError, ValueError):
        return False
    if not who:
        return False
    acc = access if access is not None else default_access()
    site = site_of(hostname_of(url))
    with acc._lock:
        row = acc.blocked.get(site)
        if not isinstance(row, dict) or not person_held(row):
            return False
        placed = _held_at(row)
        if key and row.get("mirror_key") == key:
            try:
                placed = float(row.get("mirror_held_at") or "")
            except (TypeError, ValueError):
                return False
        if placed > at:
            return False
    try:
        release(f"site:{site}", who, path=acc.path or ACCESS_STATE)
    except ReleaseNotSaved:
        return False                   # not on disk: the hold stands, and says so
    with acc._lock:
        cur = acc.blocked.get(site)
        if isinstance(cur, dict) and not cur.get("released_by"):
            acc.blocked[site] = {**cur, "released_by": who, "released_at": time.time()}
    return True


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects surface as HTTPError, so the fetcher checks each target BEFORE following it.

    It runs AHEAD of the fence's own redirect handler (`handler_order = 400` < 500) and RAISES
    rather than returning None: a None would hand the 30x to `terms_fence.FencedRedirectHandler`,
    which follows it, and the hop would skip this module's robots and hold checks."""

    handler_order = 400

    def _raise(self, req, fp, code, msg, headers):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_302 = http_error_303 = http_error_307 = _raise
    http_error_308 = _raise

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def open_no_redirect(req: urllib.request.Request, timeout: float,
                     context: ssl.SSLContext | None = None) -> Any:
    """The module's own network call: certifi-backed TLS, redirects NOT followed, and every
    request terms-fenced -- the opener is THE ONE FETCH DOOR's (`terms_fence.guarded_opener`,
    the door `fenced_urlopen` opens) with `NoRedirect` ahead of its redirect handler."""
    # Built per call, like the crawler's `_open`: the fence's opener is resolved at call time,
    # so the door in force is always the current one (never a stale cached opener).
    return _tf.guarded_opener(ssl_context(), NoRedirect()).open(req, timeout=timeout)


Send = Callable[[urllib.request.Request, float], Any]


# --------------------------------------------------------------------------- robots.txt rules
class RobotsRules:
    """robots.txt per RFC 9309, the desk's ONE reading of it (`HostAccess` is its only caller
    on the network path; nothing else in the desk parses robots.txt).

    SEMANTICS, kept identical to `research/hard_stop.robots_verdict` (alt-seat-cells
    bc6549361) -- `tests/data/robots_parity_fixtures.json` is the shared table both must pass:
    * GROUP: every group whose `User-agent` value equals the product token (case-insensitive)
      -- stacked `User-agent` lines accumulate into one group, and several matching groups are
      merged; when none names it, the `*` group(s); when neither exists, everything is allowed.
      A group ends only when a `User-agent` line follows an Allow/Disallow line.
    * MATCH: the LONGEST matching Allow/Disallow pattern wins; an Allow wins a tie. `*` matches
      any run of characters and a trailing `$` anchors the end. An empty pattern is no rule.
      Patterns and the path+query are compared as written (no percent-decoding).
      `/robots.txt` itself is always allowed. A leading UTF-8 BOM is ignored.
    `urllib.robotparser` is NOT used: it takes the first matching rule in file order (so
    `Allow: /` above `Disallow: /private` let the private path through) and reads `*`/`$` as
    literal characters (so `Disallow: /*.pdf` matched nothing)."""

    def __init__(self, text: str = "") -> None:
        self.groups: list[tuple[set[str], list[tuple[bool, str]], float | None]] = []
        agents: set[str] = set()
        rules: list[tuple[bool, str]] = []
        delay: float | None = None
        in_rules = False
        for raw in (text or "").lstrip("\ufeff").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "user-agent":
                if in_rules:                      # a new group starts after the last one's rules
                    self.groups.append((agents, rules, delay))
                    agents, rules, delay, in_rules = set(), [], None, False
                agents.add(val.lower())           # stacked User-agent lines ACCUMULATE
            elif key in ("allow", "disallow") and agents:
                in_rules = True
                rules.append((key == "allow", val))
            elif key == "crawl-delay" and agents and delay is None:
                with contextlib.suppress(ValueError):
                    delay = max(0.0, float(val))  # not a rule line: it never ends a group
        if agents:
            self.groups.append((agents, rules, delay))

    def _group(self, product: str) -> tuple[list[tuple[bool, str]], float | None] | None:
        token = str(product or "").lower()
        for want in (token, "*"):
            if not want:
                continue
            rules: list[tuple[bool, str]] = []
            delay: float | None = None
            hit = False
            for agents, grules, gdelay in self.groups:
                if want in agents:
                    hit = True
                    rules.extend(grules)
                    delay = gdelay if delay is None else delay
            if hit:
                return rules, delay
        return None

    @staticmethod
    def _matches(pattern: str, target: str) -> bool:
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
        return re.match(rx + ("$" if anchored else ""), target) is not None

    def can_fetch(self, product: str, url: str) -> bool:
        parts = urlsplit(url)
        target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if target == "/robots.txt":
            return True
        group = self._group(product)
        if group is None:
            return True
        best: tuple[int, bool] | None = None      # (pattern length, allow): longest wins
        for allow, pattern in group[0]:
            if not pattern or not self._matches(pattern, target):
                continue
            if best is None or len(pattern) > best[0] or (len(pattern) == best[0] and allow):
                best = (len(pattern), allow)
        return best is None or best[1]

    def crawl_delay(self, product: str) -> float | None:
        group = self._group(product)
        return None if group is None else group[1]


def parse_robots(text: str) -> RobotsRules:
    """robots.txt text -> `RobotsRules` (the ONE parser; see its docstring)."""
    return RobotsRules(text)


#: How long a save waits for the ledger's lock file before refusing (never overwriting).
SAVE_LOCK_WAIT_S = 10.0
#: A lock file older than this is a crashed writer's and is broken (a save holds it for ms).
SAVE_LOCK_STALE_S = 120.0


class _LedgerLock:
    """A cross-process lock on the shared access ledger: `<ledger>.lock`, created with O_EXCL
    (atomic on POSIX and on Windows/NTFS, no fcntl/msvcrt) and stamped with this holder's TOKEN
    (pid + random nonce). Bounded wait. A lock older than SAVE_LOCK_STALE_S is a dead writer's:
    it is broken by RENAMING it to a unique name first (only one waiter's rename can succeed;
    the loser retries the acquire), and a renamed lock that turns out fresh -- a live peer's,
    re-created between the age check and the rename -- is put back, never deleted. `release`
    removes the lock only while it still carries this holder's token."""

    def __init__(self, ledger: Path, wait_s: float | None = None) -> None:
        self.path = ledger.with_name(f"{ledger.name}.lock")
        self.wait_s = SAVE_LOCK_WAIT_S if wait_s is None else wait_s
        self.token = f"{os.getpid()} {os.urandom(8).hex()}"
        self.held = False

    def _read_token(self, path: Path | None = None) -> str:
        try:
            return (path or self.path).read_bytes().decode("utf-8", "replace").strip()
        except OSError:
            return ""

    def _break_stale(self) -> None:
        """Break the lock if it is stale. Never deletes a lock that is not stale."""
        try:
            if time.time() - self.path.stat().st_mtime <= SAVE_LOCK_STALE_S:
                return
        except OSError:
            return
        aside = self.path.with_name(f"{self.path.name}.stale.{os.getpid()}."
                                    f"{os.urandom(6).hex()}")
        try:
            os.rename(self.path, aside)
        except OSError:
            return                  # another waiter broke (renamed) it first: retry the acquire
        try:
            fresh = time.time() - aside.stat().st_mtime <= SAVE_LOCK_STALE_S
        except OSError:
            fresh = False
        if fresh:
            # a live peer's lock, created after our age check: put it back (link fails if the
            # name is taken again, which leaves the newer holder's lock alone)
            with contextlib.suppress(OSError):
                os.link(aside, self.path)
        with contextlib.suppress(OSError):
            aside.unlink()

    def acquire(self) -> bool:
        deadline = time.monotonic() + self.wait_s
        with contextlib.suppress(OSError):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                self._break_stale()
            except OSError:
                pass                      # Windows: PermissionError while another unlinks it
            else:
                try:
                    os.write(fd, self.token.encode())
                finally:
                    os.close(fd)
                self.held = True
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02 + random.random() * 0.03)  # noqa: S311 - lock jitter

    def release(self) -> None:
        """Unlink the lock only if it still carries this holder's token (a peer that broke it
        as stale owns whatever lock is there now)."""
        if not self.held:
            return
        self.held = False
        if self._read_token() == self.token:
            with contextlib.suppress(OSError):
                self.path.unlink()


class HostAccess:
    """robots.txt per scheme://host[:port] and the refusals each site has given.

    THE RULES (auditor ruling 2026-10-14):
      * robots.txt decides every fetch, read for the exact origin -- a subdomain or a port has
        its own file -- and matched against `DESK_UA_PRODUCT`. Cached `ROBOTS_TTL_S`.
      * robots.txt unreadable (network error, 5xx) means NO fetch to that origin this run;
        a 404/410 (any other 4xx) on robots.txt means allow all, per the standard.
      * 401 (NEEDS_KEY), 403 and 429 (METHOD_BLOCKED), on a page or on robots.txt, are a hard stop
        for the whole site: nothing else is sent to it, by any route. Every hold (429 and WAF
        included) waits for a person's `release`; no clock ends it.
    Thread-safe: miners call `permits` from a pool.
    """

    user_agent = DESK_UA
    product = DESK_UA_PRODUCT

    def __init__(self, path: Path | None = None, now: float | None = None) -> None:
        self.path = path
        self._now = now
        self.robots: dict[str, dict[str, Any]] = {}
        self.blocked: dict[str, dict[str, Any]] = {}
        self._parsers: dict[str, Any] = {}
        self._unreadable: dict[str, str] = {}
        self.robots_fetches = 0
        self.disallowed = 0
        self._lock = threading.RLock()
        self._origin_locks: dict[str, threading.Lock] = {}
        #: every save this process refused (unreadable ledger, lock timeout), newest last
        self.save_refusals: list[dict[str, Any]] = []

    def now(self) -> float:
        return self._now if self._now is not None else time.time()

    @classmethod
    def load(cls, path: Path | None = None) -> HostAccess:
        acc = cls(path or ACCESS_STATE)
        acc._merge(acc._read_disk())
        return acc

    def _read_disk(self) -> dict[str, Any]:
        """The shared ledger for a READ (load): anything unreadable reads as empty."""
        data, _why = self._read_disk_strict(quarantine=False)
        return data or {}

    def _read_disk_strict(self, *, quarantine: bool) -> tuple[dict[str, Any] | None, str]:
        """(ledger, '') when the file is absent (an empty ledger) or parsed; (None, why) when it
        exists and cannot be read. A save must never merge over an unreadable ledger: it holds
        OTHER processes' person-held holds, and writing only ours would drop them. A file that
        parses as something other than a JSON object is CORRUPT and, with `quarantine`, is moved
        aside to `<name>.corrupt.<utc>.<pid>` (kept for a person) -- an OSError other than absence
        (a Windows share violation mid-replace) is transient and left where it is."""
        if self.path is None:
            return {}, ""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return {}, ""
        except OSError as exc:
            return None, f"unreadable ({type(exc).__name__}: {exc})"
        try:
            # invalid UTF-8 (UnicodeDecodeError) is a ValueError too: CORRUPT, quarantined
            data = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            data, why = None, f"corrupt ({type(exc).__name__}: {exc})"
        else:
            if isinstance(data, dict):
                return data, ""
            why = f"corrupt (top level is {type(data).__name__}, not an object)"
        if quarantine:
            aside = self.path.with_name(
                f"{self.path.name}.corrupt.{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
                f".{os.getpid()}")
            try:
                os.replace(self.path, aside)
                why += f"; moved aside to {aside.name} (kept)"
            except OSError as exc:
                why += f"; could not move aside ({type(exc).__name__}), left in place"
        return None, why

    def _refuse_save(self, why: str) -> None:
        """Record a save this process refused, in memory and beside the ledger. Never raises."""
        row = {"at_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
               "pid": os.getpid(), "why": why, "holds_unsaved": sorted(self.blocked)}
        self.save_refusals.append(row)
        if self.path is None:
            return
        rec = self.path.with_name(f"{self.path.name}.save_refusals.jsonl")
        with contextlib.suppress(OSError), rec.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _merge(self, data: dict[str, Any]) -> None:
        """Union another writer's rows into this one: holds this process lacks are adopted, and
        a robots row is kept if it is newer. Another process's holds are never dropped, and a
        person's release on disk is adopted for the hold it released (never for a newer one)."""
        for k, v in (data.get("blocked") or {}).items():
            if not isinstance(v, dict):
                continue
            mine = self.blocked.get(str(k))
            if mine is None or (v.get("released_by") and not mine.get("released_by")
                                and _held_at(v) >= _held_at(mine)):
                self.blocked[str(k)] = v
        for k, v in (data.get("robots") or {}).items():
            if not isinstance(v, dict):
                continue
            mine = self.robots.get(str(k))
            if mine is None or float(v.get("fetched_ts") or 0) > float(mine.get("fetched_ts") or 0):
                self.robots[str(k)] = v
                self._parsers.pop(str(k), None)

    def save(self) -> bool:
        """Read-merge-replace the shared ledger under a cross-process lock file. Returns False
        (and records why) when it refused: the existing ledger could not be read, or the lock
        could not be taken in SAVE_LOCK_WAIT_S. A refused save never overwrites the file."""
        if self.path is None:
            return False
        with self._lock:
            lock = _LedgerLock(self.path)
            if not lock.acquire():
                self._refuse_save(f"lock {lock.path.name} not taken in {SAVE_LOCK_WAIT_S:g}s "
                                  f"(held by another writer); the ledger was not overwritten")
                return False
            try:
                disk, why = self._read_disk_strict(quarantine=True)
                if disk is None:
                    self._refuse_save(f"existing ledger {why}; this merge was not saved, so "
                                      "no other process's holds were dropped")
                    return False
                self._merge(disk)
                now = self.now()
                robots = {k: v for k, v in self.robots.items()
                          if now - float(v.get("fetched_ts") or 0) < ROBOTS_TTL_S}
                payload = {
                    "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                    "user_agent": self.user_agent,
                    "note": ("per-host robots.txt cache (24h) and refusal holds, shared by every "
                             "polite fetcher. Every 401/403/429/WAF hold is active while "
                             "released_by is null; no clock releases it. A person releases one "
                             "with `python -m libs.data.polite_fetch --release site:<site> "
                             "--by <name>`."),
                    "blocked": dict(self.blocked),
                    "robots": robots,
                }
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.path.with_name(
                        f"{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
                    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
                    tmp.replace(self.path)
                except OSError as exc:
                    self._refuse_save(f"write failed ({type(exc).__name__}: {exc})")
                    return False
                return True
            finally:
                lock.release()

    # ---- the network seam
    def send(self, req: urllib.request.Request, timeout: float) -> Any:
        """Open one request, redirects NOT followed. Subclasses (the crawler) override this."""
        return open_no_redirect(req, timeout)

    def request(self, url: str, accept: str) -> urllib.request.Request:
        return urllib.request.Request(ascii_url(url), headers={
            "User-Agent": self.user_agent, "Accept": accept, "Accept-Language": "*"})

    def robots_timeout(self) -> float:
        return ROBOTS_TIMEOUT_S

    # ---- holds
    def hold(self, url: str) -> str:
        """The verdict holding this URL's site, or ''. Only a person's release ends a hold."""
        site = site_of(hostname_of(url))
        with self._lock:
            row = self.blocked.get(site)
            if not person_held(row):
                return ""
            assert isinstance(row, dict)
            return str(row.get("verdict") or "METHOD_BLOCKED")

    def block(self, url: str, status: int | str, verdict: str = "", cause: str = "",
              extra: Mapping[str, Any] | None = None) -> str:
        """Record a hold for the URL's site and SAVE IT AT ONCE, so a run killed mid-loop keeps
        it. `status` is the HTTP code, or "WAF" for a challenge page. Every hold, 429 and WAF
        included, waits for a person: the row is the shared person-held record (`hold_record`)."""
        verdict = verdict or (BLOCK_STATUS.get(status, "METHOD_BLOCKED")
                              if isinstance(status, int) else "METHOD_BLOCKED")
        host = hostname_of(url)
        site = site_of(host)
        with self._lock:
            self.blocked[site] = hold_record(
                site, url, verdict, status, self.now(),
                missed_growth=hold_missed_growth(site, verdict, status,
                                                 cause or f"HTTP {status} from {host}"))
            if extra:
                self.blocked[site].update(dict(extra))
        self.save()
        return verdict

    # ---- robots
    def _read_robots(self, origin: str, send: Send) -> dict[str, Any]:
        """Fetch origin/robots.txt. Returns a row: state allow_all | rules | unreadable | blocked.
        Its redirects are followed (each hop held-checked) up to the cap."""
        url = origin + "/robots.txt"
        for hop in range(MAX_REDIRECTS + 1):
            if self.hold(url):
                return {"state": "blocked"}
            if hop and (_tf.platform_of_url(url) or _tf.login_wall(url)):
                # a robots.txt redirect into a held source or a login wall is never followed:
                # the rules cannot be read, so nothing on the origin is fetched (fail closed)
                return {"state": "unreadable", "why": "robots redirect into a fenced route"}
            with self._lock:
                self.robots_fetches += 1
            try:
                with send(self.request(url, "text/plain,*/*;q=0.5"), self.robots_timeout()) as fh:
                    body = fh.read(MAX_ROBOTS_BYTES)
                    rh = getattr(fh, "headers", None)
                    rstatus = getattr(fh, "status", None)
                text = body.decode("utf-8", errors="replace")
                marker = looks_challenged(text, rh, rstatus)
                if marker:
                    # A REAL challenge (markup, header or status) is a refusal: hold the site.
                    why = f"challenge ({marker!r}) served as robots.txt"
                    self.block(url, "WAF", "METHOD_BLOCKED", why)
                    return {"state": "blocked", "why": why}
                if looks_like_html(text):
                    # RFC 9309 s2.2/2.3: unparseable lines are ignored, so a soft-404 HTML page
                    # served as robots.txt carries no rules -- allow, exactly like a real 404.
                    return {"state": "allow_all", "why": "HTML (soft-404) served as robots.txt"}
                return {"state": "rules", "text": text}
            except urllib.error.HTTPError as exc:
                code = int(exc.code)
                loc = exc.headers.get("Location") if exc.headers else None
                ebody = b""
                with contextlib.suppress(Exception):
                    ebody = exc.read(16000)
                with contextlib.suppress(Exception):
                    exc.close()
                if code in BLOCK_STATUS:
                    self.block(url, code)
                    return {"state": "blocked", "status": code}
                marker = looks_challenged(ebody, exc.headers, code)
                if marker:
                    why = f"challenge ({marker!r}) on robots.txt, HTTP {code}"
                    self.block(url, "WAF", "METHOD_BLOCKED", why)
                    return {"state": "blocked", "status": code, "why": why}
                if code in REDIRECT_STATUS:
                    if not loc:
                        return {"state": "unreadable", "why": f"robots HTTP {code} no Location"}
                    url = urljoin(url, str(loc))
                    continue
                if 400 <= code < 500:
                    return {"state": "allow_all", "status": code}
                return {"state": "unreadable", "why": f"robots HTTP {code}"}
            except Exception as exc:
                return {"state": "unreadable", "why": f"robots {type(exc).__name__}"}
        return {"state": "unreadable", "why": "robots redirect loop"}

    def _parser(self, origin: str, send: Send) -> Any:
        with self._lock:
            olock = self._origin_locks.setdefault(origin, threading.Lock())
        with olock:                       # one robots read per origin, however many threads ask
            with self._lock:
                if origin in self._parsers:
                    return self._parsers[origin]
                if origin in self._unreadable:
                    return None
                row = self.robots.get(origin)
            fresh = (row is not None
                     and self.now() - float(row.get("fetched_ts") or 0) < ROBOTS_TTL_S)
            if not fresh:
                got = self._read_robots(origin, send)
                if got["state"] in ("unreadable", "blocked"):
                    # Not cached across runs: unreadable this run is retried next run.
                    with self._lock:
                        self._unreadable[origin] = str(got.get("why") or got["state"])
                    return None
                row = {"fetched_ts": self.now(), "state": got["state"],
                       "text": got.get("text", "")[:MAX_ROBOTS_BYTES]}
                with self._lock:
                    self.robots[origin] = row
                self.save()
            assert row is not None
            # allow_all (a 4xx robots.txt) parses as an empty file, which permits everything.
            text = "" if row.get("state") == "allow_all" else str(row.get("text") or "")
            parser = parse_robots(text)
            with self._lock:
                self._parsers[origin] = parser
            return parser

    def permits(self, url: str, send: Send | None = None) -> tuple[bool, str]:
        """(may fetch, reason if not). Holds first, then the origin's own robots.txt. `send` is
        the opener robots.txt is read through (default: this object's own seam)."""
        held = self.hold(url)
        if held:
            return False, held
        if urlsplit(url).scheme.lower() not in ("http", "https"):
            return False, "SCHEME_REFUSED"
        origin = origin_of(url)
        parser = self._parser(origin, send or self.send)
        if parser is None:
            held = self.hold(url)
            return False, held or f"ROBOTS_UNREADABLE {self._unreadable.get(origin, '')}".strip()
        if not parser.can_fetch(self.product, ascii_url(url)):
            with self._lock:
                self.disallowed += 1
            return False, "ROBOTS_DISALLOW"
        return True, ""

    def crawl_delay(self, url: str, send: Send | None = None) -> float:
        """The origin's robots.txt Crawl-delay for the desk's token, in seconds (0 when none or
        when robots is unreadable -- an unreadable origin is not fetched at all)."""
        parser = self._parser(origin_of(url), send or self.send)
        if parser is None:
            return 0.0
        try:
            d = parser.crawl_delay(self.product)
        except Exception:
            return 0.0
        try:
            return max(0.0, float(d)) if d is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {"user_agent": self.user_agent, "robots_fetches": self.robots_fetches,
                    "robots_disallowed": self.disallowed,
                    "robots_unreadable": dict(self._unreadable),
                    "holds": {k: {kk: v.get(kk) for kk in ("key", "verdict", "status", "host",
                                                            "waits_for", "released_by")}
                              for k, v in self.blocked.items() if person_held(v)}}


_ACCESS: HostAccess | None = None
_ACCESS_LOCK = threading.Lock()


def default_access() -> HostAccess:
    """The process-wide access record, loaded once from ACCESS_STATE."""
    global _ACCESS
    with _ACCESS_LOCK:
        if _ACCESS is None:
            _ACCESS = HostAccess.load(ACCESS_STATE)
        return _ACCESS


# --------------------------------------------------------------------------- stats
@dataclass
class LegStats:
    fetches: int = 0
    ok: int = 0
    http_errors: int = 0
    transport_errors: int = 0
    retries: int = 0
    refused: int = 0
    bytes: int = 0
    seconds: float = 0.0
    by_error: dict[str, int] = field(default_factory=dict)
    #: site -> the missed_growth line of every person-held hold this leg met (recorded or was
    #: refused by), so each fetcher's own artifact (`fetch_stats`) carries the bill
    held: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return {"access_holds": [self.held[k] for k in sorted(self.held)],
                "n_access_holds": len(self.held),
                "fetches": self.fetches, "ok": self.ok, "http_errors": self.http_errors,
                "transport_errors": self.transport_errors, "retries": self.retries,
                "refused": self.refused,
                "bytes": self.bytes, "fetch_seconds": round(self.seconds, 2),
                "by_error": dict(sorted(self.by_error.items(), key=lambda kv: -kv[1])[:12])}


_STATS: dict[str, LegStats] = {}
_STATS_LOCK = threading.Lock()


def _stat(leg: str, **inc: Any) -> None:
    with _STATS_LOCK:
        s = _STATS.setdefault(leg, LegStats())
        for k, v in inc.items():
            if k == "error":
                s.by_error[str(v)] = s.by_error.get(str(v), 0) + 1
            else:
                setattr(s, k, getattr(s, k) + v)


def _note_held(leg: str, acc: HostAccess, url: str) -> None:
    """Carry the missed_growth line of the person-held hold on `url`'s site into `leg`'s stats.
    A refusal that is not a hold (robots, a fence) adds nothing. Never raises."""
    with contextlib.suppress(Exception):
        site = site_of(hostname_of(url))
        with acc._lock:
            row = acc.blocked.get(site)
        if row is None or not person_held(row):
            return
        mg = row.get("missed_growth") if isinstance(row.get("missed_growth"), dict) else None
        line = dict(mg) if mg else hold_missed_growth(
            site, str(row.get("verdict") or "METHOD_BLOCKED"), row.get("status") or "",
            f"held site {site}")
        with _STATS_LOCK:
            _STATS.setdefault(leg, LegStats()).held[site] = line


def stats(leg: str) -> dict[str, Any]:
    with _STATS_LOCK:
        return (_STATS.get(leg) or LegStats()).as_row()


def reset_stats(leg: str | None = None) -> None:
    with _STATS_LOCK:
        if leg is None:
            _STATS.clear()
        else:
            _STATS.pop(leg, None)


# --------------------------------------------------------------------------- the method fence
# ONE FETCH DOOR, ONE TABLE (composition of #162 and #262). The per-source policy and the method
# rules live in `libs.data.terms_fence` and nowhere else; this module re-exports the door under the
# names its callers already use, so there is no second redirect handler and no second login-wall
# pattern to drift. What stays off is the METHOD (principal ruling 2026-10-13: no source is
# banned): a HELD source, or a redirect into a login / sign-in / CAPTCHA wall, is refused and named
# -- never followed, never retried with other headers -- and every followed hop stays visible.
from libs.data import terms_fence as _tf  # noqa: E402

LOGIN_WALL = _tf.LOGIN_WALL
login_wall = _tf.login_wall
#: The refusal THE ONE FETCH DOOR raises: a `URLError`, deterministic, never retried.
MethodRefused = _tf.TermsFenced


def fenced_urlopen(req: Any, timeout: float | None = None,
                   context: ssl.SSLContext | None = None, *, live_input: bool = False,
                   access: HostAccess | None = None) -> Any:
    """THE ONE FETCH DOOR for the desk's urllib call sites: `terms_fence.guarded_urlopen`. A held
    source, a first URL that is a login wall, or a redirect into either raises `MethodRefused`;
    the redirect chain is kept on the response as `.redirects` [(code, from, to)]. A live-input
    organ passes `live_input=True`: an IDEAS_ONLY or held route is then refused on every hop.

    The same robots + hold checks as `get`: before the first request and every redirect hop the
    site's person-held hold and the hop's origin robots.txt are asked (`access`, default
    `default_access()`); a refusal raises `AccessRefused` (a `MethodRefused`) with nothing sent,
    and a 401/403/429 or challenge holds the refusing site until a person releases it."""
    return _tf.guarded_urlopen(req, timeout=timeout, context=context, live_input=live_input,
                               access=access)


#: The door's polite refusal (a `MethodRefused`): a person-held hold or robots.txt.
AccessRefused = _tf.AccessRefused


# --------------------------------------------------------------------------- decoding
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)


#: THE INFLATE CAP: a gzip/deflate body is never inflated past this many bytes, so a small
#: compressed answer (a decompression bomb, or just a huge dump) cannot exhaust the box's memory.
MAX_INFLATED = 20_000_000


def inflate(raw: bytes, content_encoding: str = "", cap: int = MAX_INFLATED) -> bytes:
    """Undo gzip/deflate, bounded to `cap` output bytes. Returns `raw` unchanged when it is not
    compressed or cannot be inflated. Never raises."""
    enc = (content_encoding or "").lower()
    try:
        if "gzip" in enc or raw[:2] == b"\x1f\x8b":
            return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, cap)
        if "deflate" in enc:
            try:
                return zlib.decompressobj().decompress(raw, cap)
            except zlib.error:
                return zlib.decompressobj(-zlib.MAX_WBITS).decompress(raw, cap)
    except Exception:
        pass
    return raw


def decode_body(raw: bytes, content_type: str = "", content_encoding: str = "") -> str:
    """Bytes -> text: undo gzip/deflate (bounded, `inflate`), then the header charset, then
    `<meta charset>`, then UTF-8. Never raises."""
    raw = inflate(raw, content_encoding)
    charset = ""
    if content_type:
        msg = Message()
        msg["content-type"] = content_type
        charset = str(msg.get_param("charset") or "")
    if not charset:
        m = _META_CHARSET.search(raw[:4096])
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    charset = (charset or "utf-8").strip().lower()
    if charset in ("gb2312", "gbk"):
        charset = "gb18030"                        # the superset: gb2312 pages routinely use it
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- the GET
@dataclass
class Response:
    url: str
    status: int | None = None
    text: str = ""
    final_url: str = ""
    content_type: str = ""
    error: str = ""
    elapsed_s: float = 0.0
    attempts: int = 0
    #: NEEDS_KEY / METHOD_BLOCKED / ROBOTS_DISALLOW / ROBOTS_UNREADABLE when the fetch was
    #: refused or held; '' otherwise. A refusal is a recorded answer, never routed around.
    verdict: str = ""
    #: The body as bytes (content-encoding undone, bounded): what a raw landing stores.
    body: bytes = b""
    #: Every redirect hop the fetch followed, [(code, from, to)] -- redirects are VISIBLE.
    redirects: list[tuple[int, str, str]] = field(default_factory=list)
    #: (platform, url) when THE METHOD FENCE refused the fetch (first URL or a hop); a seam
    #: re-raises it as `terms_fence.TermsFenced` so a urlopen-shaped caller keeps its fence path.
    fenced: tuple[str, str] | None = None
    #: The last response's headers, every one (an HTTP error's too), so a urlopen-shaped caller
    #: still sees Retry-After or a challenge marker on a refusal; {} when nothing was received.
    headers: dict[str, str] = field(default_factory=dict)
    #: An HTTP error's body (bounded), kept apart from `body` so no caller ever ingests it as
    #: content; the urlopen seam hands it back on its HTTPError, as urlopen does.
    error_body: bytes = b""

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 400 and not self.error


def _retry_after(headers: Any) -> float | None:
    try:
        v = headers.get("Retry-After") if headers is not None else None
        return min(MAX_RETRY_AFTER_S, float(v)) if v else None
    except (TypeError, ValueError):
        return None


def get(url: str, *, headers: Mapping[str, str] | None = None, timeout: float = 20.0,
        retries: int = 2, backoff_s: float = 1.5, deadline: float | None = None,
        max_bytes: int = MAX_BYTES, leg: str = "default", gate: HostGate | None = GATE,
        opener: Callable[..., Any] | None = None, access: HostAccess | None = None,
        sleep: Callable[[float], None] = time.sleep, live_input: bool = False,
        follow_redirects: bool = True) -> Response:
    """GET `url` once, politely, with bounded retries. NEVER RAISES: the Response carries the
    status or the error, so a caller can record what happened rather than a stack trace.

    Before every request -- `url` and each redirect hop -- `access.permits` checks the site's
    holds and the hop's own origin robots.txt (read through the same `opener`). A refusal
    returns with `verdict` set and nothing sent. 401/403/429 record a site hold and stop: no
    retry, no other route. The User-Agent sent is always honest (`honest_headers`).

    `follow_redirects=False` stops at the first 30x: the Response carries that status and the
    hop in `.redirects`, and the target is NOT requested -- for a caller that checks each hop
    against its own holds first (deep_forest `fetch_hops`).

    `timeout` is per attempt; `deadline` (a `time.monotonic()` value) caps the whole call,
    retries and backoff included, so no fetch can outlive the budget of the leg that made it.
    """
    resp = Response(url=url)
    # THE METHOD FENCE (libs/data/terms_fence.py; ruling of 2026-10-13, no source is banned): a
    # URL on a HELD source (METHOD_BLOCKED, or NEEDS_KEY until its key exists) is never requested.
    # The Response carries the named refusal, so the caller records it instead of a silent miss.
    _why = _tf.platform_of_url(url)
    if _why:
        resp.error = f"{_tf.PLATFORMS[_why]['status']}:{_why}: {_tf.PLATFORMS[_why]['reason']}"
        resp.fenced = (_why, url)
        _stat(leg, error=f"terms_fenced:{_why}")
        return resp
    hdr = honest_headers(headers)
    acc = access if access is not None else default_access()
    # THE REDIRECT GUARD: the default opener is the module's no-redirect door, itself built on
    # THE ONE FETCH DOOR's opener (`terms_fence.guarded_opener`): every request it sends is
    # terms-fenced, and each 30x surfaces as HTTPError so the loop below checks the hop's fence,
    # holds and robots BEFORE following it. A caller-supplied opener is the caller's own test.
    open_ = opener or open_no_redirect

    def _send(req: urllib.request.Request, t: float) -> Any:
        return open_(req, timeout=t, context=ssl_context())

    t0 = time.monotonic()
    cur = url
    hops = 0
    attempt = 0
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            resp.error = resp.error or "deadline"
            break
        # THE METHOD FENCE ON EVERY HOP, before robots and holds: a held source (or a discord
        # user-token request) or a login / CAPTCHA wall is refused and named, never requested.
        # `live_input=True` (an acquirer of live input) also refuses an IDEAS_ONLY or held route
        # on the first URL and on every hop (`terms_fence.input_source`).
        fenced = (_tf.fenced_request(cur, hdr) or ("login_wall" if _tf.login_wall(cur) else None)
                  or (_tf.input_source(cur) if live_input else None))
        if fenced:
            refusal = _tf.TermsFenced(fenced, cur)
            resp.status, resp.error = None, str(refusal.reason)[:240]
            resp.fenced = (fenced, cur)
            _stat(leg, error=(refusal.status if fenced == "login_wall"
                              else f"terms_fenced:{fenced}"))
            break
        allowed, why = acc.permits(cur, send=_send)
        if not allowed:
            resp.status, resp.error = None, why
            resp.verdict = why.split(" ")[0].split(":")[0]
            _stat(leg, refused=1, error=resp.verdict)
            break
        host = hostname_of(cur)
        if gate is not None and host:
            # Robots Crawl-delay widens the host's spacing, never narrows it.
            delay = acc.crawl_delay(cur, send=_send)
            w = gate.reserve(host, delay)
            if deadline is not None and time.monotonic() + w >= deadline:
                resp.error = f"deadline (crawl-delay {delay:g}s for {host})"
                break
            if w > 0:
                sleep(w)
        per_try = timeout
        if deadline is not None:
            per_try = max(1.0, min(timeout, deadline - time.monotonic()))
        resp.attempts = attempt + 1
        _stat(leg, fetches=1, retries=1 if attempt else 0)
        wait: float | None = None
        try:
            req = urllib.request.Request(ascii_url(cur), headers=hdr)
            with open_(req, timeout=per_try, context=ssl_context()) as fh:
                final = str(getattr(fh, "url", "") or cur)
                if final != cur and final != ascii_url(cur):
                    # An opener that followed a redirect itself: the target was not checked
                    # before it was read, so check it now and discard the body if refused.
                    ok2, why2 = acc.permits(final, send=_send)
                    if not ok2:
                        resp.status, resp.error = None, why2
                        resp.verdict = why2.split(" ")[0].split(":")[0]
                        _stat(leg, refused=1, error=resp.verdict)
                        break
                raw = fh.read(max_bytes)
                h = getattr(fh, "headers", None)
                ctype = str(h.get("Content-Type") or "") if h is not None else ""
                cenc = str(h.get("Content-Encoding") or "") if h is not None else ""
                status = int(getattr(fh, "status", None) or getattr(fh, "code", 200) or 200)
                text = decode_body(raw, ctype, cenc)
                marker = looks_challenged(text, h, status)
                if marker:
                    # A 200 challenge page is a block, not content: held, never ingested.
                    resp.status, resp.final_url = status, final
                    resp.verdict = acc.block(final, "WAF", "METHOD_BLOCKED",
                                             f"challenge page ({marker!r}) served as content")
                    resp.error = f"{resp.verdict}: challenge page ({marker})"
                    _stat(leg, refused=1, error="WAF")
                    break
                resp.status = status
                resp.final_url = final
                resp.content_type = ctype
                resp.headers = {str(k): str(v) for k, v in h.items()} if h is not None else {}
                resp.body = inflate(raw, cenc)
                resp.text = text
                # hops a caller-supplied opener followed itself, after the ones this loop took
                resp.redirects.extend(getattr(fh, "redirects", None) or [])
                resp.error = ""
                _stat(leg, ok=1, bytes=len(raw))
                break
        except MethodRefused as exc:
            # A held source or a 30x into one or into a login wall: refused, never followed,
            # and never retried -- the next attempt would be redirected to the same place.
            resp.error = str(exc.reason)[:240]
            resp.fenced = (exc.platform, exc.url)
            _stat(leg, error=(exc.status if exc.platform == "login_wall"
                              else f"terms_fenced:{exc.platform}"))
            break
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            # HTTPError also owns the response stream. Release it on every path rather than
            # leaving the socket to garbage collection.
            ebody = b""
            try:
                wait = _retry_after(getattr(exc, "headers", None))
                loc = exc.headers.get("Location") if exc.headers is not None else None
                if code not in REDIRECT_STATUS:
                    # a refusal's body too: a challenge page on a 403 is how a caller's own
                    # hard stop tells a WAF from a plain refusal (bounded; never ingested)
                    with contextlib.suppress(Exception):
                        ebody = exc.read(16000)
            finally:
                exc.close()
            if code in REDIRECT_STATUS:
                hops += 1
                if not loc:
                    resp.status, resp.error = code, f"HTTP {code} without Location"
                    _stat(leg, http_errors=1, error=f"HTTP {code}")
                    break
                if hops > MAX_REDIRECTS:
                    resp.status, resp.error = code, "too many redirects"
                    _stat(leg, http_errors=1, error="too many redirects")
                    break
                nxt = urljoin(cur, str(loc))
                resp.redirects.append((code, cur, nxt))    # redirects are VISIBLE
                if not follow_redirects:
                    resp.status, resp.final_url = code, cur
                    resp.error = f"HTTP {code}: redirect to {nxt[:160]} not followed"
                    break
                cur = nxt                          # the next pass checks THIS hop's fence + robots
                continue
            resp.status = code
            eh = getattr(exc, "headers", None)
            resp.headers = {str(k): str(v) for k, v in eh.items()} if eh is not None else {}
            resp.error_body = ebody
            _stat(leg, http_errors=1, error=f"HTTP {code}")
            if code in BLOCK_STATUS:
                resp.verdict = acc.block(cur, code)
                resp.error = f"{resp.verdict}: HTTP {code}"
                break                              # hard stop: no retry, no other route
            marker = looks_challenged(ebody, getattr(exc, "headers", None), code)
            if marker:
                # A challenge on an error status (Cloudflare's 503 interstitial, say) is a
                # refusal, not a "come back later": held like a 429, never retried (P4).
                resp.verdict = acc.block(cur, "WAF", "METHOD_BLOCKED",
                                         f"challenge ({marker!r}) on HTTP {code}")
                resp.error = f"{resp.verdict}: challenge on HTTP {code} ({marker})"
                _stat(leg, refused=1, error="WAF")
                break
            resp.error = f"HTTP {code}"
            if code not in RETRY_STATUS:
                break
            if gate is not None and host:
                gate.penalise(host, wait or backoff_s * (2 ** attempt))
        except Exception as exc:
            name = type(exc).__name__
            reason = getattr(exc, "reason", None)
            if reason is not None:
                name = f"{name}:{type(reason).__name__}"
            resp.error = f"{name}: {str(exc)[:160]}"
            _stat(leg, transport_errors=1, error=name)
            # A certificate the trust stores reject is deterministic; retrying cannot fix it.
            if isinstance(reason, ssl.SSLCertVerificationError) or isinstance(
                    exc, ssl.SSLCertVerificationError):
                break
        if attempt >= retries:
            break
        jitter = 1 + random.random() / 4                       # noqa: S311 - backoff jitter
        pause = wait if wait is not None else backoff_s * (2 ** attempt) * jitter
        if deadline is not None:
            pause = min(pause, max(0.0, deadline - time.monotonic()))
        if pause > 0:
            sleep(pause)
        attempt += 1
    resp.elapsed_s = time.monotonic() - t0
    _stat(leg, seconds=resp.elapsed_s)
    if resp.verdict:
        _note_held(leg, acc, resp.final_url or cur)
    return resp


class FetchRefused(RuntimeError):
    """A polite fetch that did not return content: a hold, a robots refusal, an HTTP error or a
    transport failure. `code` is the HTTP status when there was one (so a caller's own `code ==
    429` check still reads it) and `verdict` is NEEDS_KEY / METHOD_BLOCKED / ROBOTS_* or ''."""

    def __init__(self, url: str, status: int | None, verdict: str, error: str) -> None:
        super().__init__(f"{verdict or 'FETCH_FAILED'}: {error or status} ({url[:160]})")
        self.url = url
        self.code = status
        self.verdict = verdict
        self.error = error


def get_text(url: str, *, headers: Mapping[str, str] | None = None, timeout: float = 25.0,
             retries: int = 1, leg: str = "default", access: HostAccess | None = None,
             opener: Callable[..., Any] | None = None) -> str:
    """`get()` for callers written against `urlopen(...).read().decode()`: the body text, or
    `FetchRefused`. Same honest UA, robots check per hop and 401/403/429 site hold as `get()`."""
    r = get(url, headers=headers, timeout=timeout, retries=retries, leg=leg, access=access,
            opener=opener)
    if r.verdict or not r.ok:
        raise FetchRefused(url, r.status, r.verdict, r.error)
    return r.text


def post(url: str, data: bytes, *, headers: Mapping[str, str] | None = None,
         timeout: float = 20.0, leg: str = "default", access: HostAccess | None = None,
         opener: Callable[..., Any] | None = None) -> str:
    """`_post`, with a hold it met carried into `leg`'s stats (`access_holds`)."""
    acc = access if access is not None else default_access()
    try:
        return _post(url, data, headers=headers, timeout=timeout, leg=leg, access=acc,
                     opener=opener)
    except FetchRefused as exc:
        if exc.verdict:
            _note_held(leg, acc, url)
        raise


def _post(url: str, data: bytes, *, headers: Mapping[str, str] | None = None,
          timeout: float = 20.0, leg: str = "default", access: HostAccess | None = None,
          opener: Callable[..., Any] | None = None) -> str:
    """One POST (a GraphQL search, say), under the same rules as `get()`: honest UA, the site's
    holds and the origin's robots.txt checked first, redirects not followed, and 401/403/429 or a
    challenge record a hold and raise `FetchRefused`. Never retried: a POST is not idempotent."""
    acc = access if access is not None else default_access()
    open_ = opener or open_no_redirect

    def _send(req: urllib.request.Request, t: float) -> Any:
        return open_(req, timeout=t, context=ssl_context())

    ok, why = acc.permits(url, send=_send)
    if not ok:
        raise FetchRefused(url, None, why.split(" ")[0].split(":")[0], why)
    host = hostname_of(url)
    if GATE is not None and host:
        w = GATE.reserve(host, acc.crawl_delay(url, send=_send))
        if w > 0:
            time.sleep(w)
    req = urllib.request.Request(ascii_url(url), data=data, headers=honest_headers(headers),
                                 method="POST")
    try:
        with open_(req, timeout=timeout, context=ssl_context()) as fh:
            raw = fh.read(MAX_BYTES)
            h = getattr(fh, "headers", None)
            status = int(getattr(fh, "status", None) or 200)
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        ebody = b""
        with contextlib.suppress(Exception):
            ebody = exc.read(16000)
        with contextlib.suppress(Exception):
            exc.close()
        _stat(leg, fetches=1, http_errors=1, error=f"HTTP {code}")
        if code in BLOCK_STATUS:
            v = acc.block(url, code)
            raise FetchRefused(url, code, v, f"{v}: HTTP {code}") from None
        marker = looks_challenged(ebody, exc.headers, code)
        if marker:
            v = acc.block(url, "WAF", "METHOD_BLOCKED", f"challenge ({marker!r}) on HTTP {code}")
            raise FetchRefused(url, code, v, f"{v}: challenge on HTTP {code}") from None
        raise FetchRefused(url, code, "", f"HTTP {code}") from None
    ctype = str(h.get("Content-Type") or "") if h is not None else ""
    text = decode_body(raw, ctype, str(h.get("Content-Encoding") or "") if h is not None else "")
    marker = looks_challenged(text, h, status)
    if marker:
        v = acc.block(url, "WAF", "METHOD_BLOCKED", f"challenge ({marker!r}) served as content")
        _stat(leg, fetches=1, refused=1, error="WAF")
        raise FetchRefused(url, status, v, f"{v}: challenge page")
    _stat(leg, fetches=1, ok=1, bytes=len(raw))
    return text


# --------------------------------------------------------------------------- drop-in seams
# The desk's older fetchers were written against `urllib.request.urlopen` and `requests.get`.
# These two seams let such a caller keep its shape while every request goes through THIS module:
# honest UA, the site's holds, the origin's robots.txt (RobotsRules, via HostAccess) before any
# byte is sent, and 401/403/429 or a challenge recorded as a hold. `tests/data/
# test_no_raw_fetchers.py` fails CI on a raw urlopen/requests caller outside its audited list.

#: A query parameter whose value is a credential. A URL carrying one is never written into the
#: access record (a hold stores the URL): the hold is placed on the redacted URL instead.
_SECRET_PARAM = re.compile(r"(?i)(?:^|_|-)(?:api_?key|apikey|key|token|secret|signature|sig|"
                           r"password|passwd|access_token|app_?id|appkey)$")
#: The seams read like `urlopen` -- the whole body -- so their cap is far above `MAX_BYTES`;
#: a body longer than it is reported as an error, never silently truncated.
SEAM_MAX_BYTES = 128_000_000


def redact_url(url: str) -> str:
    """`url` with every credential-looking query value replaced by `REDACTED`."""
    from urllib.parse import parse_qsl, urlencode
    parts = urlsplit(url)
    if not parts.query:
        return url
    q = [(k, "REDACTED" if _SECRET_PARAM.search(k) else v)
         for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def carries_secret(url: str) -> bool:
    return redact_url(url) != url


def admit(url: str, *, access: HostAccess | None = None,
          opener: Callable[..., Any] | None = None) -> tuple[bool, str]:
    """(may fetch, why not): the method fence, then the site's holds and the origin's robots.txt
    (`HostAccess.permits`). For a caller that must send the request itself (a keyed API whose
    credential rides in the query); it reports a 401/403/429 back with `refuse_status`."""
    fenced = _tf.platform_of_url(url) or _tf.fenced_request(url, {}) or (
        "login_wall" if _tf.login_wall(url) else None)
    if fenced:
        return False, f"terms_fenced:{fenced}"
    acc = access if access is not None else default_access()
    open_ = opener or open_no_redirect

    def _send(req: urllib.request.Request, t: float) -> Any:
        return open_(req, timeout=t, context=ssl_context())

    return acc.permits(url, send=_send)


def refuse_status(url: str, status: int, *, access: HostAccess | None = None) -> str:
    """Record a 401/403/429 a caller received as the site's hold (on the redacted URL)."""
    acc = access if access is not None else default_access()
    return acc.block(redact_url(url), int(status))


class PoliteRefused(urllib.error.URLError):
    """A seam fetch that was refused before or without a status (a hold, robots, the method
    fence, a transport error). A `URLError`, so an `except URLError` / `except OSError` caller
    written for urlopen still catches it. `verdict` is the refusal's name or ''."""

    def __init__(self, url: str, verdict: str, error: str) -> None:
        super().__init__(f"{verdict or 'FETCH_FAILED'}: {error} ({redact_url(url)[:160]})")
        self.url, self.verdict, self.error = url, verdict, error


class SeamResponse:
    """What `polite_urlopen` returns: a file-like body (`read`, context manager) with `status`,
    `code`, `headers`, `url` and `geturl()`, like the object urlopen returns."""

    def __init__(self, url: str, status: int, body: bytes, content_type: str = "") -> None:
        import io
        self._buf = io.BytesIO(body)
        self.url = url
        self.status = self.code = status
        msg = Message()
        if content_type:
            msg["Content-Type"] = content_type
        self.headers = msg

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def readline(self, n: int = -1) -> bytes:
        return self._buf.readline(n)

    def __iter__(self) -> Any:
        return iter(self._buf)

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return self.status

    def info(self) -> Message:
        return self.headers

    def close(self) -> None:
        self._buf.close()

    def __enter__(self) -> SeamResponse:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _seam_http_error(url: str, status: int, error: str,
                     headers: Mapping[str, str] | None = None,
                     body: bytes = b"") -> urllib.error.HTTPError:
    """The HTTPError a urlopen-shaped caller expects: the response's own headers and (bounded)
    error body travel with it, exactly as urlopen's would, so Retry-After and a challenge page
    still reach the caller's hard stop."""
    msg = Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError(redact_url(url), status, error or f"HTTP {status}",
                                  msg, io.BytesIO(body))


def _keyed_open(url: str, hdr: dict[str, str], data: bytes | None, method: str | None,
                timeout: float, max_bytes: int, acc: HostAccess,
                opener: Callable[..., Any] | None, live_input: bool = False,
                leg: str = "seam") -> SeamResponse:
    """`_keyed_open_once`, with a hold it met carried into `leg`'s stats (`access_holds`)."""
    try:
        return _keyed_open_once(url, hdr, data, method, timeout, max_bytes, acc, opener,
                                live_input)
    except urllib.error.HTTPError as exc:
        if exc.code in BLOCK_STATUS:
            _note_held(leg, acc, url)
        raise
    except PoliteRefused as exc:
        if exc.verdict:
            _note_held(leg, acc, url)
        raise


def _keyed_open_once(url: str, hdr: dict[str, str], data: bytes | None, method: str | None,
                     timeout: float, max_bytes: int, acc: HostAccess,
                     opener: Callable[..., Any] | None, live_input: bool = False
                     ) -> SeamResponse:
    """A request whose URL carries a credential: admitted first (holds + robots), sent once
    through the module's no-redirect door (a 30x is returned as HTTPError, never followed), and
    a 401/403/429 held on the REDACTED url. `live_input` also refuses an IDEAS_ONLY route."""
    if live_input:
        src = _tf.input_source(url)
        if src:
            raise _tf.TermsFenced(src, redact_url(url))
    ok, why = admit(url, access=acc, opener=opener)
    if not ok and why.startswith("terms_fenced:"):
        raise _tf.TermsFenced(why.split(":", 1)[1], redact_url(url))
    if not ok:
        raise PoliteRefused(url, why.split(" ")[0].split(":")[0], why)
    open_ = opener or open_no_redirect
    host = hostname_of(url)
    if GATE is not None and host:
        w = GATE.reserve(host)
        if w > 0:
            time.sleep(w)
    req = urllib.request.Request(ascii_url(url), data=data, headers=hdr, method=method)
    try:
        with open_(req, timeout=timeout, context=ssl_context()) as fh:
            raw = fh.read(max_bytes + 1)
            h = getattr(fh, "headers", None)
            status = int(getattr(fh, "status", None) or getattr(fh, "code", 200) or 200)
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        with contextlib.suppress(Exception):
            exc.close()
        if code in BLOCK_STATUS:
            v = refuse_status(url, code, access=acc)
            raise _seam_http_error(url, code, f"{v}: HTTP {code}") from None
        raise _seam_http_error(url, code, f"HTTP {code}") from None
    if len(raw) > max_bytes:
        raise PoliteRefused(url, "", f"body longer than {max_bytes} bytes")
    ctype = str(h.get("Content-Type") or "") if h is not None else ""
    return SeamResponse(url, status, inflate(raw, str(h.get("Content-Encoding") or "")
                                             if h is not None else ""), ctype)


def polite_urlopen(req: urllib.request.Request | str, timeout: float = 30.0, *,
                   data: bytes | None = None, leg: str = "seam",
                   max_bytes: int = SEAM_MAX_BYTES, access: HostAccess | None = None,
                   opener: Callable[..., Any] | None = None, retries: int = 1,
                   live_input: bool = False, context: Any = None) -> SeamResponse:
    """`urllib.request.urlopen` for a desk fetcher, under this module's rules. Returns a
    `SeamResponse`; raises `urllib.error.HTTPError` for an HTTP status >= 400 (a 401/403/429
    has already been held) and `PoliteRefused` (a URLError) for a refusal -- robots, a hold, the
    method fence -- or a transport failure. Nothing is sent to a disallowed or held URL.
    `context` is accepted and ignored: TLS is always this module's verified `ssl_context()`."""
    del context
    if isinstance(req, urllib.request.Request):
        url = req.full_url
        hdrs = dict(req.header_items())
        body = req.data if data is None else data
        method = req.get_method()
    else:
        url, hdrs, body, method = str(req), {}, data, ("POST" if data is not None else "GET")
    if isinstance(body, str):
        body = body.encode("utf-8")
    if body is not None and not isinstance(body, bytes | bytearray):
        body = b"".join(body) if not hasattr(body, "read") else body.read()  # type: ignore[arg-type]
    payload: bytes | None = bytes(body) if body is not None else None
    body = payload
    acc = access if access is not None else default_access()
    hdr = honest_headers(hdrs)
    if carries_secret(url) or (method not in ("GET", "HEAD") and body is None):
        return _keyed_open(url, hdr, body, method, timeout, max_bytes, acc, opener, live_input,
                           leg=leg)
    if body is not None:
        if live_input and _tf.input_source(url):
            raise _tf.TermsFenced(str(_tf.input_source(url)), redact_url(url))
        try:
            text = post(url, body, headers=hdr, timeout=timeout, leg=leg, access=acc,
                        opener=opener)
        except FetchRefused as exc:
            if exc.code is not None:
                raise _seam_http_error(url, int(exc.code), exc.error) from None
            raise PoliteRefused(url, exc.verdict, exc.error) from None
        return SeamResponse(url, 200, text.encode("utf-8"), "text/plain; charset=utf-8")
    r = get(url, headers=hdr, timeout=timeout, retries=retries, leg=leg,
            max_bytes=max_bytes + 1, access=acc, opener=opener, live_input=live_input)
    if r.ok:
        if len(r.body) > max_bytes:
            raise PoliteRefused(url, "", f"body longer than {max_bytes} bytes")
        return SeamResponse(r.final_url or url, int(r.status or 200), r.body, r.content_type)
    if r.status is not None and (r.status >= 400 or r.status == 304):
        # urlopen raises for a 304 too; a conditional-GET caller reads it from the HTTPError
        raise _seam_http_error(url, int(r.status), r.error, r.headers, r.error_body)
    if r.fenced is not None:
        # the method fence's own refusal type, so a caller's `except TermsFenced` path still
        # names the held platform (it is a URLError too)
        raise _tf.TermsFenced(r.fenced[0], redact_url(r.fenced[1]))
    raise PoliteRefused(url, r.verdict, r.error or "fetch failed")


class SeamRequestsResponse:
    """What `polite_requests_get` returns: the parts of a `requests.Response` the desk's miners
    read. `status_code` is 0 when nothing was received (a refusal or a transport failure), and
    `raise_for_status()` raises `FetchRefused` for anything but a 2xx/3xx."""

    def __init__(self, url: str, status: int, content: bytes, text: str, content_type: str,
                 verdict: str = "", error: str = "") -> None:
        self.url = redact_url(url)               # a credential never rides on a response
        self.status_code = status
        self.content = content
        self.text = text
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.verdict = verdict
        self.error = error
        self.encoding = "utf-8"

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400 and not self.error

    def json(self) -> Any:
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if not self.ok:
            raise FetchRefused(self.url, self.status_code or None, self.verdict,
                               self.error or f"HTTP {self.status_code}")


def polite_requests_get(url: str, params: Mapping[str, Any] | None = None, *,
                        headers: Mapping[str, str] | None = None, timeout: float = 30.0,
                        leg: str = "seam", max_bytes: int = SEAM_MAX_BYTES,
                        access: HostAccess | None = None,
                        opener: Callable[..., Any] | None = None, retries: int = 1,
                        live_input: bool = False, **_ignored: Any) -> SeamRequestsResponse:
    """`requests.get` for a desk fetcher, under this module's rules. NEVER RAISES: a refusal or
    failure is a response with `status_code` 0 (or the HTTP status) and `verdict`/`error` set.
    `allow_redirects`, `verify`, `stream` and similar keywords are ignored: redirects are always
    followed hop by hop under robots and holds, and TLS is always verified."""
    if params:
        from urllib.parse import urlencode
        sep = "&" if urlsplit(url).query else "?"
        url = f"{url}{sep}{urlencode(dict(params), doseq=True)}"
    try:
        r = polite_urlopen(urllib.request.Request(url, headers=dict(headers or {})),
                           timeout=timeout, leg=leg, max_bytes=max_bytes, access=access,
                           opener=opener, retries=retries, live_input=live_input)
    except urllib.error.HTTPError as exc:
        return SeamRequestsResponse(url, int(exc.code), b"", "", "", "", str(exc.reason))
    except PoliteRefused as exc:
        return SeamRequestsResponse(url, 0, b"", "", "", exc.verdict, exc.error)
    except _tf.TermsFenced as exc:
        return SeamRequestsResponse(url, 0, b"", "", "", "terms_fenced", str(exc.reason))
    raw = r.read()
    ctype = str(r.headers.get("Content-Type") or "")
    return SeamRequestsResponse(r.url, r.status, raw, decode_body(raw, ctype), ctype)


class PoliteSession:
    """`requests.Session` for a desk fetcher: `headers` persist across calls and every `get` is
    `polite_requests_get` (holds and robots.txt first, honest UA). Nothing else of a Session --
    cookies, adapters, auth -- exists here, by design: a fetcher that needs a login is not one."""

    def __init__(self, leg: str = "seam") -> None:
        self.headers: dict[str, str] = {}
        self.leg = leg

    def get(self, url: str, params: Mapping[str, Any] | None = None, *,
            headers: Mapping[str, str] | None = None, timeout: float = 30.0,
            **kw: Any) -> SeamRequestsResponse:
        return polite_requests_get(url, params, headers={**self.headers, **dict(headers or {})},
                                   timeout=timeout, leg=self.leg, **kw)

    def close(self) -> None:
        return None


T = TypeVar("T")
R = TypeVar("R")


def run_concurrently(items: Iterable[T], fn: Callable[[T], R], *, workers: int = 8,
                     ) -> list[tuple[T, R | None, str]]:
    """Apply `fn` to every item on a thread pool; one item's exception costs the others
    nothing. Returns (item, result, error) in input order."""
    items = list(items)
    if not items:
        return []

    def _one(it: T) -> tuple[T, R | None, str]:
        try:
            return it, fn(it), ""
        except Exception as exc:
            return it, None, f"{type(exc).__name__}: {str(exc)[:160]}"

    if workers <= 1 or len(items) == 1:
        return [_one(it) for it in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items)),
                            thread_name_prefix="polite-fetch") as pool:
        return list(pool.map(_one, items))


def main(argv: list[str] | None = None) -> int:
    """`python -m libs.data.polite_fetch --release site:<site> --by <name>` (the same argument
    shape as `research/hard_stop.py`); `--list` prints the holds in force."""
    import argparse
    ap = argparse.ArgumentParser(description="the polite fetchers' person-held access holds")
    ap.add_argument("--release", metavar="KEY", help="site:<site> to release")
    ap.add_argument("--by", metavar="NAME", help="the person releasing it")
    ap.add_argument("--list", action="store_true", help="print the holds in force")
    args = ap.parse_args(argv)
    if args.release:
        if not args.by:
            ap.error("--release needs --by <name>")
        try:
            row = release(args.release, args.by)
        except ReleaseNotSaved as exc:
            print(str(exc))
            return 1
        print(f"released {row['key']} by {row['released_by']}")
        return 0
    acc = HostAccess.load(ACCESS_STATE)
    for site, row in sorted(acc.blocked.items()):
        if person_held(row):
            print(f"site:{site}\t{row.get('verdict')}\t{row.get('status')}\t{row.get('url')}")
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
