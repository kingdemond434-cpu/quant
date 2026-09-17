#!/usr/bin/env python3
"""THE MOAT COLLECTORS -- the physical moat: immutable raw captures, normalised documents.

WHY THIS EXISTS (ledger M2/M9). The registry knows about SOURCES and the miners know how to
FETCH, and between the two there was nothing that kept what was fetched. A claim on this desk
could name its url and its crawl time and could not produce the bytes it was read off: when the
page changed, the evidence changed with it, silently and in the direction that flatters whoever
looked last. The desk's licence position (concept reimplemented, provenance cited) and its
point-in-time position (a claim is only usable from the moment the world could read it) both
depend on the same artifact -- the ORIGINAL BYTES, stamped with where they came from and when
they became knowable. This module is that artifact store.

THREE RULES, and they are the whole design.

**A CAPTURE IS WRITTEN ONCE.** `raw_intel/<source_id>/<sha256>.<ext>` is content-addressed, so
the same bytes fetched again land on the same name and the second write is a NO-OP, counted as a
duplicate rather than performed. A file that already exists is NEVER overwritten: the writer
opens with O_EXCL and, when the existing bytes are not the bytes it was asked to write, REFUSES
and says so. There is no flag that turns this off. An archive that can be rewritten is not an
archive, it is a cache with a good opinion of itself.

**A CHART IS A LEAD, NEVER EVIDENCE.** Images -- charts, screenshots, diagrams -- are captured
and normalised to a LEAD STUB: `media_path` plus the alt/caption text the source itself wrote,
`quantitative: false`, and every claim cut out of them carries `kind="lead_stub"` into the
claims table. Nothing in this module reads a pixel, estimates a level off an axis, or converts a
picture into a number, because a number read off a chart has no error bars, no vintage and no
way back to a source -- and once it is in a table nobody downstream can tell it from a measured
series. A chart says WHERE TO LOOK. The desk's own bars say what happened.

**WHEN SOMETHING BECAME KNOWABLE IS STORED BESIDE WHAT IT SAID.** `knowable_at` is the
publish/post stamp the SOURCE states -- a meta tag, a feed's pubDate, a PDF creation date, a
notebook's execution stamp -- and never the crawl time. A source that states none gives
`UNMEASURED`, which is a verdict (L1.28a), not a blank and never a substitute. `provenance`
keeps the crawl time separately, so the two can never be confused by a reader who skims.

WHAT IT REUSES AND WHAT IT REFUSES TO REWRITE. There is ONE HTTP client on this desk and it
belongs to `deep_forest_miner`: `_http` (its headers, its Accept-Language, its 2 MB read bound),
`html_text`, `html_links`, `_title`, `page_meta`, `parse_feed`, `youtube_transcript`,
`wayback_snapshot`. This module calls those. The one thing it adds is `fetch_bytes`, which is
`_http` with the decode step removed, because `errors="replace"` destroys a PDF and a shared
text client cannot be asked to return one. Robots is not re-litigated here either: the live
re-probe is `side_channels/seed_miners._robots_still_disallows` and is called through an
optional import, fail-closed; youtube.com's own caption endpoints stay barred by its robots.txt
(measured 2026-08-27) and are never tried -- the transcript route is the keyless mirror rotation
`scripts/fetch_video_transcript.py` already owns.

TRANSLATION IS RECORDED, NEVER PERFORMED. The language heuristic is script ranges only (CJK,
Cyrillic, Arabic, Latin) -- no new dependency, no model, no guess about which of three languages
shares a script. `translated` is always False and `translation_note` names the script and says
the LLM seats do the translating. A silently machine-translated claim cannot be audited back to
its ground, which is the one thing a verbatim capture is for.

    python moat_collectors.py --budget-s 300 --max-sources 20
    python moat_collectors.py --dry-run     # plans the pass, fetches nothing, writes nothing
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deep_forest_miner as dfm  # noqa: E402  (the desk's ONE http client)

from libs.moat import registry as reg  # noqa: E402
from libs.research import lead_schema as ls  # noqa: E402

#: The moat's root. A module global so a test can point the whole store at `tmp_path`; every
#: subdirectory is derived from it at call time rather than frozen at import.
MOAT = _ROOT / "data" / "moat"
REPORT = _DESK / "reports" / "MOAT_COLLECTORS.json"

UNMEASURED = "UNMEASURED"
#: Statuses a source must hold before this module will fetch it. Anything else -- walled,
#: retired, internal, unclassified -- is left alone and counted, never quietly crawled.
ACTIVE_STATUSES: frozenset[str] = frozenset({"active", "candidate-cleared", "candidate_cleared"})
MEDIA_TYPES: tuple[str, ...] = ("html", "pdf", "transcript", "table", "notebook", "chart",
                                "slides")
#: Seconds between two fetches of the same source, matching `deep_forest_miner`'s own pacing.
#: A global so a test with stubbed fetchers spends no wall clock on politeness it is not using.
SLEEP_S = 1.0
FETCH_TIMEOUT_S = 20.0
MAX_BYTES = 8_000_000
MAX_TEXT_CHARS = 400_000
MAX_TABLE_ROWS = 500
MAX_FEED_ITEMS = 12
#: Claims compared against each other for DUPLICATES/CONTRADICTS in one pass. Pairwise work is
#: quadratic; beyond this the pass is a listing and the edges it would draw are noise.
MAX_EDGE_CLAIMS = 400
EDGE_LOOKBACK = 300
#: Alt/caption text carried onto a lead stub, matching `lead_schema.MAX_CLAIM_CHARS`.
MAX_CLAIM_ALT = 2000
#: Near-duplicate and same-topic thresholds on `lead_schema.token_cosine`.
DUP_COSINE = 0.85
TOPIC_COSINE = 0.60

RULE = ("raw captures are immutable and provenance-stamped; a chart is a lead, never evidence; "
        "when something became knowable is stored beside what it said")

#: Registry `sources.kind` (and url extension) -> media type. A kind nobody has written yet is
#: not a refusal: it falls through to the url's extension and then to `html`, and the report says
#: which rule decided. Guessing wrong costs one capture; refusing costs a whole ground.
_KIND_MEDIA: dict[str, str] = {
    "html": "html", "web": "html", "forum": "html", "blog": "html", "news": "html",
    "qa": "html", "competition": "html", "official": "html", "rss": "transcript",
    "pdf": "pdf", "paper": "pdf", "academic": "pdf", "filing": "pdf", "report": "pdf",
    "transcript": "transcript", "video": "transcript", "youtube": "transcript",
    "podcast": "transcript", "audio": "transcript",
    "table": "table", "spreadsheet": "table", "csv": "table", "xlsx": "table",
    "dataset": "table", "data": "table",
    "notebook": "notebook", "ipynb": "notebook", "code": "notebook",
    "chart": "chart", "image": "chart", "screenshot": "chart", "diagram": "chart",
    "slides": "slides", "deck": "slides", "presentation": "slides",
}
_EXT_MEDIA: dict[str, str] = {
    ".pdf": "pdf", ".csv": "table", ".tsv": "table", ".xlsx": "table", ".xls": "table",
    ".ipynb": "notebook", ".png": "chart", ".jpg": "chart", ".jpeg": "chart", ".gif": "chart",
    ".webp": "chart", ".svg": "chart", ".xml": "transcript", ".rss": "transcript",
}
_MEDIA_EXT: dict[str, str] = {"html": "html", "pdf": "pdf", "transcript": "txt", "table": "csv",
                              "notebook": "ipynb", "chart": "bin", "slides": "pdf"}
#: Paths this desk has MEASURED as barred by their host's robots.txt (SS13, 2026-08-27). Never
#: fetched, never retried, and named here so the refusal is auditable rather than folklore.
ROBOTS_BARRED: tuple[tuple[str, str], ...] = (("youtube.com", "/api/"),
                                              ("youtube.com", "/youtubei/"),
                                              ("www.youtube.com", "/api/"),
                                              ("www.youtube.com", "/youtubei/"))

#: SCRIPT ranges, written as escapes so no reviewer has to trust a glyph that renders like its
#: neighbour: kana + CJK ideographs + Hangul, Cyrillic, Arabic, Latin (incl. the extended blocks).
_SCRIPTS: tuple[tuple[str, str], ...] = (
    ("cjk", "[぀-ヿ㐀-䶿一-鿿가-힯]"),
    ("cyrillic", "[Ѐ-ӿԀ-ԯ]"),
    ("arabic", "[؀-ۿݐ-ݿ]"),
    ("latin", "[A-Za-zÀ-ɏ]"),
)
_SCRIPT_RE = {name: re.compile(rx) for name, rx in _SCRIPTS}
_YT_ID = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{6,20})")
_ENCLOSURE = re.compile(r'(?is)<enclosure\b[^>]*url=["\']([^"\']+)["\'][^>]*>')
_PODCAST_TRANSCRIPT = re.compile(r'(?is)<podcast:transcript\b[^>]*url=["\']([^"\']+)["\']')
_IMG_ALT = re.compile(r'(?is)<img\b[^>]*alt=["\']([^"\']{2,300})["\']')


# --------------------------------------------------------------------------- store primitives
def sources_dir() -> Path:
    return MOAT / "sources"


def raw_dir() -> Path:
    return MOAT / "raw_intel"


def normalized_dir() -> Path:
    return MOAT / "normalized_intel"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _slug(source_id: str) -> str:
    """A filesystem name for a source id that may carry anything. Collision-proofed by a short
    hash of the original, so two ids differing only in punctuation never share a directory."""
    raw = str(source_id or "unknown")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")[:48] or "source"
    return f"{safe}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:8]}"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError, PermissionError):
            os.unlink(name)


class ImmutableCaptureError(RuntimeError):
    """A capture path already holds bytes that are not the bytes being written."""


def write_capture(source_id: str, data: bytes, ext: str) -> tuple[Path, str, bool]:
    """Land one raw capture. Returns (path, sha256, created).

    CONTENT-ADDRESSED AND WRITE-ONCE. The name IS the hash, so refetching an unchanged page is a
    no-op that costs one stat call. The file is opened O_EXCL: if it already exists the existing
    bytes are read back and compared, and anything but an exact match RAISES. No caller can pass
    a flag that overwrites, because the only reason a content-addressed file would hold different
    bytes is that the store was corrupted or tampered with, and silently repairing that would
    destroy the record of it.
    """
    sha = hashlib.sha256(data).hexdigest()
    target = raw_dir() / _slug(source_id) / f"{sha}.{ext.lstrip('.') or 'bin'}"
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(target, flags)
    except FileExistsError:
        existing = target.read_bytes()
        if existing == data:
            return target, sha, False
        raise ImmutableCaptureError(
            f"{target} already holds {len(existing)} bytes that are not the {len(data)} bytes "
            "offered; a raw capture is never overwritten") from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return target, sha, True


def detect_script(text: str) -> str:
    """The dominant SCRIPT of a document: cjk, cyrillic, arabic, latin, or UNMEASURED.

    Script ranges only, and deliberately not a language: Chinese, Japanese and Korean share Han,
    and Russian and Bulgarian share Cyrillic. Claiming a language off a character range would be
    a guess dressed as a measurement; the seats that translate can tell them apart and this
    module's job is to say honestly which alphabet the bytes are in.
    """
    body = str(text or "")
    if not body.strip():
        return UNMEASURED
    counts = {name: len(rx.findall(body)) for name, rx in _SCRIPT_RE.items()}
    best = max(counts, key=lambda k: counts[k])
    return best if counts[best] > 0 else UNMEASURED


def translation_note(script: str) -> str:
    if script in ("latin", UNMEASURED):
        return ""
    return (f"text is {script} script and is carried VERBATIM, untranslated: the LLM seats "
            "translate, this collector records -- a silently machine-translated claim cannot be "
            "audited back to its ground")


# --------------------------------------------------------------------------- fetching (reused)
def robots_barred(url: str) -> str:
    """Why this url must not be fetched, or "". The measured hard stops first, then a live
    re-probe through `seed_miners._robots_still_disallows` when it can be imported -- fail
    closed, because an unreachable robots.txt is not consent."""
    low = str(url or "").lower()
    for host, prefix in ROBOTS_BARRED:
        if host in low and prefix in low:
            return f"{host}{prefix} is Disallow in {host}/robots.txt (measured 2026-08-27)"
    return ""


def robots_still_disallows(host: str, user_agent: str = "*") -> bool:
    """The desk's one robots reader, borrowed. True (refused) when it cannot be reached."""
    try:
        from seed_miners import _robots_still_disallows
    except ImportError:
        return True
    try:
        return bool(_robots_still_disallows(host, user_agent))
    except Exception:  # a probe that fails proves nothing; the wall stands
        return True


def fetch_text(url: str, lang: str = "") -> tuple[str, int, str]:
    """`deep_forest_miner._http`, with the status and the failure reported rather than raised.

    Returns (body, http_status, error). The desk's HTTP client lives in that module -- its
    headers, its Accept-Language and its 2 MB read bound -- and this is the only wrapper: a
    second client would be a second crawler with a second set of manners.
    """
    try:
        return dfm._http(url, timeout=FETCH_TIMEOUT_S, lang=lang), 200, ""
    except urllib.error.HTTPError as exc:
        return "", int(exc.code), f"HTTPError {exc.code}"
    except Exception as exc:  # every network failure is a measurement, not a stop
        return "", 0, f"{type(exc).__name__}: {str(exc)[:120]}"


def fetch_bytes(url: str, lang: str = "") -> tuple[bytes, int, str]:
    """`_http` with the decode step removed. A PDF, an image or a spreadsheet cannot survive
    `errors="replace"`, and the shared text client cannot be asked to stop decoding -- so this
    borrows its headers and its bound and returns the body untouched."""
    hdr = {**dfm._UA, "Accept-Language": dfm.accept_language(lang)}
    req = urllib.request.Request(url, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as fh:
            return fh.read(MAX_BYTES), int(getattr(fh, "status", 200) or 200), ""
    except urllib.error.HTTPError as exc:
        return b"", int(exc.code), f"HTTPError {exc.code}"
    except Exception as exc:
        return b"", 0, f"{type(exc).__name__}: {str(exc)[:120]}"


# --------------------------------------------------------------------------- the capture
@dataclass
class Capture:
    """One immutable raw capture and everything read off it WITHOUT reinterpreting it."""

    source_id: str
    url: str
    media_type: str
    sha256: str
    raw_path: str
    created: bool
    fetched_at: str
    http_status: int
    content_length: int
    text: str = ""
    title: str = ""
    knowable_at: str = UNMEASURED
    media_path: str = ""
    lead_stub: bool = False
    unmeasured: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def media_type_of(row: Mapping[str, Any]) -> tuple[str, str]:
    """(media type, which rule decided). Kind first, url extension second, `html` last."""
    kind = str(row.get("kind") or "").strip().lower()
    if kind in _KIND_MEDIA:
        return _KIND_MEDIA[kind], "sources.kind"
    url = str(row.get("url") or "").lower().split("?")[0]
    ext = Path(url).suffix
    if ext in _EXT_MEDIA:
        return _EXT_MEDIA[ext], "url extension"
    if "youtube.com" in url or "youtu.be" in url:
        return "transcript", "url host"
    return "html", "default (a declared source with a web url is a document)"


def _meta(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("meta_json")
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        with suppress(ValueError):
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
    return {}


def _declared_knowable(row: Mapping[str, Any]) -> str:
    """The publish stamp the SOURCE ROW declares, or UNMEASURED. Never `first_seen`, never
    `last_crawled` -- those are when the desk looked, which is a different fact."""
    meta = _meta(row)
    for key in ("published_at", "published_time", "published", "posted_at", "date"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:40]
    return UNMEASURED


def _capture(row: Mapping[str, Any], data: bytes, media_type: str, *, url: str, status: int,
             ext: str | None = None, **fields: Any) -> Capture:
    source_id = str(row.get("source_id") or "unknown")
    path, sha, created = write_capture(source_id, data, ext or _MEDIA_EXT.get(media_type, "bin"))
    return Capture(source_id=source_id, url=url, media_type=media_type, sha256=sha,
                   raw_path=str(path), created=created, fetched_at=_now(), http_status=status,
                   content_length=len(data), **fields)


# --------------------------------------------------------------------------- the collectors
def collect_html(row: Mapping[str, Any], budget_s: float) -> list[Capture]:
    """One page, captured verbatim; text, title and published stamp read with the shared
    helpers. Link-following belongs to the crawler and the deep-forest miner -- a collector's
    job is the immutable capture of the DECLARED document, not a second walk of the web."""
    url = str(row.get("url") or "")
    if budget_s <= 0 or not url:
        return []
    body, status, err = fetch_text(url, str(row.get("language") or ""))
    if not body:
        return [_capture(row, b"", "html", url=url, status=status,
                         unmeasured=err or "empty body")]
    meta = dfm.page_meta(body)
    return [_capture(row, body.encode("utf-8"), "html", url=url, status=status,
                     text=dfm.html_text(body)[:MAX_TEXT_CHARS], title=dfm._title(body),
                     knowable_at=str(meta.get("published_time") or _declared_knowable(row)))]


def _pdf_text(data: bytes) -> tuple[str, str, str]:
    """(text, knowable_at, unmeasured). pypdf when importable; otherwise the capture is KEPT and
    the text is UNMEASURED -- a PDF whose text nobody extracted is still the evidence."""
    try:
        import pypdf
    except ImportError:
        return "", UNMEASURED, "pypdf is not importable: capture kept, text UNMEASURED"
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = [str(p.extract_text() or "") for p in reader.pages[:200]]
        info = reader.metadata or {}
        stamp = str(info.get("/CreationDate") or "") or UNMEASURED
        return "\n".join(pages)[:MAX_TEXT_CHARS], _pdf_date(stamp), ""
    except Exception as exc:  # a malformed PDF is a measurement
        return "", UNMEASURED, f"pypdf failed: {type(exc).__name__}: {str(exc)[:100]}"


def _pdf_date(raw: str) -> str:
    """`D:20260917143000+00'00'` -> an ISO date. Anything else is left UNMEASURED rather than
    coerced: a stamp the desk cannot parse is not a stamp it may invent."""
    m = re.match(r"D?:?(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", str(raw or ""))
    if not m:
        return UNMEASURED
    y, mo, d = m.group(1), m.group(2), m.group(3)
    hh, mi, ss = m.group(4) or "00", m.group(5) or "00", m.group(6) or "00"
    return f"{y}-{mo}-{d}T{hh}:{mi}:{ss}"


def collect_pdf(row: Mapping[str, Any], budget_s: float, media_type: str = "pdf") -> list[Capture]:
    """The PDF bytes, kept whole. `slides` is the same capture with the deck's own media_type --
    a slide deck IS a PDF and pretending otherwise would fork the store for no gain."""
    url = str(row.get("url") or "")
    if budget_s <= 0 or not url:
        return []
    data, status, err = fetch_bytes(url, str(row.get("language") or ""))
    if not data:
        return [_capture(row, b"", media_type, url=url, status=status, ext="pdf",
                         unmeasured=err or "empty body")]
    text, stamp, note = _pdf_text(data)
    cap = _capture(row, data, media_type, url=url, status=status, ext="pdf", text=text,
                   title=str(row.get("source_id") or ""), unmeasured=note,
                   knowable_at=stamp if stamp != UNMEASURED else _declared_knowable(row))
    if media_type == "slides":
        cap.media_path = cap.raw_path
    return [cap]


def collect_slides(row: Mapping[str, Any], budget_s: float) -> list[Capture]:
    return collect_pdf(row, budget_s, media_type="slides")


def collect_transcript(row: Mapping[str, Any], budget_s: float) -> list[Capture]:
    """A spoken-word ground: YouTube captions where a route is allowed, podcasts through the
    feed. YOUTUBE'S OWN CAPTION ENDPOINTS ARE NEVER TRIED -- `/api/` and `/youtubei/` are
    Disallow under `User-agent: *` in youtube.com/robots.txt (measured 2026-08-27, SS13), so the
    only route is the keyless mirror rotation `scripts/fetch_video_transcript.py` owns, reached
    through `deep_forest_miner.youtube_transcript`. A podcast feed gives enclosure METADATA and
    the transcript only when the feed itself carries one; audio is never transcribed here."""
    url = str(row.get("url") or "")
    if budget_s <= 0 or not url:
        return []
    barred = robots_barred(url)
    if barred:
        return [_capture(row, b"", "transcript", url=url, status=0, ext="txt", unmeasured=barred)]
    vid = _YT_ID.search(url)
    if vid and ("youtube" in url.lower() or "youtu.be" in url.lower()):
        text, why = dfm.youtube_transcript(vid.group(1), str(row.get("language") or "en") or "en")
        data = text.encode("utf-8") if text else b""
        return [_capture(row, data, "transcript", url=url, status=200 if text else 0, ext="txt",
                         text=text[:MAX_TEXT_CHARS], title=f"youtube:{vid.group(1)}",
                         knowable_at=_declared_knowable(row),
                         unmeasured="" if text else (why or "no caption track"))]
    xml, status, err = fetch_text(url, str(row.get("language") or ""))
    if not xml:
        return [_capture(row, b"", "transcript", url=url, status=status, ext="txt",
                         unmeasured=err or "empty feed")]
    items = dfm.parse_feed(xml)[:MAX_FEED_ITEMS]
    enclosures = _ENCLOSURE.findall(xml)[:MAX_FEED_ITEMS]
    tscript = _PODCAST_TRANSCRIPT.findall(xml)[:MAX_FEED_ITEMS]
    lines = [f"{i.get('title', '')}\n{i.get('summary', '')}" for i in items]
    text = "\n\n".join(lines)[:MAX_TEXT_CHARS]
    published = next((str(i.get("published") or "") for i in items if i.get("published")), "")
    return [_capture(row, xml.encode("utf-8"), "transcript", url=url, status=status, ext="xml",
                     text=text, title=items[0].get("title", "") if items else "",
                     knowable_at=published or _declared_knowable(row),
                     unmeasured="" if tscript else "feed carries no podcast:transcript; "
                                                   "enclosure metadata only, audio not "
                                                   "transcribed here",
                     extra={"enclosures": enclosures, "transcripts": tscript,
                            "feed_items": len(items)})]


def _csv_text(data: bytes) -> tuple[str, str]:
    """CSV/TSV rows as text WITH THE HEADER KEPT. A table stripped of its header is a matrix of
    numbers nobody can name, and a claim extracted from one would be uncheckable."""
    body = data.decode("utf-8", errors="replace")
    rows = [r for r in body.splitlines() if r.strip()]
    if not rows:
        return "", "table has no rows"
    kept = rows[:MAX_TABLE_ROWS + 1]
    note = "" if len(rows) <= MAX_TABLE_ROWS + 1 else (
        f"{len(rows) - 1} data rows, {MAX_TABLE_ROWS} kept in the normalised text; the raw "
        "capture holds all of them")
    return "\n".join(kept)[:MAX_TEXT_CHARS], note


def _xlsx_text(data: bytes) -> tuple[str, str]:
    """XLSX through pandas when its engine is installed. It is NOT on this box (openpyxl absent,
    measured), so the capture is kept and the rows are UNMEASURED rather than silently empty."""
    try:
        import pandas as pd
    except ImportError:
        return "", "pandas/openpyxl not importable: capture kept, rows UNMEASURED"
    try:
        frame = pd.read_excel(io.BytesIO(data), nrows=MAX_TABLE_ROWS)
    except Exception as exc:
        return "", f"read_excel failed: {type(exc).__name__}: {str(exc)[:100]}"
    header = ",".join(str(c) for c in frame.columns)
    lines = [",".join("" if v is None else str(v) for v in rec)
             for rec in frame.itertuples(index=False, name=None)]
    return "\n".join([header, *lines])[:MAX_TEXT_CHARS], ""


def collect_table(row: Mapping[str, Any], budget_s: float) -> list[Capture]:
    """A spreadsheet or delimited file, header preserved."""
    url = str(row.get("url") or "")
    if budget_s <= 0 or not url:
        return []
    data, status, err = fetch_bytes(url, str(row.get("language") or ""))
    if not data:
        return [_capture(row, b"", "table", url=url, status=status, ext="csv",
                         unmeasured=err or "empty body")]
    ext = Path(url.split("?")[0]).suffix.lower()
    text, note = (_xlsx_text(data) if ext in (".xlsx", ".xls") else _csv_text(data))
    return [_capture(row, data, "table", url=url, status=status, ext=(ext or ".csv").lstrip("."),
                     text=text, title=Path(url.split("?")[0]).name, unmeasured=note,
                     knowable_at=_declared_knowable(row))]


def _notebook_text(data: bytes) -> tuple[str, str, str]:
    """(text, knowable_at, unmeasured) for a .ipynb: markdown and code cells, in order, labelled.
    Outputs are deliberately NOT read -- a stored output is a number from a run nobody can date."""
    try:
        doc = json.loads(data.decode("utf-8", errors="replace"))
    except ValueError as exc:
        return "", UNMEASURED, f"not JSON: {str(exc)[:80]}"
    if not isinstance(doc, dict):
        return "", UNMEASURED, "notebook is not an object"
    parts: list[str] = []
    for cell in doc.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        kind = str(cell.get("cell_type") or "")
        if kind not in ("markdown", "code"):
            continue
        src = cell.get("source")
        body = "".join(src) if isinstance(src, list) else str(src or "")
        if body.strip():
            parts.append(f"[{kind}]\n{body.strip()}")
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    stamp = ""
    for key in ("date", "created", "papermill"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            stamp = value.strip()[:40]
            break
    note = "" if parts else "notebook carries no markdown or code cells"
    return "\n\n".join(parts)[:MAX_TEXT_CHARS], stamp or UNMEASURED, note


def collect_notebook(row: Mapping[str, Any], budget_s: float) -> list[Capture]:
    url = str(row.get("url") or "")
    if budget_s <= 0 or not url:
        return []
    data, status, err = fetch_bytes(url, str(row.get("language") or ""))
    if not data:
        return [_capture(row, b"", "notebook", url=url, status=status, ext="ipynb",
                         unmeasured=err or "empty body")]
    text, stamp, note = _notebook_text(data)
    return [_capture(row, data, "notebook", url=url, status=status, ext="ipynb", text=text,
                     title=Path(url.split("?")[0]).name, unmeasured=note,
                     knowable_at=stamp if stamp != UNMEASURED else _declared_knowable(row))]


def collect_chart(row: Mapping[str, Any], budget_s: float) -> list[Capture]:
    """An image: captured whole, normalised to a LEAD STUB.

    NOTHING HERE READS A PIXEL. The stub is the `media_path` plus the alt/caption text the SOURCE
    wrote, and nothing else: no level estimated off an axis, no series digitised, no number
    invented. A chart is where to look; the desk's own bars are what happened. Every claim cut
    out of a stub carries `kind="lead_stub"` into the registry so no downstream reader can
    promote a picture to evidence by accident.
    """
    url = str(row.get("url") or "")
    if budget_s <= 0 or not url:
        return []
    data, status, err = fetch_bytes(url, str(row.get("language") or ""))
    meta = _meta(row)
    alt = str(meta.get("alt") or meta.get("caption") or "").strip()
    ext = (Path(url.split("?")[0]).suffix or ".bin").lstrip(".")
    if not data:
        return [_capture(row, b"", "chart", url=url, status=status, ext=ext, lead_stub=True,
                         text=alt[:MAX_CLAIM_ALT], unmeasured=err or "empty body")]
    cap = _capture(row, data, "chart", url=url, status=status, ext=ext, lead_stub=True,
                   text=alt[:MAX_CLAIM_ALT], title=Path(url.split("?")[0]).name,
                   knowable_at=_declared_knowable(row),
                   unmeasured="" if alt else "the source published no alt or caption text: the "
                                             "image is kept and says nothing")
    cap.media_path = cap.raw_path
    return [cap]


COLLECTORS: dict[str, Callable[[Mapping[str, Any], float], list[Capture]]] = {
    "html": collect_html, "pdf": collect_pdf, "transcript": collect_transcript,
    "table": collect_table, "notebook": collect_notebook, "chart": collect_chart,
    "slides": collect_slides,
}


# --------------------------------------------------------------------------- normalisation
def normalise(cap: Capture) -> dict[str, Any]:
    """One capture as a normalised document. Dedupe is by CONTENT SHA -- the same bytes are the
    same document however many grounds serve them."""
    script = detect_script(cap.text)
    doc_id = ls.doc_id_of(cap.source_id, cap.url, cap.title)
    return {
        "doc_id": doc_id,
        "source_id": cap.source_id,
        "capture_sha": cap.sha256,
        "media_type": cap.media_type,
        "language": script,
        "text": cap.text,
        "published_at": cap.knowable_at,
        "knowable_at": cap.knowable_at or UNMEASURED,
        "translated": False,
        "translation_note": translation_note(script),
        "provenance": {"fetched_at": cap.fetched_at, "url": cap.url,
                       "fetcher": "deep_forest_miner._http" if cap.media_type == "html"
                                  else "moat_collectors.fetch_bytes",
                       "http_status": cap.http_status, "content_length": cap.content_length,
                       "raw_path": cap.raw_path},
        "media_path": cap.media_path,
        "lead_stub": cap.lead_stub,
        "quantitative": False if cap.lead_stub else None,
        "title": cap.title,
        "unmeasured": cap.unmeasured,
        "extra": cap.extra,
        "rule": RULE,
    }


def write_document(doc: Mapping[str, Any]) -> tuple[Path, bool]:
    """Land a normalised document. Returns (path, created); an existing sha is a no-op."""
    path = (normalized_dir() / _slug(str(doc["source_id"])) / f"{doc['capture_sha']}.json")
    if path.exists():
        return path, False
    _atomic_json(path, dict(doc))
    return path, True


def write_source_manifest(row: Mapping[str, Any], extra: Mapping[str, Any] | None = None) -> Path:
    """The source's own manifest, mirroring the registry row so the store is readable without
    the database open."""
    path = sources_dir() / f"{_slug(str(row.get('source_id') or 'unknown'))}.json"
    _atomic_json(path, {**{k: row[k] for k in row if not str(k).startswith("_")},
                        **dict(extra or {}), "manifest_written_at": _now()})
    return path


# --------------------------------------------------------------------------- claims and edges
def _instruments(text: str) -> list[str]:
    """Instrument tokens a claim names, through the lead schema's own vocabulary."""
    lead = ls.from_intelligence_row({"claim": text, "source": "moat_collectors"})
    return list(lead.instruments) if lead else []


def claims_of(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The claim-bearing sentences of one normalised document, in document order.

    A LEAD STUB's sentences are claims too -- they are what the chart's caption SAID -- but they
    are stamped `lead_stub` so nothing downstream can read a picture as a measurement.
    """
    text = str(doc.get("text") or "")
    kind = "lead_stub" if doc.get("lead_stub") else "claim"
    out: list[dict[str, Any]] = []
    for sentence in ls.claims_from_text(text):
        out.append({
            "claim_id": ls.lead_id_of(str(doc["source_id"]), sentence),
            "doc_id": str(doc["doc_id"]),
            "source_id": str(doc["source_id"]),
            "text": sentence,
            "language": str(doc.get("language") or UNMEASURED),
            "knowable_at": str(doc.get("knowable_at") or UNMEASURED),
            "instruments": _instruments(sentence),
            "kind": kind,
            "media_type": str(doc.get("media_type") or ""),
            "provenance": dict(doc.get("provenance") or {}),
        })
    return out


def _edges(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, str]]:
    """DUPLICATES and CONTRADICTS, by the lead schema's OWN rules.

    CONTRADICTS IS TESTED FIRST, and that order is the whole point. "gold rises into the London
    fix" and "gold falls into the London fix" share every token but one: a cosine test alone
    reads them as the SAME claim and collapses them, destroying the single most valuable fact in
    a corpus -- that two grounds disagree. So an opposite STATED direction (both non-zero,
    majority-counted by `direction_of`) on the same topic is a contradiction no matter how
    similar the bag of words, and duplication is only what is left over.

    DUPLICATES: the same `dedupe_key` (the normalised claim plus its instruments) or a token
    cosine over `DUP_COSINE`. CONTRADICTS: cosine over `TOPIC_COSINE` with opposite directions --
    a tie is never a contradiction, because "buy the dip and sell the rip" is not a directional
    claim and manufacturing edges out of balanced prose would make agreement unmeasurable.
    """
    prepared = []
    for r in rows[:MAX_EDGE_CLAIMS]:
        text = str(r.get("text") or "")
        lead = ls.Lead(lead_id=ls.lead_id_of(str(r.get("source_id") or ""), text), kind="other",
                       source_id=str(r.get("source_id") or ""), url_or_ref="", seen_at="",
                       knowable_at="", language="", claim_text=text,
                       doc_id=str(r.get("doc_id") or ""), claim_index=0,
                       instruments=[str(s) for s in (r.get("instruments") or [])])
        prepared.append((str(r.get("claim_id") or ""), ls.dedupe_key(lead), ls.token_set(text),
                         ls.direction_of(text)))
    out: list[tuple[str, str, str]] = []
    for i in range(len(prepared)):
        cid_a, key_a, tok_a, dir_a = prepared[i]
        for j in range(i + 1, len(prepared)):
            cid_b, key_b, tok_b, dir_b = prepared[j]
            if not cid_a or not cid_b or cid_a == cid_b:
                continue
            cos = ls.token_cosine(tok_a, tok_b)
            if cos >= TOPIC_COSINE and dir_a and dir_b and dir_a != dir_b:
                out.append((cid_a, cid_b, "CONTRADICTS"))
            elif key_a == key_b or cos >= DUP_COSINE:
                out.append((cid_a, cid_b, "DUPLICATES"))
    return out


def record_claims(conn: Any, rows: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    """Claims and their edges into the canonical registry. Returns (claims, edges) WRITTEN."""
    written = 0
    for r in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO claims(claim_id, created_at, doc_id, source_id, text, "
            "language, knowable_at, instruments_json, kind, media_type, provenance_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (r["claim_id"], _now(), r["doc_id"], r["source_id"], r["text"], r["language"],
             r["knowable_at"], json.dumps(r["instruments"], sort_keys=True),
             r["kind"], r["media_type"],
             json.dumps(r["provenance"], sort_keys=True, default=str)))
        written += int(cur.rowcount or 0)
    known = [dict(x) for x in conn.execute(
        "SELECT claim_id, doc_id, source_id, text, instruments_json FROM claims "
        "ORDER BY created_at DESC LIMIT ?", (EDGE_LOOKBACK,))]
    for k in known:
        with suppress(ValueError, TypeError):
            k["instruments"] = json.loads(k.get("instruments_json") or "[]")
    # NEW CLAIMS FIRST. `_edges` truncates at MAX_EDGE_CLAIMS, and truncating away the claims
    # this pass just wrote would draw edges between old rows and nothing else.
    pool: dict[str, Mapping[str, Any]] = {}
    for r in [*rows, *known]:
        pool.setdefault(str(r["claim_id"]), r)
    edges = 0
    for a, b, rel in _edges(list(pool.values())):
        cur = conn.execute(
            "INSERT OR IGNORE INTO claim_edges(from_claim, to_claim, relation, created_at) "
            "VALUES(?,?,?,?)", (a, b, rel, _now()))
        edges += int(cur.rowcount or 0)
    conn.commit()
    return written, edges


# --------------------------------------------------------------------------- the pass
def choose_sources(conn: Any, max_sources: int) -> list[dict[str, Any]]:
    """The pass's grounds: active/candidate-cleared, best `source_yield` ROI first, ties broken
    by the OLDEST last_crawled -- so a ground the desk has never touched (no stamp at all) sorts
    ahead of one it has already mined to nothing."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM sources")]
    yields = {str(r["source_id"]): dict(r)
              for r in conn.execute("SELECT * FROM source_yield")}
    live = [r for r in rows if str(r.get("status") or "").strip().lower() in ACTIVE_STATUSES]
    for r in live:
        r["_roi"] = source_roi(yields.get(str(r.get("source_id"))))
    live.sort(key=lambda r: (tuple(-v for v in r["_roi"]),
                             str(r.get("last_crawled") or "")))
    return live[:max(0, int(max_sources))]


def source_roi(y: Mapping[str, Any] | None) -> tuple[float, float, float]:
    """(independent survivors, survivors, claims) per compute second -- a LEXICOGRAPHIC order.

    NOT A WEIGHTED SUM, and the difference is the whole rule. Any single number lets a ground buy
    rank with VOLUME: ten thousand claims over a hundred seconds outscores one independent
    survivor at every weighting a reader would call reasonable, and the desk would then spend its
    budget on whichever forest is chattiest. Lexicographic means claims break ties between
    grounds with the same survivor rate and can never overturn one.

    A source with NO yield row is all zeros and is not penalised further: it has never been
    measured, and the `last_crawled` tie-break puts a never-crawled ground ahead of one already
    mined to nothing, which is where an unmeasured ground belongs.
    """
    if not y:
        return (0.0, 0.0, 0.0)
    compute = max(float(y.get("compute_s") or 0.0), 1.0)
    return (float(y.get("independent_survivors") or 0) / compute,
            float(y.get("survivors") or 0) / compute,
            float(y.get("claims") or 0) / compute)


def run(*, budget_s: float = 300.0, max_sources: int = 20, dry_run: bool = False,
        conn: Any = None) -> dict[str, Any]:
    """One pass: choose, capture, normalise, claim. Returns the report payload."""
    started = time.monotonic()
    close_after = conn is None
    c = conn if conn is not None else reg.connect()
    report: dict[str, Any] = {
        "at": _now(), "moat_root": str(MOAT), "budget_s": float(budget_s),
        "max_sources": int(max_sources), "dry_run": bool(dry_run),
        "sources_visited": 0, "captures_new": 0, "captures_duplicate": 0,
        "by_media_type": {}, "documents_normalised": 0, "claims_written": 0, "claim_edges": 0,
        "knowable_at_measured_share": None, "languages": {}, "refused": [],
        "unmeasured": {"by_source": {}, "knowable_at": None}, "planned": [],
        "budget_stopped": False, "rule": RULE,
    }
    try:
        chosen = choose_sources(c, max_sources)
        claims: list[dict[str, Any]] = []
        knowable_measured = 0
        for row in chosen:
            media, why = media_type_of(row)
            report["planned"].append({"source": str(row.get("source_id")), "media_type": media,
                                      "decided_by": why,
                                      "roi": [round(v, 6) for v in row["_roi"]],
                                      "last_crawled": row.get("last_crawled") or UNMEASURED})
            if dry_run:
                continue
            left = budget_s - (time.monotonic() - started)
            if left <= 0:
                report["budget_stopped"] = True
                break
            # EVERY CHOSEN GROUND IS STAMPED, visited or refused. A ground that is walled and
            # keeps sorting to the front of the rotation would starve every ground behind it;
            # the refusal is still named in `refused` on every pass, so the stamp hides nothing.
            c.execute("UPDATE sources SET last_crawled=? WHERE source_id=?",
                      (_now(), str(row.get("source_id"))))
            url = str(row.get("url") or "")
            barred = robots_barred(url)
            if not url:
                report["refused"].append({"source": str(row.get("source_id")),
                                          "why": "source row carries no url"})
                continue
            if barred:
                report["refused"].append({"source": str(row.get("source_id")), "why": barred})
                continue
            collector = COLLECTORS.get(media)
            if collector is None:
                report["refused"].append({"source": str(row.get("source_id")),
                                          "why": f"no collector for media type {media!r}"})
                continue
            report["sources_visited"] += 1
            try:
                caps = collector(row, left)
            except ImmutableCaptureError as exc:
                report["refused"].append({"source": str(row.get("source_id")),
                                          "why": f"immutable capture refused: {exc}"})
                caps = []
            except Exception as exc:  # one bad ground never ends the pass
                report["refused"].append({
                    "source": str(row.get("source_id")),
                    "why": f"{type(exc).__name__}: {str(exc)[:160]}"})
                caps = []
            for cap in caps:
                report["captures_new" if cap.created else "captures_duplicate"] += 1
                report["by_media_type"][cap.media_type] = \
                    report["by_media_type"].get(cap.media_type, 0) + 1
                if cap.unmeasured:
                    report["unmeasured"]["by_source"].setdefault(
                        cap.source_id, []).append(cap.unmeasured)
                doc = normalise(cap)
                _, created = write_document(doc)
                report["languages"][doc["language"]] = \
                    report["languages"].get(doc["language"], 0) + 1
                if doc["knowable_at"] != UNMEASURED:
                    knowable_measured += 1
                if created:
                    report["documents_normalised"] += 1
                    claims.extend(claims_of(doc))
            write_source_manifest(row, {"media_type": media, "captures": len(caps)})
            if SLEEP_S > 0:
                time.sleep(SLEEP_S)
        if not dry_run and claims:
            written, edges = record_claims(c, claims)
            report["claims_written"], report["claim_edges"] = written, edges
        if not dry_run:
            c.commit()
        total = report["captures_new"] + report["captures_duplicate"]
        report["knowable_at_measured_share"] = (None if total == 0
                                                else round(knowable_measured / total, 4))
        if total == 0:
            report["unmeasured"]["knowable_at"] = (
                "no captures this pass: the share is UNMEASURED, not 0.0")
        report["seconds"] = round(time.monotonic() - started, 2)
        return report
    finally:
        if close_after:
            c.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--max-sources", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true",
                    help="plan the pass and print it; fetch nothing, write nothing")
    ap.add_argument("--report", default=str(REPORT))
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, max_sources=a.max_sources, dry_run=a.dry_run)
    if not a.dry_run:
        _atomic_json(Path(a.report), doc)
    print(json.dumps({k: v for k, v in doc.items() if k != "planned"}, indent=1, default=str))
    if a.dry_run:
        for p in doc["planned"]:
            print(f"  PLAN {p['source']:<28} {p['media_type']:<11} roi={p['roi']}")
        print("  (dry run: nothing fetched, nothing written)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
