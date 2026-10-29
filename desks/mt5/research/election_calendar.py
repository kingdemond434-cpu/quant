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

NATIONAL VOTES, READ TWICE (audit on #388). Only a segment naming a national vote is read (a
governor's race, a by-election or a referendum is excluded; Japanese text must name a house),
only the one date nearest the keyword that reads as the vote date is taken, and a vote enters a
series only once TWO different pages agree on it (within MERGE_DAYS). A vote both pages mis-read,
or one that moved, is withdrawn in `data/election_calendar/voided.json`; the series' vintage is a
hash of the votes it carries, so every withdrawal is a visible revision.

POINT IN TIME. A vote confirmed BEFORE it was held is knowable only from that confirmation: day
D's row is stamped max(D - 1 day, confirmed_at), `stamp_basis = first_sight`. History confirmed
after the vote is stamped D - 1 day, 00:00 UTC, on the statutory notice and flagged
`stamp_basis = statutory_history`: Japan's Public Offices Election Act requires a House of
Representatives election to be proclaimed at least 12 days ahead (17 for the House of
Councillors), and South African, Mexican and New Zealand general elections are fixed months
ahead, so PRE_DAYS + 1 sits inside the shortest notice. After the conditioner's own 24 h lag the
row conditions day D's bars. Rows exist only up to today.

WHAT IS DONATED. Per country, per symbol: `exogenous_conditioner` on `pre_event` and on
`post_event` (level_z, threshold 1), with the side fixed by MECHANISMS. Every cell is judged by
the one gauntlet; nothing here sizes, promotes or vetoes anything.
"""
from __future__ import annotations

import contextlib
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

#: (country, page, language). The authority's own site carries the coming vote; two public list
#: pages carry the history, so every past vote can be confirmed by a second page.
SOURCES: tuple[tuple[str, str, str], ...] = (
    ("za", "https://www.elections.org.za/", "en"),
    ("za", "https://en.wikipedia.org/wiki/Elections_in_South_Africa", "en"),
    ("za", "https://en.wikipedia.org/wiki/List_of_elections_in_South_Africa", "en"),
    ("mx", "https://www.ine.mx/", "es"),
    ("mx", "https://en.wikipedia.org/wiki/Elections_in_Mexico", "en"),
    ("mx", "https://es.wikipedia.org/wiki/Elecciones_federales_de_M%C3%A9xico", "es"),
    ("nz", "https://elections.nz/", "en"),
    ("nz", "https://en.wikipedia.org/wiki/List_of_New_Zealand_general_elections", "en"),
    ("nz", "https://en.wikipedia.org/wiki/Elections_in_New_Zealand", "en"),
    ("jp", "https://www.soumu.go.jp/senkyo/", "ja"),
    ("jp", "https://en.wikipedia.org/wiki/Elections_in_Japan", "en"),
    ("jp", "https://ja.wikipedia.org/wiki/%E8%A1%86%E8%AD%B0%E9%99%A2%E8%AD%B0%E5%93%A1%E7%B7%8F"
           "%E9%81%B8%E6%8C%99", "ja"),
)

#: symbol -> (side while pre_event is on, side while post_event is on), per country. A rising
#: USDxxx is the domestic currency weakening: the pre-vote risk premium, then its release.
MECHANISMS: dict[str, dict[str, tuple[int, int]]] = {
    "za": {"USDZAR": (1, -1), "EURZAR": (1, -1)},
    "mx": {"USDMXN": (1, -1), "EURMXN": (1, -1)},
    "nz": {"NZDUSD": (-1, 1), "AUDNZD": (1, -1)},
    "jp": {"USDJPY": (1, -1), "EURJPY": (1, -1)},
}

#: NATIONAL votes only (audit must-fix 1 on #388): a generic "election day" or 投票日 also names a
#: governor's race, a by-election or a referendum. Japanese text must also name a house.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "en": ("general election", "national election", "national and provincial elections",
           "federal election", "presidential election", "legislative election",
           "house of representatives election", "house of councillors election"),
    "es": ("elección federal", "elecciones federales", "elección presidencial",
           "jornada electoral federal", "proceso electoral federal"),
    "ja": ("総選挙", "通常選挙"),
}
JA_HOUSES = ("衆議院", "参議院")
#: A segment naming any of these is not a national vote, whatever else it says.
EXCLUDE: dict[str, tuple[str, ...]] = {
    "en": ("by-election", "by election", "local election", "municipal", "mayor", "governor",
           "gubernatorial", "referendum", "primary", "council election", "state election",
           "regional election", "leadership election", "party election", "provincial election"),
    "es": ("local", "municipal", "gubernatura", "estatal", "consulta", "revocación",
           "ayuntamiento"),
    "ja": ("知事", "市長", "区長", "町長", "村長", "統一地方", "補欠", "補選", "住民投票", "地方選",
           "議会"),
}
#: A date is the VOTE date only with a vote cue just before it (or 投票/執行 just after, or as
#: the date cell of a list-table row), and never right after an event that is not the vote
#: (audit must-fix 2: "first sat", "results declared", "registration closes" were taken).
CUE_SPAN = 40
CUE: dict[str, re.Pattern[str]] = {
    "en": re.compile(r"held on|\bheld\b|took place|polling day|election day|voting day|"
                     r"vot(?:e|ed|ing) on|will be held|scheduled for|\bdate\b", re.I),
    "es": re.compile(r"se celebr|celebrar|tendrá lugar|el día|realizad[ao] el|celebrad[ao] el|"
                     r"\bdel\b", re.I),
    "ja": re.compile(r"投票日|投票|執行日|期日"),
}
CUE_AFTER_JA = re.compile("^\\s*(?:\\([^)]{0,3}\\)|\uff08[^\uff09]{0,3}\uff09)?\\s*(?:投票|執行)")
NOT_THE_VOTE: dict[str, re.Pattern[str]] = {
    "en": re.compile(r"first sat|\bsat\b|declared|announced|registration|closes|close on|"
                     r"results|dissolved|proclaimed|sworn|took office|inaugurat|nomination|"
                     r"\bcalled\b", re.I),
    "es": re.compile(r"resultados|cómputo|registro|convocatoria|toma de protesta", re.I),
    "ja": re.compile(r"公示|告示|解散|開票|当選|任期|召集"),
}
#: Two different pages must read the same vote (within MERGE_DAYS) before it enters a series
#: (audit must-fix 3): one page's mis-read can never become a regime on its own.
MIN_SOURCES = 2
VOIDED = BASE / "data" / "election_calendar" / "voided.json"

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


def _dates_spans(text: str) -> list[tuple[int, date, int]]:
    """(start, date, end) for every date this code can read, in any of the four shapes."""
    out: list[tuple[int, date, int]] = []

    def add(mt: re.Match[str], y: int, m: int, d: int) -> None:
        with contextlib.suppress(ValueError):
            out.append((mt.start(), date(y, m, d), mt.end()))
    for mt in _EN1.finditer(text):
        add(mt, int(mt.group(3)), _MONTHS_EN[mt.group(2).lower()], int(mt.group(1)))
    for mt in _EN2.finditer(text):
        add(mt, int(mt.group(3)), _MONTHS_EN[mt.group(1).lower()], int(mt.group(2)))
    for mt in _ES.finditer(text):
        add(mt, int(mt.group(3)), _MONTHS_ES[mt.group(2).lower()], int(mt.group(1)))
    for mt in _JA.finditer(text):
        add(mt, int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
    for mt in _ISO.finditer(text):
        add(mt, int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
    return out



def _national(seg: str, lang: str) -> bool:
    low = seg.lower().replace("national and provincial", "national")
    langs = {lang, "en"}
    if any(x in low for lg in langs for x in EXCLUDE.get(lg, ())):
        return False
    return not (lang == "ja" and any(k in seg for k in KEYWORDS["ja"])
                and not any(h in seg for h in JA_HOUSES))


def _is_vote_date(seg: str, pos: int, lang: str, end: int) -> bool:
    before = seg[max(0, pos - CUE_SPAN):pos]
    langs = (lang, "en") if lang != "en" else ("en",)
    if any(NOT_THE_VOTE[lg].search(before) for lg in langs if lg in NOT_THE_VOTE):
        return False
    if any(CUE[lg].search(before) for lg in langs if lg in CUE):
        return True
    if lang == "ja" and CUE_AFTER_JA.search(seg[end:end + 12]):
        return True
    return " | " in seg            # the date cell of a list-table row


def extract(text: str, lang: str, *, today: date | None = None) -> list[dict[str, str]]:
    """Per block and sentence that names a NATIONAL vote: the one date nearest the keyword,
    within KEYWORD_SPAN characters, that reads as the vote date (cue, no non-vote event before
    it). One date per segment, with the quote it was read from."""
    keys = KEYWORDS.get(lang, ()) + (KEYWORDS["en"] if lang != "en" else ())
    limit = (today or datetime.now(UTC).date()) + timedelta(days=400)
    out: dict[str, dict[str, str]] = {}
    for seg in re.split(r"\n|(?<=[.!?\u3002])\s+", text):
        low = seg.lower()
        hits = [m.start() for k in keys for m in re.finditer(re.escape(k.lower()), low)]
        if not hits or not _national(seg, lang):
            continue
        best: tuple[int, date] | None = None
        for pos, d, end in _dates_spans(seg):
            gap = min(abs(pos - h) for h in hits)
            if (EARLIEST <= d <= limit and gap <= KEYWORD_SPAN
                    and _is_vote_date(seg, pos, lang, end)
                    and (best is None or gap < best[0])):
                best = (gap, d)
        if best is not None:
            out.setdefault(best[1].isoformat(), {"date": best[1].isoformat(),
                                                 "quote": seg[:240]})
    return sorted(out.values(), key=lambda e: e["date"])


def merge_events(store: dict[str, Any], cc: str, found: Sequence[dict[str, str]], url: str,
                 seen: str) -> int:
    """Record which page read which vote. A date within MERGE_DAYS of a known one is the same
    vote, read again: this page joins its `sources`, and the vote is CONFIRMED (stamped
    `confirmed_at`) the first time a second distinct page reads it. Returns new votes added."""
    rows = store.setdefault(cc, [])
    added = 0
    for e in found:
        d = date.fromisoformat(e["date"])
        row = next((r for r in rows
                    if abs((d - date.fromisoformat(r["date"])).days) <= MERGE_DAYS), None)
        if row is None:
            rows.append({"date": e["date"], "first_seen": seen, "url": url, "quote": e["quote"],
                         "sources": {url: seen}, "confirmed_at": None})
            added += 1
            continue
        srcs = row.setdefault("sources", {row.get("url", ""): row.get("first_seen", "")})
        if url not in srcs:
            srcs[url] = seen
            if len(srcs) >= MIN_SOURCES and not row.get("confirmed_at"):
                row["confirmed_at"] = seen
    rows.sort(key=lambda r: r["date"])
    return added


def voided(path: Path | None = None) -> dict[str, list[str]]:
    """{country: [dates]} withdrawn by hand (a mis-read both pages share, a moved vote). A vote
    within MERGE_DAYS of a voided date never enters a series or a cell again."""
    doc = _read_json(path or VOIDED, {}) or {}
    return {str(k): [str(d) for d in v] for k, v in doc.items() if isinstance(v, list)}


def confirmed(events: Sequence[dict[str, Any]], void: Sequence[str] = ()) -> list[dict[str, Any]]:
    """The votes two pages agree on and nobody voided -- the only ones a series may carry."""
    gone = [date.fromisoformat(v) for v in void]
    return [e for e in events
            if len(e.get("sources") or {}) >= MIN_SOURCES and e.get("confirmed_at")
            and not any(abs((date.fromisoformat(e["date"]) - g).days) <= MERGE_DAYS
                        for g in gone)]


SERIES_COLUMNS = ("available_time", "published_time", "retrieval_time", "source_id",
                  "vintage_id", "stamp_basis", "pre_event", "post_event")


def _stamp(d: date, ev: dict[str, Any] | None) -> tuple[datetime, str]:
    """When day D's row became knowable (audit must-fix 4 on #388). A vote the desk confirmed
    BEFORE it was held is stamped no earlier than that confirmation; one first confirmed after
    it was held is history, stamped D - 1 on the statutory notice and flagged as such."""
    statutory = datetime(d.year, d.month, d.day, tzinfo=UTC) - timedelta(days=1)
    if ev is None:
        return statutory, "calendar"
    try:
        seen = datetime.fromisoformat(str(ev.get("confirmed_at")))
    except (TypeError, ValueError):
        return statutory, "statutory_history"
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    vote = date.fromisoformat(str(ev["date"]))
    if seen < datetime(vote.year, vote.month, vote.day, tzinfo=UTC):
        return max(statutory, seen), "first_sight"
    return statutory, "statutory_history"


def series_rows(events: Sequence[dict[str, Any]], cc: str, *, today: date | None = None
                ) -> list[dict[str, Any]]:
    """One row a day from 400 days before the first vote to today, 0/1 in each window. The
    vintage is a hash of the votes it was built from, so a voided or added vote is a revision."""
    if not events:
        return []
    end = today or datetime.now(UTC).date()
    by_day = {date.fromisoformat(e["date"]): e for e in events}
    days = sorted(by_day)
    vintage = hashlib.sha256(json.dumps(sorted(e["date"] for e in events)).encode()
                             ).hexdigest()[:12]
    start = max(EARLIEST, days[0] - timedelta(days=400))
    rows = []
    d = start
    while d <= end:
        pre = next((e for e in days if 1 <= (e - d).days <= PRE_DAYS), None)
        post = next((e for e in days if 0 <= (d - e).days < POST_DAYS), None)
        hit = pre or post
        ev = by_day[hit] if hit is not None else None
        avail, basis = _stamp(d, ev)
        rows.append({"available_time": avail.isoformat(), "published_time": avail.isoformat(),
                     "retrieval_time": str(ev.get("confirmed_at") or "") if ev else "",
                     "source_id": f"election_{cc}", "vintage_id": vintage,
                     "stamp_basis": basis,
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
          lane_ok: Callable[[str, str], bool] | None = None,
          void: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """The pre-registered cells for every country with at least two CONFIRMED votes."""
    out: list[dict[str, Any]] = []
    for cc, syms in MECHANISMS.items():
        n = len(confirmed(store.get(cc) or [], (void or {}).get(cc, ())))
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
    void = voided()
    for cc in MECHANISMS:
        good = confirmed(store.get(cc) or [], void.get(cc, ()))
        rows = series_rows(good, cc, today=today)
        if rows:
            write_series(cc, rows)
        counts[cc] = {"events": len(store.get(cc) or []), "confirmed": len(good),
                      "voided": len(void.get(cc, ())), "rows": len(rows)}
    if lane_ok is None:
        try:
            import llm_lab
            lane_ok = llm_lab._lane_ok
        except Exception:
            def lane_ok(_s: str, _f: str) -> bool:    # no lane policy, no permission
                return False
    donate = cells(store, uni, lane_ok, void)
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
    # UNMEASURED IS A STATE (audit must-fix 5): pages that answered with no vote date, or a
    # calendar with no confirmed vote anywhere, measured nothing -- never "RAN" or "FRESH".
    why = None
    if ok and not any(p.get("dates") for p in ok):
        why = "every page fetched this pass held no national vote date the extractor accepts"
    elif not any(c["confirmed"] for c in counts.values()):
        why = (f"no vote is confirmed by {MIN_SOURCES} pages for any country, so no series "
               f"or cell exists")
    fresh_all = all(p["status"] == "FRESH" for p in per)
    state = ("DARK" if not ok and not fresh_all else UNMEASURED if why
             else "RAN" if ok else "FRESH")
    doc = {"generated_at": _now(), "state": state, **({"why": why} if why else {}),
           "sources": per, "countries": counts,
           "cells_total": len(donate), "cells_donated": len(fresh),
           "seconds": round(time.time() - started, 1),
           "pit": f"a vote confirmed before it was held: row D stamped max(D-1, confirmation) "
                  f"(stamp_basis first_sight); history confirmed after the vote: D-1 on the "
                  f"statutory notice (stamp_basis statutory_history; the {PRE_DAYS}d pre window "
                  f"sits inside the shortest notice, JP HoR 12d)"}
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
