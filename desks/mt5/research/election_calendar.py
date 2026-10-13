"""ELECTION CALENDAR: a point-in-time pre/post-election state for ZAR, MXN, NZD and JPY.

THE IDEA (coordinator's hourly pass, idea F3, 2026-10-13): a national election is a scheduled
regime for that country's currency -- a risk premium builds into the vote and is released after
it -- and the desk had no record of when any of them were. This organ reads the dates from public
pages (each electoral authority's own site, plus the public list page that carries the history),
writes one lake series per country, and donates exactly pre-registered conditioner cells.

NO MODEL IS IN THE PATH, ON PURPOSE. A date is accepted only when FIXED CODE finds it verbatim
in the fetched page within KEYWORD_SPAN characters of an election keyword in the page's language.
A model choosing which elections to keep could select the ones followed by large moves, which is
look-ahead by selection; deterministic extraction has no such channel, so no model cutoff trims
this series and no LLM look-ahead guard applies. The cells' sides are fixed below from the stated
mechanism, never from data or a model.

POINT IN TIME. The row for day D is stamped available at D - 1 day, 00:00 UTC, so that after the
conditioner's own 24 h lag it conditions day D's bars. That presumes the vote was public by D - 1
for every D in [E - PRE_DAYS - 1, E + POST_DAYS]: a statutory fact, not our first sight --
Japan's Public Offices Election Act requires a House of Representatives election to be proclaimed
at least 12 days ahead (17 for the House of Councillors), and South African, Mexican and New
Zealand general elections are fixed months ahead -- so PRE_DAYS + 1 sits inside the shortest
notice. Our own first sight is kept in `retrieval_time` for audit. Rows exist only up to today.

WHAT IS DONATED. Per country, per symbol: `exogenous_conditioner` on `pre_event` and on
`post_event` (level_z, threshold 1), with the side fixed by MECHANISMS. Every cell is judged by
the one gauntlet; nothing here sizes, promotes or vetoes anything.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_DIR = BASE / "data" / "election_calendar"
EVENTS = STATE_DIR / "events.json"
FETCHED = STATE_DIR / "fetched.json"
SERIES_DIR = BASE / "data" / "lake" / "series"
DONATE_DIR = BASE / "data" / "intelligence" / "election_calendar"
REPORT = BASE / "reports" / "ELECTION_CALENDAR.json"
UNMEASURED = "UNMEASURED"

PRE_DAYS = 5
POST_DAYS = 5
KEYWORD_SPAN = 120
REFETCH_S = 20 * 3600.0
EARLIEST = date(1990, 1, 1)
#: Two accepted dates closer than this are one event (a two-day vote, a results day).
MERGE_DAYS = 3

#: (country, page, language). The authority's own site carries the coming vote; the public list
#: page carries the history the conditioner needs to be judged on.
SOURCES: tuple[tuple[str, str, str], ...] = (
    ("za", "https://www.elections.org.za/", "en"),
    ("za", "https://en.wikipedia.org/wiki/Elections_in_South_Africa", "en"),
    ("mx", "https://www.ine.mx/", "es"),
    ("mx", "https://en.wikipedia.org/wiki/Elections_in_Mexico", "en"),
    ("nz", "https://elections.nz/", "en"),
    ("nz", "https://en.wikipedia.org/wiki/List_of_New_Zealand_general_elections", "en"),
    ("jp", "https://www.soumu.go.jp/senkyo/", "ja"),
    ("jp", "https://en.wikipedia.org/wiki/Elections_in_Japan", "en"),
)

#: symbol -> (side while pre_event is on, side while post_event is on), per country. A rising
#: USDxxx is the domestic currency weakening: the pre-vote risk premium, then its release.
MECHANISMS: dict[str, dict[str, tuple[int, int]]] = {
    "za": {"USDZAR": (1, -1), "EURZAR": (1, -1)},
    "mx": {"USDMXN": (1, -1), "EURMXN": (1, -1)},
    "nz": {"NZDUSD": (-1, 1), "AUDNZD": (1, -1)},
    "jp": {"USDJPY": (1, -1), "EURJPY": (1, -1)},
}

KEYWORDS: dict[str, tuple[str, ...]] = {
    "en": ("general election", "national election", "election day", "polling day",
           "voting day", "elections were held", "election was held", "election held"),
    "es": ("jornada electoral", "elección federal", "elecciones federales", "proceso electoral",
           "día de la elección"),
    "ja": ("投票日", "総選挙", "通常選挙", "選挙期日"),
}

_MONTHS_EN = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"))}
_MONTHS_ES = {m: i + 1 for i, m in enumerate(
    ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
     "octubre", "noviembre", "diciembre"))}
_EN1 = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS_EN) + r")\s+(\d{4})\b", re.I)
_EN2 = re.compile(r"\b(" + "|".join(_MONTHS_EN) + r")\s+(\d{1,2}),?\s+(\d{4})\b", re.I)
_ES = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(_MONTHS_ES) + r")\s+(?:de|del)\s+(\d{4})\b",
                 re.I)
_JA = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def page_text(body: bytes) -> str:
    """Visible text, one line per block (paragraph, table row, list item, heading): a keyword
    and a date are only read together when they share a block."""
    raw = body.decode("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|noscript|head)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)</t[dh]\s*>", " | ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|tr|li|div|h[1-6]|dd|dt|caption|section|article)\s*>",
                 "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    import html
    lines = (re.sub(r"[ \t\r\f\v]+", " ", ln).strip()
             for ln in html.unescape(raw).split("\n"))
    return "\n".join(ln for ln in lines if ln)


def _dates(text: str) -> list[tuple[int, date]]:
    """(offset, date) for every date this code can read, in any of the four shapes."""
    out: list[tuple[int, date]] = []

    def add(pos: int, y: int, m: int, d: int) -> None:
        try:
            out.append((pos, date(y, m, d)))
        except ValueError:
            pass
    for mt in _EN1.finditer(text):
        add(mt.start(), int(mt.group(3)), _MONTHS_EN[mt.group(2).lower()], int(mt.group(1)))
    for mt in _EN2.finditer(text):
        add(mt.start(), int(mt.group(3)), _MONTHS_EN[mt.group(1).lower()], int(mt.group(2)))
    for mt in _ES.finditer(text):
        add(mt.start(), int(mt.group(3)), _MONTHS_ES[mt.group(2).lower()], int(mt.group(1)))
    for mt in _JA.finditer(text):
        add(mt.start(), int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
    for mt in _ISO.finditer(text):
        add(mt.start(), int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
    return out


def extract(text: str, lang: str, *, today: date | None = None) -> list[dict[str, str]]:
    """Every date in the same block and sentence as an election keyword, within KEYWORD_SPAN
    characters of it, with the quote it was read from."""
    keys = KEYWORDS.get(lang, ()) + (KEYWORDS["en"] if lang != "en" else ())
    limit = (today or datetime.now(UTC).date()) + timedelta(days=400)
    out: dict[str, dict[str, str]] = {}
    for seg in re.split(r"\n|(?<=[.!?\u3002])\s+", text):
        low = seg.lower()
        hits = [m.start() for k in keys for m in re.finditer(re.escape(k.lower()), low)]
        if not hits:
            continue
        for pos, d in _dates(seg):
            if EARLIEST <= d <= limit and any(abs(pos - h) <= KEYWORD_SPAN for h in hits):
                out.setdefault(d.isoformat(), {"date": d.isoformat(), "quote": seg[:240]})
    return sorted(out.values(), key=lambda e: e["date"])


def merge_events(store: dict[str, Any], cc: str, found: Sequence[dict[str, str]], url: str,
                 seen: str) -> int:
    """Add newly read dates; a date within MERGE_DAYS of a known one is the same event."""
    rows = store.setdefault(cc, [])
    known = [date.fromisoformat(r["date"]) for r in rows]
    added = 0
    for e in found:
        d = date.fromisoformat(e["date"])
        if any(abs((d - k).days) <= MERGE_DAYS for k in known):
            continue
        rows.append({"date": e["date"], "first_seen": seen, "url": url, "quote": e["quote"]})
        known.append(d)
        added += 1
    rows.sort(key=lambda r: r["date"])
    return added


SERIES_COLUMNS = ("available_time", "published_time", "retrieval_time", "source_id",
                  "vintage_id", "pre_event", "post_event")


def series_rows(events: Sequence[dict[str, Any]], cc: str, *, today: date | None = None
                ) -> list[dict[str, Any]]:
    """One row a day from 400 days before the first event to today, 0/1 in each window."""
    if not events:
        return []
    end = today or datetime.now(UTC).date()
    days = sorted(date.fromisoformat(e["date"]) for e in events)
    seen = {e["date"]: e.get("first_seen", "") for e in events}
    start = max(EARLIEST, days[0] - timedelta(days=400))
    rows = []
    d = start
    while d <= end:
        pre = next((e for e in days if 1 <= (e - d).days <= PRE_DAYS), None)
        post = next((e for e in days if 0 <= (d - e).days < POST_DAYS), None)
        ev = pre or post
        avail = datetime(d.year, d.month, d.day, tzinfo=UTC) - timedelta(days=1)
        rows.append({"available_time": avail.isoformat(), "published_time": avail.isoformat(),
                     "retrieval_time": seen.get(ev.isoformat(), "") if ev else "",
                     "source_id": f"election_{cc}", "vintage_id": "v1",
                     "pre_event": int(pre is not None), "post_event": int(post is not None)})
        d += timedelta(days=1)
    return rows


def write_series(cc: str, rows: Sequence[dict[str, Any]]) -> Path:
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    path = SERIES_DIR / f"election_{cc}.csv"
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(SERIES_COLUMNS))
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    return path


def cells(store: dict[str, Any], uni: dict[str, str] | None = None,
          lane_ok: Callable[[str, str], bool] | None = None) -> list[dict[str, Any]]:
    """The pre-registered cells for every country with at least two events on record."""
    out: list[dict[str, Any]] = []
    for cc, syms in MECHANISMS.items():
        n = len(store.get(cc) or [])
        if n < 2:
            continue
        for sym, (pre_side, post_side) in syms.items():
            if uni is not None and sym not in uni:
                continue
            if lane_ok is not None and not lane_ok(sym, "exogenous_conditioner"):
                continue
            for signal, side in (("pre_event", pre_side), ("post_event", post_side)):
                params = {"source": f"election_{cc}", "signal": signal, "transform": "level_z",
                          "threshold": 1.0, "side_when_high": side}
                ident = hashlib.sha256(json.dumps(
                    {"family": "exogenous_conditioner", "params": params, "symbol": sym},
                    sort_keys=True).encode()).hexdigest()[:16]
                phase = "into" if signal == "pre_event" else "after"
                out.append({
                    "kind": "hypothesis", "family": "exogenous_conditioner", "params": params,
                    "symbols": [sym], "symbol": sym, "cell_id": f"election_{ident}",
                    "mechanism": (f"national election risk premium: the {cc.upper()} currency "
                                  f"weakens into the vote and recovers after it; this cell "
                                  f"takes the leg {phase} the vote on {sym} ({n} on record)"),
                    "falsifier": (f"{sym} returns in the {PRE_DAYS} days {phase} each national "
                                  f"election are no different from unconditioned returns"),
                    "title": f"election calendar: {sym} {phase} the {cc.upper()} vote",
                    "mechanism_class": "event", "novelty_class": "GENUINELY_NOVEL",
                    "lineage": {"root": f"election_calendar:{cc}", "operator": "fixed_rule"},
                    "producer": "election_calendar", "url": f"lake://election_{cc}",
                    "copy_trade": False, "credibility_inherited": False,
                    "gauntlet_bypass": False})
    return out


def run(*, budget_s: float = 60.0, get: Any = None, resolve: Any = None,
        uni: dict[str, str] | None = None, lane_ok: Callable[[str, str], bool] | None = None,
        today: date | None = None) -> dict[str, Any]:
    """Refresh each source at most once per REFETCH_S, rebuild the series, donate new cells."""
    import collector_lab
    started = time.time()
    deadline = started + max(5.0, budget_s)
    store: dict[str, Any] = _read_json(EVENTS, {}) or {}
    fetched: dict[str, Any] = _read_json(FETCHED, {}) or {}
    per: list[dict[str, Any]] = []
    for cc, url, lang in SOURCES:
        if time.time() > deadline - 5:
            per.append({"url": url, "status": "NOT_REACHED"})
            continue
        last = float((fetched.get(url) or {}).get("at_epoch") or 0)
        if time.time() - last < REFETCH_S:
            per.append({"url": url, "status": "FRESH"})
            continue
        body, why = collector_lab.fetch(url, url, get=get, resolve=resolve,
                                        budget_s=min(collector_lab.FETCH_S,
                                                     max(1.0, deadline - time.time())))
        if why:
            fetched[url] = {"at_epoch": time.time(), "status": why}
            per.append({"url": url, "status": why})
            continue
        found = extract(page_text(body), lang, today=today)
        added = merge_events(store, cc, found, url, _now())
        fetched[url] = {"at_epoch": time.time(), "status": "OK", "dates": len(found)}
        per.append({"url": url, "status": "OK", "dates": len(found), "new_events": added})
    _write_json(EVENTS, store)
    _write_json(FETCHED, fetched)
    counts = {}
    for cc in MECHANISMS:
        rows = series_rows(store.get(cc) or [], cc, today=today)
        if rows:
            write_series(cc, rows)
        counts[cc] = {"events": len(store.get(cc) or []), "rows": len(rows)}
    if lane_ok is None:
        try:
            import llm_lab
            lane_ok = llm_lab._lane_ok
        except Exception:
            lane_ok = None
    donate = cells(store, uni, lane_ok)
    known = set(_read_json(STATE_DIR / "donated.json", []) or [])
    fresh = [r for r in donate if r["cell_id"] not in known]
    if fresh:
        DONATE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")[:15]
        _write_json(DONATE_DIR / f"discoveries_{stamp}.json",
                    {"source": "election_calendar", "generated_at": _now(),
                     "rule": "fixed-code extraction; pre-registered sides; the gauntlet judges",
                     "discoveries": fresh})
        _write_json(STATE_DIR / "donated.json", sorted(known | {r["cell_id"] for r in fresh}))
    ok = [p for p in per if p["status"] == "OK"]
    state = ("RAN" if ok else "FRESH" if all(p["status"] == "FRESH" for p in per)
             else "DARK")
    doc = {"generated_at": _now(), "state": state, "sources": per, "countries": counts,
           "cells_total": len(donate), "cells_donated": len(fresh),
           "seconds": round(time.time() - started, 1),
           "pit": f"row D stamped D-1 (conditions day D after the 24h lag); the {PRE_DAYS}d "
                  "pre window sits inside the shortest statutory notice (JP HoR 12d); first "
                  "sight kept in retrieval_time"}
    _write_json(REPORT, doc)
    return doc


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--budget-s", type=float, default=60.0)
    a = ap.parse_args(argv)
    print(json.dumps(run(budget_s=a.budget_s), indent=1, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
