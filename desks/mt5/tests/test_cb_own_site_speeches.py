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


def test_a_speech_with_only_a_date_is_available_late_never_early() -> None:
    assert cb.available_time(None, "2025-12-15") == "2025-12-16T23:59:00+00:00"
    assert cb.available_time("2026-10-15T02:55:00+00:00", "2026-10-15") == \
        "2026-10-15T02:55:00+00:00"


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
              report=tmp_path / "r.json", today=date(2026, 11, 10))
    rep = cb.refresh(**kw)
    assert rep["banks"]["Fed"]["scored_this_pass"] == 1 and rep["speeches_total"] == 1
    row = json.loads((tmp_path / "o" / "own_site_speech_tone.jsonl").read_text().splitlines()[0])
    assert row["terms"] == "PERMITTED" and row["access"] == "PUBLIC" and row["currency"] == "USD"
    assert row["hawk"] > 0 and row["dove"] == 1            # the body's one "rate cut", not the chrome
    assert row["available_time"] == "2026-10-15T02:55:00+00:00"
    assert "restrictive" not in json.dumps(row)            # counts only, never the text
    series = json.loads((tmp_path / "o" / "own_site_tone_series.jsonl").read_text().splitlines()[0])
    assert series["terms"] == "PERMITTED" and series["net_tone"] > 0
    cb.refresh(**kw)
    assert fetch.calls.count(url) == 1                     # a page is read once in its life


def test_a_refusal_stops_the_host_and_is_named_as_missed_growth(tmp_path: Path) -> None:
    bank = {**FED, "index": None}
    fetch = _site({"https://www.federalreserve.gov/robots.txt": (200, ""),
                   FED["feeds"][0]: (403, "")})
    kw = dict(fetch=fetch, registry=_one_bank(bank), out=tmp_path / "o",
              report=tmp_path / "r.json", today=date(2026, 11, 10))
    rep = cb.refresh(**kw)
    assert rep["banks"]["Fed"]["hard_stop"]["code"] == 403
    n = len(fetch.calls)
    rep = cb.refresh(**kw)
    assert len(fetch.calls) == n                           # never retried, never routed around
    assert "UNMEASURED" in rep["banks"]["Fed"]["missed_growth"]


def test_page_budget_bounds_a_pass_and_a_disallow_is_a_label(tmp_path: Path) -> None:
    idx = FED["index"].format(year=2026)
    links = "".join(f'<a href="/newsevents/speech/x202601{d:02d}a.htm">s</a>' for d in range(1, 11))
    pages = {"https://www.federalreserve.gov/robots.txt":
             (200, "User-agent: *\nDisallow: /newsevents/"),
             FED["feeds"][0]: (200, "<rss></rss>"), idx: (200, links)}
    for d in range(1, 11):
        pages[f"https://www.federalreserve.gov/newsevents/speech/x202601{d:02d}a.htm"] = (200, SPEECH)
    bank = {**FED, "index_from_year": 2026}
    rep = cb.refresh(fetch=_site(pages), registry=_one_bank(bank), out=tmp_path / "o",
                     report=tmp_path / "r.json", today=date(2026, 11, 10), max_pages=4)
    assert rep["pages_fetched"] == 4 and rep["banks"]["Fed"]["backlog"] == 6
    rows = [json.loads(x) for x in
            (tmp_path / "o" / "own_site_speech_tone.jsonl").read_text().splitlines()]
    assert {r["access"] for r in rows} == {"PUBLIC_WITH_TERMS"}     # labelled, still read (5e)
    assert rows[0]["available_time"].endswith("T23:59:00+00:00")


def test_output_is_outside_the_donation_tree() -> None:
    assert "intelligence" not in cb.OUT.parts
