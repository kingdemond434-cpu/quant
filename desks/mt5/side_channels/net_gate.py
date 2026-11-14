"""ONE NETWORK DOOR FOR EVERY SIDE-CHANNEL MINER (Hourly pass ask, 2026-11-13).

`run_all_miners` runs each miner in its own spawned process and calls `install()` there first.
That process then cannot send a request that skips the two checks below:

  1. TERMS. A host on `REFUSED_HOSTS` is never contacted. The value says why (the ruling or the
     terms clause). This is the code copy of each channel's terms verdict, so a miner that keeps
     a refused URL in its source cannot fetch it.
  2. ROBOTS, FAIL CLOSED. robots.txt is read once per host under the agent actually sent. A 404
     or 410 allows; a 401 or 403 disallows everything; any other failure refuses. A Disallow on
     the exact path refuses. The robots read is the one request this door cannot gate.

The door also sends an HONEST User-Agent. A browser-impersonating header (several miners shipped
"Mozilla/5.0 ... Chrome") is replaced by `AGENT`. A declared contact agent (SEC fair access,
`QUANT_EDGAR_UA`) is kept as sent.

A refused request raises `Refused`. Under `requests` it subclasses `RequestException`, so a
miner's ordinary `except` catches it and the refusal reaches the log by name.
Every decision is counted in `LEDGER`, and `run_all_miners` writes it next to the discoveries.
"""
from __future__ import annotations

import ssl
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter
from typing import Any

AGENT = "quant-desk-research/1.0 (side-channel miners; robots-respecting)"

#: host suffix -> why it is never contacted. A suffix matches the host and its subdomains.
REFUSED_HOSTS: dict[str, str] = {
    "stlouisfed.org": "FRED/ALFRED terms refuse automated use (governance ruling 2026-11-13)",
    "youtube.com": "hard rule: the box never contacts YouTube (2026-11-13)",
    "googleapis.com": "hard rule: no YouTube Data API key and no YouTube contact",
    "reddit.com": "Reddit Data API terms: commercial use needs a separate agreement",
    "tradingview.com": "TradingView terms forbid scraping and automated collection",
    "forexfactory.com": "Forex Factory terms forbid automated collection",
    "faireconomy.media": "Forex Factory calendar feed: same owner and terms as forexfactory.com",
    "investing.com": "Investing.com terms forbid scraping",
    "dataviz.cnn.io": "CNN terms forbid automated collection of site content",
    "finance.yahoo.com": "Yahoo terms forbid automated access to Yahoo Finance",
    "aaii.com": "AAII survey is member content; terms forbid redistribution and automation",
    "trends.google.com": "Google terms forbid automated queries to Trends without an API",
    "ssrn.com": "SSRN terms forbid automated downloading",
    "tradingeconomics.com": "Trading Economics data is licensed; free site terms forbid scraping",
    "zhihu.com": "off-limits (Zhihu terms forbid crawling; #1091)",
    "eastmoney.com": "off-limits (Eastmoney terms; #1091)",
    "naver.com": "Naver terms forbid automated collection",
    "open-meteo.com": "Open-Meteo free API is licensed for non-commercial use only",
}

LEDGER: Counter[str] = Counter()
#: Robots rules per host, read ONCE per process under the first agent that reaches the host;
#: `can_fetch` is then asked with the agent each request actually sends.
_ROBOTS: dict[str, urllib.robotparser.RobotFileParser | str] = {}
#: Redirect hops a requests call may follow, each one re-checked at the door.
MAX_HOPS = 5


def _base_exc() -> type[Exception]:
    try:
        import requests
        return requests.exceptions.RequestException
    except Exception:  # requests absent: a plain OSError is what urllib callers catch
        return OSError


class Refused(_base_exc()):  # type: ignore[misc]
    """A request the door would not send."""


def terms_refusal(url: str) -> str | None:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    for suffix, why in REFUSED_HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return why
    return None


def honest_agent(agent: str | None) -> str:
    """The agent to send: a declared contact is kept; a browser impersonation never is."""
    a = (agent or "").strip()
    if not a or a.lower().startswith("mozilla") or "python-requests" in a.lower():
        return AGENT
    return a


def _robots(scheme: str, netloc: str, agent: str) -> urllib.robotparser.RobotFileParser | str:
    key = f"{scheme}://{netloc}"
    if key in _ROBOTS:
        return _ROBOTS[key]
    rp = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(f"{key}/robots.txt", headers={"User-Agent": agent})
    out: urllib.robotparser.RobotFileParser | str
    try:
        with _ORIGINAL_URLOPEN(req, timeout=15) as r:
            body = r.read(500_000).decode("utf-8", errors="replace")
        if body.lstrip()[:1] == "<":
            out = "robots.txt unreadable (an HTML page, not a robots file)"
        else:
            rp.parse(body.splitlines())
            out = rp
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            rp.parse([])
            out = rp
        elif e.code in (401, 403):
            rp.parse(["User-agent: *", "Disallow: /"])
            out = rp
        else:
            out = f"robots.txt unreadable (HTTP {e.code})"
    except Exception as e:
        out = f"robots.txt unreadable ({type(e).__name__})"
    _ROBOTS[key] = out
    return out


def refusal(url: str, agent: str = AGENT) -> str | None:
    """None when the door would send this request, else why not."""
    why = terms_refusal(url)
    if why:
        LEDGER["refused_terms"] += 1
        return f"BLOCKED_TERMS: {why}"
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    if parts.path == "/robots.txt":
        return None
    rules = _robots(parts.scheme, parts.netloc, agent)
    if isinstance(rules, str):
        LEDGER["refused_robots_unreadable"] += 1
        return f"ROBOTS_REFUSED: {rules}"
    if not rules.can_fetch(agent, url):
        LEDGER["refused_robots_disallow"] += 1
        return "ROBOTS_REFUSED: robots.txt disallows this path"
    LEDGER["allowed"] += 1
    return None


class _GatedRedirects(urllib.request.HTTPRedirectHandler):
    """urllib follows 3xx inside its opener, past any wrapper round `urlopen`. Every hop is put
    to the door here: a refused host or a robots refusal stops the fetch (Auditor MF1)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = urllib.parse.urljoin(req.full_url, newurl)
        agent = honest_agent(req.get_header("User-agent"))
        why = refusal(target, agent)
        if why:
            LEDGER["refused_redirect"] += 1
            raise Refused(f"redirect refused: {why} ({target[:120]})")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GatedRedirects())


def _ORIGINAL_URLOPEN(url: Any, *a: Any, **k: Any) -> Any:
    """The door's own transport: the stock opener with every redirect hop gated. A caller's own
    TLS context is honoured when it verifies (a private CA bundle, say); one that switches
    verification off is dropped, and the default verifying context is used instead."""
    ctx = k.pop("context", None)
    if ctx is not None and getattr(ctx, "verify_mode", None) != ssl.CERT_NONE:
        op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                         _GatedRedirects())
        return op.open(url, *a, **k)
    return _OPENER.open(url, *a, **k)


#: Headers that carry a credential. requests' own redirect handling (`rebuild_auth`) strips
#: Authorization when the host changes; the door's hop loop must do the same, or a miner's token
#: would be sent to whatever allowed host a redirect names (Auditor MF2).
_SECRET_HEADERS = {"authorization", "proxy-authorization", "cookie"}


def strip_credentials(headers: dict[str, Any]) -> dict[str, Any]:
    """`headers` without any credential-bearing header, for a hop onto another host."""
    return {h: v for h, v in headers.items()
            if str(h).lower() not in _SECRET_HEADERS
            and "key" not in str(h).lower() and "token" not in str(h).lower()}


def _header(headers: Any, name: str) -> str | None:
    for k, v in dict(headers or {}).items():
        if str(k).lower() == name.lower():
            return str(v)
    return None


def install() -> None:
    """Route this process's `requests` and `urllib` traffic through the door. Idempotent."""
    if getattr(urllib.request.urlopen, "_net_gate", False):
        return

    def urlopen(url: Any, *a: Any, **k: Any) -> Any:
        if isinstance(url, urllib.request.Request):
            agent = honest_agent(url.get_header("User-agent"))
            url.remove_header("User-agent")
            url.add_header("User-Agent", agent)
            target = url.full_url
        else:
            agent = AGENT
            target = str(url)
            url = urllib.request.Request(target, headers={"User-Agent": agent})
        why = refusal(target, agent)
        if why:
            raise Refused(f"{why} ({target[:120]})")
        return _ORIGINAL_URLOPEN(url, *a, **k)

    urlopen._net_gate = True  # type: ignore[attr-defined]
    urllib.request.urlopen = urlopen  # type: ignore[assignment]

    try:
        import requests
    except Exception:
        return
    original = requests.Session.request

    def request(self: Any, method: str, url: str, *a: Any, **k: Any) -> Any:
        headers = dict(k.pop("headers", None) or {})
        agent = honest_agent(_header(headers, "User-Agent") or self.headers.get("User-Agent"))
        headers = {h: v for h, v in headers.items() if str(h).lower() != "user-agent"}
        headers["User-Agent"] = agent
        follow = k.pop("allow_redirects", True)
        why = refusal(url, agent)
        if why:
            raise Refused(f"{why} ({str(url)[:120]})")
        # requests follows 3xx inside Session.send, past this wrapper, so redirects are turned
        # off and every hop is taken here, through the door (Auditor MF1).
        resp = original(self, method, url, *a, headers=headers, allow_redirects=False, **k)
        hops = 0
        while follow and resp.is_redirect and hops < MAX_HOPS:
            target = urllib.parse.urljoin(resp.url or url, resp.headers.get("location", ""))
            why = refusal(target, agent)
            if why:
                LEDGER["refused_redirect"] += 1
                raise Refused(f"redirect refused: {why} ({target[:120]})")
            if urllib.parse.urlsplit(target).netloc.lower() != \
                    urllib.parse.urlsplit(str(resp.url or url)).netloc.lower():
                headers = strip_credentials(headers)
                # A None value is how requests drops a SESSION-level header for one call, so a
                # session's own token is withheld from this hop without changing the session.
                for h in list(self.headers):
                    if strip_credentials({h: 1}) == {}:
                        headers[h] = None
                k.pop("auth", None)
                k.pop("cookies", None)
            if resp.status_code in (301, 302, 303) and method.upper() != "HEAD":
                method = "GET"
                k.pop("data", None)
                k.pop("json", None)
            resp = original(self, method, target, *a, headers=headers, allow_redirects=False,
                            **k)
            hops += 1
        return resp

    requests.Session.request = request  # type: ignore[method-assign]
