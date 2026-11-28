#!/usr/bin/env python3
"""LIVE PRESS-CONFERENCE SPEECH-TO-TEXT: a policy press conference's tone, minute by minute.

WHAT IT DOES. During a central bank's scheduled press conference it pulls the bank's OWN directly
hosted media (an HLS stream while live, a media file once recorded), transcribes it with a LOCAL
speech model, scores each minute's words with the desk's existing signed lexicon
(`libs.research.event_factors.tag`, factor `monetary_tone`: +1 hawkish ... -1 dovish), and writes
one row per minute into `data/intelligence/presser_stt/`, a news seat that
`news_event_stream.py` reads. The rows are RESEARCH INPUT ONLY: nothing here sizes, caps, vetoes
or shrinks, no allocator fraction is written, and no language model decides anything -- the
score is a deterministic lexicon count over the transcript.

TERMS FIRST, AND THE REGISTRY IS THE VERDICT. `SOURCES` records, per bank, what was read on
2026-11-18 (robots.txt and the published terms) and the verdict that reading forces:

  * ALLOWED              -- robots allow the media path, the terms allow automated commercial
                            research use, and the media is a file or stream on the bank's own host.
  * HELD_UNTIL_RELEASED  -- a 401/403/451/WAF answer, an unreadable robots.txt or unreadable terms.
                            Robots and terms fail CLOSED; a human edit of this table releases it.
  * REFUSED              -- robots disallow the media path, the terms are non-commercial only, the
                            media sits on a refused host (YouTube, never contacted, no mirrors), or
                            the bank is refused outright (BoJ).

ON 2026-11-18 NO SOURCE IS ALLOWED, so the box contacts nothing: every press conference is reported
with its source's reason, and the per-minute rows stay at zero. That is the measurement, not a
fault (L1.28a). A source moves to ALLOWED only by an edit here that cites the reading.

EVEN AN ALLOWED SOURCE IS GATED ON EVERY REQUEST: `refused_hosts.refusal` first (and on every
redirect hop), then robots.txt for the exact path with this module's honest user agent -- 404/410
means no rules, 401/403 means disallow everything, anything else unreadable is a refusal. An HTTP
401/403/451 or a WAF page on the media itself parks the source as HELD_UNTIL_RELEASED in the report.

THE MODEL IS LOCAL AND NEVER INSTALLED HERE. `faster_whisper` is imported lazily, inside
`transcribe`, with `local_files_only=True`; absent package or absent model weights make the pass
UNMEASURED with the reason, never a crash. Installing them is the box task installer's job
(`desks/mt5/scripts/install_presser_stt_task.ps1`), the only money-path file of this build.

THE CLOCKS. Hourly leg `presser_stt` (`--plan`): reads the central-bank calendars the desk holds
(FOMC in `data/event_calendar.json`, Bank of Canada in `desks/mt5/data/calendars/`), names the
next press-conference windows and their source verdicts, checks the model, and writes
`reports/PRESSER_STT.json`. Box task `MT5-PresserSTT` (`--watch`, every 5 minutes): when a window
is open and its source is ALLOWED, captures the live stream until the window closes; otherwise it
writes the same report and exits in well under a second.

    python research/presser_stt.py --plan
    python research/presser_stt.py --watch
    python research/presser_stt.py --media FILE --bank fed --started-at 2026-12-09T19:30:00Z
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.refused_hosts import opener as refusing_opener  # noqa: E402
from libs.data.refused_hosts import refusal  # noqa: E402

UNMEASURED = "UNMEASURED"
ALLOWED, HELD, REFUSED = "ALLOWED", "HELD_UNTIL_RELEASED", "REFUSED"
UA = "quant-desk-presser/1.0 (research; robots-gated; official central-bank media only)"

SEAT = _DESK / "data" / "intelligence" / "presser_stt"
REPORT = _DESK / "reports" / "PRESSER_STT.json"
FOMC_CALENDAR = _ROOT / "data" / "event_calendar.json"
BOC_CALENDAR = _DESK / "data" / "calendars" / "boc_policy_rate.json"
MODEL_ENV = "QUANT_WHISPER_MODEL_DIR"
MODEL_DEFAULT = Path(r"C:\opt\whisper\models\small") if os.name == "nt" else (
    _DESK / "data" / "models" / "whisper-small")
MAX_MEDIA_BYTES = 400_000_000
WINDOW_LEAD = timedelta(minutes=5)

#: THE SOURCE REGISTRY. One row per bank; `reading` is what was actually read, `verdict` what it
#: forces. `media_url` is a directly hosted official stream/file, set only when one is verified.
SOURCES: dict[str, dict[str, Any]] = {
    "fed": {
        "bank": "Federal Reserve",
        "page": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "verdict": HELD, "media_url": None,
        "reading": ("robots.txt answered a client error (4xx) to an automated read on 2026-11-18, "
                    "and so did the website-policies page; robots fail closed. The presser page "
                    "loads its player by script and names no media file. Content is US-Government "
                    "work, but an unreadable robots.txt is not permission."),
    },
    "ecb": {
        "bank": "European Central Bank",
        "page": "https://www.ecb.europa.eu/press/pressconf/html/index.en.html",
        "verdict": REFUSED, "media_url": None,
        "reading": ("robots.txt (read 2026-11-18) disallows "
                    "/press/tvservices/webcast/shared/video/ for every agent: the ECB's own "
                    "press-conference video path."),
    },
    "boe": {
        "bank": "Bank of England",
        "page": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes",
        "verdict": REFUSED, "media_url": None,
        "reading": ("robots.txt allows; the legal page (read 2026-11-18) permits use only for "
                    "personal or internal NON-COMMERCIAL purposes, commercial re-use by request. "
                    "Non-commercial-only terms are refused, as BIS speech rows are."),
    },
    "rba": {
        "bank": "Reserve Bank of Australia",
        "page": "https://www.rba.gov.au/media-releases/",
        "verdict": HELD, "media_url": None,
        "reading": ("robots.txt (read 2026-11-18) disallows /assets/ and /media/image-library/; no "
                    "directly hosted press-conference media file was verified outside them, and "
                    "the terms were not read. Held until a media path and terms are read."),
    },
    "boc": {
        "bank": "Bank of Canada",
        "page": "https://www.bankofcanada.ca/press/speeches/webcasts/",
        "verdict": REFUSED, "media_url": None,
        "reading": ("Terms allow reuse with credit but grant nothing for third-party content. The "
                    "Oct-2026 press-conference page embeds YouTube video (refused host, never "
                    "contacted) and audio on video.isilive.ca, a vendor whose robots.txt refused "
                    "the read (2026-11-18). No media on bankofcanada.ca itself."),
    },
    "snb": {
        "bank": "Swiss National Bank",
        "page": "https://www.snb.ch/en/",
        "verdict": HELD, "media_url": None,
        "reading": ("robots.txt allows all (read 2026-11-18); the legal notice answered a client "
                    "error, so the terms are unread and fail closed; no direct media verified."),
    },
    "rbnz": {
        "bank": "Reserve Bank of New Zealand",
        "page": "https://www.rbnz.govt.nz/",
        "verdict": REFUSED, "media_url": None,
        "reading": ("robots.txt (read 2026-11-18) publishes content signals limiting use to search "
                    "and reference and refusing AI training; transcribing for trading research is "
                    "outside both, so the stricter reading governs."),
    },
    "norges": {
        "bank": "Norges Bank",
        "page": "https://video.norges-bank.no/",
        "verdict": HELD, "media_url": None,
        "reading": ("robots.txt allows (crawl-delay 5); the disclaimer allows copies with source "
                    "quoted. But rate-decision videos are served by a third-party vendor "
                    "(Brightcove players and CDN), not the bank's host, and that vendor's terms "
                    "were not read. Held until a bank-hosted file is verified."),
    },
    "riksbank": {
        "bank": "Sveriges Riksbank",
        "page": "https://www.riksbank.se/en-gb/",
        "verdict": HELD, "media_url": None,
        "reading": ("robots.txt allows the site except office files and query URLs (read "
                    "2026-11-18); terms and the press-conference media host were not read."),
    },
    "boj": {
        "bank": "Bank of Japan", "page": "",
        "verdict": REFUSED, "media_url": None,
        "reading": "Bank of Japan is refused for every automated fetch by standing ruling.",
    },
}

#: Press-conference offsets from the calendar's announcement stamp, and their declared lengths.
PRESSER_OFFSET = {"fed": timedelta(minutes=30), "boc": timedelta(minutes=60)}
PRESSER_LENGTH = {"fed": timedelta(minutes=70), "boc": timedelta(minutes=60)}
CALENDAR_GAPS = {b: f"no central-bank calendar for {SOURCES[b]['bank']} is held on this desk"
                 for b in SOURCES if b not in PRESSER_OFFSET and b != "boj"}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ============================================================================= the calendar
def windows(now: datetime | None = None, *, fomc: Path | None = None,
            boc: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Every press-conference window the held calendars know, and what they cannot say."""
    notes: list[str] = []
    out: list[dict[str, Any]] = []
    doc = _read_json(fomc or FOMC_CALENDAR)
    if isinstance(doc, dict):
        for ev in doc.get("events") or []:
            if isinstance(ev, dict) and "FOMC" in str(ev.get("name")):
                with_ts = _parse(ev.get("utc"))
                if with_ts:
                    out.append(_window("fed", with_ts))
    else:
        notes.append(f"{fomc or FOMC_CALENDAR} unreadable: FOMC windows {UNMEASURED}")
    doc = _read_json(boc or BOC_CALENDAR)
    if isinstance(doc, dict) and isinstance(doc.get("dates"), dict):
        from zoneinfo import ZoneInfo
        try:
            tz = ZoneInfo(str(doc.get("tz") or "America/Toronto"))
        except Exception:                                 # pragma: no cover - tzdata absent
            tz = None
        for day, hhmm in doc["dates"].items():
            if tz is None:
                notes.append(f"time zone {doc.get('tz')} unavailable: BoC windows {UNMEASURED}")
                break
            try:
                local = datetime.fromisoformat(f"{day}T{hhmm}").replace(tzinfo=tz)
            except ValueError:
                continue
            out.append(_window("boc", local.astimezone(UTC)))
    else:
        notes.append(f"{boc or BOC_CALENDAR} unreadable: BoC windows {UNMEASURED}")
    notes.extend(f"{b}: {why}: its windows are {UNMEASURED}" for b, why in CALENDAR_GAPS.items())
    out.sort(key=lambda w: w["starts_at"])
    return out, notes


def _parse(value: Any) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


def _window(bank: str, announced: datetime) -> dict[str, Any]:
    start = announced + PRESSER_OFFSET[bank]
    return {"bank": bank, "announced_at": _iso(announced), "starts_at": _iso(start),
            "ends_at": _iso(start + PRESSER_LENGTH[bank]),
            "verdict": SOURCES[bank]["verdict"]}


def open_window(wins: Iterable[Mapping[str, Any]], now: datetime) -> dict[str, Any] | None:
    for w in wins:
        start, end = _parse(w["starts_at"]), _parse(w["ends_at"])
        if start and end and start - WINDOW_LEAD <= now <= end:
            return dict(w)
    return None


# ============================================================================= the fetch law
_ROBOTS: dict[str, urllib.robotparser.RobotFileParser | str] = {}
#: host -> when a 429 on its robots.txt stops holding it. A 429 is a TIMED hold, like the fetch
#: law's: the host asked us to wait, it did not publish rules, and it is asked again after a day.
_ROBOTS_HELD_UNTIL: dict[str, datetime] = {}
ROBOTS_429_HOLD = timedelta(hours=24)
_HTML_HEAD = ("<html", "<!doctype")


def _robots_body_is_rules(content_type: str, body: bytes) -> bool:
    """A 200 is RULES only as text/plain (or no type) whose body is not an HTML page. A WAF or
    soft-404 page served as 200 would otherwise parse as 'no rules' and read as permission."""
    ctype = content_type.split(";")[0].strip().lower()
    if ctype and ctype != "text/plain":
        return False
    head = body[:512].decode("utf-8", errors="replace").lstrip().lower()
    return not head.startswith(_HTML_HEAD)


def _robots_for(scheme: str, host: str, open_url: Callable[..., Any],
                now: Callable[[], datetime] | None = None
                ) -> urllib.robotparser.RobotFileParser | str:
    """The host's robots rules, or why they are unread (which the gate turns into HELD).

    TODO: switch to libs/data/robots_body once #1343 is on LIVE; this is the same fail-closed
    reading, kept local until then."""
    key = f"{scheme}://{host}"
    clock = now or _now
    until = _ROBOTS_HELD_UNTIL.get(key)
    if until is not None:
        if clock() < until:
            return f"robots.txt answered HTTP 429; held until {_iso(until)}"
        _ROBOTS_HELD_UNTIL.pop(key, None)
    if key in _ROBOTS:
        return _ROBOTS[key]
    rp = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(f"{key}/robots.txt", headers={"User-Agent": UA})
    out: urllib.robotparser.RobotFileParser | str
    try:
        with open_url(req, timeout=15.0) as r:
            headers = getattr(r, "headers", None)
            ctype = str(headers.get("Content-Type") or "") if headers is not None else ""
            body = r.read(500_000)
        if _robots_body_is_rules(ctype, body):
            rp.parse(body.decode("utf-8", errors="replace").splitlines())
            out = rp
        else:
            out = (f"robots.txt unreadable (HTTP 200 as {ctype or 'no type'} with an HTML or "
                   "non-text body: a WAF or soft-404 page is not rules)")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            held = clock() + ROBOTS_429_HOLD
            _ROBOTS_HELD_UNTIL[key] = held
            return f"robots.txt answered HTTP 429; held until {_iso(held)}"
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


def gate(url: str, *, open_url: Callable[..., Any] | None = None) -> str | None:
    """None when this exact URL may be fetched, else why not. Refused hosts before robots."""
    why = refusal(url)
    if why:
        return f"REFUSED: {why}"
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        return "REFUSED: only https media is fetched"
    rules = _robots_for(parts.scheme, parts.netloc, open_url or refusing_opener().open)
    if isinstance(rules, str):
        return f"{HELD}: {rules}"
    if not rules.can_fetch(UA, url):
        return "REFUSED: robots.txt disallows this path"
    return None


def fetch(url: str, *, cap: int = MAX_MEDIA_BYTES,
          open_url: Callable[..., Any] | None = None) -> tuple[bytes | None, str]:
    """One gated GET. 401/403/451 or a WAF page means HELD_UNTIL_RELEASED, never a retry."""
    opener = open_url or refusing_opener().open
    blocked = gate(url, open_url=opener)
    if blocked:
        return None, blocked
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with opener(req, timeout=30.0) as r:
            ctype = str(r.headers.get("Content-Type") or "")
            body = r.read(cap + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 451):
            return None, f"{HELD}: HTTP {e.code}"
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"
    if len(body) > cap:
        return None, f"media larger than the {cap}-byte cap"
    if "text/html" in ctype.lower() and not url.lower().endswith((".htm", ".html")):
        return None, f"{HELD}: HTML where media was expected (WAF or interstitial)"
    return body, "ok"


# ============================================================================= the model
def model_status(model_dir: Path | None = None) -> dict[str, Any]:
    """Whether a local speech model can run, WITHOUT importing or installing anything."""
    where = Path(model_dir or os.environ.get(MODEL_ENV) or MODEL_DEFAULT)
    if importlib.util.find_spec("faster_whisper") is None:
        return {"ready": False, "status": UNMEASURED, "model_dir": str(where),
                "reason": "faster_whisper is not installed; the box installer installs it"}
    if not (where / "model.bin").is_file():
        return {"ready": False, "status": UNMEASURED, "model_dir": str(where),
                "reason": f"no local model weights at {where} (model.bin absent)"}
    return {"ready": True, "status": "READY", "model_dir": str(where), "reason": ""}


#: The small int8 model plus decode buffers needs ~3 GB resident; the headroom keeps the trading
#: terminal's working set untouched. Below this much AVAILABLE memory nothing is loaded.
MODEL_RAM_NEED_MB = 3072
MODEL_RAM_HEADROOM_MB = 1024
MODEL_RAM_FLOOR_MB = MODEL_RAM_NEED_MB + MODEL_RAM_HEADROOM_MB


def memory_admits(available_mb: Callable[[], float] | None = None) -> tuple[bool, str]:
    """(True, '') when measured available memory clears MODEL_RAM_FLOOR_MB, else why not."""
    try:
        if available_mb is None:
            import psutil  # type: ignore[import-untyped,unused-ignore]
            have = psutil.virtual_memory().available / 1024 ** 2
        else:
            have = float(available_mb())
    except Exception as e:
        return False, f"available memory unmeasurable ({type(e).__name__}); nothing loaded"
    if have < MODEL_RAM_FLOOR_MB:
        return False, (f"{have:.0f} MB available is below the {MODEL_RAM_FLOOR_MB} MB floor "
                       f"({MODEL_RAM_NEED_MB} MB model + {MODEL_RAM_HEADROOM_MB} MB headroom); "
                       "nothing loaded")
    return True, ""


Segment = tuple[float, float, str]


def transcribe(media: Path, *, model_dir: Path | None = None,
               language: str | None = "en") -> tuple[list[Segment], dict[str, Any]]:
    """Local transcription. Returns ([], status) with the reason when the model cannot run."""
    status = model_status(model_dir)
    if not status["ready"]:
        return [], status
    ok, why = memory_admits()
    if not ok:
        return [], {**status, "ready": False, "status": UNMEASURED, "reason": why}
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found,unused-ignore]
        model = WhisperModel(status["model_dir"], device="cpu", compute_type="int8",
                             cpu_threads=max(1, (os.cpu_count() or 2) // 4),
                             local_files_only=True)
        segs, _info = model.transcribe(str(media), language=language, vad_filter=True,
                                       beam_size=1)
        out = [(float(s.start), float(s.end), str(s.text).strip()) for s in segs]
    except Exception as e:
        return [], {**status, "ready": False, "status": UNMEASURED,
                    "reason": f"transcription failed: {type(e).__name__}: {str(e)[:120]}"}
    return out, status


# ============================================================================= the tone
def minute_rows(segments: Sequence[Segment], *, bank: str, started_at: datetime,
                knowable_at: Callable[[datetime], datetime], media: str = "",
                model: str = "") -> list[dict[str, Any]]:
    """One row per spoken minute, scored by the desk's signed lexicon (no model decides)."""
    from libs.research import event_factors
    buckets: dict[int, list[str]] = {}
    for start, _end, text in segments:
        if text:
            buckets.setdefault(int(max(0.0, start) // 60), []).append(text)
    rows: list[dict[str, Any]] = []
    for minute in sorted(buckets):
        text = " ".join(buckets[minute]).strip()
        spoken = started_at + timedelta(minutes=minute)
        tag = event_factors.tag(text)
        rows.append({
            "kind": "presser_minute", "source": f"central_bank_presser_{bank}",
            "bank": bank, "minute": minute,
            "title": f"{SOURCES[bank]['bank']} press conference, minute {minute}",
            "text": text[:4000], "spoken_at": _iso(spoken),
            "knowable_at": _iso(knowable_at(spoken)), "received_at": _iso(_now()),
            "monetary_tone": round(tag.intensity("monetary_tone"), 4),
            "monetary_tone_signed": int(tag.signed.get("monetary_tone", 0)),
            "monetary_tone_hits": int(tag.counts.get("monetary_tone", 0)),
            "matched": list(tag.matched), "scorer": "libs.research.event_factors.tag",
            "media": media, "model": model, "research_input_only": True,
        })
    return rows


def append_rows(rows: Sequence[Mapping[str, Any]], when: datetime | None = None,
                seat: Path | None = None) -> int:
    if not rows:
        return 0
    folder = seat or SEAT
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"presser_tone_{(when or _now()):%Y%m%d}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def from_media(media: Path, bank: str, started_at: datetime, *, live: bool = False,
               model_dir: Path | None = None) -> dict[str, Any]:
    """Transcribe one local media file and write its minutes. Recorded media is knowable when
    the desk read it, not when it was spoken; live minutes are knowable as they land."""
    segs, status = transcribe(media, model_dir=model_dir)
    if not status["ready"]:
        return {"rows": 0, "status": status["status"], "reason": status["reason"]}
    read_at = _now()
    rows = minute_rows(segs, bank=bank, started_at=started_at,
                       knowable_at=(lambda s: s) if live else (lambda _s: read_at),
                       media=media.name, model=Path(status["model_dir"]).name)
    return {"rows": append_rows(rows), "status": "MEASURED", "minutes": len(rows),
            "mean_tone": (round(sum(r["monetary_tone"] for r in rows) / len(rows), 4)
                          if rows else None)}


# ============================================================================= the live stream
_SEG_RE = re.compile(r"^(?!#)(\S+)$", re.M)


def _playlist_children(base: str, text: str) -> list[str]:
    return [urllib.parse.urljoin(base, m.group(1).strip()) for m in _SEG_RE.finditer(text)]


def capture_live(bank: str, until: datetime, *, poll_s: float = 10.0,
                 open_url: Callable[..., Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], datetime] = _now) -> dict[str, Any]:
    """Follow an ALLOWED source's HLS stream until `until`, transcribing every ~minute of audio."""
    src = SOURCES[bank]
    if src["verdict"] != ALLOWED or not src.get("media_url"):
        return {"rows": 0, "status": src["verdict"], "reason": src["reading"]}
    url = str(src["media_url"])
    seen: set[str] = set()
    pending: list[bytes] = []
    chunk_start: datetime | None = None
    rows = 0
    last = "no segment yet"
    while clock() <= until:
        body, why = fetch(url, cap=2_000_000, open_url=open_url)
        if body is None:
            if why.startswith(HELD) or why.startswith("REFUSED"):
                return {"rows": rows, "status": HELD if why.startswith(HELD) else REFUSED,
                        "reason": why}
            last = why
        else:
            kids = _playlist_children(url, body.decode("utf-8", errors="replace"))
            if kids and all(k.endswith(".m3u8") or ".m3u8?" in k for k in kids):
                url = kids[0]                       # master playlist: follow the first variant
                continue
            for seg_url in kids:
                if seg_url in seen:
                    continue
                seen.add(seg_url)
                data, why = fetch(seg_url, cap=50_000_000, open_url=open_url)
                if data is None:
                    last = why
                    continue
                chunk_start = chunk_start or clock()
                pending.append(data)
            if chunk_start and (clock() - chunk_start).total_seconds() >= 60:
                rows += _flush(bank, pending, chunk_start)
                pending, chunk_start = [], None
        sleep(poll_s)
    if pending and chunk_start:
        rows += _flush(bank, pending, chunk_start)
    return {"rows": rows, "status": "MEASURED" if rows else UNMEASURED,
            "reason": "" if rows else last}


def _flush(bank: str, pending: list[bytes], chunk_start: datetime) -> int:
    with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as fh:
        fh.write(b"".join(pending))
        path = Path(fh.name)
    try:
        got = from_media(path, bank, chunk_start, live=True)
    finally:
        path.unlink(missing_ok=True)
    return int(got.get("rows") or 0)


# ============================================================================= the passes
def plan(now: datetime | None = None, *, report: Path | None = None,
         write: bool = True) -> dict[str, Any]:
    when = now or _now()
    wins, notes = windows(when)
    upcoming = [w for w in wins if (_parse(w["ends_at"]) or when) >= when][:6]
    model = model_status()
    allowed = [b for b, s in SOURCES.items() if s["verdict"] == ALLOWED]
    doc = {
        "generated_at": _iso(when), "organ": "desks/mt5/research/presser_stt.py",
        "rule": ("research input only: a lexicon score per spoken minute into a news seat; "
                 "nothing sizes, caps, vetoes or shrinks, and no language model decides"),
        "model": model,
        "sources": {b: {"bank": s["bank"], "verdict": s["verdict"], "reading": s["reading"],
                        "media_url": s.get("media_url")} for b, s in SOURCES.items()},
        "allowed_sources": allowed,
        "status": ("MEASURED" if allowed and model["ready"] else UNMEASURED),
        "why": ("" if allowed and model["ready"] else
                "; ".join(x for x in (
                    "" if allowed else "no source is ALLOWED on terms and robots (see sources)",
                    "" if model["ready"] else model["reason"]) if x)),
        "open_window": open_window(wins, when),
        "upcoming_windows": upcoming, "calendar_notes": notes,
        "seat": SEAT.as_posix(), "rows_today": _rows_today(when),
    }
    if write:
        path = report or REPORT
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
    return doc


def _rows_today(when: datetime) -> int:
    path = SEAT / f"presser_tone_{when:%Y%m%d}.jsonl"
    try:
        with path.open(encoding="utf-8") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def watch(now: datetime | None = None, *,
          available_mb: Callable[[], float] | None = None) -> dict[str, Any]:
    doc = plan(now)
    doc["runtime"] = {"python": sys.version.split()[0], "executable": sys.executable}
    print(f"[presser_stt] python {doc['runtime']['python']} at {sys.executable}", flush=True)
    win = doc["open_window"]
    if not win:
        doc["capture"] = {"status": "NO_WINDOW"}
    elif SOURCES[win["bank"]]["verdict"] != ALLOWED:
        doc["capture"] = {"status": SOURCES[win["bank"]]["verdict"],
                          "reason": SOURCES[win["bank"]]["reading"]}
    elif not doc["model"]["ready"]:
        doc["capture"] = {"status": UNMEASURED, "reason": doc["model"]["reason"]}
    elif not (mem := memory_admits(available_mb))[0]:
        doc["capture"] = {"status": UNMEASURED, "reason": mem[1]}
    else:
        doc["capture"] = capture_live(win["bank"], _parse(win["ends_at"]) or _now())
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="hourly: calendar, verdicts, model")
    mode.add_argument("--watch", action="store_true", help="box task: capture an open window")
    mode.add_argument("--media", type=Path, help="transcribe one local media file")
    ap.add_argument("--bank", choices=sorted(SOURCES), default="fed")
    ap.add_argument("--started-at", default="")
    a = ap.parse_args(argv)
    if a.media:
        start = _parse(a.started_at) or _now()
        out = from_media(a.media, a.bank, start)
    elif a.watch:
        out = watch()
        out = {k: out[k] for k in ("status", "why", "runtime", "open_window", "capture")}
    else:
        out = plan()
        out = {k: out[k] for k in ("status", "why", "allowed_sources", "upcoming_windows")}
    print(json.dumps(out, indent=1, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
