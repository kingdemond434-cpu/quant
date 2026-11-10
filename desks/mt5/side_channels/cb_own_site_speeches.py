"""Central bank speeches from the banks' OWN sites -> dated per-currency tone the desk may trade.

WHY THIS EXISTS (2026-11-10). The only speech bodies the desk held came from the BIS
`speeches.zip` corpus (`bis_speech_tone.py`). Its download page reads "Use of the content is
allowed for noncommercial purposes", so nothing built on it may size a live position or back a
certificate that trades; and the copy on disk ends 2026-06-25 with nothing refreshing it. The
central banks publish the same speeches themselves, several under terms that do permit use: the
Federal Reserve's site is public domain, the Bank of Canada permits free use with attribution,
and the RBA publishes under CC BY 4.0. This reads those, on a schedule.

WHAT IT STORES. Lexicon COUNTS per speech (the same hawkish/dovish phrases `bis_speech_tone`
uses), the speech's URL and title, and the reuse clause it was read under. Never the body: the
desk needs the reading, not a copy of the text.

POINT-IN-TIME. `available_time` is the feed's own publication stamp when the speech came from a
feed. A speech found on a year index has only its delivery DATE, so it is stamped at the end of
the NEXT day (UTC): late on purpose, never early.

POLITENESS. One request per host at a time through `libs.data.polite_fetch` (shared host gate),
an honest User-Agent, a hard per-pass page budget, and every page fetched once in its life
(`state.json`). robots.txt is read and recorded as a label (LAWS 5e); 401/403/429/451 stops that
host and is recorded, never retried in the pass and never routed around.

OUTPUT (outside `data/intelligence/`, which the candidate compiler reads as donations):
    desks/mt5/data/cb_speeches/own_site_speech_tone.jsonl   one row per speech, append-only
    desks/mt5/data/cb_speeches/own_site_tone_series.jsonl   one row per (date, currency)
    desks/mt5/reports/CB_OWN_SITE_SPEECHES.json             coverage, labels, stops, backlog
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.robotparser
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCES = Path(__file__).with_name("cb_speech_sources.json")
OUT = DESK / "data" / "cb_speeches"
REPORT = DESK / "reports" / "CB_OWN_SITE_SPEECHES.json"

#: Speech pages fetched per pass, all banks together. The history is ~100 pages a year per bank;
#: at this rate the backlog drains in days while no host ever sees more than a slow reader.
MAX_PAGES_PER_PASS = 60
#: Index pages (one per bank-year) fetched per pass. Each is fetched once, except the current
#: and previous year, which are re-read so a new speech is found without a feed.
MAX_INDEX_PER_PASS = 6
#: A page shorter than this after tag-stripping is navigation chrome or an error page, not a
#: speech; it is counted and retried on a later pass, never scored.
MIN_SPEECH_CHARS = 1500
HARD_STOP = frozenset({401, 403, 429, 451})

_DROP_BLOCKS = re.compile(r"(?is)<(script|style|nav|header|footer|noscript|form)\b.*?</\1>")
_TAGS = re.compile(r"(?s)<[^>]+>")
_WS = re.compile(r"\s+")
_ITEM = re.compile(r"(?is)<item\b.*?</item>")
_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")


def _cdata(s: str) -> str:
    return html.unescape(re.sub(r"(?s)<!\[CDATA\[(.*?)\]\]>", r"\1", s)).strip()


def page_text(raw: str) -> str:
    """Visible text of a page: scripts, styles and site chrome removed, tags stripped."""
    return _WS.sub(" ", html.unescape(_TAGS.sub(" ", _DROP_BLOCKS.sub(" ", raw)))).strip()


def page_title(raw: str) -> str:
    m = _TITLE.search(raw)
    return _WS.sub(" ", html.unescape(m.group(1))).strip()[:300] if m else ""


def link_date(m: re.Match[str]) -> str | None:
    """YYYY-MM-DD from a link regex's groups: (y, m, d), or None when it carries no full date."""
    g = [x for x in m.groups() if x]
    if len(g) < 3:
        return None
    try:
        return date(int(g[0]), int(g[1]), int(g[2])).isoformat()
    except ValueError:
        return None


def feed_items(xml: str, bank: Mapping[str, Any]) -> list[dict[str, str]]:
    """[{url, published, title}] from an RSS 2.0 or RSS 1.0/RDF feed. An item with no
    publication stamp is dropped: an undated row cannot be placed on the bar clock."""
    out: list[dict[str, str]] = []
    rx = re.compile(str(bank["link_regex"]))
    for block in _ITEM.findall(xml):
        lm = re.search(r"(?is)<link[^>]*>(.*?)</link>", block)
        url = _cdata(lm.group(1)) if lm else ""
        if not rx.search(url):
            continue
        stamp: datetime | None = None
        pm = re.search(r"(?is)<pubDate[^>]*>(.*?)</pubDate>", block)
        dm = re.search(r"(?is)<dc:date[^>]*>(.*?)</dc:date>", block)
        try:
            if pm:
                stamp = parsedate_to_datetime(_cdata(pm.group(1)))
            elif dm:
                stamp = datetime.fromisoformat(_cdata(dm.group(1)).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            stamp = None
        if stamp is None:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        tm = _TITLE.search(block)
        out.append({"url": url, "published": stamp.astimezone(UTC).isoformat(timespec="seconds"),
                    "title": _cdata(tm.group(1))[:300] if tm else ""})
    return out


def index_links(raw: str, bank: Mapping[str, Any]) -> list[dict[str, str]]:
    """[{url, date}] of every speech link on a year index whose URL carries its own date."""
    rx = re.compile(str(bank["link_regex"]))
    seen: dict[str, str] = {}
    for m in rx.finditer(raw):
        d = link_date(m)
        if d is None:
            continue
        u = m.group(0)
        seen.setdefault(u if u.startswith("http") else str(bank["base"]) + u, d)
    return [{"url": u, "date": d} for u, d in sorted(seen.items())]


def available_time(published: str | None, day: str) -> str:
    """The feed's stamp when there is one; otherwise the end of the day AFTER delivery (UTC)."""
    if published:
        return published
    d = date.fromisoformat(day) + timedelta(days=1)
    return datetime(d.year, d.month, d.day, 23, 59, tzinfo=UTC).isoformat(timespec="seconds")


def robots_label(robots_text: str | None, url: str, agent: str) -> dict[str, str]:
    """LAWS 5e: robots is a LABEL. Unreadable -> ACCESS_UNCLEAR; a Disallow -> PUBLIC_WITH_TERMS."""
    if robots_text is None:
        return {"access": "ACCESS_UNCLEAR", "note": "robots.txt unreadable"}
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_text.splitlines())
    if rp.can_fetch(agent, url):
        return {"access": "PUBLIC", "note": ""}
    return {"access": "PUBLIC_WITH_TERMS", "note": "robots.txt Disallow covers this path"}


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False), "utf-8")
    try:
        os.replace(tmp, p)
    except PermissionError:
        p.unlink(missing_ok=True)
        os.replace(tmp, p)


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (date, currency), stamped with the LATEST availability among its speeches.
    net_tone is None, not 0.0, when the day's speeches carry no lexicon hit (L1.28a)."""
    agg: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "hawk": 0, "dove": 0, "banks": set(), "avail": "", "terms": set()})
    for r in rows:
        a = agg[(r["date"], r["currency"])]
        a["n"] += 1
        a["hawk"] += int(r["hawk"])
        a["dove"] += int(r["dove"])
        a["banks"].add(r["bank"])
        a["terms"].add(r["terms"])
        a["avail"] = max(a["avail"], str(r["available_time"]))
    out = []
    for (day, ccy), a in sorted(agg.items()):
        tot = a["hawk"] + a["dove"]
        out.append({"date": day, "currency": ccy, "banks": sorted(a["banks"]),
                    "n_speeches": a["n"], "hawk": a["hawk"], "dove": a["dove"],
                    "net_tone": round((a["hawk"] - a["dove"]) / tot, 4) if tot else None,
                    "available_time": a["avail"], "source": "own_site",
                    # a day is PERMITTED only if every speech in it was read under such terms
                    "terms": "PERMITTED" if a["terms"] == {"PERMITTED"} else "RESEARCH_ONLY"})
    return out


Fetch = Callable[[str], tuple[int | None, str, str]]


def _polite_fetch(agent: str) -> Fetch:
    from libs.data import polite_fetch

    def fetch(url: str) -> tuple[int | None, str, str]:
        r = polite_fetch.get(url, headers={"User-Agent": agent}, leg="cb_own_site_speeches")
        return r.status, r.text, r.error
    return fetch


def refresh(*, fetch: Fetch | None = None, registry: Mapping[str, Any] | None = None,
            out: Path | None = None, report: Path | None = None, today: date | None = None,
            max_pages: int = MAX_PAGES_PER_PASS, max_index: int = MAX_INDEX_PER_PASS
            ) -> dict[str, Any]:
    """One pass: discover speeches (feeds first, then a few year indexes), score a bounded number
    of unread pages, rewrite the series and the report. Returns the report."""
    from side_channels.bis_speech_tone import score_tone

    reg = registry if registry is not None else _read_json(SOURCES, {})
    out = out or OUT
    report = report or REPORT
    today = today or datetime.now(UTC).date()
    agent = str(reg.get("user_agent") or "quant-desk-research/1.0")
    get = fetch or _polite_fetch(agent)
    out.mkdir(parents=True, exist_ok=True)
    state = _read_json(out / "state.json", {})
    done: dict[str, str] = state.setdefault("done", {})
    known: dict[str, dict[str, str]] = state.setdefault("known", {})
    idx_done: dict[str, str] = state.setdefault("index_done", {})
    stops: dict[str, Any] = state.setdefault("hard_stops", {})
    per_speech = out / "own_site_speech_tone.jsonl"
    rep: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "banks": {}, "pages_fetched": 0, "index_fetched": 0}
    index_budget, page_budget = max_index, max_pages
    new_rows: list[dict[str, Any]] = []

    for bank in reg.get("banks") or []:
        name = str(bank["bank"])
        b: dict[str, Any] = {"currency": bank["currency"], "terms": bank["terms"],
                             "terms_clause": bank.get("terms_clause", ""),
                             "terms_url": bank.get("terms_url", ""), "short_pages": 0,
                             "errors": [], "scored_this_pass": 0}
        rep["banks"][name] = b
        if name in stops:
            b["hard_stop"] = stops[name]
            b["missed_growth"] = (f"{name} speeches unread since the host answered "
                                  f"{stops[name].get('code')}; {bank['currency']} tone is "
                                  "UNMEASURED from this source, not neutral")
            continue

        def stop(code: int, url: str, name: str = name, b: dict[str, Any] = b) -> None:
            stops[name] = {"code": code, "url": url,
                           "at": datetime.now(UTC).isoformat(timespec="seconds")}
            b["hard_stop"] = stops[name]

        st, txt, _err = get(str(bank["base"]) + "/robots.txt")
        if st in HARD_STOP:
            stop(int(st or 0), str(bank["base"]) + "/robots.txt")
            continue
        robots_text = txt if st is not None and 200 <= st < 300 else None

        for feed in bank.get("feeds") or []:
            st, txt, err = get(str(feed))
            if st in HARD_STOP:
                stop(int(st or 0), str(feed))
                break
            if st is None or not 200 <= st < 300:
                b["errors"].append({"url": feed, "status": st, "error": err[:60]})
                continue
            for it in feed_items(txt, bank):
                k = known.setdefault(it["url"], {"bank": name})
                k.setdefault("published", it["published"])
                k.setdefault("date", it["published"][:10])
                k.setdefault("title", it["title"])
        if name in stops:
            continue

        tmpl = bank.get("index")
        if tmpl:
            years = list(range(today.year, int(bank.get("index_from_year", today.year)) - 1, -1))
            for y in years:
                url = str(tmpl).format(year=y)
                fresh = y >= today.year - 1
                if index_budget <= 0 or (url in idx_done and not fresh) \
                        or idx_done.get(url) == today.isoformat():
                    continue
                st, txt, err = get(url)
                index_budget -= 1
                rep["index_fetched"] += 1
                if st in HARD_STOP:
                    stop(int(st or 0), url)
                    break
                if st is None or not 200 <= st < 300:
                    b["errors"].append({"url": url, "status": st, "error": err[:60]})
                    continue
                for it in index_links(txt, bank):
                    k = known.setdefault(it["url"], {"bank": name})
                    k.setdefault("date", it["date"])
                idx_done[url] = today.isoformat()
            if name in stops:
                continue

        todo = sorted((u for u, k in known.items() if k.get("bank") == name and u not in done),
                      key=lambda u: known[u].get("date", ""), reverse=True)
        b["backlog"] = len(todo)
        for url in todo:
            if page_budget <= 0:
                break
            k = known[url]
            day = str(k.get("date") or "")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or day > today.isoformat():
                done[url] = "undated_or_future"
                continue
            st, raw, err = get(url)
            page_budget -= 1
            rep["pages_fetched"] += 1
            if st in HARD_STOP:
                stop(int(st or 0), url)
                break
            if st is None or not 200 <= st < 300:
                b["errors"].append({"url": url, "status": st, "error": err[:60]})
                if st == 404:
                    done[url] = "404"
                continue
            text = page_text(raw)
            if len(text) < MIN_SPEECH_CHARS:
                b["short_pages"] += 1
                continue
            hawk, dove = score_tone(text)
            lab = robots_label(robots_text, url, agent)
            new_rows.append({
                "date": day, "available_time": available_time(k.get("published"), day),
                "bank": name, "currency": bank["currency"], "hawk": hawk, "dove": dove,
                "chars": len(text), "url": url,
                "title": (k.get("title") or page_title(raw))[:300],
                "source": "own_site", "terms": bank["terms"], "access": lab["access"],
                "access_note": lab["note"], "attribution": bank.get("attribution", ""),
            })
            done[url] = day
            b["scored_this_pass"] += 1
        b["backlog"] = sum(1 for u, k in known.items() if k.get("bank") == name and u not in done)
        b["errors"] = b["errors"][:10]

    if new_rows:
        with per_speech.open("a", encoding="utf-8") as fh:
            for r in new_rows:
                fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    rows: list[dict[str, Any]] = []
    if per_speech.exists():
        for line in per_speech.read_text("utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    series = aggregate(rows)
    tmp = out / "own_site_tone_series.jsonl.tmp"
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                           for r in series), "utf-8")
    os.replace(tmp, out / "own_site_tone_series.jsonl")
    _write_json(out / "state.json", state)
    by_ccy: dict[str, dict[str, Any]] = {}
    for r in rows:
        c = by_ccy.setdefault(r["currency"], {"speeches": 0, "first": r["date"], "last": r["date"]})
        c["speeches"] += 1
        c["first"], c["last"] = min(c["first"], r["date"]), max(c["last"], r["date"])
    rep.update({"speeches_total": len(rows), "series_rows": len(series), "coverage": by_ccy,
                "uncovered_note": "a currency absent from coverage is UNMEASURED, never neutral",
                "research_only_elsewhere": "BIS speeches.zip (noncommercial terms)"})
    _write_json(report, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_PASS)
    args = ap.parse_args(argv)
    rep = refresh(max_pages=args.max_pages)
    print(json.dumps({"speeches_total": rep["speeches_total"],
                      "pages_fetched": rep["pages_fetched"], "coverage": rep["coverage"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
