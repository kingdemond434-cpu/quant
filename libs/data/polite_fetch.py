"""One polite, concurrent, measured HTTP GET for every alt-data miner.

WHY THIS EXISTS (measured 2026-09-30 on the trading box). The alt-data miners fetched one URL at a
time with ad-hoc sleeps and no retry, so their wall time was mostly spent waiting, and every
transient failure was booked as a verdict about the source:

* `readitrades_africa` lost 217 of 217 attempts to `SSLError` -- a trust-store problem on the
  Windows Python build, not a closed source. `ssl_context()` loads certifi's bundle ON TOP of the
  system store, so a chain either knows is accepted.
* `share4you`, `hfm_pamm`, `followme_cn`, `minfx_jp` were booked `HTTPError` on the first answer.
  A 429 or a 5xx is a request to come back later; `get()` does, with exponential backoff and the
  server's own `Retry-After` (capped), inside a hard deadline. A 403/404 is deterministic and is
  NOT retried here -- the caller resolves it with another URL, never by hammering.
* Chinese and Japanese grounds serve GBK / Shift_JIS. Decoding every body as UTF-8 with
  `errors="replace"` turned their text into U+FFFD soup that no claim extractor can read.
  `decode_body()` honours the header charset, then the page's own `<meta charset>`.

POLITENESS IS PER HOST, NOT PER MINER. `HostGate` spaces requests to one host by a minimum
interval shared by every thread in the process, so a miner can run many fetches at once against
MANY hosts without ever sending one host more than it did when it ran sequentially. That is how
concurrency buys coverage per second without buying a ban.

MEASURED, NEVER ASSUMED. `STATS` counts fetches, successes, HTTP and transport failures, bytes
and seconds per `leg` label, so a miner can publish its own fetches/second.

No secret is read or sent. Stdlib only (certifi is optional).
"""
from __future__ import annotations

import gzip
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
from email.message import Message
from typing import Any, TypeVar
from urllib.parse import urlparse

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": BROWSER_UA,
    "Accept": ("text/html,application/xhtml+xml,application/json,application/xml;q=0.9,"
               "*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
}
#: Statuses that mean "come back later", and the only ones retried.
RETRY_STATUS: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522,
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

    def reserve(self, host: str) -> float:
        """Book the next slot for `host`; returns how long the caller must wait for it."""
        now = time.monotonic()
        with self._lock:
            slot = max(now, self._next.get(host, 0.0))
            self._next[host] = slot + self.interval(host)
        return max(0.0, slot - now)

    def penalise(self, host: str, seconds: float) -> None:
        """A 429/503 pushes the host's next slot out for every thread, not only the one that saw
        it."""
        with self._lock:
            self._next[host] = max(self._next.get(host, 0.0), time.monotonic() + seconds)

    def wait(self, host: str, sleep: Callable[[float], None] = time.sleep) -> None:
        w = self.reserve(host)
        if w > 0:
            sleep(w)


GATE = HostGate(per_host=HOST_INTERVAL_S)


# --------------------------------------------------------------------------- stats
@dataclass
class LegStats:
    fetches: int = 0
    ok: int = 0
    http_errors: int = 0
    transport_errors: int = 0
    retries: int = 0
    bytes: int = 0
    seconds: float = 0.0
    by_error: dict[str, int] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        return {"fetches": self.fetches, "ok": self.ok, "http_errors": self.http_errors,
                "transport_errors": self.transport_errors, "retries": self.retries,
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


def stats(leg: str) -> dict[str, Any]:
    with _STATS_LOCK:
        return (_STATS.get(leg) or LegStats()).as_row()


def reset_stats(leg: str | None = None) -> None:
    with _STATS_LOCK:
        if leg is None:
            _STATS.clear()
        else:
            _STATS.pop(leg, None)


# --------------------------------------------------------------------------- decoding
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)


def decode_body(raw: bytes, content_type: str = "", content_encoding: str = "") -> str:
    """Bytes -> text: undo gzip/deflate, then the header charset, then `<meta charset>`, then
    UTF-8. Never raises."""
    enc = (content_encoding or "").lower()
    try:
        if "gzip" in enc or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        pass
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
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep) -> Response:
    """GET `url` once, politely, with bounded retries. NEVER RAISES: the Response carries the
    status or the error, so a caller can record what happened rather than a stack trace.

    `timeout` is per attempt; `deadline` (a `time.monotonic()` value) caps the whole call,
    retries and backoff included, so no fetch can outlive the budget of the leg that made it.
    """
    resp = Response(url=url)
    # THE PLATFORM TERMS FENCE (2026-09-30): a URL on a platform whose own agreement bars this
    # desk's automated use (Reddit, StockTwits -- libs/data/terms_fence.py) is never requested.
    # The Response carries the named refusal, so the caller records it instead of a silent miss.
    from libs.data import terms_fence as _tf
    _why = _tf.platform_of_url(url)
    if _why:
        resp.error = f"{_tf.PLATFORMS[_why]['status']}:{_why}: {_tf.PLATFORMS[_why]['reason']}"
        _stat(leg, error=f"terms_fenced:{_why}")
        return resp
    hdr = {**BROWSER_HEADERS, **(headers or {})}
    host = urlparse(url).netloc.lower()
    open_ = opener or urllib.request.urlopen
    t0 = time.monotonic()
    for attempt in range(max(0, retries) + 1):
        if deadline is not None and time.monotonic() >= deadline:
            resp.error = resp.error or "deadline"
            break
        if gate is not None and host:
            gate.wait(host, sleep)
        per_try = timeout
        if deadline is not None:
            per_try = max(1.0, min(timeout, deadline - time.monotonic()))
        resp.attempts = attempt + 1
        _stat(leg, fetches=1, retries=1 if attempt else 0)
        wait: float | None = None
        try:
            req = urllib.request.Request(url, headers=hdr)
            with open_(req, timeout=per_try, context=ssl_context()) as fh:
                raw = fh.read(max_bytes)
                h = getattr(fh, "headers", None)
                ctype = str(h.get("Content-Type") or "") if h is not None else ""
                cenc = str(h.get("Content-Encoding") or "") if h is not None else ""
                resp.status = int(getattr(fh, "status", None) or getattr(fh, "code", 200) or 200)
                resp.final_url = str(getattr(fh, "url", "") or url)
                resp.content_type = ctype
                resp.text = decode_body(raw, ctype, cenc)
                resp.error = ""
                _stat(leg, ok=1, bytes=len(raw))
                break
        except urllib.error.HTTPError as exc:
            resp.status = int(exc.code)
            resp.error = f"HTTP {exc.code}"
            _stat(leg, http_errors=1, error=f"HTTP {exc.code}")
            # HTTPError also owns the response stream. Release it on both a terminal
            # rejection and a retry, rather than leaving the socket to garbage collection.
            try:
                wait = _retry_after(getattr(exc, "headers", None))
            finally:
                exc.close()
            if exc.code not in RETRY_STATUS:
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
    resp.elapsed_s = time.monotonic() - t0
    _stat(leg, seconds=resp.elapsed_s)
    return resp


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
