"""Owner-attested publisher permissions: one data file, one reader, one fetch door.

The owner attested on 2026-11-17 (20:38-20:39Z,
governance/owner-permission-attestation-2026-11-17.md) that seven publishers granted automated
use and that he takes responsibility. That is an OWNER ATTESTATION, not a verified publisher
grant, so the basis is never hidden: every row this door fetches carries
``permission=owner_attestation_2026-11-17``.

``desks/mt5/data/owner_permissions.json`` holds one row per source, each with its own ``enabled``
flag. :func:`is_permitted` is true only when the file reads, the row exists and ``enabled`` is
true. Everything else FAILS CLOSED: a missing, unreadable or malformed file, a missing row or a
false flag is "not permitted", and the fence that consults it keeps its existing refusal with a
missed_growth line.

What a row can never do:

* unlock a HARD-REFUSED host. ``libs/data/off_limits.py`` grounds and the hosts the attestation
  names as NOT covered (FRED/ALFRED, Reddit, Yahoo, UN Comtrade, archive.org, YouTube, Dukascopy,
  ICE, SPDR, IMF PortWatch, the prop-firm sites) win over any row. When the terms branch's
  ``libs/data/refused_hosts.py`` lands it is consulted too, except for the hosts this attestation
  names in scope (``ATTESTED_IN_SCOPE``: Cboe, for the options OI/gamma chain only).
* skip robots.txt. :func:`robots_allows` fails closed: ONLY 404 and 410 mean "no file, allowed";
  401/403 deny; every other status (any other 4xx, any 5xx), a network error or an HTML page
  served as robots.txt refuses the pass.
* follow a redirect it has not checked. Every 30x hop is refused BEFORE it is requested when it
  points at a hard-refused host or a host outside the source's row (:class:`_HopGuard`), for the
  robots fetch and the data request alike.
* retry a refusal. 401/403/429/451 (on robots.txt or the data request) is a hard stop HELD for
  ``HARD_STOP_S`` (24h) per source in ``HOLDS`` (gitignored ``data/``); while held the source is
  skipped with its missed_growth line and nothing is requested.
* log in, pass a paywall or a CAPTCHA, or send anything but an honest generic User-Agent.
"""
from __future__ import annotations

import contextvars
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PERMISSIONS = REPO / "desks" / "mt5" / "data" / "owner_permissions.json"
BASIS = "owner_attestation_2026-11-17"
PROVENANCE = f"permission={BASIS}"
GOVERNANCE = "docs/policy/owner-permission-attestation-2026-11-17.md"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; owner_permitted_sources)"
HARD_STOP: frozenset[int] = frozenset({401, 403, 429, 451})
MAX_BYTES = 8_000_000
HARD_STOP_S = 24 * 3600
#: Per-source hard-stop holds, ``{source_id: {"until": iso, "why": str, "http": int}}``. Repo-root
#: ``data/`` is gitignored, so a hold is box state that never reaches origin.
HOLDS = REPO / "data" / "owner_permitted" / "hard_stops.json"
#: Where owner-permitted DERIVED output lands (gitignored: ``desks/mt5/data/owner_permitted/``).
#: Cboe-derived rows never go to a tracked path.
OWNER_PERMITTED_DIR = REPO / "desks" / "mt5" / "data" / "owner_permitted"
CBOE_GEX_FILE = OWNER_PERMITTED_DIR / "cboe_options" / "cboe_spx_options.jsonl"
#: The error prefix a transport returns when it refused to follow a redirect hop.
REDIRECT_REFUSED = "REDIRECT_REFUSED"
#: robots.txt statuses that mean "no file": the ONLY allowing non-2xx answers.
ROBOTS_ABSENT: frozenset[int] = frozenset({404, 410})
ROBOTS_DENY: frozenset[int] = frozenset({401, 403})

#: Hosts the attestation names as NOT covered, plus the settled terms refusals. A row naming one
#: of these is never permitted, whatever its flag says. Matched on the domain or any subdomain.
HARD_REFUSED_DOMAINS: dict[str, str] = {
    "stlouisfed.org": "FRED/ALFRED: refused for all automated fetches (ruling 2026-11-13)",
    "reddit.com": "Reddit: refused (not covered by the 2026-11-17 attestation)",
    "redd.it": "Reddit: refused (not covered by the 2026-11-17 attestation)",
    "yahoo.com": "Yahoo: terms refuse automated collection",
    "yahooapis.com": "Yahoo: terms refuse automated collection",
    "comtrade.un.org": "UN Comtrade: refused (ruling 2026-11-14)",
    "comtradeplus.un.org": "UN Comtrade: refused (ruling 2026-11-14)",
    "comtradeapi.un.org": "UN Comtrade: refused (ruling 2026-11-14)",
    "archive.org": "archive.org/Wayback: refused (ruling 2026-11-14)",
    "youtube.com": "YouTube: refused (ruling 2026-11-14)",
    "youtu.be": "YouTube: refused (ruling 2026-11-14)",
    "youtube-nocookie.com": "YouTube: refused (ruling 2026-11-14)",
    "ytimg.com": "YouTube: refused (ruling 2026-11-14)",
    "dukascopy.com": "Dukascopy: terms refuse bots and commercial use",
    "theice.com": "ICE: terms refuse automated collection",
    "ice.com": "ICE: terms refuse automated collection",
    "ssga.com": "SPDR (State Street): refused (not covered by the 2026-11-17 attestation)",
    "spdrgoldshares.com": "SPDR: refused (not covered by the 2026-11-17 attestation)",
    "spdrs.com": "SPDR: refused (not covered by the 2026-11-17 attestation)",
    "portwatch.imf.org": "IMF PortWatch: pending reconciliation, refused",
    "the5ers.com": "prop-firm site: refused (ruling 2026-11-14)",
    "fundednext.com": "prop-firm site: refused (ruling 2026-11-14)",
    "topstep.com": "prop-firm site: refused (ruling 2026-11-14)",
    "alphacapitalgroup.uk": "prop-firm site: refused (ruling 2026-11-14)",
    "fintokei.com": "prop-firm site: refused (ruling 2026-11-14)",
    "ftmo.com": "prop-firm site: not confirmed, never contacted (ruling 2026-11-14)",
    "e8markets.com": "prop-firm site: not confirmed, never contacted (ruling 2026-11-14)",
    "fxify.com": "prop-firm site: not confirmed, never contacted (ruling 2026-11-14)",
    "fundingpips.com": "prop-firm site: not confirmed, never contacted (ruling 2026-11-14)",
    "apextraderfunding.com": "prop-firm site: not confirmed, never contacted (ruling 2026-11-14)",
}
#: IMF PortWatch is served from an ArcGIS host shared with many publishers; its path names it.
HARD_REFUSED_PATH_MARKERS: tuple[tuple[str, str], ...] = (
    ("services9.arcgis.com/weJ1QsnbMYJlCHdG", "IMF PortWatch: pending reconciliation, refused"),)
#: Domains a settled terms list refuses but this attestation names IN SCOPE. Only these may be
#: unlocked by a row, and only for the endpoints that row lists.
ATTESTED_IN_SCOPE: frozenset[str] = frozenset({"cboe.com"})


# --------------------------------------------------------------------------- the data file
def _host(url_or_host: str) -> str | None:
    s = str(url_or_host or "").strip()
    if not s:
        return None
    try:
        host = urllib.parse.urlsplit(s if "//" in s else f"//{s}").hostname
    except ValueError:
        return None
    return (host or "").lower().rstrip(".") or None


def _matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def load(path: Path | None = None) -> tuple[dict[str, dict[str, Any]], str]:
    """``({source_id: row}, why)``. An unreadable or malformed file is ``({}, why)``:
    FAIL CLOSED."""
    p = Path(path) if path is not None else PERMISSIONS
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {}, f"owner_permissions unreadable ({type(exc).__name__}): nothing permitted"
    rows = doc.get("sources") if isinstance(doc, Mapping) else None
    if not isinstance(rows, list):
        return {}, "owner_permissions has no sources list: nothing permitted"
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if isinstance(r, Mapping) and isinstance(r.get("id"), str) and r["id"]:
            out[r["id"]] = dict(r)
    return out, "read"


def hard_refusal(url: str) -> str | None:
    """Why ``url`` may never be fetched under an owner row, or None. Fails closed on a URL whose
    host cannot be read."""
    host = _host(url)
    if host is None:
        return "the URL does not parse to a host: refused (fail closed)"
    from libs.data.off_limits import off_limits
    why = off_limits(url)
    if why:
        return why
    for dom, reason in HARD_REFUSED_DOMAINS.items():
        if _matches(host, dom):
            return f"BLOCKED_ON_TERMS (hard-refused, no owner row unlocks it): {reason} [{host}]"
    low = str(url).lower()
    for marker, reason in HARD_REFUSED_PATH_MARKERS:
        if marker.lower() in low:
            return f"BLOCKED_ON_TERMS (hard-refused, no owner row unlocks it): {reason}"
    try:                      # the terms branch's list, when it is on this tree
        from libs.data import refused_hosts as _rh  # type: ignore[attr-defined,unused-ignore]
    except ImportError:
        return None
    rh = getattr(_rh, "refusal", None)
    why = rh(url) if callable(rh) else None
    if why and not any(_matches(host, d) for d in ATTESTED_IN_SCOPE):
        return f"BLOCKED_ON_TERMS (hard-refused, no owner row unlocks it): {why}"
    return None


def row_for(source_or_host: str, path: Path | None = None) -> dict[str, Any] | None:
    """The row named by a source id, or the enabled-or-not row whose ``hosts`` hold that host."""
    rows, _ = load(path)
    if source_or_host in rows:
        return rows[source_or_host]
    host = _host(source_or_host)
    if host is None:
        return None
    for r in rows.values():
        if any(isinstance(h, str) and host == h.lower() for h in (r.get("hosts") or [])):
            return r
    return None


def _row_ok(row: Mapping[str, Any] | None) -> bool:
    if not row or row.get("enabled") is not True:
        return False
    hosts = [h for h in (row.get("hosts") or []) if isinstance(h, str) and h]
    if not hosts:
        return False
    # A row that names a hard-refused host is malformed and permits nothing at all.
    return not any(hard_refusal(f"https://{h}/") for h in hosts)


def is_permitted(source_or_host: str, path: Path | None = None) -> bool:
    """True only when the file reads, the row exists, ``enabled`` is literally true and none of
    the row's hosts is hard-refused. Given a URL or host, also requires that host not be
    hard-refused itself."""
    row = row_for(source_or_host, path)
    if not _row_ok(row):
        return False
    target = source_or_host if "//" in source_or_host else f"https://{source_or_host}/"
    return source_or_host == (row or {}).get("id") or not hard_refusal(target)


def refusal(source_id: str, url: str | None = None, path: Path | None = None) -> str | None:
    """None when ``source_id`` may fetch ``url`` now; otherwise the refusal, with its
    missed_growth line. The hard-refused list is checked FIRST, so no row can override it."""
    if url is not None:
        hard = hard_refusal(url)
        if hard:
            return hard
    rows, why = load(path)
    row = rows.get(source_id)
    mg = (row or {}).get("missed_growth") or (
        f"missed_growth: {source_id} is UNMEASURED while it is refused")
    if not rows:
        return f"BLOCKED_ON_TERMS: {why}; {mg}"
    if row is None:
        return f"BLOCKED_ON_TERMS: no owner_permissions row for {source_id!r}; {mg}"
    if row.get("enabled") is not True:
        return (f"BLOCKED_ON_TERMS: owner_permissions row {source_id!r} is disabled "
                f"(enabled={row.get('enabled')!r}); {mg}")
    if not _row_ok(row):
        return f"BLOCKED_ON_TERMS: row {source_id!r} names a hard-refused host or none; {mg}"
    if url is not None:
        host = _host(url)
        if host not in {str(h).lower() for h in row.get("hosts") or []}:
            return (f"BLOCKED_ON_TERMS: {host} is not a host of owner row {source_id!r}; {mg}")
    return None


def provenance(source_id: str, **extra: Any) -> dict[str, Any]:
    """The stamp every fetched row and artifact carries."""
    return {"permission": BASIS, "provenance": PROVENANCE, "source": source_id,
            "governance": GOVERNANCE, **extra}


# --------------------------------------------------------------------------- the fetch door
@dataclass
class Fetched:
    """What one permitted request produced. ``status`` is ``ok``, ``refused``, ``hard_stop``,
    ``held``, ``robots_refused`` or ``error``; ``body`` is set only on ``ok``."""
    source: str
    url: str
    status: str
    why: str = ""
    http: int | None = None
    body: bytes = b""
    content_type: str = ""
    fetched_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


#: transport(url, headers, timeout) -> (http_status | None, body, final_url, content_type, error)
Transport = Callable[[str, Mapping[str, str], float], tuple[int | None, bytes, str, str, str]]

#: The hop check for the request in flight. :func:`permitted_get` sets it to the source's own
#: refusal; with nothing set the transport still refuses every hard-refused host.
_HOP_GUARD: contextvars.ContextVar[Callable[[str], str | None] | None] = contextvars.ContextVar(
    "owner_permissions_hop_guard", default=None)


class _RefusedRedirect(urllib.error.URLError):
    def __init__(self, newurl: str, why: str) -> None:
        super().__init__(why)
        self.newurl = newurl


class _HopGuard(urllib.request.HTTPRedirectHandler):
    """Checks every 30x target BEFORE urllib requests it; a refused hop raises, so the refused
    host is never contacted."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        guard = _HOP_GUARD.get()
        why = hard_refusal(newurl) or (guard(newurl) if guard is not None else None)
        if why:
            raise _RefusedRedirect(newurl, f"redirect into a refused host, not followed: {why}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _urllib_transport(url: str, headers: Mapping[str, str],
                      timeout: float) -> tuple[int | None, bytes, str, str, str]:
    from libs.data import polite_fetch
    host = urllib.parse.urlsplit(url).netloc.lower()
    if host:
        polite_fetch.GATE.wait(host)                  # per-host spacing, process-wide
    req = urllib.request.Request(url, headers=dict(headers))
    opener = urllib.request.build_opener(
        _HopGuard(), urllib.request.HTTPSHandler(context=polite_fetch.ssl_context()))
    try:
        with opener.open(req, timeout=timeout) as fh:
            raw = fh.read(MAX_BYTES)
            h = getattr(fh, "headers", None)
            ctype = str(h.get("Content-Type") or "") if h is not None else ""
            code = int(getattr(fh, "status", None) or 200)
            return code, raw, str(getattr(fh, "url", "") or url), ctype, ""
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        exc.close()
        return code, b"", url, "", f"HTTP {code}"
    except _RefusedRedirect as exc:
        return None, b"", exc.newurl, "", f"{REDIRECT_REFUSED}: {exc.reason}"
    except Exception as exc:
        return None, b"", url, "", f"{type(exc).__name__}: {str(exc)[:160]}"


# --------------------------------------------------------------------------- hard-stop holds
def _read_holds(holds: Path) -> dict[str, Any]:
    try:
        doc = json.loads(holds.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dict(doc) if isinstance(doc, Mapping) else {}


def held(source_id: str, holds: Path | None = None,
         now: datetime | None = None) -> dict[str, Any] | None:
    """The live hold on ``source_id`` (``{"until", "why", "http"}``), or None."""
    h = _read_holds(holds or HOLDS).get(source_id)
    if not isinstance(h, Mapping):
        return None
    try:
        until = datetime.fromisoformat(str(h.get("until")).replace("Z", "+00:00"))
    except ValueError:
        return None
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return dict(h) if until > (now or datetime.now(UTC)) else None


def hold(source_id: str, code: int, why: str, holds: Path | None = None,
         now: datetime | None = None) -> str:
    """Hold ``source_id`` for HARD_STOP_S; returns the ISO time it lifts."""
    p = holds or HOLDS
    until = ((now or datetime.now(UTC)) + timedelta(seconds=HARD_STOP_S)).isoformat(
        timespec="seconds")
    doc = _read_holds(p)
    doc[source_id] = {"until": until, "http": code, "why": why}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass                    # an unwritable hold still stops this pass; next pass re-learns
    return until


def _missed_growth(source_id: str, path: Path | None) -> str:
    rows, _ = load(path)
    return str((rows.get(source_id) or {}).get("missed_growth") or
               f"missed_growth: {source_id} is UNMEASURED while it is refused")


def _robots(url: str, transport: Transport, agent: str = UA) -> tuple[bool, str, int | None]:
    from urllib.robotparser import RobotFileParser
    parts = urllib.parse.urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    code, body, _final, _ctype, err = transport(robots, {"User-Agent": agent}, 15.0)
    if code is None:
        return False, (f"robots.txt unreadable ({err or 'no answer'}): not fetched "
                       "(fail closed)"), None
    if code in ROBOTS_DENY:
        return False, f"robots.txt HTTP {code}: denied, not fetched (hard stop)", code
    if code in HARD_STOP:
        return False, f"robots.txt HTTP {code}: hard stop, not fetched (fail closed)", code
    if code in ROBOTS_ABSENT:
        return True, f"robots.txt HTTP {code}: no robots file, allowed (RFC 9309)", code
    if not (200 <= code < 300) or err:
        return False, (f"robots.txt HTTP {code}: not a readable answer, not fetched "
                       "(fail closed)"), code
    text = body.decode("utf-8", "replace")
    if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        return False, "robots.txt is an HTML page: not fetched (fail closed)", code
    rp = RobotFileParser()
    try:
        rp.parse(text.splitlines())
    except Exception as exc:
        return False, f"robots.txt did not parse ({type(exc).__name__}): not fetched", code
    if rp.can_fetch(agent, url):
        return True, "robots.txt consulted: allowed", code
    return False, "robots.txt Disallow covers this path: not fetched", code


def robots_allows(url: str, transport: Transport, agent: str = UA) -> tuple[bool, str]:
    """robots.txt for the URL's host, FAILING CLOSED: a parsed 2xx file is obeyed; ONLY 404 and
    410 mean "no file" (allowed); 401/403 deny; every other status, 4xx or 5xx, a network error,
    a refused redirect or an HTML page served as robots.txt refuses this pass."""
    ok, why, _code = _robots(url, transport, agent)
    return ok, why


def permitted_get(source_id: str, url: str, *, transport: Transport | None = None,
                  path: Path | None = None, timeout: float = 40.0,
                  accept: str = "*/*", holds: Path | None = None) -> Fetched:
    """ONE request under an owner row: hard-refused list, then the row, then a live 24h hold,
    then robots (fail closed), then one honest GET with no retry. Every redirect hop is checked
    before it is followed. 401/403/429/451 is a hard stop held for HARD_STOP_S."""
    t = transport or _urllib_transport
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    why = refusal(source_id, url, path)
    if why:
        return Fetched(source_id, url, "refused", why, fetched_at=now)
    h = held(source_id, holds)
    if h:
        return Fetched(source_id, url, "held",
                       f"HARD_STOP held until {h.get('until')} (HTTP {h.get('http')}: "
                       f"{h.get('why')}); not requested; {_missed_growth(source_id, path)}",
                       http=h.get("http"), fetched_at=now)
    token = _HOP_GUARD.set(lambda u: hard_refusal(u) or refusal(source_id, u, path))
    try:
        ok, rwhy, rcode = _robots(url, t)
        if not ok:
            if rcode in HARD_STOP:
                until = hold(source_id, rcode, rwhy, holds)
                rwhy = f"{rwhy}; held until {until}; {_missed_growth(source_id, path)}"
            return Fetched(source_id, url, "robots_refused", rwhy, http=rcode, fetched_at=now)
        code, body, final, ctype, err = t(url, {"User-Agent": UA, "Accept": accept}, timeout)
    finally:
        _HOP_GUARD.reset(token)
    if err.startswith(REDIRECT_REFUSED):
        return Fetched(source_id, url, "refused", f"redirected: {err}", http=code,
                       fetched_at=now)
    if final and final != url:
        hop = hard_refusal(final) or refusal(source_id, final, path)
        if hop:
            return Fetched(source_id, url, "refused", f"redirected: {hop}", http=code,
                           fetched_at=now)
    if code in HARD_STOP:
        stop = f"HTTP {code}: the publisher said no"
        until = hold(source_id, code, stop, holds)
        return Fetched(source_id, url, "hard_stop", f"{stop}; held until {until}, never "
                       f"retried in the hold; {_missed_growth(source_id, path)}", http=code,
                       fetched_at=now)
    if code is None or err or not (200 <= code < 300):
        return Fetched(source_id, url, "error", err or f"HTTP {code}", http=code,
                       fetched_at=now)
    return Fetched(source_id, url, "ok", rwhy, http=code, body=body, content_type=ctype,
                   fetched_at=now, meta=provenance(source_id, url=url, fetched_at=now))
