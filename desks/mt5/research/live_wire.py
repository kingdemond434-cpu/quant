#!/usr/bin/env python3
"""THE LIVE WIRE: free first-party official feeds, polled at sub-hour cadence, straight into the
ground the fast lane already reads.

WHAT IT IS FOR. The desk's news intake was six central-bank and statistics RSS feeds polled by
`news_desk.poll_official_rss` (free_data.RSS_FEEDS), and every source in free_stack_sources.json
polls hourly or slower. A rate decision, an OFAC designation, an RBA statement or a StatCan
release is public the second it lands on the publisher's own feed; a desk that hears it from a
wire minutes later, or from an hourly pass up to an hour later, has given away the only part of
the reaction it can realistically trade (news_event_stream: "seconds-to-minutes repricing,
cross-asset propagation ... hours-to-days of transmission").

THE REGISTRY IS DATA. Every feed lives in `desks/mt5/data/live_wire_feeds.json`, never here. Each
row carries its terms verdict with the reading that settled it; ONLY rows whose verdict is OK are
ever requested. BLOCKED_ON_TERMS, REFUSED_HOST, DUPLICATE (another organ polls it), NOT_AVAILABLE
and NOT_LOCATED rows are the measured breadth of what was assessed and why it is not polled, each
with a missed_growth line. Crypto-exchange public feeds are research/signal inputs only (owner
ruling 2026-11-17 20:40Z: "mt5 only means mt5 only fr trading"): a row on a crypto-exchange
domain must carry publisher_class `crypto_exchange`, and this organ only ever reads.

EVERY REQUEST IS GATED, FAIL CLOSED, BEFORE A SOCKET OPENS:
  1. the terms-refused host list (the registry's own `refused_hosts`, unioned with
     `libs.data.refused_hosts` when that module exists) and `libs.data.off_limits`;
  2. robots.txt through the repo's gate, `index_discovery.robots_refusal` (an unreadable robots is
     a refusal, never an assumed allow), cached per host for ROBOTS_TTL_S;
  3. every redirect hop is re-checked against (1), so an allowed host cannot launder a refused one;
  4. 401/403/429/451 is a HARD STOP: the feed is held for HARD_STOP_S and reported, never retried
     in the same pass.
Requests carry an honest generic User-Agent (no personal or contact details), are spaced per host
by `polite_fetch.GATE`, and are CONDITIONAL (If-None-Match / If-Modified-Since), so an unchanged
feed costs the publisher a 304 and no body.

FOUR CLOCKS PER ITEM, written into `desks/mt5/data/news_captures.jsonl` in news_desk's own row
shape: `happened_at` (the event's own time when the feed carries one, else its publication time),
`published_at`, `received_at` (this desk saw it), `processed_at` (this row was written). The
latency received - published is measured per feed and published.

WHY news_captures.jsonl AND NOTHING NEW. news_event_stream.collect_items already reads it, so a
captured item reaches the fast lane's classification, the world-state nudge, the allocator
RE-SOLVE REQUEST and (above novelty x surprise) the deep lane's discoveries with no new consumer.
The `source` of every row names the publisher class first ("live_wire.central_bank.rba_media"),
so news_event_stream.source_tier ranks it on its existing ladder without an edit there.

TWO CLOCKS. The hourly cycle runs `--once` as leg `live_wire` immediately before
`news_event_stream`. The box task MT5-LiveWire runs `--once --trigger` every two minutes, and
with --trigger a pass that captured anything runs news_event_stream's fast lane in-process right
away, so the re-solve request is lodged within minutes rather than at the next hourly leg.
Per-feed `poll_every_s` keeps a daily feed from being asked every two minutes.

NOTHING HERE SIZES, CAPS, VETOES OR SHRINKS. It captures, stamps and hands over.

    python research/live_wire.py --once
    python research/live_wire.py --once --trigger
    python research/live_wire.py --loop --interval-s 120 --trigger
    python research/live_wire.py --once --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = _DESK / "data"
REGISTRY = DATA / "live_wire_feeds.json"
CAPTURES = DATA / "news_captures.jsonl"
STATE = DATA / "live_wire_state.json"
EVENT_LOG = DATA / "events" / "events.jsonl"
REPORT = _DESK / "reports" / "LIVE_WIRE.json"

SOURCE = "live_wire"
SCHEMA = "live-wire-feeds/1"
UNMEASURED = "UNMEASURED"
KINDS: frozenset[str] = frozenset({"rss", "atom", "rdf", "json-api", "ics", "sse"})
#: Kinds this poller can parse today. `ics` and `sse` are legal registry kinds so a row can be
#: assessed and recorded; a row of an unparsed kind that is marked OK is reported FAILED by name.
PARSED_KINDS: frozenset[str] = frozenset({"rss", "atom", "rdf", "json-api"})
VERDICTS: frozenset[str] = frozenset({"OK", "BLOCKED_ON_TERMS", "REFUSED_HOST", "DUPLICATE",
                                      "NOT_AVAILABLE", "NOT_LOCATED"})
#: Publisher classes, chosen so the class token sits on news_event_stream.SOURCE_TIERS' ladder
#: where one exists (central_bank, statistics, treasury).
PUBLISHER_CLASSES: frozenset[str] = frozenset({"central_bank", "statistics", "treasury",
                                               "regulator",
                                               "energy", "government", "hazard", "exchange",
                                               "crypto_exchange", "refused"})
HARD_STOP_STATUS: frozenset[int] = frozenset({401, 403, 429, 451})
HARD_STOP_S = 24 * 3600
ROBOTS_TTL_S = 6 * 3600
MIN_POLL_S = 60
TIMEOUT_S = 15.0
MAX_BYTES = 2_000_000
SEEN_KEEP = 600
DEFAULT_UA = ("quant-desk-livewire/1.0 (public official feeds; honours robots.txt and "
              "conditional GET)")
RULE = ("first-party official feeds only, terms verdict OK only, robots and the refused-host list "
        "checked before any socket opens; captures land in news_captures.jsonl for the fast lane; "
        "nothing here sizes, caps or vetoes")


# ============================================================================== small helpers
def _now() -> datetime:
    return datetime.now(UTC)


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).isoformat(timespec="seconds")


def parse_time(value: Any) -> datetime | None:
    """RFC 822 (RSS), ISO 8601 (Atom/JSON), a bare date, or epoch milliseconds; None otherwise."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        secs = float(value) / (1000.0 if float(value) > 1e11 else 1.0)
        with suppress(OverflowError, OSError, ValueError):
            return datetime.fromtimestamp(secs, UTC)
        return None
    text = str(value).strip()
    with suppress(TypeError, ValueError, IndexError):
        got = parsedate_to_datetime(text)
        if got is not None:
            return got if got.tzinfo else got.replace(tzinfo=UTC)
    with suppress(ValueError):
        got = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return got if got.tzinfo else got.replace(tzinfo=UTC)
    return None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str), "utf-8")
    os.replace(tmp, path)


def host_of(url: str) -> str | None:
    try:
        host = urllib.parse.urlsplit(str(url or "")).hostname
    except ValueError:
        return None
    return (host or "").lower().rstrip(".") or None


def _domain_hit(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


# ============================================================================== the registry
def load_registry(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or REGISTRY)
    return doc if isinstance(doc, dict) else {}


def registry_problems(doc: Mapping[str, Any]) -> list[str]:
    """Schema problems; an empty list is a valid registry. The test suite fences this."""
    out: list[str] = []
    if doc.get("schema") != SCHEMA:
        out.append(f"schema must be {SCHEMA!r}")
    feeds = doc.get("feeds")
    if not isinstance(feeds, list) or not feeds:
        return [*out, "feeds must be a non-empty list"]
    crypto = [str(d).lower() for d in doc.get("crypto_exchange_domains") or []]
    refused = refused_table(doc)
    seen: set[str] = set()
    for i, row in enumerate(feeds):
        if not isinstance(row, Mapping):
            out.append(f"feeds[{i}] is not an object")
            continue
        fid = str(row.get("id") or "")
        tag = fid or f"feeds[{i}]"
        if not fid:
            out.append(f"{tag}: id missing")
        elif fid in seen:
            out.append(f"{tag}: duplicate id")
        seen.add(fid)
        for key in ("url", "kind", "publisher", "publisher_class", "region", "language",
                    "asset_classes", "symbols", "cadence", "terms"):
            if key not in row:
                out.append(f"{tag}: {key} missing")
        if not isinstance(row.get("keyless"), bool):
            out.append(f"{tag}: keyless must be a boolean")
        url = str(row.get("url") or "")
        host = host_of(url)
        if not url.startswith(("https://", "http://")) or not host:
            out.append(f"{tag}: url must be an absolute http(s) URL")
        if str(row.get("kind")) not in KINDS:
            out.append(f"{tag}: kind {row.get('kind')!r} not in {sorted(KINDS)}")
        if str(row.get("publisher_class")) not in PUBLISHER_CLASSES:
            out.append(f"{tag}: publisher_class {row.get('publisher_class')!r} unknown")
        if (host and any(_domain_hit(host, d) for d in crypto)
                and str(row.get("publisher_class")) != "crypto_exchange"):
            # Research/signal use only (owner ruling 2026-11-17 20:40Z); the class makes the row's
            # nature explicit so a crypto venue can never pass as an official publisher.
            out.append(f"{tag}: crypto-exchange host {host} must carry publisher_class "
                       "'crypto_exchange' (research/signal input only; MT5 trades only)")
        terms = row.get("terms")
        if not isinstance(terms, Mapping):
            out.append(f"{tag}: terms must be an object")
            continue
        verdict = str(terms.get("verdict"))
        if verdict not in VERDICTS:
            out.append(f"{tag}: terms.verdict {verdict!r} not in {sorted(VERDICTS)}")
            continue
        if verdict == "OK":
            if not str(terms.get("basis") or "").strip():
                out.append(f"{tag}: an OK verdict must cite its basis")
            if not str(terms.get("terms_url") or "").strip():
                out.append(f"{tag}: an OK verdict must cite terms_url")
            if not row.get("keyless", False):
                out.append(f"{tag}: an OK row must be keyless (no key is read by this organ)")
            if host and refusal_of(url, refused):
                out.append(f"{tag}: OK verdict on a terms-refused host {host}")
            try:
                poll = int(row.get("poll_every_s") or 0)
            except (TypeError, ValueError):
                poll = 0
            if poll < MIN_POLL_S:
                out.append(f"{tag}: an OK row must poll no faster than every {MIN_POLL_S}s")
        else:
            if not str(terms.get("reason") or "").strip():
                out.append(f"{tag}: a {verdict} verdict must name its reason")
            if verdict != "DUPLICATE" and not str(row.get("missed_growth") or "").strip():
                out.append(f"{tag}: a {verdict} verdict must carry a missed_growth line")
        if verdict == "REFUSED_HOST" and host and not refusal_of(url, refused):
            out.append(f"{tag}: REFUSED_HOST verdict but {host} is not on the refused list")
    return out


def refused_table(doc: Mapping[str, Any]) -> dict[str, str]:
    """The registry's refused hosts, unioned with libs.data.refused_hosts when it exists."""
    table = {str(k).lower(): str(v) for k, v in (doc.get("refused_hosts") or {}).items()}
    try:
        from libs.data import refused_hosts as rh  # type: ignore[attr-defined]
    except ImportError:
        return table
    for k, v in (getattr(rh, "REFUSED_HOSTS", {}) or {}).items():
        table.setdefault(str(k).lower(), str(v))
    return table


def refusal_of(url: str, refused: Mapping[str, str]) -> str | None:
    """Why `url` may never be contacted, or None. A URL with no readable host is refused."""
    host = host_of(url)
    if host is None:
        return "the URL does not parse to a host, so its terms cannot be read (fail closed)"
    for domain, why in refused.items():
        if _domain_hit(host, domain):
            return f"REFUSED_HOST {host}: {why}"
    try:
        from libs.data.off_limits import off_limits
    except ImportError:                                  # pragma: no cover - repo always has it
        return None
    return off_limits(url)


# ============================================================================== robots
def robots_refusal(url: str, ua: str) -> str | None:
    """The repo's robots gate (index_discovery.robots_refusal, fail closed), then the same parsed
    rules asked for THIS organ's agent string as well."""
    import index_discovery as idx  # type: ignore[import-not-found]
    if getattr(idx, "_TLS", None) is None:
        with suppress(Exception):
            from libs.data.polite_fetch import ssl_context
            idx._TLS = ssl_context()
    why = idx.robots_refusal(url)
    if why:
        return str(why)
    parts = urllib.parse.urlsplit(url)
    rules = idx._ROBOTS.get(f"{parts.scheme}://{parts.netloc}")
    if rules is not None and not isinstance(rules, str) and not rules.can_fetch(ua, url):
        return "robots.txt disallows this path for the live-wire agent"
    return None


# ============================================================================== the GET
@dataclass
class Fetched:
    url: str
    status: int | None = None
    body: str = ""
    etag: str = ""
    last_modified: str = ""
    final_url: str = ""
    error: str = ""
    elapsed_s: float = 0.0

    @property
    def not_modified(self) -> bool:
        return self.status == 304

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and not self.error


class _RefusedRedirect(urllib.error.URLError):
    pass


def _redirect_handler(refused: Mapping[str, str]) -> urllib.request.HTTPRedirectHandler:
    class _Handler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
            why = refusal_of(newurl, refused)
            if why:
                raise _RefusedRedirect(f"redirect into a refused host, not followed: {why}")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    return _Handler()


class _NoErrorProcessor(urllib.request.HTTPErrorProcessor):
    """Hand 304 back as a response rather than raising, so the conditional path reads cleanly."""

    def http_response(self, request, response):  # type: ignore[no-untyped-def]
        if response.code == 304:
            return response
        return super().http_response(request, response)

    https_response = http_response


def http_get(url: str, *, ua: str, etag: str = "", last_modified: str = "",
             refused: Mapping[str, str] | None = None, timeout: float = TIMEOUT_S) -> Fetched:
    """One conditional GET. NEVER RAISES. The refusal check runs first and again on every hop."""
    out = Fetched(url=url)
    table = refused or {}
    why = refusal_of(url, table)
    if why:
        out.error = why
        return out
    headers = {"User-Agent": ua, "Accept": "application/rss+xml, application/atom+xml, "
               "application/xml, application/json;q=0.9, */*;q=0.5"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    try:
        from libs.data.polite_fetch import GATE, decode_body, ssl_context
    except ImportError:                                  # pragma: no cover - repo always has it
        out.error = "libs.data.polite_fetch not importable"
        return out
    host = host_of(url) or ""
    GATE.wait(host)
    # ProxyHandler({}) IS DELIBERATE: a clearnet feed is fetched DIRECT, never through an
    # environment proxy, so the request the publisher sees is the one its terms were read for.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _redirect_handler(table), _NoErrorProcessor(),
        urllib.request.HTTPSHandler(context=ssl_context()))
    t0 = time.monotonic()
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as fh:
            out.status = int(getattr(fh, "status", None) or getattr(fh, "code", 0) or 0)
            out.final_url = str(getattr(fh, "url", "") or url)
            h = getattr(fh, "headers", None)
            out.etag = str(h.get("ETag") or "") if h is not None else ""
            out.last_modified = str(h.get("Last-Modified") or "") if h is not None else ""
            if out.status != 304:
                raw = fh.read(MAX_BYTES)
                ctype = str(h.get("Content-Type") or "") if h is not None else ""
                cenc = str(h.get("Content-Encoding") or "") if h is not None else ""
                out.body = decode_body(raw, ctype, cenc)
    except urllib.error.HTTPError as exc:
        out.status = int(exc.code)
        out.error = f"HTTP {exc.code}"
        with suppress(Exception):
            exc.close()
        if exc.code in (429, 503):
            with suppress(Exception):
                GATE.penalise(host, 60.0)
    except _RefusedRedirect as exc:
        out.error = str(exc.reason)
    except Exception as exc:
        out.error = f"{type(exc).__name__}: {str(exc)[:160]}"
    out.elapsed_s = round(time.monotonic() - t0, 3)
    return out


# ============================================================================== parsing
def _text(el: ET.Element | None) -> str:
    return "" if el is None else "".join(el.itertext()).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_xml_feed(body: str) -> list[dict[str, str]]:
    """RSS 2.0, RSS 1.0 (RDF) and Atom items as {guid, link, title, summary, published,
    happened}."""
    try:
        root = ET.fromstring(body.encode("utf-8") if isinstance(body, str) else body)
    except ET.ParseError:
        return []
    items: list[dict[str, str]] = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        got: dict[str, str] = {}
        for child in el:
            name = _local(child.tag)
            if name == "link":
                href = child.attrib.get("href")
                rel = child.attrib.get("rel", "alternate")
                if href and rel == "alternate" and not got.get("link"):
                    got["link"] = href.strip()
                elif not href and _text(child):
                    got.setdefault("link", _text(child))
            elif name in ("guid", "id"):
                got.setdefault("guid", _text(child))
            elif name == "title":
                got["title"] = " ".join(_text(child).split())
            elif name in ("description", "summary", "content") and not got.get("summary"):
                got["summary"] = " ".join(_text(child).split())[:1200]
            elif name in ("pubDate", "published", "issued"):
                got.setdefault("published", _text(child))
            elif name in ("date", "updated", "modified"):
                got.setdefault("updated", _text(child))
        if not got.get("guid"):
            about = next((v for k, v in el.attrib.items() if _local(k) == "about"), "")
            if about:
                got["guid"] = about
        got.setdefault("published", got.get("updated", ""))
        got["happened"] = got.get("published", "")
        if got.get("title") or got.get("link"):
            items.append(got)
    return items


def _dig(doc: Any, path: str) -> Any:
    cur = doc
    for part in [p for p in str(path or "").split(".") if p]:
        if isinstance(cur, Mapping):
            cur = cur.get(part)
        else:
            return None
    return cur


def parse_json_feed(body: str, spec: Mapping[str, Any]) -> list[dict[str, str]]:
    """A keyless JSON API, read by the row's declared `json` mapping (never by guesswork)."""
    try:
        doc = json.loads(body)
    except ValueError:
        return []
    rows = _dig(doc, str(spec.get("items") or ""))
    if not isinstance(rows, list):
        return []
    id_keys = [str(k) for k in (spec.get("id") or [])]
    title_keys = [str(k) for k in (spec.get("title") or [])]
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        guid = "|".join(str(row.get(k, "")) for k in id_keys)
        title = " ".join(f"{k}={row.get(k)}" for k in title_keys
                         if row.get(k) not in (None, "", "null"))
        pub = str(_dig(row, str(spec.get("published") or "")) or "")
        hap = str(_dig(row, str(spec.get("happened") or spec.get("published") or "")) or "")
        if guid or title:
            out.append({"guid": guid, "link": str(spec.get("link") or ""), "title": title,
                        "summary": "", "published": pub, "happened": hap})
    return out


def parse_items(row: Mapping[str, Any], body: str) -> list[dict[str, str]]:
    kind = str(row.get("kind"))
    if kind == "json-api":
        return parse_json_feed(body, row.get("json") or {})
    return parse_xml_feed(body)


# ============================================================================== capture
def source_of(row: Mapping[str, Any]) -> str:
    """`live_wire.<publisher_class>.<id>` -- the class token puts it on SOURCE_TIERS' ladder."""
    return f"{SOURCE}.{row.get('publisher_class')}.{row.get('id')}"


def item_key(row: Mapping[str, Any], item: Mapping[str, str]) -> str:
    ident = item.get("guid") or item.get("link") or item.get("title") or ""
    digest = hashlib.sha1(str(ident).encode("utf-8")).hexdigest()[:16]
    return f"{SOURCE}:{row.get('id')}:{digest}"


def capture_rows(row: Mapping[str, Any], items: Sequence[Mapping[str, str]], seen: set[str], *,
                 received: datetime, first_sight: bool, backfill_h: float,
                 max_new: int) -> tuple[list[dict[str, Any]], int]:
    """New items as news_captures rows (news_desk's shape plus provenance). Returns the rows and
    how many items were SEEDED unwritten: on a feed's first sight only items published inside the
    backfill window are written, so a feed's archive never floods the fast lane as 'news'."""
    rows: list[dict[str, Any]] = []
    seeded = 0
    cutoff = received - timedelta(hours=backfill_h)
    for item in items:
        key = item_key(row, item)
        if key in seen:
            continue
        seen.add(key)
        pub = parse_time(item.get("published"))
        hap = parse_time(item.get("happened")) or pub
        if first_sight and (pub is None or pub < cutoff):
            seeded += 1
            continue
        if len(rows) >= max_new:
            seeded += 1
            continue
        processed = _now()
        rows.append({
            "key": key, "source": source_of(row), "title": str(item.get("title") or "")[:400],
            "summary": str(item.get("summary") or "")[:1200],
            "url": str(item.get("link") or item.get("guid") or row.get("url")),
            "guid": str(item.get("guid") or ""),
            "happened_at": _iso(hap) if hap else None,
            "published_at": _iso(pub) if pub else None,
            "received_at": _iso(received), "processed_at": _iso(processed),
            "latency_s": (round((received - pub).total_seconds(), 1) if pub else None),
            "lane": "fast", "raw": True, "origin": SOURCE, "feed_id": row.get("id"),
            "publisher": row.get("publisher"), "publisher_class": row.get("publisher_class"),
            "region": row.get("region"), "language": row.get("language"),
            "asset_classes": list(row.get("asset_classes") or []),
            "symbols": list(row.get("symbols") or []),
        })
    return rows, seeded


def append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return len(rows)


# ============================================================================== one pass
Transport = Callable[..., Fetched]
RobotsGate = Callable[[str, str], "str | None"]


@dataclass
class FeedResult:
    id: str
    status: str
    http: int | None = None
    new_items: int = 0
    seeded: int = 0
    parsed: int = 0
    latency_s: list[float] = field(default_factory=list)
    why: str = ""
    elapsed_s: float = 0.0


def _due(st: Mapping[str, Any], row: Mapping[str, Any], now: datetime) -> tuple[bool, str]:
    hold = parse_time(st.get("hard_stop_until"))
    if hold and hold > now:
        return False, f"HARD_STOP held until {_iso(hold)} ({st.get('hard_stop_why')})"
    last = parse_time(st.get("last_polled_at"))
    every = max(MIN_POLL_S, int(row.get("poll_every_s") or 0))
    if last and (now - last).total_seconds() < every - 5:
        return False, f"not due (every {every}s)"
    return True, ""


def poll_feed(row: Mapping[str, Any], st: dict[str, Any], *, ua: str, refused: Mapping[str, str],
              transport: Transport, robots: RobotsGate, now: datetime, backfill_h: float,
              max_new: int, dry_run: bool) -> tuple[FeedResult, list[dict[str, Any]]]:
    fid = str(row.get("id"))
    url = str(row.get("url"))
    why = refusal_of(url, refused)
    if why:
        return FeedResult(fid, "REFUSED", why=why), []
    cached = st.get("robots") or {}
    at = parse_time(cached.get("at"))
    if at and (now - at).total_seconds() < ROBOTS_TTL_S:
        rwhy = cached.get("refusal")
    else:
        try:
            rwhy = robots(url, ua)
        except Exception as exc:                         # fail closed
            rwhy = f"robots gate raised {type(exc).__name__}: {exc}"
        st["robots"] = {"refusal": rwhy, "at": _iso(now)}
    if rwhy:
        return FeedResult(fid, "REFUSED", why=f"robots: {rwhy}"), []
    if str(row.get("kind")) not in PARSED_KINDS:
        return FeedResult(fid, "FAILED", why=f"kind {row.get('kind')!r} has no parser yet"), []
    got = transport(url, ua=ua, etag=str(st.get("etag") or ""),
                    last_modified=str(st.get("last_modified") or ""), refused=refused)
    st["last_polled_at"] = _iso(now)
    res = FeedResult(fid, "FAILED", http=got.status, elapsed_s=got.elapsed_s)
    if got.status in HARD_STOP_STATUS:
        st["hard_stop_until"] = _iso(now + timedelta(seconds=HARD_STOP_S))
        st["hard_stop_why"] = f"HTTP {got.status}"
        res.status, res.why = "HARD_STOP", (f"HTTP {got.status}: hard stop, held "
                                            f"{HARD_STOP_S // 3600}h, never retried in-pass")
        return res, []
    if got.not_modified:
        res.status, res.why = "NOT_MODIFIED", "304: conditional GET, no body sent"
        st["last_ok_at"] = _iso(now)
        return res, []
    if not got.ok:
        res.why = got.error or f"HTTP {got.status}"
        return res, []
    items = parse_items(row, got.body)
    res.parsed = len(items)
    if not items:
        res.why = "the body parsed to no items"
        return res, []
    seen = set(st.get("seen") or [])
    first = not st.get("seen")
    rows, seeded = capture_rows(row, items, seen, received=now, first_sight=first,
                                backfill_h=backfill_h, max_new=max_new)
    if not dry_run:
        st["seen"] = sorted(seen)[-SEEN_KEEP:] if len(seen) > SEEN_KEEP else sorted(seen)
        if got.etag:
            st["etag"] = got.etag
        if got.last_modified:
            st["last_modified"] = got.last_modified
        st["total_items"] = int(st.get("total_items") or 0) + len(rows)
    st["last_ok_at"] = _iso(now)
    res.status = "OK"
    res.new_items, res.seeded = len(rows), seeded
    res.latency_s = [float(r["latency_s"]) for r in rows if r.get("latency_s") is not None]
    return res, rows


def _median(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 1)


def events_by_feed(path: Path | None = None, tail_bytes: int = 4_000_000) -> Counter[str]:
    """How many fast-lane events each live-wire feed has produced, from the event log's tail."""
    p = path or EVENT_LOG
    out: Counter[str] = Counter()
    if not p.exists():
        return out
    try:
        with p.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - tail_bytes))
            blob = fh.read().decode("utf-8", "replace")
    except OSError:
        return out
    prefix = SOURCE + "."
    for line in blob.splitlines():
        if prefix not in line:
            continue
        with suppress(ValueError):
            row = json.loads(line)
            sid = str(row.get("source_id") or "")
            if sid.startswith(prefix):
                out[sid.rsplit(".", 1)[-1]] += 1
    return out


def trigger_fast_lane(runner: Callable[[], Mapping[str, Any]] | None = None,
                      lock: bool = True) -> dict[str, Any]:
    """Run news_event_stream's fast lane NOW, in-process, so a captured item reaches the world
    state and the allocator re-solve request within minutes. Under the stream's job lock."""
    def _default() -> Mapping[str, Any]:
        import news_event_stream as nes  # type: ignore[import-not-found]
        got: Mapping[str, Any] = nes.run()
        return got
    run_ = runner or _default
    try:
        if lock:
            from job_lock import exclusive_job  # type: ignore[import-not-found]
            with exclusive_job("news_event_stream") as owned:
                if not owned:
                    return {"ran": False, "why": "news_event_stream holds its job lock"}
                out = run_()
        else:
            out = run_()
    except Exception as exc:
        return {"ran": False, "why": f"{type(exc).__name__}: {exc}"}
    events = [e for e in (out.get("events") or []) if isinstance(e, Mapping)]
    mine = [e for e in events if str(e.get("source_id") or "").startswith(SOURCE + ".")]
    ids = {str(e.get("id")) for e in mine}
    reqs = [r for r in (out.get("resolve_requests") or [])
            if isinstance(r, Mapping) and str(r.get("event_id")) in ids]
    by_feed = Counter(str(e.get("source_id")).rsplit(".", 1)[-1] for e in mine)
    return {"ran": True, "events": len(events), "live_wire_events": len(mine),
            "resolve_requests": len(reqs), "deep_events": sum(1 for e in mine if e.get("deep")),
            "by_feed": dict(by_feed)}


def run(*, registry_path: Path | None = None, captures_path: Path | None = None,
        state_path: Path | None = None, report_path: Path | None = None,
        event_log: Path | None = None, now: datetime | None = None,
        transport: Transport | None = None, robots: RobotsGate | None = None,
        trigger: bool = False, trigger_runner: Callable[[], Mapping[str, Any]] | None = None,
        trigger_lock: bool = True, dry_run: bool = False, only: Iterable[str] | None = None,
        force: bool = False, budget_s: float = 240.0, workers: int = 8) -> dict[str, Any]:
    """One pass over every OK feed that is due. Writes captures, state and the health report."""
    when = now or _now()
    doc = load_registry(registry_path)
    problems = registry_problems(doc) if doc else ["registry absent or unreadable"]
    feeds = [r for r in (doc.get("feeds") or []) if isinstance(r, Mapping)]
    ua = str(doc.get("user_agent") or DEFAULT_UA)
    refused = refused_table(doc)
    backfill = float(doc.get("backfill_window_h") or 48)
    max_new = int(doc.get("max_new_per_feed") or 50)
    state_file = state_path or STATE
    state = _read_json(state_file) if state_file.exists() else None
    state = state if isinstance(state, dict) else {}
    fstate: dict[str, dict[str, Any]] = state.setdefault("feeds", {})
    wanted = set(only or [])
    transport_ = transport or http_get
    robots_ = robots or robots_refusal

    eligible = [r for r in feeds if (r.get("terms") or {}).get("verdict") == "OK"
                and (not wanted or r.get("id") in wanted)]
    results: dict[str, FeedResult] = {}
    todo: list[Mapping[str, Any]] = []
    for row in eligible:
        st = fstate.setdefault(str(row.get("id")), {})
        due, why = (True, "") if force else _due(st, row, when)
        if due:
            todo.append(row)
        else:
            results[str(row.get("id"))] = FeedResult(str(row.get("id")),
                                                     "HELD" if "HARD_STOP" in why else "NOT_DUE",
                                                     why=why)
    deadline = time.monotonic() + max(5.0, budget_s)
    new_rows: list[dict[str, Any]] = []

    def _one(row: Mapping[str, Any]) -> tuple[FeedResult, list[dict[str, Any]]]:
        if time.monotonic() >= deadline:
            return FeedResult(str(row.get("id")), "FAILED", why="pass budget exhausted"), []
        st = fstate[str(row.get("id"))]
        try:
            return poll_feed(row, st, ua=ua, refused=refused, transport=transport_,
                             robots=robots_, now=when, backfill_h=backfill, max_new=max_new,
                             dry_run=dry_run)
        except Exception as exc:                         # one feed never takes the pass down
            return FeedResult(str(row.get("id")), "FAILED",
                              why=f"{type(exc).__name__}: {exc}"), []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for res, rows in pool.map(_one, todo):
            results[res.id] = res
            new_rows.extend(rows)
            st = fstate[res.id]
            st["last_status"] = res.status
            if res.why:
                st["last_why"] = res.why

    written = 0 if dry_run else append_rows(captures_path or CAPTURES, new_rows)
    trig: dict[str, Any] = {"ran": False, "why": "not requested (--trigger)"}
    if trigger and not dry_run:
        trig = (trigger_fast_lane(trigger_runner, lock=trigger_lock) if written
                else {"ran": False, "why": "no new item this pass"})
    report = build_report(doc, problems, results, state, written=written, trigger=trig,
                          now=when, event_counts=events_by_feed(event_log), dry_run=dry_run)
    if not dry_run:
        state["at"] = _iso(when)
        _atomic_json(state_file, state)
        _atomic_json(report_path or REPORT, report)
    return report


# ============================================================================== the report
def build_report(doc: Mapping[str, Any], problems: Sequence[str], results: Mapping[str, FeedResult],
                 state: Mapping[str, Any], *, written: int, trigger: Mapping[str, Any],
                 now: datetime, event_counts: Mapping[str, int], dry_run: bool) -> dict[str, Any]:
    feeds = [r for r in (doc.get("feeds") or []) if isinstance(r, Mapping)]
    fstate = state.get("feeds") or {}
    verdicts = Counter(str((r.get("terms") or {}).get("verdict")) for r in feeds)
    status = Counter(r.status for r in results.values())
    trig_by = trigger.get("by_feed") or {}
    rows: list[dict[str, Any]] = []
    cadence: dict[str, dict[str, int]] = {}
    refusal_reasons: Counter[str] = Counter()
    missed: list[dict[str, str]] = []
    for row in feeds:
        fid = str(row.get("id"))
        terms = row.get("terms") or {}
        verdict = str(terms.get("verdict"))
        st = fstate.get(fid) or {}
        res = results.get(fid)
        wired = verdict == "OK"
        in_tape = int(st.get("total_items") or 0) > 0 or bool(res and res.new_items)
        feeding = int(event_counts.get(fid, 0)) + int(trig_by.get(fid, 0)) > 0
        cad = str(row.get("cadence") or UNMEASURED)
        cell = cadence.setdefault(cad, {"rows": 0, "wired": 0, "in_tape": 0,
                                        "feeding_cells_or_triggers": 0, "sub_hour": 0})
        cell["rows"] += 1
        cell["wired"] += int(wired)
        cell["in_tape"] += int(in_tape)
        cell["feeding_cells_or_triggers"] += int(feeding)
        cell["sub_hour"] += int(bool(row.get("sub_hour")))
        entry: dict[str, Any] = {
            "id": fid, "publisher": row.get("publisher"), "region": row.get("region"),
            "language": row.get("language"), "cadence": cad, "sub_hour": bool(row.get("sub_hour")),
            "poll_every_s": row.get("poll_every_s"), "verdict": verdict, "wired": wired,
            "in_tape": in_tape, "feeding_cells_or_triggers": feeding,
            "fast_lane_events": int(event_counts.get(fid, 0)) + int(trig_by.get(fid, 0)),
            "total_items": int(st.get("total_items") or 0),
            "last_ok_at": st.get("last_ok_at"), "robots": (st.get("robots") or {}).get("refusal"),
        }
        if res is not None:
            entry.update({"status": res.status, "http": res.http, "new_items": res.new_items,
                          "seeded_unwritten": res.seeded, "parsed": res.parsed,
                          "latency_s_median": _median(res.latency_s), "why": res.why or None,
                          "elapsed_s": res.elapsed_s})
        elif wired:
            entry["status"] = "NOT_POLLED"
        else:
            entry["status"] = verdict
            entry["why"] = terms.get("reason")
            refusal_reasons[_reason_bucket(verdict, str(terms.get("reason") or ""))] += 1
        if (res is not None and res.status in ("REFUSED", "FAILED", "HARD_STOP", "HELD")):
            refusal_reasons[f"runtime {res.status}: {(res.why or '')[:60]}"] += 1
            missed.append({"feed": fid, "status": res.status, "missed_growth": (
                f"{row.get('publisher')} first-party items not captured this pass ({res.why}); "
                f"the fast lane hears them only via other sources")})
        elif not wired and row.get("missed_growth"):
            missed.append({"feed": fid, "status": verdict,
                           "missed_growth": str(row["missed_growth"])})
        rows.append(entry)
    lat = [x for r in results.values() for x in r.latency_s]
    polled = [r for r in results.values() if r.status not in ("NOT_DUE", "HELD")]
    return {
        "at": _iso(now), "source": SOURCE, "rule": RULE, "dry_run": dry_run,
        "registry": (str(REGISTRY.relative_to(_ROOT)) if REGISTRY.is_relative_to(_ROOT)
                     else str(REGISTRY)),
        "registry_problems": list(problems),
        "probe": doc.get("probe"),
        "crypto_exchange_rule": doc.get("crypto_exchange_rule"),
        "counts": {
            "assessed": len(feeds), "terms_ok": verdicts.get("OK", 0),
            "blocked_on_terms": verdicts.get("BLOCKED_ON_TERMS", 0),
            "refused_host": verdicts.get("REFUSED_HOST", 0),
            "duplicate_owned_elsewhere": verdicts.get("DUPLICATE", 0),
            "not_available": verdicts.get("NOT_AVAILABLE", 0),
            "not_located": verdicts.get("NOT_LOCATED", 0),
            "polled": len(polled), "ok": status.get("OK", 0),
            "not_modified": status.get("NOT_MODIFIED", 0), "refused": status.get("REFUSED", 0),
            "failed": status.get("FAILED", 0), "hard_stop": status.get("HARD_STOP", 0),
            "held": status.get("HELD", 0), "not_due": status.get("NOT_DUE", 0),
            "new_items": sum(r.new_items for r in results.values()), "written": written,
            "wired": sum(1 for e in rows if e["wired"]),
            "in_tape": sum(1 for e in rows if e["in_tape"]),
            "feeding_cells_or_triggers": sum(1 for e in rows if e["feeding_cells_or_triggers"]),
            "sub_hour_wired": sum(1 for e in rows if e["wired"] and e["sub_hour"]),
        },
        "latency_s": {"median": _median(lat), "n": len(lat),
                      "definition": "received_at - published_at, per captured item this pass"},
        "cadence": cadence,
        "top_refusal_reasons": refusal_reasons.most_common(10),
        "trigger": dict(trigger),
        "feeds": rows,
        "missed_growth": missed,
        "consumer": ("news_event_stream.collect_items reads news_captures.jsonl: fast lane -> "
                     "world_state.json -> allocator_resolve_request.json; deep lane -> "
                     "discoveries"),
    }


def _reason_bucket(verdict: str, reason: str) -> str:
    low = reason.lower()
    if verdict == "REFUSED_HOST":
        return "REFUSED_HOST: settled terms refusal"
    if verdict == "DUPLICATE":
        return "DUPLICATE: polled by another organ"
    if "non-commercial" in low:
        return "BLOCKED_ON_TERMS: non-commercial-only licence"
    if "licensed" in low:
        return "BLOCKED_ON_TERMS: exchange data is licensed"
    if "robots" in low:
        return "BLOCKED_ON_TERMS: robots disallowed"
    if "all rights reserved" in low or "excludes" in low:
        return "BLOCKED_ON_TERMS: rights reserved / excluded from licence"
    if verdict == "BLOCKED_ON_TERMS":
        return "BLOCKED_ON_TERMS: terms not read (fail closed)"
    return f"{verdict}"


# ============================================================================== CLI
def _summary(rep: Mapping[str, Any]) -> str:
    c = rep.get("counts") or {}
    return (f"{SOURCE} at={rep.get('at')} assessed={c.get('assessed')} "
            f"terms_ok={c.get('terms_ok')} "
            f"polled={c.get('polled')} ok={c.get('ok')} 304={c.get('not_modified')} "
            f"refused={c.get('refused')} failed={c.get('failed')} new={c.get('new_items')} "
            f"trigger={(rep.get('trigger') or {}).get('ran')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass and exit (the default)")
    ap.add_argument("--loop", action="store_true", help="pass every --interval-s, forever")
    ap.add_argument("--interval-s", type=float, default=120.0)
    ap.add_argument("--trigger", action="store_true",
                    help="after a pass that captured anything, run news_event_stream's fast lane")
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse; write nothing")
    ap.add_argument("--only", nargs="*", default=None, help="feed ids to poll")
    ap.add_argument("--force", action="store_true", help="ignore poll_every_s for this pass")
    ap.add_argument("--budget-s", type=float,
                    default=float(os.environ.get("QUANT_LEG_BUDGET_S") or 240) * 0.9)
    args = ap.parse_args(argv)

    def _pass() -> dict[str, Any]:
        return run(trigger=args.trigger, dry_run=args.dry_run, only=args.only,
                   force=args.force, budget_s=args.budget_s)

    if not args.loop:
        try:
            from job_lock import exclusive_job
        except ImportError:                              # pragma: no cover - repo always has it
            print(_summary(_pass()), flush=True)
            return 0
        with exclusive_job(SOURCE) as owned:
            if not owned:
                print(f"{SOURCE}: another pass holds the lock; this trigger stands down",
                      flush=True)
                return 0
            print(_summary(_pass()), flush=True)
        return 0
    while True:
        started = time.time()
        try:
            print(_summary(_pass()), flush=True)
        except Exception as exc:                         # pragma: no cover - resident guard
            print(f"{SOURCE} pass failed: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(max(MIN_POLL_S, args.interval_s - (time.time() - started)))


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
