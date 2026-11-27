"""ONION TRANSPORT -- .onion hosts only, through a local Tor SOCKS5 port, allowlist only.

THE RULING (governance/tor-proxy-ruling-2026-11-17.md; zuck 20:31Z "tor is legal", "remove our no
proxy rule"). Tor may be used for LEGITIMATE access. It is never used to get past something a site
put in our way, and this module is where that line is drawn in code:

1. **TOR CARRIES .onion HOSTS ONLY.** `require_onion` refuses every URL whose host is not a v3
   onion address -- before any socket is opened, robots.txt included. A clearnet host fetched over
   Tor would reach it from a rotating exit address, which is block evasion by construction, so
   there is no flag that turns this off.
2. **ALLOWLIST ONLY, NO CRAWLING.** `OnionFetcher` fetches a URL only when a reviewed roster row
   names it exactly (a feed or page URL), or, for an attachment, when it sits on a fetchable row's
   own onion host and passes `attachment_allowed`. Links are never followed and redirects are not
   either (a 3xx is recorded, never chased).
3. **A ROW MUST BE FETCHABLE.** Address VERIFIED from the publisher's own clearnet page and terms
   ALLOWED -- the mirror inherits its publisher's terms (`onion_forest.effective_verdict`). Any
   other row is refused here with its verdict, whatever the caller asks.
4. **ROBOTS, FAIL CLOSED; HARD STOPS.** The onion host's own robots.txt is read (through Tor, it
   is the same host) once per process; unreadable means refused, 404/410 means no rules. A
   401/403/429/451 stops that host for the rest of the process -- never retried, never re-routed.
5. **POLITE AND HONEST.** One request per `MIN_INTERVAL_S` per host, a generic UA that names what
   is reading, no cookies, no login, no form, a byte cap.

TOR AND SOCKS ARE NORMAL ABSENCES. `tor_status()` probes the configured port (env
`QUANT_TOR_SOCKS=host:port`, else 127.0.0.1:9050 then 127.0.0.1:9150) with a real SOCKS5
greeting, and checks that a SOCKS client library (PySocks, which `requests[socks]` uses) is
importable. Either missing is TOR_ABSENT or SOCKS_ABSENT with a missed_growth line -- a state the
report carries, never a crash. Nothing is installed from here.
"""
from __future__ import annotations

import contextlib
import importlib.util
import os
import re
import socket
import threading
import time
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from libs.data.robots_body import robots_rules_or_refusal

__all__ = [
    "ATTACHMENT_MAX_BYTES", "DEFAULT_PORTS", "HARD_STOP", "MIN_INTERVAL_S", "ROBOTS_AGENT",
    "SOCKS_ABSENT", "TOR_ABSENT", "TOR_PRESENT", "UA", "FetchResult", "OnionFetcher",
    "OnionRefused", "attachment_allowed", "onion_host", "require_onion", "socks_support",
    "tor_status",
]

TOR_PRESENT = "TOR_PRESENT"
TOR_ABSENT = "TOR_ABSENT"
SOCKS_ABSENT = "SOCKS_ABSENT"
DEFAULT_PORTS: tuple[tuple[str, int], ...] = (("127.0.0.1", 9050), ("127.0.0.1", 9150))
ROBOTS_AGENT = "quant-desk-research"
UA = f"{ROBOTS_AGENT}/1.0 (onion_forest; public text claims; honours robots.txt)"
MIN_INTERVAL_S = 10.0
MAX_BYTES = 2_000_000
TIMEOUT_S = 60.0
HARD_STOP: frozenset[int] = frozenset({401, 403, 429, 451})
#: Attachments: small text, CSV or PDF only. No executables, no archives, no office macros.
ATTACHMENT_MAX_BYTES = 3_000_000
ATTACHMENT_TYPES: frozenset[str] = frozenset({"text/plain", "text/csv", "application/pdf"})
ATTACHMENT_EXTS: frozenset[str] = frozenset({".txt", ".csv", ".pdf"})

MISSED_TOR = ("missed_growth: the onion lane reads nothing while no Tor SOCKS port answers on this "
              "box; every allowlisted mirror's claims stay UNMEASURED until Tor runs as a "
              "service (desks/mt5/scripts/install_tor_service.ps1). A gap, not a zero.")
MISSED_SOCKS = ("missed_growth: Tor may be up but no SOCKS client library (PySocks / "
                "requests[socks]) is importable, so no onion request can be made; the lane's "
                "claims stay UNMEASURED until it is installed on the box. A gap, not a zero.")

_V3 = re.compile(r"^(?:[a-z0-9-]+\.)*[a-z2-7]{56}\.onion$")


class OnionRefused(ValueError):
    """The request is not allowed; no socket was opened."""


def onion_host(url: str) -> str | None:
    """The host of `url` when it is a v3 .onion host over http(s), else None."""
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or parts.username or parts.password:
        return None
    host = (parts.hostname or "").lower()
    return host if _V3.match(host) else None


def require_onion(url: str) -> str:
    """The onion host, or OnionRefused. Clearnet over Tor is block evasion: refused, always."""
    host = onion_host(url)
    if host is None:
        raise OnionRefused(f"CLEARNET_REFUSED: {str(url)[:120]!r} is not a v3 .onion URL; Tor "
                           f"carries .onion hosts only (tor-proxy ruling 2026-11-17, line 1)")
    return host


def socks_support(find: Callable[[str], Any] = importlib.util.find_spec) -> tuple[bool, str]:
    """(importable, why). PySocks is the module `requests[socks]` needs for socks5h://."""
    try:
        ok = find("socks") is not None
    except (ImportError, ValueError):
        ok = False
    return ok, ("PySocks importable" if ok else
                f"{SOCKS_ABSENT}: no 'socks' module (PySocks / requests[socks]) is importable")


def _configured_ports(env: Mapping[str, str]) -> list[tuple[str, int]]:
    raw = str(env.get("QUANT_TOR_SOCKS") or "").strip()
    if raw:
        host, _, port = raw.rpartition(":")
        try:
            return [(host or "127.0.0.1", int(port))]
        except ValueError:
            pass
    return list(DEFAULT_PORTS)


def _greets(host: str, port: int, connect: Callable[..., Any], timeout: float) -> bool:
    """A SOCKS5 no-auth greeting answered with 05 00: a SOCKS server is listening, not just
    something on the port."""
    try:
        sock = connect((host, port), timeout=timeout)
    except OSError:
        return False
    try:
        sock.sendall(b"\x05\x01\x00")
        return bytes(sock.recv(2)) == b"\x05\x00"
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            sock.close()


def tor_status(*, env: Mapping[str, str] | None = None,
               connect: Callable[..., Any] = socket.create_connection,
               find: Callable[[str], Any] = importlib.util.find_spec,
               timeout: float = 3.0) -> dict[str, Any]:
    """{status, proxy, tried, socks_lib, why, missed_growth?}. Never raises."""
    ports = _configured_ports(os.environ if env is None else env)
    tried = [f"{h}:{p}" for h, p in ports]
    found = next(((h, p) for h, p in ports if _greets(h, p, connect, timeout)), None)
    lib_ok, lib_why = socks_support(find)
    if found is None:
        return {"status": TOR_ABSENT, "proxy": None, "tried": tried, "socks_lib": lib_ok,
                "why": f"{TOR_ABSENT}: no SOCKS5 server answered on {', '.join(tried)}",
                "missed_growth": MISSED_TOR}
    proxy = f"socks5h://{found[0]}:{found[1]}"
    if not lib_ok:
        return {"status": SOCKS_ABSENT, "proxy": proxy, "tried": tried, "socks_lib": False,
                "why": lib_why, "missed_growth": MISSED_SOCKS}
    return {"status": TOR_PRESENT, "proxy": proxy, "tried": tried, "socks_lib": True,
            "why": f"SOCKS5 answered at {found[0]}:{found[1]}; {lib_why}"}


def attachment_allowed(url: str, content_type: str = "", size: int | None = None) -> str | None:
    """None when an attachment may be read, else the reason. Text, CSV or PDF only, size-capped;
    an unknown size is refused (no archive or binary is ever opened to find out)."""
    path = urlsplit(str(url or "")).path.lower()
    ext = path[path.rfind("."):] if "." in path.rsplit("/", 1)[-1] else ""
    ctype = str(content_type or "").split(";")[0].strip().lower()
    if ext not in ATTACHMENT_EXTS and ctype not in ATTACHMENT_TYPES:
        return f"ATTACHMENT_TYPE_REFUSED: {ext or ctype or 'unknown type'} (text, CSV or PDF only)"
    if ctype and ctype not in ATTACHMENT_TYPES:
        return f"ATTACHMENT_TYPE_REFUSED: {ctype}"
    if size is None:
        return "ATTACHMENT_SIZE_UNKNOWN: refused rather than opened to measure"
    if size > ATTACHMENT_MAX_BYTES:
        return f"ATTACHMENT_TOO_LARGE: {size} bytes > {ATTACHMENT_MAX_BYTES}"
    return None


@dataclass
class FetchResult:
    url: str
    status: int | None = None
    body: bytes = b""
    content_type: str = ""
    verdict: str = "OK"
    why: str = ""

    @property
    def ok(self) -> bool:
        return self.verdict == "OK" and self.status is not None and 200 <= self.status < 300

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


#: transport(url, headers, timeout, proxy) -> (status, content_type, body). Injected in tests.
Transport = Callable[[str, Mapping[str, str], float, str], tuple[int, str, bytes]]


def _requests_transport(url: str, headers: Mapping[str, str], timeout: float,
                        proxy: str) -> tuple[int, str, bytes]:
    import requests  # imported only when Tor is present
    with requests.get(url, headers=dict(headers), timeout=timeout, stream=True,
                      allow_redirects=False, proxies={"http": proxy, "https": proxy}) as r:
        body = r.raw.read(MAX_BYTES + 1, decode_content=True) or b""
        return int(r.status_code), str(r.headers.get("Content-Type") or ""), bytes(body)


@dataclass
class OnionFetcher:
    """Every onion request the desk makes goes through one of these."""

    rows: Iterable[Mapping[str, Any]]
    status: Mapping[str, Any]
    is_fetchable: Callable[[Mapping[str, Any]], bool]
    transport: Transport | None = None
    min_interval_s: float = MIN_INTERVAL_S
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._rows = [dict(r) for r in self.rows]
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | str] = {}
        self._stopped: dict[str, str] = {}

    # ------------------------------------------------------------------ allowlist
    def row_for(self, url: str, *, attachment: bool = False) -> Mapping[str, Any] | None:
        host = onion_host(url)
        for r in self._rows:
            if not attachment and url in (r.get("feed_urls") or []):
                return r
            if (attachment and host and r.get("attachments")
                    and host == str(r.get("onion_host") or "").lower()):
                return r
        return None

    def _refuse(self, url: str, verdict: str, why: str) -> FetchResult:
        res = FetchResult(url=url, verdict=verdict, why=why)
        self.log.append({"url": url, "verdict": verdict, "why": why[:200]})
        return res

    # ------------------------------------------------------------------ the one door
    def fetch(self, url: str, *, attachment: bool = False, content_type: str = "",
              size: int | None = None) -> FetchResult:
        try:
            host = require_onion(url)
        except OnionRefused as exc:
            return self._refuse(url, "CLEARNET_REFUSED", str(exc))
        row = self.row_for(url, attachment=attachment)
        if row is None:
            return self._refuse(url, "NOT_ALLOWLISTED",
                                "no reviewed roster row names this URL; nothing is crawled")
        if not self.is_fetchable(row):
            return self._refuse(url, "ROW_NOT_FETCHABLE",
                                f"roster row {row.get('id')!r} is not VERIFIED + ALLOWED")
        if attachment:
            why = attachment_allowed(url, content_type, size)
            if why:
                return self._refuse(url, "ATTACHMENT_REFUSED", why)
        st = str(self.status.get("status") or TOR_ABSENT)
        if st != TOR_PRESENT:
            return self._refuse(url, st, str(self.status.get("why") or st))
        if host in self._stopped:
            return self._refuse(url, "HARD_STOP", self._stopped[host])
        robots_why = self._robots_refusal(url, host)
        if robots_why:
            return self._refuse(url, "ROBOTS_REFUSED", robots_why)
        return self._get(url, host)

    def _get(self, url: str, host: str) -> FetchResult:
        require_onion(url)                                # belt and braces: every socket
        with self._lock:
            wait = self._last.get(host, -1e18) + self.min_interval_s - self.clock()
        if wait > 0:
            self.sleep(wait)
        with self._lock:
            self._last[host] = self.clock()
        transport = self.transport or _requests_transport
        try:
            code, ctype, body = transport(url, {"User-Agent": UA, "Accept": "*/*"}, TIMEOUT_S,
                                          str(self.status.get("proxy") or ""))
        except Exception as exc:                          # transport failures are results
            return self._refuse(url, "TRANSPORT_ERROR", f"{type(exc).__name__}: {str(exc)[:160]}")
        if code in HARD_STOP:
            self._stopped[host] = f"HTTP {code}: hard stop for this host (never retried)"
            return FetchResult(url=url, status=code, verdict="HARD_STOP",
                               why=self._stopped[host])
        if 300 <= code < 400:
            return FetchResult(url=url, status=code, verdict="REDIRECT_NOT_FOLLOWED",
                               why="redirects are never followed")
        if len(body) > MAX_BYTES:
            return FetchResult(url=url, status=code, verdict="TOO_LARGE",
                               why=f"body over {MAX_BYTES} bytes")
        res = FetchResult(url=url, status=code, body=body, content_type=ctype,
                          verdict="OK" if 200 <= code < 300 else f"HTTP_{code}")
        self.log.append({"url": url, "verdict": res.verdict, "status": code, "bytes": len(body)})
        return res

    def _robots_refusal(self, url: str, host: str) -> str | None:
        rp = self._robots.get(host)
        if rp is None:
            scheme = urlsplit(url).scheme
            got = self._get(f"{scheme}://{host}/robots.txt", host)
            if got.status is None or (300 <= got.status < 400):
                # Never reached, or a redirect we do not follow: unread, so fail closed.
                rp = f"robots.txt unreadable ({got.verdict} {got.status}): fail closed"
            else:
                # The shared reader: 404/410 = no rules, an HTML body or a hard-stop status is a
                # refusal, so an onion host's robots.txt is judged exactly as a clearnet one is.
                read = robots_rules_or_refusal(got.status, got.content_type or None, got.body)
                rp = f"{read}: fail closed" if isinstance(read, str) else read
            self._robots[host] = rp
        if isinstance(rp, str):
            return rp
        return None if rp.can_fetch(ROBOTS_AGENT, url) else "robots.txt disallows this path"
