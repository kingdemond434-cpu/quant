"""DATA RAILS FOR THE BOX'S OWN MINER CLOCK (2026-10-29, PR #524 audit finding 3).

The miners were written for the VPS and send a browser User-Agent (`seed_miners.HEADERS`,
`libs.data.polite_fetch.BROWSER_UA`, and each external miner's own header). A browser UA defeats
every robots.txt group that names an agent -- forexpeacearmy refused ClaudeBot in writing and was
still being fetched under a Chrome string. `vps_seat_clock` widens those fetches onto the box's
own IP, so on THAT path every HTTP request in the process (and in the miner children
`run_all_miners` spawns) goes through these rails, whatever the miner's own code says:

1. AN HONEST USER-AGENT. Every request is re-stamped `USER_AGENT`: the project's research
   crawler, with the public repository as its contact. No email, no browser string.
2. ROBOTS.TXT ON EVERY SOURCE, not only where a wall entry names it. A URL is fetched only when
   the host's robots.txt allows it for EVERY token in `ROBOTS_TOKENS` -- the `*` group, this
   crawler's own token, and ClaudeBot (the agent these sessions run as; a site that refused it
   has refused this work). robots.txt is read with the honest UA. 401/403 on robots.txt =
   disallow all; any other 4xx = no policy (allowed, RFC 9309); 5xx, a timeout or a transport
   error = UNREACHABLE, which is not consent, so the host is refused for this process.
3. NO HOST WALLED ON THE VPS. A host named in `seed_miners.SOURCE_WALLS` is never contacted from
   the box at all -- not its content and not its robots.txt. Its rediscovery probe stays on the
   VPS clock that owns the wall.

A refusal raises `RailRefusal` (a requests ConnectionError for requests callers, a URLError for
urllib callers), which every miner already books as a fetch_error row -- so a refusal is a
recorded fact on disk, never a silent skip and never a retry. Redirects are checked hop by hop;
robots.txt's own redirects are followed by hand (at most ROBOTS_MAX_HOPS, RFC 9309), each hop
wall-checked, never through the patched opener.

Installed only by `vps_seat_clock.py` child processes (env `QUANT_BOX_RAILS=1`); the VPS's own
timers run the miners exactly as before.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import urllib.robotparser
from typing import Any
from urllib.parse import urlsplit

ENV = "QUANT_BOX_RAILS"
#: When set, every refusal in this process AND in every child that inherits the environment (the
#: miner processes `run_all_miners` spawns) is appended here as one JSON line, so the unit's
#: report names the children's refusals too, not only its own process's.
LOG_ENV = "QUANT_BOX_RAILS_LOG"
REPO_URL = "https://github.com/kingdemond434-cpu/quant"
AGENT_TOKEN = "QuantResearchCrawler"  # noqa: S105 - a robots.txt agent token, not a secret
USER_AGENT = f"{AGENT_TOKEN}/1.0 (+{REPO_URL})"
#: Every robots.txt group a URL must be allowed by. All of them, not the first that matches.
ROBOTS_TOKENS: tuple[str, ...] = ("*", AGENT_TOKEN, "ClaudeBot")
ROBOTS_TIMEOUT_S = 15.0

_LOCK = threading.Lock()
_INSTALL_LOCK = threading.Lock()
_ROBOTS: dict[str, tuple[urllib.robotparser.RobotFileParser | None, str]] = {}
_STATE: dict[str, Any] = {"installed": False, "walled": frozenset(), "orig": {},
                          "refused": []}


class RailRefusal(OSError):
    """The rails refused a URL. `reason` names why (walled / robots / unreachable)."""


def _norm(host: str) -> str:
    host = (host or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def walled_hosts() -> frozenset[str]:
    """Every host `seed_miners.SOURCE_WALLS` walls on the VPS, normalised (no `www.`)."""
    import seed_miners
    out = set()
    for w in seed_miners.SOURCE_WALLS.values():
        for key in ("host", "url"):
            v = str((w or {}).get(key) or "")
            h = urlsplit(v).hostname if "://" in v else v
            if h:
                out.add(_norm(h))
    return frozenset(out)


def host_walled(host: str, walled: frozenset[str] | None = None) -> bool:
    h = _norm(host)
    ws = _STATE["walled"] if walled is None else walled
    return any(h == w or h.endswith("." + w) for w in ws)


#: RFC 9309 2.3.1.2: follow at least five consecutive redirects for robots.txt. Past that, or a
#: redirect onto a walled host, the policy is UNREACHABLE (not consent) -- never a recursion.
ROBOTS_MAX_HOPS = 5
_GUARD = threading.local()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface every 3xx as an HTTPError so robots.txt hops are followed (and checked) by hand.

    The stock handler re-enters `OpenerDirector.open` -- the PATCHED open -- for each hop, and a
    robots.txt that redirects to a non-robots path then re-entered `check()` -> `_robots()` ->
    `_fetch_robots()` until RecursionError (PR #524 audit: 109 requests in 0.3 s)."""

    def redirect_request(self, req: Any, fp: Any, code: Any, msg: Any, headers: Any,
                         newurl: Any) -> None:
        return None


def _fetch_robots(scheme: str, netloc: str) -> tuple[int | None, str]:
    """(status, text) of robots.txt, read with the honest UA through the UNPATCHED opener, with
    redirects followed by hand: at most ROBOTS_MAX_HOPS, each hop wall-checked."""
    from urllib.parse import urljoin
    opener = urllib.request.build_opener(_NoRedirect)
    open_ = _STATE["orig"].get("urllib_open") or urllib.request.OpenerDirector.open
    url = f"{scheme}://{netloc}/robots.txt"
    _GUARD.active = getattr(_GUARD, "active", 0) + 1
    try:
        for _hop in range(ROBOTS_MAX_HOPS + 1):
            host = urlsplit(url).hostname or ""
            if host_walled(host):
                return None, f"robots.txt redirects to walled host {host}"[:200]
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with open_(opener, req, timeout=ROBOTS_TIMEOUT_S) as r:
                    return int(r.status), r.read(512_000).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location") if e.headers is not None else None
                if e.code in (301, 302, 303, 307, 308) and loc:
                    nxt = urljoin(url, loc)
                    if urlsplit(nxt).scheme not in ("http", "https"):
                        return None, f"robots.txt redirects to non-http {nxt[:120]}"
                    url = nxt
                    continue
                return int(e.code), ""
            except Exception as e:  # unreachable is a verdict, recorded below
                return None, f"{type(e).__name__}: {e}"[:200]
        return None, f"robots.txt: more than {ROBOTS_MAX_HOPS} redirects"
    finally:
        _GUARD.active -= 1


def _robots(scheme: str, netloc: str) -> tuple[urllib.robotparser.RobotFileParser | None, str]:
    key = f"{scheme}://{netloc.lower()}"
    with _LOCK:
        if key in _ROBOTS:
            return _ROBOTS[key]
    status, text = _fetch_robots(scheme, netloc)
    rp = urllib.robotparser.RobotFileParser()
    if status is None or status >= 500:
        got: tuple[urllib.robotparser.RobotFileParser | None, str] = (
            None, f"robots.txt unreachable ({status or text}) -- not consent")
    elif status in (401, 403):
        rp.disallow_all = True
        got = (rp, f"robots.txt answers {status}: disallow all")
    elif status >= 400:
        rp.allow_all = True
        got = (rp, f"robots.txt {status}: no policy")
    else:
        rp.parse(text.splitlines())
        got = (rp, "robots.txt read")
    with _LOCK:
        _ROBOTS[key] = got
    return got


def check(url: str, exc_t: type[Exception] = RailRefusal) -> None:
    """Raise `exc_t` (a RailRefusal) unless the box may fetch `url`."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if host_walled(host):
        _refuse(url, f"host {host} is walled on the VPS (seed_miners.SOURCE_WALLS)", exc_t)
    if parts.path == "/robots.txt":
        return
    rp, why = _robots(parts.scheme or "https", parts.netloc)
    if rp is None:
        _refuse(url, why, exc_t)
        return
    for tok in ROBOTS_TOKENS:
        if not rp.can_fetch(tok, url):
            _refuse(url, f"robots.txt disallows user-agent {tok!r} ({why})", exc_t)


def _refuse(url: str, why: str, exc_t: type[Exception] = RailRefusal) -> None:
    row = {"url": url[:300], "why": why, "pid": os.getpid()}
    with _LOCK:
        _STATE["refused"].append(row)
        log = os.environ.get(LOG_ENV)
        if log:
            try:
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
            except OSError:
                pass
    print(f"BOX_RAILS REFUSED {url[:200]} -- {why}", flush=True)
    raise exc_t(f"box rails refused {url[:200]}: {why}")


def refused() -> list[dict[str, Any]]:
    with _LOCK:
        return list(_STATE["refused"])


def logged_refusals(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Every refusal appended to `path` (LOG_ENV) by this process and its children."""
    out: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    out.append(d)
    except OSError:
        pass
    return out


def install(walled: frozenset[str] | None = None) -> None:
    """Patch requests and urllib in THIS process. Idempotent. `installed` is set only once every
    patch is in place: a failure part-way (the wall list unreadable, say) raises, leaves the flag
    clear, and the next call tries again rather than reading as installed with no rails."""
    with _INSTALL_LOCK:
        if _STATE["installed"]:
            return
        _install(walled)
        _STATE["installed"] = True


def _install(walled: frozenset[str] | None) -> None:
    ws = walled_hosts() if walled is None else frozenset(_norm(h) for h in walled)

    orig_open = _STATE["orig"].get("urllib_open") or urllib.request.OpenerDirector.open

    class _UrllibRefusal(RailRefusal, urllib.error.URLError):
        def __init__(self, msg: str) -> None:
            urllib.error.URLError.__init__(self, msg)

    def _open(self: Any, fullurl: Any, data: Any = None, timeout: Any = None,
              **kw: Any) -> Any:
        req = fullurl if isinstance(fullurl, urllib.request.Request) \
            else urllib.request.Request(fullurl)
        if data is not None:
            req.data = data
        for k in [k for k in req.headers if k.lower() == "user-agent"]:
            del req.headers[k]
        for k in [k for k in req.unredirected_hdrs if k.lower() == "user-agent"]:
            del req.unredirected_hdrs[k]
        req.add_header("User-Agent", USER_AGENT)
        if getattr(_GUARD, "active", 0):
            # The rails' own robots.txt read: the wall check only, never a nested robots read.
            host = urlsplit(req.full_url).hostname or ""
            if host_walled(host):
                _refuse(req.full_url, f"host {host} is walled on the VPS", _UrllibRefusal)
        else:
            check(req.full_url, _UrllibRefusal)
        if timeout is None:
            return orig_open(self, req, **kw)
        return orig_open(self, req, timeout=timeout, **kw)

    _STATE["walled"] = ws
    _STATE["orig"]["urllib_open"] = orig_open
    urllib.request.OpenerDirector.open = _open  # type: ignore[method-assign]
    try:
        import requests
    except ImportError:                                   # pragma: no cover - always present
        return
    orig_send = _STATE["orig"].get("requests_send") or requests.Session.send
    _STATE["orig"]["requests_send"] = orig_send

    class _RequestsRefusal(RailRefusal, requests.exceptions.ConnectionError):
        pass

    def _send(self: Any, request: Any, **kw: Any) -> Any:
        request.headers["User-Agent"] = USER_AGENT
        check(str(request.url), _RequestsRefusal)
        return orig_send(self, request, **kw)

    requests.Session.send = _send  # type: ignore[method-assign]


def _reset_for_tests() -> None:
    """Undo install() (tests only)."""
    with _LOCK:
        o = _STATE["orig"]
        if "urllib_open" in o:
            urllib.request.OpenerDirector.open = o["urllib_open"]  # type: ignore[method-assign]
        if "requests_send" in o:
            import requests
            requests.Session.send = o["requests_send"]  # type: ignore[method-assign]
        _STATE.update({"installed": False, "walled": frozenset(), "orig": {}, "refused": []})
        _ROBOTS.clear()
