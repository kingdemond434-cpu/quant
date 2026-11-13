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

POINT-IN-TIME. `published_utc` is the feed's own publication instant when the speech came from a
feed. A speech found on a year index has only its delivery DATE; then `published_utc` is that
bare date, and the contract with the reader (`cb_tone_event`) is that a bare date is knowable
only from the END of the next day (00:00 UTC of D+2): a US-evening speech on date D is spoken
after 00:00 UTC of D+1. The series this module writes applies the same rule.

POLITENESS. One request per host at a time through `libs.data.polite_fetch` (shared host gate),
an honest User-Agent, a hard per-pass page budget, and every page fetched once in its life
(`state.json`). robots.txt is read FIRST and obeyed for this series: a Disallowed feed, index or
page is not fetched, is counted per bank (`robots_skipped`) and carries a missed_growth line,
because a row the desk may trade on must have been read through an open door. An UNREADABLE
robots.txt (5xx, network error, an HTML page) fails closed: the bank is skipped for the pass
with a missed_growth line, since polite_fetch itself checks no robots. 401/403/429/451
stops that host and is recorded, never retried in the pass and never routed around; after
HARD_STOP_COOLDOWN the host is tried again, and the first refusal stops it again.

PERMITTED means BOTH: the bank's reuse terms were read and permit use, AND the page was PUBLIC
under a robots.txt this pass could read. Anything else is `unverified` and research-only.

OUTPUT.
    desks/mt5/data/intelligence/central_banks/official_speech_tone.jsonl
        one row per speech, append-only; the file `cb_tone_event` reads. ONLY rows read under
        permitting terms AND through a PUBLIC door are written here: the candidate compiler
        reads every .jsonl in this tree as donations and does not know what `terms` means.
    desks/mt5/data/cb_speeches/research_only_speech_tone.jsonl
        every other row (unverified terms, unreadable robots, a changed terms page):
        research-only, outside the donation tree
    desks/mt5/data/cb_speeches/state.json, official_tone_series.jsonl
        this module's own state and a (date, currency) series, kept out of the donation tree
    desks/mt5/reports/CB_OWN_SITE_SPEECHES.json   coverage, labels, stops, backlog
"""
from __future__ import annotations

import argparse
import hashlib
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
SPEECH_ROWS = DESK / "data" / "intelligence" / "central_banks" / "official_speech_tone.jsonl"
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
#: A stopped host is left alone this long, then tried again; a refusal stops it again.
HARD_STOP_COOLDOWN = timedelta(hours=24)
#: A page that comes back too short this many times is given up on and named in the report.
MAX_SHORT_ATTEMPTS = 3
#: The bank's terms page is re-read this often; a changed page drops the bank to `unverified`
#: until someone re-reads the clause and moves `terms_read` in the registry.
TERMS_RECHECK = timedelta(days=7)

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


def published_utc(published: str | None, day: str) -> str:
    """The feed's publication instant, or the bare delivery date when no instant is known."""
    return published or day


def knowable_from(published: str) -> str:
    """When a row may first be used: its instant, or the END of the day after a bare date
    (00:00 UTC of D+2). Late on purpose: a speech given in the US evening of date D is spoken
    at or after 00:00 UTC of D+1 (20:00 Pacific is 04:00 UTC), so the start of D+1 would let a
    bar use words not yet said."""
    if len(published) > 10:
        return published
    d = date.fromisoformat(published) + timedelta(days=2)
    return datetime(d.year, d.month, d.day, tzinfo=UTC).isoformat(timespec="seconds")


def robots_label(robots_text: str | None, url: str, agent: str) -> dict[str, str]:
    """Unreadable robots.txt -> ACCESS_UNCLEAR; a Disallow -> PUBLIC_WITH_TERMS (and `refresh`
    does not fetch that URL); otherwise PUBLIC."""
    if robots_text is None:
        return {"access": "ACCESS_UNCLEAR", "note": "robots.txt unreadable"}
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_text.splitlines())
    if rp.can_fetch(agent, url):
        return {"access": "PUBLIC", "note": ""}
    return {"access": "PUBLIC_WITH_TERMS", "note": "robots.txt Disallow covers this path"}


def tradeable(row: Mapping[str, Any]) -> bool:
    """May this row sit in the donation tree: permitting terms AND a PUBLIC door, nothing less."""
    return row.get("terms") == "permitted" and row.get("access") == "PUBLIC"


def read_rows(path: Path) -> list[dict[str, Any]]:
    """The per-speech rows, one per URL, FIRST row wins. Rows are appended before the state file
    is saved, so a crash between the two re-scores the same URLs on the next pass; without this
    a speech would be counted twice in its day."""
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return []
    for line in path.read_text("utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("url"):
            rows.setdefault(str(r["url"]), r)
    return list(rows.values())


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
        lambda: {"n": 0, "hawk": 0, "dove": 0, "banks": set(), "avail": "", "terms": set(),
                 "access": set()})
    for r in rows:
        a = agg[(str(r.get("delivered") or r["published_utc"])[:10], r["currency"])]
        a["n"] += 1
        a["hawk"] += int(r["hawk"])
        a["dove"] += int(r["dove"])
        a["banks"].add(r["bank"])
        a["terms"].add(r["terms"])
        a["access"].add(r.get("access"))
        a["avail"] = max(a["avail"], knowable_from(str(r["published_utc"])))
    out = []
    for (day, ccy), a in sorted(agg.items()):
        tot = a["hawk"] + a["dove"]
        out.append({"date": day, "currency": ccy, "banks": sorted(a["banks"]),
                    "n_speeches": a["n"], "hawk": a["hawk"], "dove": a["dove"],
                    "net_tone": round((a["hawk"] - a["dove"]) / tot, 4) if tot else None,
                    "available_time": a["avail"],
                    # permitted only if EVERY speech in the day was read under permitting
                    # terms AND through a door robots.txt showed open
                    "terms": "permitted" if a["terms"] == {"permitted"}
                    and a["access"] == {"PUBLIC"} else "unverified"})
    return out


Fetch = Callable[[str], tuple[int | None, str, str]]


def _polite_fetch(agent: str) -> Fetch:
    from libs.data import polite_fetch

    def fetch(url: str) -> tuple[int | None, str, str]:
        r = polite_fetch.get(url, headers={"User-Agent": agent}, leg="cb_own_site_speeches")
        return r.status, r.text, r.error
    return fetch


def refresh(*, fetch: Fetch | None = None, registry: Mapping[str, Any] | None = None,
            out: Path | None = None, report: Path | None = None,
            speech_rows: Path | None = None, today: date | None = None,
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
    short: dict[str, int] = state.setdefault("short_attempts", {})
    terms_seen: dict[str, dict[str, str]] = state.setdefault("terms_pages", {})
    now = datetime.now(UTC)
    per_speech = speech_rows or SPEECH_ROWS
    per_speech.parent.mkdir(parents=True, exist_ok=True)
    rep: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "banks": {}, "pages_fetched": 0, "index_fetched": 0}
    index_budget, page_budget = max_index, max_pages
    new_rows: list[dict[str, Any]] = []

    for bank in reg.get("banks") or []:
        name = str(bank["bank"])
        b: dict[str, Any] = {"currency": bank["currency"], "terms": bank["terms"],
                             "terms_clause": bank.get("terms_clause", ""),
                             "terms_url": bank.get("terms_url", ""), "short_pages": 0,
                             "short_given_up": [], "robots_skipped": 0, "future_pending": 0,
                             "errors": [], "scored_this_pass": 0}
        rep["banks"][name] = b
        if name in stops:
            try:
                cooled = now - datetime.fromisoformat(stops[name]["at"]) >= HARD_STOP_COOLDOWN
            except (KeyError, TypeError, ValueError):
                cooled = False
            if cooled:
                # one more knock: robots.txt is the first request below, and any refusal on
                # this pass stops the host again with a fresh stamp
                b["retried_after_stop"] = stops.pop(name)
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
        # no robots.txt at all (404) is the convention for "nothing is disallowed"
        robots_text = txt if st is not None and 200 <= st < 300 else "" if st == 404 else None
        if robots_text is not None and robots_text.lstrip()[:15].lower().startswith(
                ("<!doctype", "<html")):
            robots_text = None      # an HTML page served as robots.txt is no robots file
        b["robots"] = "unreadable" if robots_text is None else "read"
        if robots_text is None:
            # FAIL CLOSED: a 5xx, a network error or an HTML body means this pass cannot know
            # what the bank disallows, so nothing of it is fetched until a later pass reads it
            b["robots_unreadable_status"] = st
            b["missed_growth"] = (f"{name} speeches unread this pass because robots.txt was "
                                  f"unreadable (status {st}); {bank['currency']} tone is "
                                  "UNMEASURED from this source, not neutral")
            continue

        def allowed(url: str, robots_text: str | None = robots_text,
                    b: dict[str, Any] = b) -> bool:
            if robots_label(robots_text, url, agent)["access"] == "PUBLIC_WITH_TERMS":
                b["robots_skipped"] += 1
                return False
            return True

        # the terms page itself: fetch date and content hash, re-read on a slow clock
        bank_terms, turl = str(bank["terms"]), str(bank.get("terms_url") or "")
        seen = terms_seen.get(name) or {}
        if seen.get("terms_read") != str(bank.get("terms_read", "")) or seen.get("url") != turl:
            seen = {}           # the clause was re-read by a person or session: new baseline
        due = True
        if seen.get("fetched"):
            try:
                due = now - datetime.fromisoformat(seen["fetched"]) >= TERMS_RECHECK
            except ValueError:
                due = True
        if turl and due and allowed(turl):
            st, txt, _err = get(turl)
            if st in HARD_STOP:
                stop(int(st or 0), turl)
                continue
            if st is not None and 200 <= st < 300:
                digest = hashlib.sha256(page_text(txt).encode("utf-8")).hexdigest()
                seen = {"url": turl, "terms_read": str(bank.get("terms_read", "")),
                        "baseline_sha256": seen.get("baseline_sha256") or digest,
                        "sha256": digest, "fetched": now.isoformat(timespec="seconds")}
                terms_seen[name] = seen
        b["terms_page"] = dict(seen)
        if seen and seen.get("sha256") != seen.get("baseline_sha256"):
            bank_terms = "unverified"
            b["terms_changed"] = True
            b["missed_growth"] = (f"{name} terms page changed since it was read "
                                  f"{bank.get('terms_read', '')}; new rows are research-only "
                                  "until the clause is re-read and terms_read is moved")
        b["terms_effective"] = bank_terms

        for feed in bank.get("feeds") or []:
            if not allowed(str(feed)):
                continue
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
                if not allowed(url):
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
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                done[url] = "undated"
                continue
            if day > today.isoformat():
                b["future_pending"] += 1    # announced, not yet given: read it when it is
                continue
            if not allowed(url):
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
                short[url] = int(short.get(url, 0)) + 1
                if short[url] >= MAX_SHORT_ATTEMPTS:
                    done[url] = "short"
                    short.pop(url, None)
                continue
            short.pop(url, None)
            hawk, dove = score_tone(text)
            lab = robots_label(robots_text, url, agent)
            new_rows.append({
                "source": str(bank["source"]), "terms": bank_terms,
                "terms_basis": f"{bank.get('terms_clause', '')} ({bank.get('terms_url', '')}, "
                               f"read {bank.get('terms_read', '')})",
                "bank": name, "currency": str(bank["currency"]).upper(),
                "published_utc": published_utc(k.get("published"), day), "delivered": day,
                "hawk": hawk, "dove": dove, "chars": len(text), "url": url,
                "title": (k.get("title") or page_title(raw))[:300],
                "access": lab["access"], "access_note": lab["note"],
                "attribution": bank.get("attribution", ""),
            })
            done[url] = day
            b["scored_this_pass"] += 1
        b["backlog"] = sum(1 for u, k in known.items() if k.get("bank") == name and u not in done)
        b["short_given_up"] = sorted(u for u, v in done.items() if v == "short"
                                     and (known.get(u) or {}).get("bank") == name)[:50]
        if b["robots_skipped"]:
            b["missed_growth_robots"] = (
                f"{b['robots_skipped']} {name} URL(s) not fetched because robots.txt disallows "
                f"them; any {bank['currency']} speech behind them is UNMEASURED, not neutral")
        b["errors"] = b["errors"][:10]

    research_only = out / "research_only_speech_tone.jsonl"
    for dest, keep in ((per_speech, True), (research_only, False)):
        batch = [r for r in new_rows if tradeable(r) is keep]
        if batch:
            with dest.open("a", encoding="utf-8") as fh:
                for r in batch:
                    fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    # a permitted row never comes from the research-only file, whatever was appended to it
    rows = [r for r in read_rows(per_speech) if tradeable(r)]
    seen_urls = {str(r["url"]) for r in rows}
    held = [r for r in read_rows(research_only) if str(r["url"]) not in seen_urls]
    rep["research_only_rows"] = len(held)
    rows += [{**r, "terms": "unverified"} if tradeable(r) else r for r in held]
    series = aggregate(rows)
    tmp = out / "official_tone_series.jsonl.tmp"
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                           for r in series), "utf-8")
    os.replace(tmp, out / "official_tone_series.jsonl")
    _write_json(out / "state.json", state)
    by_ccy: dict[str, dict[str, Any]] = {}
    for r in rows:
        day = str(r.get("delivered") or r["published_utc"])[:10]
        c = by_ccy.setdefault(r["currency"], {"speeches": 0, "first": day, "last": day,
                                              "terms": r["terms"]})
        c["speeches"] += 1
        c["first"], c["last"] = min(c["first"], day), max(c["last"], day)
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
