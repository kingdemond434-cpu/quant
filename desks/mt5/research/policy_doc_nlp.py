"""POLICY-DOCUMENT NLP -- Asian and EM central-bank and regulator statements as dated event states.

WHAT IT DOES (build_check row 47, C_DEDUPE 2026-11-18). Reads official statements from the
PBOC, CSRC, SAFE, BOK, MAS, BOJ, RBI and SARB, scores each one's hawkish/dovish stance with
`cb_tone_lab`'s lexicon in the document's own language, and writes one dated event state per
(document, target symbol) for the FX pairs and indices each body moves. The states are inputs a
conditioner may read; nothing here sizes, promotes or gates anything.

ACCESS COMES BEFORE EVERYTHING, AND IT FAILS CLOSED. For every source, in this order:

    1. `libs.data.refused_hosts.refusal(url)`  -- a settled terms refusal sends nothing at all;
    2. the source's own terms row (policy_doc_sources.json) must read OPEN, with its clause;
    3. a persisted hold must not be in force (below);
    4. robots.txt for the exact path, under the same agent the request will carry. A 404/410 is
       "no rules". A body that is HTML where robots.txt should be is UNREAD, and UNREAD refuses;
    5. only then the listing, and only then each document, through `refused_hosts.opener()` so a
       redirect to a refused host is never followed.

HOLD RULES (every response, robots.txt included). 401, 403, 451 or a WAF/challenge page puts the
source HELD_UNTIL_RELEASED, persisted in `data/policy_doc/source_state.json`; it lifts only when a
person writes a release for that source into `data/policy_doc/RELEASES.json` dated after the
hold. A 429 holds the source for 24 hours and then lifts by itself. Nothing is retried under
another agent, and the agent is the HONEST_UA literal below.

TERMS READ 2026-11-18 (the clauses are quoted verbatim in policy_doc_sources.json): SAFE, MAS,
RBI and SARB refuse on terms; BOJ was fenced on terms on 2026-11-17 (#1254); PBOC refuses under
robots; CSRC's robots answered HTML and its legal notice could not be read; BOK's copyright
policy could not be read in full. So every source is fenced today and the leg publishes that as
its measurement: zero documents, zero states, each with the named reason. A fenced source is a
gap with a missed-growth line, not a zero.

DEDUPE. `cb_tone_lab` (#332, open) owns the lexicons and the PBoC/BoJ/SARB tone series; this
organ imports its `score_lex`, never copies it, and when it is not on the tree the tone is
UNMEASURED with that reason. The Federal Register lane (#1290) reads US rulemaking only; no
publisher overlaps. Document text is never written to a tracked file: the ledger holds URL,
title, hash and scores.

    python desks/mt5/research/policy_doc_nlp.py [--once] [--budget-s 240]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import refused_hosts  # noqa: E402

SOURCES = DESK / "research" / "policy_doc_sources.json"
STATE_DIR = DESK / "data" / "policy_doc"
STATE = STATE_DIR / "source_state.json"
RELEASES = STATE_DIR / "RELEASES.json"
DOCS = STATE_DIR / "docs.jsonl"
EVENTS = STATE_DIR / "event_states.jsonl"
OUT = DESK / "reports" / "POLICY_DOC_NLP.json"

ROBOTS_AGENT = "quant-desk-research"
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (policy_doc_nlp; research; honours robots.txt)"
HELD_UNTIL_RELEASED = "HELD_UNTIL_RELEASED"
HELD_24H = "HELD_24H"
HOLD_429_H = 24
MAX_DOCS_PER_SOURCE = 12
UNMEASURED = "UNMEASURED"
MISSED_GROWTH = ("source not fetched: its statements never become dated tone states for its "
                 "targets, so conditioner cells on those pairs and indices cannot be built")

#: Markers of a challenge or WAF wall answered with a 200. Lower-cased substring match.
WAF_MARKERS: tuple[str, ...] = (
    "just a moment...", "cf-chl", "attention required! | cloudflare", "cf-browser-verification",
    "_incapsula_resource", "the requested url was rejected", "request rejected",
    "access denied</title>", "are you a robot", "安全验证", "访问验证",
)

#: (status, body bytes, content type). Tests inject one; the default goes through
#: `refused_hosts.opener()` so every redirect hop is checked against the refused list.
Getter = Callable[[str, float], tuple[int, bytes, str]]


# ------------------------------------------------------------------------------ small io
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def load_sources(path: Path | None = None) -> list[dict[str, Any]]:
    doc = _read_json(path or SOURCES, {})
    rows = doc.get("sources") if isinstance(doc, dict) else None
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("id") and r.get("url")]


# ------------------------------------------------------------------------------ network
def default_get(url: str, timeout: float) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": HONEST_UA})
    try:
        with refused_hosts.opener().open(req, timeout=timeout) as resp:
            return int(resp.status), resp.read(4_000_000), str(resp.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        body = b""
        with contextlib.suppress(Exception):
            body = exc.read(200_000)
        return int(exc.code), body, str(exc.headers.get("Content-Type", "") if exc.headers else "")


def _looks_html(body: bytes) -> bool:
    head = body[:400].lstrip().lower()
    return head.startswith((b"<!doctype", b"<html", b"<head", b"<?xml-stylesheet")) or \
        b"<html" in head


def is_waf(body: bytes) -> bool:
    low = body[:20000].decode("utf-8", errors="replace").lower()
    return any(m in low for m in WAF_MARKERS)


def hold_for(status: int, body: bytes, now: datetime) -> dict[str, Any] | None:
    """The hold a response puts on its source, or None."""
    if status in (401, 403, 451) or (status == 200 and is_waf(body)):
        why = f"HTTP {status}" if status != 200 else "WAF or challenge page answered 200"
        return {"hold": HELD_UNTIL_RELEASED, "since": _iso(now), "why": why}
    if status == 429:
        return {"hold": HELD_24H, "since": _iso(now),
                "until": _iso(now + timedelta(hours=HOLD_429_H)), "why": "HTTP 429"}
    return None


def hold_in_force(sstate: Mapping[str, Any], release: Mapping[str, Any] | None,
                  now: datetime) -> tuple[bool, str]:
    """(held, why). A 24h hold lifts by the clock; a HELD_UNTIL_RELEASED hold lifts only on a
    person's release dated at or after the hold."""
    hold = sstate.get("hold")
    if not hold:
        return False, ""
    if hold == HELD_24H:
        until = _parse_time(sstate.get("until"))
        if until is not None and now >= until:
            return False, "24h hold expired"
        return True, f"{HELD_24H} until {sstate.get('until')} ({sstate.get('why')})"
    if hold == HELD_UNTIL_RELEASED:
        since = _parse_time(sstate.get("since"))
        rel_doc = release or {}
        rel = _parse_time(rel_doc.get("released_at"))
        if rel is not None and since is not None and rel >= since and rel_doc.get("by"):
            return False, f"released by {rel_doc.get('by')} at {rel_doc.get('released_at')}"
        return True, (f"{HELD_UNTIL_RELEASED} since {sstate.get('since')} ({sstate.get('why')}); "
                      f"lifts only when a person adds a release to {RELEASES.name}")
    return True, f"unknown hold {hold!r}: fails closed"


def robots_refusal(url: str, get: Getter, timeout: float, now: datetime
                   ) -> tuple[str | None, dict[str, Any] | None]:
    """(refusal or None, hold or None). Fails closed: only 404/410 means no rules."""
    parts = urllib.parse.urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        status, body, ctype = get(robots_url, timeout)
    except Exception as exc:
        return f"ROBOTS_UNREAD: robots.txt unreadable ({type(exc).__name__})", None
    hold = hold_for(status, body, now)
    if hold:
        return f"{hold['hold']}: robots.txt answered {hold['why']}", hold
    if status in (404, 410):
        return None, None
    if status != 200:
        return f"ROBOTS_UNREAD: robots.txt answered HTTP {status}", None
    if "html" in ctype.lower() or _looks_html(body):
        return "ROBOTS_UNREAD: robots.txt answered HTML, which counts as unread", None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.decode("utf-8", errors="replace").splitlines())
    if not rp.can_fetch(ROBOTS_AGENT, url):
        return f"ROBOTS_REFUSED: robots.txt disallows {parts.path or '/'}", None
    return None, None


def access_refusal(src: Mapping[str, Any]) -> str | None:
    """The fence before any request: the shared refused list, then the source's terms row."""
    why = refused_hosts.refusal(str(src.get("url") or ""))
    if why:
        return f"BLOCKED_ON_TERMS: {why}"
    terms = str(src.get("terms") or "TERMS_UNREAD")
    if terms != "OPEN":
        return f"{terms}: {src.get('terms_clause') or 'no terms read'} ({src.get('terms_url', '')})"
    return None


# ------------------------------------------------------------------------------ parsing
_TAG = re.compile(r"<[^>]+>")
_DATE_RX = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})")


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", raw))).strip()


def _decode(body: bytes) -> str:
    for enc in ("utf-8", "gb18030", "euc-kr", "shift_jis"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def stamp(raw: str) -> tuple[str | None, str | None]:
    """(published, available_time). A full timestamp is available when published; a bare date
    is available at the next UTC midnight; nothing parseable leaves both None."""
    raw = (raw or "").strip()
    if raw:
        try:
            t = parsedate_to_datetime(raw)
            if t.tzinfo is None:
                t = t.replace(tzinfo=UTC)
            return _iso(t), _iso(t)
        except (TypeError, ValueError, IndexError):
            pass
        t2 = _parse_time(raw) if "T" in raw else None
        if t2 is not None:
            return _iso(t2), _iso(t2)
    m = _DATE_RX.search(raw)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=UTC)
        except ValueError:
            return None, None
        return d.date().isoformat(), _iso(d + timedelta(days=1))
    return None, None


def parse_listing(body: bytes, src: Mapping[str, Any]) -> list[dict[str, str]]:
    """Items {url, title, published, available_time} matching the source's include pattern."""
    text = _decode(body)
    inc = re.compile(str(src.get("include") or "."))
    base = str(src["url"])
    out: list[dict[str, str]] = []
    if str(src.get("kind")) == "rss":
        for item in re.findall(r"(?is)<(?:item|entry)\b.*?</(?:item|entry)>", text):
            title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", item)
            title = html_to_text(title_m.group(1) if title_m else "")
            link_m = (re.search(r"(?is)<link[^>]*>(.*?)</link>", item)
                      or re.search(r'(?is)<link[^>]*href="([^"]+)"', item))
            date_m = re.search(r"(?is)<(pubDate|dc:date|updated|published)[^>]*>(.*?)</\1>", item)
            link = html.unescape(link_m.group(1).strip()) if link_m else ""
            if not link or not inc.search(title):
                continue
            pub, avail = stamp(date_m.group(2) if date_m else "")
            out.append({"url": urllib.parse.urljoin(base, link), "title": title,
                        "published": pub or "", "available_time": avail or ""})
    else:
        for href, inner in re.findall(r'(?is)<a\s[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', text):
            title = html_to_text(inner)
            if not title or not inc.search(title):
                continue
            url = urllib.parse.urljoin(base, html.unescape(href))
            pub, avail = stamp(url + " " + title)
            out.append({"url": url, "title": title, "published": pub or "",
                        "available_time": avail or ""})
    seen: set[str] = set()
    uniq = []
    for it in out:
        if it["url"] not in seen:
            seen.add(it["url"])
            uniq.append(it)
    return uniq


# ------------------------------------------------------------------------------ scoring
def scorer() -> tuple[Callable[[str, str], tuple[int, int, float | None]] | None, set[str], str]:
    """cb_tone_lab's score_lex and the languages it holds a lexicon for, or (None, ..., why)."""
    try:
        import cb_tone_lab  # type: ignore[import-not-found,unused-ignore]
    except Exception as exc:
        return None, set(), (f"cb_tone_lab is not importable on this tree ({type(exc).__name__}); "
                             "it lands with #332")
    langs = set(getattr(cb_tone_lab, "LEXICON", {}) or {}) | {"en"}
    return cb_tone_lab.score_lex, langs, "cb_tone_lab.score_lex"


def tone_state(tone: float | None) -> str:
    if tone is None:
        return UNMEASURED
    return "HAWKISH" if tone > 0 else "DOVISH" if tone < 0 else "BALANCED"


def event_states(doc: Mapping[str, Any], src: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One dated state per target symbol. `signed` is tone times the symbol's side, so a positive
    value always means 'this statement leans toward the symbol rising'."""
    tone = doc.get("tone")
    rows = []
    for sym, side in sorted((src.get("targets") or {}).items()):
        rows.append({
            "symbol": sym, "source": src["id"], "bank": src.get("bank"),
            "doc_id": doc["doc_id"], "published": doc.get("published"),
            "available_time": doc.get("available_time"), "state": tone_state(tone),
            "tone": tone, "side_when_hawkish": int(side),
            "signed": (None if tone is None else round(float(tone) * int(side), 4)),
            "lang": doc.get("lang"), "scorer": doc.get("scorer"),
        })
    return rows


# ------------------------------------------------------------------------------ the pass
def _doc_id(sid: str, url: str) -> str:
    return hashlib.sha1(f"{sid}|{url}".encode()).hexdigest()[:16]


def run_source(src: Mapping[str, Any], *, get: Getter, now: datetime, sstate: dict[str, Any],
               release: Mapping[str, Any] | None, known: set[str], deadline: float,
               score: Callable[[str, str], tuple[int, int, float | None]] | None,
               langs: set[str], scorer_name: str, timeout: float = 20.0
               ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """(report row, new doc rows, new event-state rows) for one source."""
    sid = str(src["id"])
    fence = access_refusal(src)
    if fence:
        return ({"status": fence.split(":", 1)[0], "why": fence, "attempted": 0,
                 "missed_growth": MISSED_GROWTH}, [], [])
    held, why = hold_in_force(sstate, release, now)
    if held:
        return {"status": str(sstate.get("hold")), "why": why, "attempted": 0,
                "missed_growth": MISSED_GROWTH}, [], []
    if sstate.get("hold"):
        sstate["lifted"] = {"at": _iso(now), "why": why, "hold": sstate.get("hold")}
        for k in ("hold", "since", "until"):
            sstate.pop(k, None)
    url = str(src["url"])
    refusal, hold = robots_refusal(url, get, timeout, now)
    if hold:
        sstate.update(hold)
    if refusal:
        return {"status": refusal.split(":", 1)[0], "why": refusal, "attempted": 1,
                "missed_growth": MISSED_GROWTH}, [], []

    def _fetch(u: str) -> tuple[int, bytes, str] | dict[str, Any]:
        try:
            status, body, ctype = get(u, timeout)
        except Exception as exc:
            return {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"}
        h = hold_for(status, body, now)
        if h:
            sstate.update(h)
            return {"status": h["hold"], "why": f"{u} answered {h['why']}"}
        if status != 200:
            return {"status": "FAILED", "why": f"{u} answered HTTP {status}"}
        return status, body, ctype

    got = _fetch(url)
    if isinstance(got, dict):
        return {**got, "attempted": 2, "missed_growth": MISSED_GROWTH}, [], []
    items = parse_listing(got[1], src)
    attempted = 2
    docs: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    lang = str(src.get("lang") or "en")
    for it in items:
        if len(docs) >= MAX_DOCS_PER_SOURCE or time.monotonic() > deadline:
            break
        did = _doc_id(sid, it["url"])
        if did in known:
            continue
        r2 = _fetch(it["url"])
        attempted += 1
        if isinstance(r2, dict):
            if r2["status"] in (HELD_UNTIL_RELEASED, HELD_24H):
                break
            continue
        body = r2[1]
        text = html_to_text(_decode(body))
        if score is None:
            h = d = None
            tone = None
            tone_why = scorer_name
        elif lang not in langs:
            h = d = None
            tone = None
            tone_why = f"cb_tone_lab holds no {lang} lexicon; not scored in a foreign language"
        else:
            h, d, tone = score(text, lang)
            tone_why = "" if tone is not None else "no directional phrase in the document"
        doc = {"doc_id": did, "source": sid, "bank": src.get("bank"), "url": it["url"],
               "title": it["title"], "lang": lang, "published": it["published"] or None,
               "available_time": it["available_time"] or _iso(now), "fetched_at": _iso(now),
               "sha256": hashlib.sha256(body).hexdigest(), "chars": len(text),
               "hawk_hits": h, "dove_hits": d, "tone": tone,
               "scorer": "cb_tone_lab.score_lex" if score is not None else None,
               "tone_why": tone_why}
        docs.append(doc)
        known.add(did)
        states.extend(event_states(doc, src))
    sstate["last_success"] = _iso(now)
    return ({"status": "FETCHED", "attempted": attempted, "listed": len(items),
             "new_docs": len(docs), "new_states": len(states)}, docs, states)


def run(*, now: datetime | None = None, get: Getter | None = None, budget_s: float = 240.0,
        sources: list[dict[str, Any]] | None = None, write: bool = True) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    get = get or default_get
    srcs = sources if sources is not None else load_sources()
    state = _read_json(STATE, {})
    state = state if isinstance(state, dict) else {}
    releases = _read_json(RELEASES, {})
    releases = releases if isinstance(releases, dict) else {}
    known = {str(r.get("doc_id")) for r in _jsonl(DOCS)}
    score, langs, scorer_name = scorer()
    began = time.monotonic()
    report: dict[str, Any] = {}
    all_docs: list[dict[str, Any]] = []
    all_states: list[dict[str, Any]] = []
    for i, src in enumerate(srcs):
        sid = str(src["id"])
        remaining = budget_s - (time.monotonic() - began)
        if remaining <= 1:
            report[sid] = {"status": "NOT_REACHED", "why": "the pass budget ran out first"}
            continue
        deadline = time.monotonic() + remaining / max(1, len(srcs) - i)
        sstate = dict(state.get(sid) or {})
        try:
            rep, docs, sts = run_source(src, get=get, now=now, sstate=sstate,
                                        release=releases.get(sid), known=known,
                                        deadline=deadline, score=score, langs=langs,
                                        scorer_name=scorer_name)
        except Exception as exc:                     # one source never takes the others down
            rep, docs, sts = {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"}, [], []
        rep.update({"bank": src.get("bank"), "lang": src.get("lang"),
                    "targets": sorted(src.get("targets") or {}),
                    "terms": src.get("terms"), "terms_url": src.get("terms_url"),
                    "terms_read": src.get("terms_read")})
        state[sid] = sstate
        report[sid] = rep
        all_docs.extend(docs)
        all_states.extend(sts)
    by_status: dict[str, int] = {}
    for rep in report.values():
        by_status[rep["status"]] = by_status.get(rep["status"], 0) + 1
    fetched = sum(1 for r in report.values() if r["status"] == "FETCHED")
    doc = {
        "at": _iso(now),
        "status": "MEASURED" if fetched else UNMEASURED,
        "why": (None if fetched else
                "no source may be fetched: every row is fenced on terms, robots or a hold; "
                "the per-source reasons below are the measurement"),
        "scorer": scorer_name, "scorer_languages": sorted(langs),
        "sources": report, "by_status": by_status,
        "counts": {"sources": len(srcs), "fetched": fetched, "new_docs": len(all_docs),
                   "new_event_states": len(all_states),
                   "event_states_total": len(_jsonl(EVENTS)) + (len(all_states) if write else 0)},
        "states_by_symbol": _by_symbol(all_states),
        "artifacts": {"docs": str(DOCS.relative_to(ROOT)), "events": str(EVENTS.relative_to(ROOT)),
                      "state": str(STATE.relative_to(ROOT)),
                      "releases": str(RELEASES.relative_to(ROOT))},
        "dedupe": ("cb_tone_lab (#332) owns the lexicons and the PBoC/BoJ/SARB tone series and is "
                   "imported, not copied; the Federal Register lane (#1290) reads US rulemaking "
                   "only"),
        "rule": ("terms OPEN, then the hold, then robots for the exact path (HTML where robots.txt "
                 "should be is unread), then the fetch; 401/403/451/WAF holds until a person "
                 "releases it, 429 holds 24h; states are inputs, never authority"),
    }
    if write:
        _append_jsonl(DOCS, all_docs)
        _append_jsonl(EVENTS, all_states)
        _write_json(STATE, state)
        _write_json(OUT, doc)
    return doc


def _by_symbol(states: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for s in states:
        row = out.setdefault(str(s["symbol"]), {})
        row[str(s["state"])] = row.get(str(s["state"]), 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, write=not a.dry_run)
    print(f"policy_doc_nlp: {doc['counts']['fetched']}/{doc['counts']['sources']} source(s) "
          f"fetched, {doc['counts']['new_docs']} new doc(s), "
          f"{doc['counts']['new_event_states']} new state(s); by status {doc['by_status']}")
    for sid, rep in doc["sources"].items():
        print(f"  {sid:<22} {rep['status']:<20} {str(rep.get('why') or '')[:110]}")
    if not a.dry_run:
        print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
