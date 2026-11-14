"""CFTC Public Reporting (Socrata) -- one verified, robots-gated door for every COT dataset.

The desk's three COT fetchers (`mt5desk/fetch_cot.py`, `fetch_cot_disagg.py`, `fetch_tff.py`)
were never scheduled because two of them read with TLS verification switched off
(`ssl.CERT_NONE`) and all three announced themselves as "Mozilla/5.0". The in-tree parquets
therefore end 2026-08-11, and every certified COT cell `flow_seeder` revives reads STALE.

This module is the replacement transport:

  * TLS VERIFIED. The default context, with certifi's bundle when it is installed. A
    certificate failure is a failure, never a retry without verification.
  * ROBOTS, FAIL CLOSED. publicreporting.cftc.gov/robots.txt is read once under the agent sent.
    It disallows /OData.svc/ and /api/odata/ and sets "Crawl-delay: 1"; the /resource/ paths this
    module reads are allowed, and requests are spaced by the crawl delay. An unreadable robots
    file, or one that disallows the path, refuses the fetch.
  * HONEST AGENT, no key, no login: the CFTC publishes these as US government open data.

Datasets (CFTC's own ids): legacy futures-only `6dca-aqww`, disaggregated futures-only
`72hh-3qpy`, Traders in Financial Futures futures-only `gpe5-46if`.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from typing import Any

HOST = "https://publicreporting.cftc.gov"
AGENT = "quant-desk-research/1.0 (CFTC open data; robots-respecting)"
LEGACY, DISAGG, TFF = "6dca-aqww", "72hh-3qpy", "gpe5-46if"
PAGE = 5000

Get = Callable[[str], bytes]


class Refused(RuntimeError):
    """The door would not send this request (robots, or an unreadable robots file)."""


def tls_context() -> ssl.SSLContext:
    """A VERIFYING context: certifi's bundle when installed, the system store otherwise."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class CrossHostRedirect(urllib.error.URLError):
    """A redirect off publicreporting.cftc.gov: refused, never followed."""


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a 3xx only on the requested host; another host's robots and terms were never read
    (Auditor MF1, 2026-11-13). A same-host hop is still put to the robots gate by `Client`."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old = urllib.parse.urlsplit(req.full_url).netloc.lower()
        new = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl)).netloc.lower()
        if new != old:
            raise CrossHostRedirect(f"redirect {old} -> {new} refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls_context()),
                                       _SameHostRedirects())


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with opener().open(req, timeout=90) as r:
        return bytes(r.read(50_000_000))


class Client:
    """Paged Socrata reads behind a robots gate and the host's crawl delay."""

    def __init__(self, get: Get = http_get, sleep: Callable[[float], None] = time.sleep) -> None:
        self._get = get
        self._sleep = sleep
        self._rules: urllib.robotparser.RobotFileParser | str | None = None
        self._last = 0.0
        self.requests = 0

    def _robots(self) -> urllib.robotparser.RobotFileParser | str:
        if self._rules is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                body = self._get(HOST + "/robots.txt").decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code in (404, 410):
                    rp.parse([])
                    self._rules = rp
                else:
                    self._rules = f"robots.txt unreadable (HTTP {e.code})"
                return self._rules
            except Exception as e:
                self._rules = f"robots.txt unreadable ({type(e).__name__})"
                return self._rules
            if body.lstrip()[:1] == "<":
                self._rules = "robots.txt unreadable (an HTML page)"
            else:
                rp.parse(body.splitlines())
                self._rules = rp
        return self._rules

    def delay(self) -> float:
        rules = self._robots()
        if isinstance(rules, str):
            return 1.0
        d = rules.crawl_delay(AGENT)
        return float(d) if d else 1.0

    def fetch(self, url: str) -> list[dict[str, Any]]:
        rules = self._robots()
        if isinstance(rules, str):
            raise Refused(rules)
        if not rules.can_fetch(AGENT, url):
            raise Refused("robots.txt disallows " + urllib.parse.urlsplit(url).path)
        wait = self.delay() - (time.monotonic() - self._last)
        if self._last and wait > 0:
            self._sleep(wait)
        self._last = time.monotonic()
        self.requests += 1
        doc = json.loads(self._get(url).decode("utf-8"))
        if not isinstance(doc, list):
            raise ValueError(f"Socrata returned {type(doc).__name__}, not rows")
        return [r for r in doc if isinstance(r, dict)]

    def rows(self, dataset: str, *, where: str, select: str,
             order: str = "report_date_as_yyyy_mm_dd") -> list[dict[str, Any]]:
        """Every row matching `where`, paged."""
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            q = urllib.parse.urlencode({"$where": where, "$select": select, "$order": order,
                                        "$limit": str(PAGE), "$offset": str(offset)})
            batch = self.fetch(f"{HOST}/resource/{dataset}.json?{q}")
            out.extend(batch)
            if len(batch) < PAGE:
                return out
            offset += PAGE


def quote(value: str) -> str:
    """A SoQL string literal."""
    return "'" + value.replace("'", "''") + "'"
