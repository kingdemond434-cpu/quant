"""Central bank speeches from the banks' own sites: discovery, point-in-time stamps, politeness
limits and the terms label. No network: every fetch is a fake."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from side_channels import cb_own_site_speeches as cb  # noqa: E402

REG = json.loads(cb.SOURCES.read_text("utf-8"))
FED = next(b for b in REG["banks"] if b["bank"] == "Fed")
BOC = next(b for b in REG["banks"] if b["bank"] == "BoC")
RBA = next(b for b in REG["banks"] if b["bank"] == "RBA")

FED_FEED = """<rss version="2.0"><channel>
<item><title><![CDATA[Bowman, Supervisory Modernization]]></title>
<link><![CDATA[https://www.federalreserve.gov/newsevents/speech/bowman20261014a.htm]]></link>
<pubDate><![CDATA[Thu, 15 Oct 2026 02:55:00 GMT]]></pubDate></item>
<item><title>Undated</title>
<link>https://www.federalreserve.gov/newsevents/speech/waller20261001a.htm</link></item>
</channel></rss>"""

BOC_FEED = """<rdf:RDF><item rdf:about="x"><title>Opening Statement</title>
<link>https://www.bankofcanada.ca/2026/11/opening-statement-2026-11-05/</link>
<dc:date>2026-11-05T10:30:59+00:00</dc:date></item></rdf:RDF>"""

SPEECH = ("<html><head><title>Speech by Governor X</title><script>var a='rate cut';</script>"
          "</head><body><nav>easing easing easing</nav><div>"
          + "We see inflationary pressures and policy must stay restrictive. " * 40
          + "A rate cut is not on the table. </div><footer>stimulus</footer></body></html>")


def _site(pages: dict[str, tuple[int, str]]):
    calls: list[str] = []

    def fetch(url: str) -> tuple[int | None, str, str]:
        calls.append(url)
        st, body = pages.get(url, (404, ""))
        return st, body, "" if st == 200 else f"HTTP {st}"

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def _one_bank(bank: dict) -> dict:
    return {"user_agent": "test-agent", "banks": [bank]}


def test_feed_items_keep_the_publication_stamp_and_drop_undated_rows() -> None:
    items = cb.feed_items(FED_FEED, FED)
    assert [i["url"].rsplit("/", 1)[-1] for i in items] == ["bowman20261014a.htm"]
    assert items[0]["published"] == "2026-10-15T02:55:00+00:00"
    boc = cb.feed_items(BOC_FEED, BOC)
    assert boc[0]["published"] == "2026-11-05T10:30:59+00:00"


def test_index_links_read_the_date_from_the_url() -> None:
    raw = ('<a href="/newsevents/speech/miran20251215a.htm">x</a>'
           '<a href="/newsevents/speech/miran20251215a.htm">dup</a>'
           '<a href="/newsevents/speech/2025-speeches.htm">index</a>')
    assert cb.index_links(raw, FED) == [
        {"url": "https://www.federalreserve.gov/newsevents/speech/miran20251215a.htm",
         "date": "2025-12-15"}]
    rba = cb.index_links('<a href="/speeches/2025/sp-ag-2025-12-16.html">s</a>'
                         '<a href="/speeches/2026/sp-sp-ag-2026-11-09-2.html">s</a>', RBA)
    assert [r["date"] for r in rba] == ["2025-12-16", "2026-11-09"]


def test_a_bare_date_is_knowable_only_from_the_end_of_the_next_day() -> None:
    assert cb.published_utc(None, "2025-12-15") == "2025-12-15"
    assert cb.knowable_from("2025-12-15") == "2025-12-17T00:00:00+00:00"
    assert cb.knowable_from("2026-10-15T02:55:00+00:00") == "2026-10-15T02:55:00+00:00"


def test_page_text_drops_scripts_and_site_chrome() -> None:
    t = cb.page_text(SPEECH)
    assert "var a" not in t and "easing" not in t and "stimulus" not in t
    assert "inflationary pressures" in t


def test_refresh_scores_once_labels_terms_and_stores_no_body(tmp_path: Path) -> None:
    url = "https://www.federalreserve.gov/newsevents/speech/bowman20261014a.htm"
    bank = {**FED, "index": None}
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (200, "User-agent: *\nAllow: /"),
                   FED["feeds"][0]: (200, FED_FEED), url: (200, SPEECH)})
    kw = dict(fetch=fetch, registry=_one_bank(bank), out=tmp_path / "o",
              report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
              today=date(2026, 11, 10))
    rep = cb.refresh(**kw)
    assert rep["banks"]["Fed"]["scored_this_pass"] == 1 and rep["speeches_total"] == 1
    row = json.loads((tmp_path / "rows.jsonl").read_text().splitlines()[0])
    assert row["terms"] == "permitted" and row["source"] == "fed_board"
    assert row["access"] == "PUBLIC" and row["currency"] == "USD"
    assert "public domain" in row["terms_basis"] and "disclaimer.htm" in row["terms_basis"]
    assert set(row) >= {"published_utc", "delivered", "hawk", "dove", "chars", "url", "title"}
    assert row["hawk"] > 0 and row["dove"] == 1            # the body's one "rate cut", not the chrome
    assert row["published_utc"] == "2026-10-15T02:55:00+00:00" and row["delivered"] == "2026-10-15"
    assert "restrictive" not in json.dumps(row)            # counts only, never the text
    series = json.loads((tmp_path / "o" / "official_tone_series.jsonl").read_text().splitlines()[0])
    assert series["terms"] == "permitted" and series["net_tone"] > 0
    cb.refresh(**kw)
    assert fetch.calls.count(url) == 1                     # a page is read once in its life


def test_a_refusal_stops_the_host_and_is_named_as_missed_growth(tmp_path: Path) -> None:
    bank = {**FED, "index": None}
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (200, ""),
                   FED["feeds"][0]: (403, "")})
    kw = dict(fetch=fetch, registry=_one_bank(bank), out=tmp_path / "o",
              report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
              today=date(2026, 11, 10))
    rep = cb.refresh(**kw)
    assert rep["banks"]["Fed"]["hard_stop"]["code"] == 403
    n = len(fetch.calls)
    rep = cb.refresh(**kw)
    assert len(fetch.calls) == n                           # never retried, never routed around
    assert "UNMEASURED" in rep["banks"]["Fed"]["missed_growth"]


def _ten_speeches(robots: str) -> tuple[dict[str, tuple[int, str]], dict]:
    idx = FED["index"].format(year=2026)
    links = "".join(f'<a href="/newsevents/speech/x202601{d:02d}a.htm">s</a>' for d in range(1, 11))
    pages = {"https://www.federalreserve.gov/robots.txt": (200, robots),
             FED["feeds"][0]: (200, "<rss></rss>"), idx: (200, links)}
    for d in range(1, 11):
        pages[f"https://www.federalreserve.gov/newsevents/speech/x202601{d:02d}a.htm"] = (200, SPEECH)
    return pages, {**FED, "index_from_year": 2026}


def test_page_budget_bounds_a_pass(tmp_path: Path) -> None:
    pages, bank = _ten_speeches("User-agent: *\nAllow: /")
    rep = cb.refresh(fetch=_site(pages), registry=_one_bank(bank), out=tmp_path / "o",
                     report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
                     today=date(2026, 11, 10), max_pages=4)
    assert rep["pages_fetched"] == 4 and rep["banks"]["Fed"]["backlog"] == 6
    rows = [json.loads(x) for x in (tmp_path / "rows.jsonl").read_text().splitlines()]
    assert {r["access"] for r in rows} == {"PUBLIC"}
    assert len(rows[0]["published_utc"]) == 10                      # a bare date, no invented hour


def test_a_robots_disallow_is_never_fetched_and_is_counted(tmp_path: Path) -> None:
    pages, bank = _ten_speeches("User-agent: *\nDisallow: /newsevents/speech/x")
    fetch = _site(pages)
    rep = cb.refresh(fetch=fetch, registry=_one_bank(bank), out=tmp_path / "o",
                     report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
                     today=date(2026, 11, 10))
    assert not [u for u in fetch.calls if "/newsevents/speech/x" in u]
    fed = rep["banks"]["Fed"]
    assert rep["pages_fetched"] == 0 and rep["speeches_total"] == 0
    assert fed["robots_skipped"] == 10 and fed["backlog"] == 10     # still owed, not written off
    assert "UNMEASURED" in fed["missed_growth_robots"]


def test_permitted_needs_permitting_terms_and_a_public_door() -> None:
    base = {"bank": "Fed", "currency": "USD", "published_utc": "2026-10-15", "delivered":
            "2026-10-15", "hawk": 2, "dove": 1, "terms": "permitted", "access": "PUBLIC"}
    ok = cb.aggregate([{**base, "url": "a"}, {**base, "url": "b"}])
    assert ok[0]["terms"] == "permitted" and ok[0]["n_speeches"] == 2
    for bad in ({"access": "ACCESS_UNCLEAR"}, {"access": "PUBLIC_WITH_TERMS"},
                {"access": None}, {"terms": "unverified"}):
        day = cb.aggregate([{**base, "url": "a"}, {**base, "url": "b", **bad}])
        assert day[0]["terms"] == "unverified", bad                 # one doubtful speech taints the day


def test_unreadable_robots_is_read_but_never_permitted(tmp_path: Path) -> None:
    url = "https://www.federalreserve.gov/newsevents/speech/bowman20261014a.htm"
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (500, ""),
                   FED["feeds"][0]: (200, FED_FEED), url: (200, SPEECH)})
    cb.refresh(fetch=fetch, registry=_one_bank({**FED, "index": None}), out=tmp_path / "o",
               report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
               today=date(2026, 11, 10))
    assert not (tmp_path / "rows.jsonl").exists()        # nothing doubtful in the donation tree
    row = json.loads((tmp_path / "o" / "research_only_speech_tone.jsonl").read_text()
                     .splitlines()[0])
    assert row["access"] == "ACCESS_UNCLEAR" and row["terms"] == "permitted"
    series = json.loads((tmp_path / "o" / "official_tone_series.jsonl").read_text().splitlines()[0])
    assert series["terms"] == "unverified"


def test_a_crash_before_the_state_save_does_not_count_a_speech_twice(tmp_path: Path) -> None:
    url = "https://www.federalreserve.gov/newsevents/speech/bowman20261014a.htm"
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (200, ""),
                   FED["feeds"][0]: (200, FED_FEED), url: (200, SPEECH)})
    kw = dict(fetch=fetch, registry=_one_bank({**FED, "index": None}), out=tmp_path / "o",
              report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
              today=date(2026, 11, 10))
    cb.refresh(**kw)
    (tmp_path / "o" / "state.json").unlink()            # rows were appended, the state was lost
    rep = cb.refresh(**kw)
    assert fetch.calls.count(url) == 2                  # the page was re-scored and re-appended
    assert len((tmp_path / "rows.jsonl").read_text().splitlines()) == 2
    assert rep["speeches_total"] == 1                   # ...and still counts once
    series = [json.loads(x) for x in
              (tmp_path / "o" / "official_tone_series.jsonl").read_text().splitlines()]
    assert len(series) == 1 and series[0]["n_speeches"] == 1


def test_a_stopped_host_is_tried_again_after_the_cooldown_and_stops_again(tmp_path: Path) -> None:
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (403, "")})
    kw = dict(fetch=fetch, registry=_one_bank({**FED, "index": None}), out=tmp_path / "o",
              report=tmp_path / "r.json", speech_rows=tmp_path / "rows.jsonl",
              today=date(2026, 11, 10))
    cb.refresh(**kw)
    sp = tmp_path / "o" / "state.json"
    st = json.loads(sp.read_text())
    st["hard_stops"]["Fed"]["at"] = "2026-01-01T00:00:00+00:00"
    sp.write_text(json.dumps(st))
    rep = cb.refresh(**kw)
    assert len(fetch.calls) == 2                        # exactly one more knock
    assert rep["banks"]["Fed"]["hard_stop"]["at"] > "2026-01-02"    # refused: stopped afresh
    cb.refresh(**kw)
    assert len(fetch.calls) == 2


def test_short_pages_are_capped_and_named_and_a_future_speech_stays_pending(
        tmp_path: Path) -> None:
    short = "https://www.federalreserve.gov/newsevents/speech/bowman20261014a.htm"
    future = "https://www.federalreserve.gov/newsevents/speech/x20261201a.htm"
    idx = FED["index"].format(year=2026)
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (200, ""),
                   FED["feeds"][0]: (200, FED_FEED), short: (200, "<html>moved</html>"),
                   idx: (200, '<a href="/newsevents/speech/x20261201a.htm">s</a>')})
    kw = dict(fetch=fetch, registry=_one_bank({**FED, "index_from_year": 2026}),
              out=tmp_path / "o", report=tmp_path / "r.json",
              speech_rows=tmp_path / "rows.jsonl", today=date(2026, 11, 10))
    for _ in range(cb.MAX_SHORT_ATTEMPTS + 2):
        rep = cb.refresh(**kw)
    assert fetch.calls.count(short) == cb.MAX_SHORT_ATTEMPTS
    assert rep["banks"]["Fed"]["short_given_up"] == [short]
    assert fetch.calls.count(future) == 0 and rep["banks"]["Fed"]["future_pending"] == 1
    state = json.loads((tmp_path / "o" / "state.json").read_text())
    assert future not in state["done"]                  # read it when it has been given


def test_a_changed_terms_page_drops_new_rows_to_unverified(tmp_path: Path) -> None:
    url = "https://www.federalreserve.gov/newsevents/speech/bowman20261014a.htm"
    pages = {"https://www.federalreserve.gov/robots.txt": (200, ""),
             FED["terms_url"]: (200, "<p>public domain</p>"),
             FED["feeds"][0]: (200, "<rss></rss>")}
    kw = dict(fetch=_site(pages), registry=_one_bank({**FED, "index": None}),
              out=tmp_path / "o", report=tmp_path / "r.json",
              speech_rows=tmp_path / "rows.jsonl", today=date(2026, 11, 10))
    rep = cb.refresh(**kw)
    tp = rep["banks"]["Fed"]["terms_page"]
    assert len(tp["sha256"]) == 64 and tp["fetched"] and tp["sha256"] == tp["baseline_sha256"]
    sp = tmp_path / "o" / "state.json"
    st = json.loads(sp.read_text())
    st["terms_pages"]["Fed"]["fetched"] = "2026-01-01T00:00:00+00:00"   # the recheck is due
    sp.write_text(json.dumps(st))
    pages[FED["terms_url"]] = (200, "<p>all rights reserved</p>")
    pages[FED["feeds"][0]] = (200, FED_FEED)
    pages[url] = (200, SPEECH)
    rep = cb.refresh(**kw)
    assert rep["banks"]["Fed"]["terms_changed"] and "re-read" in rep["banks"]["Fed"]["missed_growth"]
    assert not (tmp_path / "rows.jsonl").exists()
    held = (tmp_path / "o" / "research_only_speech_tone.jsonl").read_text().splitlines()
    assert json.loads(held[0])["terms"] == "unverified"


def test_rba_rows_stay_unverified_and_state_stays_out_of_the_donation_tree() -> None:
    assert RBA["terms"] == "unverified" and FED["terms"] == "permitted" == BOC["terms"]
    assert {b["source"] for b in REG["banks"]} == {"fed_board", "boc", "rba"}
    # the compiler reads every .json/.jsonl under data/intelligence as donations: only the
    # per-speech rows belong there, never this module's own state or series
    assert "intelligence" not in cb.OUT.parts
    assert cb.SPEECH_ROWS.name == "official_speech_tone.jsonl"


def test_no_unverified_row_can_land_in_the_donation_tree(tmp_path: Path) -> None:
    url = "https://www.rba.gov.au/speeches/2026/sp-gov-2026-10-14.html"
    assert cb.re.search(RBA["link_regex"], url)
    feed = ("<rss><channel><item><title>Speech</title><link>" + url + "</link>"
            "<pubDate>Wed, 14 Oct 2026 02:00:00 GMT</pubDate></item></channel></rss>")
    pages = {"https://www.rba.gov.au/robots.txt": (200, ""), url: (200, SPEECH)}
    for f in RBA["feeds"]:
        pages[f] = (200, feed)
    rep = cb.refresh(fetch=_site(pages), registry=_one_bank({**RBA, "index": None}),
                     out=tmp_path / "o", report=tmp_path / "r.json",
                     speech_rows=tmp_path / "intelligence" / "rows.jsonl",
                     today=date(2026, 11, 10))
    assert rep["banks"]["RBA"]["scored_this_pass"] == 1 and rep["research_only_rows"] == 1
    assert not (tmp_path / "intelligence" / "rows.jsonl").exists()
    series = json.loads((tmp_path / "o" / "official_tone_series.jsonl").read_text().splitlines()[0])
    assert series["terms"] == "unverified" and series["currency"] == "AUD"
    assert cb.tradeable({"terms": "permitted", "access": "PUBLIC"})
    for bad in ({"terms": "unverified", "access": "PUBLIC"}, {"terms": "permitted"},
                {"terms": "permitted", "access": "ACCESS_UNCLEAR"},
                {"terms": "permitted", "access": "PUBLIC_WITH_TERMS"}):
        assert not cb.tradeable(bad), bad


def test_a_us_evening_speech_is_not_knowable_before_it_is_spoken() -> None:
    # delivered 20:00 Pacific on 14 October = 04:00 UTC on the 15th; the index gives only the date
    spoken = "2026-10-15T04:00:00+00:00"
    assert cb.knowable_from("2026-10-14") == "2026-10-16T00:00:00+00:00" > spoken
