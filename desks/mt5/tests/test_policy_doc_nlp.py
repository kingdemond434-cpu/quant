"""Policy-document NLP (row 47): fences first, holds persisted, robots fail closed, states dated."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import policy_doc_nlp as pdn  # noqa: E402

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

LISTING = b"""<html><body>
<a href="/news/2026-11-17/mps.html">Monetary Policy Statement 2026-11-17</a>
<a href="/about.html">About us</a>
</body></html>"""
DOC = b"<html><body><p>The Committee decided to raise interest rates and tighten.</p></body></html>"


def _point(monkeypatch, tmp_path: Path) -> None:
    for name, fn in (("STATE", "state.json"), ("RELEASES", "RELEASES.json"),
                     ("DOCS", "docs.jsonl"), ("EVENTS", "events.jsonl"),
                     ("OUT", "POLICY_DOC_NLP.json")):
        monkeypatch.setattr(pdn, name, tmp_path / fn)
    monkeypatch.setattr(pdn, "ROOT", tmp_path.parent)


def _open_src(**kw) -> dict:
    src = {"id": "test_bank", "bank": "TB", "lang": "en", "kind": "html",
           "url": "https://bank.example.org/news/index.html", "include": "Monetary Policy",
           "targets": {"USDZAR": -1, "EURZAR": -1}, "terms": "OPEN",
           "terms_clause": "public domain", "terms_url": "https://bank.example.org/terms"}
    src.update(kw)
    return src


def _getter(table: dict[str, tuple[int, bytes, str]], seen: list[str]):
    def get(url: str, timeout: float) -> tuple[int, bytes, str]:
        seen.append(url)
        return table.get(url, (404, b"", "text/plain"))
    return get


def _score(monkeypatch) -> None:
    def score_lex(text: str, lang: str):
        h = text.count("raise interest rates") + text.count("tighten")
        return h, 0, (1.0 if h else None)
    monkeypatch.setattr(pdn, "scorer",
                        lambda: (score_lex, {"en", "zh", "ja"}, "cb_tone_lab.score_lex"))


def test_every_shipped_source_is_fenced_and_sends_no_request(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    seen: list[str] = []
    doc = pdn.run(now=NOW, get=_getter({}, seen))
    assert seen == []
    banks = {r["bank"] for r in doc["sources"].values()}
    assert banks == {"PBOC", "CSRC", "SAFE", "BOK", "MAS", "BOJ", "RBI", "SARB"}
    assert doc["status"] == "UNMEASURED" and doc["counts"]["new_event_states"] == 0
    for rep in doc["sources"].values():
        assert rep["status"] in {"TERMS_BLOCKED", "TERMS_UNREAD", "ROBOTS_BLOCKED"}
        assert rep["missed_growth"]
    blocked = [s for s in pdn.load_sources() if s["terms"] == "TERMS_BLOCKED"]
    assert {s["bank"] for s in blocked} == {"SAFE", "MAS", "BOJ", "RBI", "SARB"}
    assert all(len(s["terms_clause"]) > 40 and s["terms_read"] for s in blocked)


def test_the_shared_refused_list_wins_over_an_open_terms_row(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    seen: list[str] = []
    doc = pdn.run(now=NOW, get=_getter({}, seen),
                  sources=[_open_src(url="https://www.cboe.com/x")])
    assert seen == [] and doc["sources"]["test_bank"]["status"] == "BLOCKED_ON_TERMS"


def test_an_open_source_yields_dated_signed_states(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _score(monkeypatch)
    seen: list[str] = []
    table = {"https://bank.example.org/robots.txt": (200, b"User-agent: *\nAllow: /\n",
                                                     "text/plain"),
             "https://bank.example.org/news/index.html": (200, LISTING, "text/html"),
             "https://bank.example.org/news/2026-11-17/mps.html": (200, DOC, "text/html")}
    doc = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "FETCHED"
    assert doc["counts"]["new_docs"] == 1 and doc["counts"]["new_event_states"] == 2
    states = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    by = {s["symbol"]: s for s in states}
    assert by["USDZAR"]["state"] == "HAWKISH" and by["USDZAR"]["signed"] == -1.0
    assert by["USDZAR"]["published"] == "2026-11-17"
    assert by["USDZAR"]["available_time"] == "2026-11-18T00:00:00+00:00"
    ledger = (tmp_path / "docs.jsonl").read_text()
    assert "raise interest rates" not in ledger            # text is never written to the ledger
    again = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
    assert again["counts"]["new_docs"] == 0                 # a known document is not re-read


def test_html_where_robots_should_be_is_unread_and_refuses(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    seen: list[str] = []
    table = {"https://bank.example.org/robots.txt": (200, b"<!DOCTYPE html><html>home</html>",
                                                     "text/html")}
    doc = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "ROBOTS_UNREAD"
    assert seen == ["https://bank.example.org/robots.txt"]


def test_robots_disallow_and_unreadable_robots_both_refuse(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    seen: list[str] = []
    dis = {"https://bank.example.org/robots.txt": (200, b"User-agent: *\nDisallow: /news/\n",
                                                   "text/plain")}
    doc = pdn.run(now=NOW, get=_getter(dis, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "ROBOTS_REFUSED"
    err = {"https://bank.example.org/robots.txt": (503, b"", "text/plain")}
    doc = pdn.run(now=NOW, get=_getter(err, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "ROBOTS_UNREAD"
    assert "https://bank.example.org/news/index.html" not in seen


def test_403_holds_until_a_person_releases_it(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    seen: list[str] = []
    table = {"https://bank.example.org/robots.txt": (404, b"", "text/plain"),
             "https://bank.example.org/news/index.html": (403, b"Forbidden", "text/html")}
    doc = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == pdn.HELD_UNTIL_RELEASED
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["test_bank"]["hold"] == pdn.HELD_UNTIL_RELEASED
    later = NOW + timedelta(days=30)
    n = len(seen)
    doc = pdn.run(now=later, get=_getter(table, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == pdn.HELD_UNTIL_RELEASED and len(seen) == n
    (tmp_path / "RELEASES.json").write_text(json.dumps(
        {"test_bank": {"released_at": later.isoformat(), "by": "principal"}}))
    ok = dict(table)
    ok["https://bank.example.org/news/index.html"] = (200, b"<html></html>", "text/html")
    doc = pdn.run(now=later, get=_getter(ok, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "FETCHED"


def test_waf_page_and_451_hold_until_released(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    for status, body in ((200, b"<html><title>Just a moment...</title></html>"), (451, b"")):
        (tmp_path / "state.json").unlink(missing_ok=True)
        seen: list[str] = []
        table = {"https://bank.example.org/robots.txt": (404, b"", "text/plain"),
                 "https://bank.example.org/news/index.html": (status, body, "text/html")}
        doc = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
        assert doc["sources"]["test_bank"]["status"] == pdn.HELD_UNTIL_RELEASED


def test_429_holds_for_24h_then_lifts_by_itself(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    seen: list[str] = []
    table = {"https://bank.example.org/robots.txt": (429, b"", "text/plain")}
    doc = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == pdn.HELD_24H
    doc = pdn.run(now=NOW + timedelta(hours=23), get=_getter(table, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == pdn.HELD_24H and len(seen) == 1
    ok = {"https://bank.example.org/robots.txt": (404, b"", "text/plain"),
          "https://bank.example.org/news/index.html": (200, b"<html></html>", "text/html")}
    doc = pdn.run(now=NOW + timedelta(hours=25), get=_getter(ok, seen), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "FETCHED"


def test_a_language_without_a_lexicon_is_unmeasured_not_scored_in_english(monkeypatch,
                                                                          tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _score(monkeypatch)
    seen: list[str] = []
    table = {"https://bank.example.org/robots.txt": (404, b"", "text/plain"),
             "https://bank.example.org/news/index.html": (200, LISTING, "text/html"),
             "https://bank.example.org/news/2026-11-17/mps.html": (200, DOC, "text/html")}
    pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src(lang="ko")])
    states = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert states and all(s["state"] == "UNMEASURED" and s["tone"] is None for s in states)


def test_the_agent_is_honest_and_names_the_organ() -> None:
    assert pdn.HONEST_UA.startswith(pdn.ROBOTS_AGENT) and "Mozilla" not in pdn.HONEST_UA
    assert "policy_doc_nlp" in pdn.HONEST_UA


def test_robots_markup_fails_closed_however_it_opens(monkeypatch, tmp_path) -> None:
    """A WAF page served as text/plain that opens with <body>, a comment or a bare <?xml is
    markup, not rules: unread, so refused, and the listing is never requested."""
    _point(monkeypatch, tmp_path)
    for body in (b"<body><h1>Checking your browser</h1></body>",
                 b"\n  <!-- edge 7f3a --><div>blocked</div>",
                 b'<?xml version="1.0"?><error>denied</error>',
                 b"User-agent: *\nAllow: /\n<!DOCTYPE html><html>tail</html>"):
        seen: list[str] = []
        table = {"https://bank.example.org/robots.txt": (200, body, "text/plain")}
        doc = pdn.run(now=NOW, get=_getter(table, seen), sources=[_open_src()])
        assert doc["sources"]["test_bank"]["status"] == "ROBOTS_UNREAD", body
        assert seen == ["https://bank.example.org/robots.txt"]
    assert pdn._looks_html(b"\xef\xbb\xbf<html>")
    assert not pdn._looks_html(b"User-agent: *\nDisallow:\n")


def test_robots_hold_mapping_is_kept_and_non_text_is_unread(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    for status, want in ((401, pdn.HELD_UNTIL_RELEASED), (403, pdn.HELD_UNTIL_RELEASED),
                         (451, pdn.HELD_UNTIL_RELEASED), (429, pdn.HELD_24H)):
        (tmp_path / "state.json").unlink(missing_ok=True)
        table = {"https://bank.example.org/robots.txt": (status, b"", "text/plain")}
        doc = pdn.run(now=NOW, get=_getter(table, []), sources=[_open_src()])
        assert doc["sources"]["test_bank"]["status"] == want
    (tmp_path / "state.json").unlink(missing_ok=True)
    table = {"https://bank.example.org/robots.txt": (200, b"User-agent: *\nAllow: /\n",
                                                     "application/octet-stream")}
    doc = pdn.run(now=NOW, get=_getter(table, []), sources=[_open_src()])
    assert doc["sources"]["test_bank"]["status"] == "ROBOTS_UNREAD"
