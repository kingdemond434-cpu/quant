"""The moat collectors: is a capture really immutable, is a chart really only a lead, and is
`knowable_at` really the publish stamp rather than the crawl time.

EVERY FETCH IS STUBBED. The module's two doors to the network -- `fetch_text` (which wraps the
desk's one HTTP client, `deep_forest_miner._http`) and `fetch_bytes` (the same client without
the decode) -- are replaced with fixtures, so no test here reaches a host, and a test that
believes it fetched something when it did not would fail rather than pass quietly.

THE THREE LOAD-BEARING TESTS, and the rest is arithmetic around them.

`test_an_existing_capture_is_never_overwritten` plants different bytes at the content-addressed
path and asserts the writer REFUSES and leaves them alone. An archive with a repair path is a
cache, and the whole point of the raw store is that a page which changed under the desk cannot
change what the desk recorded.

`test_a_chart_is_a_lead_stub_and_never_a_number` asserts that an image produces `media_path`,
the source's own caption, `quantitative: False`, and claims stamped `lead_stub` -- so nothing
downstream can read a number off a picture and have it look like a measured series.

`test_knowable_at_is_the_publish_stamp_never_the_crawl_time` asserts the two stamps are stored
in different fields with different values. They are one substitution apart, and the substitution
is a lookahead that would flatter every backtest the claim ever reaches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import moat_collectors as mc  # noqa: E402

from libs.moat import registry as R  # noqa: E402

PAGE = (
    '<html><head><title>Gold and the fix</title>'
    '<meta property="article:published_time" content="2026-09-01T10:00:00Z"></head>'
    "<body><p>Gold rallies into the London fix in 62% of sessions.</p>"
    "<p>USDJPY falls after the Tokyo TTM fix on gotobi days.</p></body></html>"
)
BARE_PAGE = "<html><body><p>Gold rallies into the London fix in 62% of sessions.</p></body></html>"
CSV = b"date,symbol,close\n2026-09-01,XAUUSD,2410.5\n2026-09-02,XAUUSD,2415.0\n"
NOTEBOOK = json.dumps({
    "cells": [
        {"cell_type": "markdown", "source": ["XAUUSD reverts after the London fix.\n"]},
        {"cell_type": "code", "source": ["sharpe = backtest('XAUUSD')\n"],
         "outputs": [{"text": ["SECRET_OUTPUT_VALUE 1.93"]}]},
    ],
    "metadata": {"date": "2026-08-14T09:00:00Z"},
}).encode("utf-8")
FEED = (
    '<?xml version="1.0"?><rss><channel>'
    "<item><title>Why gold rallies into the fix</title>"
    "<description>The 4pm London fix forces index funds to transact at 62% of sessions."
    "</description><pubDate>2026-07-04T08:00:00Z</pubDate>"
    '<enclosure url="https://example.org/ep1.mp3" type="audio/mpeg"/></item>'
    "</channel></rss>"
)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def moat(tmp_path, monkeypatch):
    """The whole store, the registry and the pacing, pointed at `tmp_path`."""
    monkeypatch.setattr(mc, "MOAT", tmp_path / "moat")
    monkeypatch.setattr(mc, "SLEEP_S", 0.0)
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


@pytest.fixture
def conn(moat):
    c = R.connect()
    yield c
    c.close()


def _source(c: Any, source_id: str, url: str, kind: str = "html", **cols: Any) -> None:
    fields = {"source_id": source_id, "url": url, "kind": kind, "status": "active",
              "language": "en", **cols}
    keys = list(fields)
    c.execute(f"INSERT INTO sources({','.join(keys)}) "
              f"VALUES({','.join('?' * len(keys))})", [fields[k] for k in keys])
    c.commit()


def _stub_text(monkeypatch, body: str = PAGE, status: int = 200, err: str = "") -> list[str]:
    seen: list[str] = []

    def _fake(url: str, lang: str = "") -> tuple[str, int, str]:
        seen.append(url)
        return body, status, err

    monkeypatch.setattr(mc, "fetch_text", _fake)
    return seen


def _stub_bytes(monkeypatch, data: bytes, status: int = 200, err: str = "") -> list[str]:
    seen: list[str] = []

    def _fake(url: str, lang: str = "") -> tuple[bytes, int, str]:
        seen.append(url)
        return data, status, err

    monkeypatch.setattr(mc, "fetch_bytes", _fake)
    return seen


def _explode(monkeypatch) -> None:
    """Both doors to the network wired to fail the test if anything opens them."""
    def _never(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a dry run fetched something")
    monkeypatch.setattr(mc, "fetch_text", _never)
    monkeypatch.setattr(mc, "fetch_bytes", _never)


# --------------------------------------------------------------------------- immutability
def test_a_second_capture_of_identical_bytes_is_a_no_op(moat):
    first, sha_a, created_a = mc.write_capture("ground", b"the bytes", "html")
    second, sha_b, created_b = mc.write_capture("ground", b"the bytes", "html")
    assert created_a is True and created_b is False
    assert first == second and sha_a == sha_b
    assert list(first.parent.iterdir()) == [first]
    assert first.read_bytes() == b"the bytes"


def test_an_existing_capture_is_never_overwritten(moat):
    path, _sha, _created = mc.write_capture("ground", b"the bytes", "html")
    path.write_bytes(b"tampered")
    with pytest.raises(mc.ImmutableCaptureError):
        mc.write_capture("ground", b"the bytes", "html")
    assert path.read_bytes() == b"tampered", "the refusal must not repair the store either"


def test_different_bytes_are_different_captures_never_a_replacement(moat):
    a, sha_a, _ = mc.write_capture("ground", b"version one", "html")
    b, sha_b, _ = mc.write_capture("ground", b"version two", "html")
    assert sha_a != sha_b and a != b
    assert a.exists() and b.exists()


def test_a_repeat_pass_records_a_duplicate_and_normalises_nothing_new(conn, monkeypatch):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    first = mc.run(budget_s=30, max_sources=5, conn=conn)
    second = mc.run(budget_s=30, max_sources=5, conn=conn)
    assert first["captures_new"] == 1 and first["documents_normalised"] == 1
    assert second["captures_new"] == 0 and second["captures_duplicate"] == 1
    assert second["documents_normalised"] == 0


# --------------------------------------------------------------------------- knowable_at
def test_knowable_at_is_the_publish_stamp_never_the_crawl_time(conn, monkeypatch):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    caps = mc.collect_html({"source_id": "ground_a", "url": "https://example.org/a"}, 30.0)
    doc = mc.normalise(caps[0])
    assert doc["knowable_at"] == "2026-09-01T10:00:00Z"
    assert doc["provenance"]["fetched_at"] != doc["knowable_at"]
    assert doc["provenance"]["url"] == "https://example.org/a"


def test_knowable_at_is_unmeasured_when_the_source_states_none(conn, monkeypatch):
    _stub_text(monkeypatch, BARE_PAGE)
    caps = mc.collect_html({"source_id": "bare", "url": "https://example.org/b"}, 30.0)
    doc = mc.normalise(caps[0])
    assert doc["knowable_at"] == mc.UNMEASURED
    assert doc["provenance"]["fetched_at"]


def test_a_source_row_may_declare_the_publish_stamp_but_never_its_crawl_time(conn, monkeypatch):
    _stub_text(monkeypatch, BARE_PAGE)
    row = {"source_id": "bare", "url": "https://example.org/b",
           "meta_json": json.dumps({"published_at": "2026-05-05T00:00:00Z"}),
           "first_seen": "2026-09-17T00:00:00Z", "last_crawled": "2026-09-17T00:00:00Z"}
    doc = mc.normalise(mc.collect_html(row, 30.0)[0])
    assert doc["knowable_at"] == "2026-05-05T00:00:00Z"


def test_the_report_calls_an_empty_pass_unmeasured_rather_than_zero(conn):
    report = mc.run(budget_s=30, max_sources=5, conn=conn)
    assert report["knowable_at_measured_share"] is None
    assert "UNMEASURED" in report["unmeasured"]["knowable_at"]


# --------------------------------------------------------------------------- per media type
def test_html_keeps_the_visible_text_and_the_title(conn, monkeypatch):
    _stub_text(monkeypatch)
    cap = mc.collect_html({"source_id": "g", "url": "https://example.org/a"}, 30.0)[0]
    assert cap.media_type == "html" and cap.title == "Gold and the fix"
    assert "London fix" in cap.text and "<p>" not in cap.text


def test_a_pdf_that_cannot_be_read_keeps_the_capture_and_says_unmeasured(conn, monkeypatch):
    _stub_bytes(monkeypatch, b"%PDF-1.4 not really a pdf")
    cap = mc.collect_pdf({"source_id": "paper", "url": "https://example.org/p.pdf"}, 30.0)[0]
    assert Path(cap.raw_path).exists(), "the capture is kept even when nothing can be extracted"
    assert cap.text == "" and cap.unmeasured
    assert mc.normalise(cap)["knowable_at"] == mc.UNMEASURED


def test_slides_are_a_pdf_capture_that_carries_its_media_path(conn, monkeypatch):
    _stub_bytes(monkeypatch, b"%PDF-1.4 deck")
    cap = mc.collect_slides({"source_id": "deck", "url": "https://example.org/d.pdf"}, 30.0)[0]
    assert cap.media_type == "slides"
    assert cap.media_path == cap.raw_path and Path(cap.media_path).exists()


def test_a_table_keeps_its_header(conn, monkeypatch):
    _stub_bytes(monkeypatch, CSV)
    cap = mc.collect_table({"source_id": "series", "url": "https://example.org/s.csv"}, 30.0)[0]
    assert cap.text.splitlines()[0] == "date,symbol,close"
    assert "2026-09-02,XAUUSD,2415.0" in cap.text


def test_an_xlsx_this_box_cannot_open_keeps_the_capture_and_says_unmeasured(conn, monkeypatch):
    # openpyxl is NOT installed here (measured), so `pd.read_excel` cannot open the workbook.
    # The rows are UNMEASURED and the bytes are still on disk -- the honest read, not an empty
    # table that looks like a spreadsheet with no rows in it.
    _stub_bytes(monkeypatch, b"PK not really a workbook")
    cap = mc.collect_table({"source_id": "book", "url": "https://example.org/b.xlsx"}, 30.0)[0]
    assert Path(cap.raw_path).exists() and cap.text == ""
    assert cap.unmeasured and "UNMEASURED" in mc.normalise(cap)["knowable_at"]


def test_a_notebook_reads_markdown_and_code_but_never_a_stored_output(conn, monkeypatch):
    _stub_bytes(monkeypatch, NOTEBOOK)
    cap = mc.collect_notebook({"source_id": "nb", "url": "https://example.org/n.ipynb"}, 30.0)[0]
    assert "[markdown]" in cap.text and "[code]" in cap.text
    assert "XAUUSD reverts" in cap.text and "backtest('XAUUSD')" in cap.text
    assert "SECRET_OUTPUT_VALUE" not in cap.text, "a stored output is a number nobody can date"
    assert cap.knowable_at == "2026-08-14T09:00:00Z"


def test_a_chart_is_a_lead_stub_and_never_a_number(conn, monkeypatch):
    _stub_bytes(monkeypatch, PNG)
    row = {"source_id": "charts", "url": "https://example.org/c.png",
           "meta_json": json.dumps({"alt": "XAUUSD rallies into the 15:00 London fix"})}
    cap = mc.collect_chart(row, 30.0)[0]
    doc = mc.normalise(cap)
    assert doc["lead_stub"] is True
    assert doc["quantitative"] is False
    assert doc["media_path"] == cap.raw_path and Path(doc["media_path"]).exists()
    assert doc["text"] == "XAUUSD rallies into the 15:00 London fix"
    claims = mc.claims_of(doc)
    assert claims and all(c["kind"] == "lead_stub" for c in claims)
    assert all(c["text"] in doc["text"] for c in claims), "no number may be invented off a chart"


def test_a_chart_with_no_caption_says_so_and_still_keeps_the_image(conn, monkeypatch):
    _stub_bytes(monkeypatch, PNG)
    cap = mc.collect_chart({"source_id": "charts", "url": "https://example.org/c.png"}, 30.0)[0]
    assert cap.text == "" and "no alt or caption" in cap.unmeasured
    assert Path(cap.raw_path).exists()
    assert mc.claims_of(mc.normalise(cap)) == []


def test_a_podcast_feed_gives_enclosure_metadata_and_the_feed_s_own_stamp(conn, monkeypatch):
    _stub_text(monkeypatch, FEED)
    cap = mc.collect_transcript({"source_id": "pod", "url": "https://example.org/feed.xml"},
                                30.0)[0]
    assert cap.knowable_at == "2026-07-04T08:00:00Z"
    assert cap.extra["enclosures"] == ["https://example.org/ep1.mp3"]
    assert "podcast:transcript" in cap.unmeasured, "audio is never transcribed here"
    assert "Why gold rallies into the fix" in cap.text


def test_youtube_caption_endpoints_are_refused_by_robots_not_attempted(conn, monkeypatch):
    _explode(monkeypatch)
    url = "https://www.youtube.com/api/timedtext?v=abc123"
    assert mc.robots_barred(url)
    cap = mc.collect_transcript({"source_id": "yt", "url": url}, 30.0)[0]
    assert "robots.txt" in cap.unmeasured and cap.content_length == 0


def test_a_youtube_watch_url_goes_through_the_desk_s_mirror_rotation(conn, monkeypatch):
    _explode(monkeypatch)
    calls: list[str] = []

    def _transcript(video_id: str, lang: str = "en") -> tuple[str, str | None]:
        calls.append(video_id)
        return "gold rallies into the London fix in 62% of sessions", None

    monkeypatch.setattr(mc.dfm, "youtube_transcript", _transcript)
    cap = mc.collect_transcript(
        {"source_id": "yt", "url": "https://www.youtube.com/watch?v=abc123xyz"}, 30.0)[0]
    assert calls == ["abc123xyz"]
    assert "London fix" in cap.text


@pytest.mark.parametrize(("text", "script"), [
    ("gold rallies into the London fix", "latin"),
    ("黄金在伦敦定盘前上涨", "cjk"),
    ("золото растёт перед лондонским фиксингом", "cyrillic"),
    ("الذهب يرتفع قبل تثبيت لندن", "arabic"),
    ("   ", mc.UNMEASURED),
    ("", mc.UNMEASURED),
])
def test_the_language_heuristic_names_a_script_and_never_a_language(text, script):
    assert mc.detect_script(text) == script


def test_a_non_latin_document_is_carried_verbatim_and_flagged_untranslated(conn, monkeypatch):
    _stub_text(monkeypatch, "<html><body><p>黄金在伦敦定盘前上涨约0.3%。</p></body></html>")
    doc = mc.normalise(mc.collect_html({"source_id": "cn", "url": "https://example.cn/x"},
                                       30.0)[0])
    assert doc["language"] == "cjk"
    assert doc["translated"] is False
    assert "VERBATIM" in doc["translation_note"]
    assert "黄金" in doc["text"], "the text is the source's, untouched"


@pytest.mark.parametrize(("row", "media"), [
    ({"kind": "pdf", "url": "https://x/a"}, "pdf"),
    ({"kind": "forum", "url": "https://x/a"}, "html"),
    ({"kind": "", "url": "https://x/a.csv"}, "table"),
    ({"kind": "", "url": "https://x/a.ipynb"}, "notebook"),
    ({"kind": "", "url": "https://x/a.png"}, "chart"),
    ({"kind": "", "url": "https://www.youtube.com/watch?v=q"}, "transcript"),
    ({"kind": "", "url": "https://x/a"}, "html"),
])
def test_media_type_is_decided_by_kind_then_extension_then_default(row, media):
    got, why = mc.media_type_of(row)
    assert got == media and why


# --------------------------------------------------------------------------- claims and edges
def test_claims_and_their_edges_reach_the_registry(conn, monkeypatch):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    report = mc.run(budget_s=30, max_sources=5, conn=conn)
    rows = [dict(r) for r in conn.execute("SELECT * FROM claims")]
    assert report["claims_written"] == len(rows) >= 2
    assert {r["source_id"] for r in rows} == {"ground_a"}
    assert all(r["knowable_at"] == "2026-09-01T10:00:00Z" for r in rows)
    assert all(r["media_type"] == "html" and r["kind"] == "claim" for r in rows)
    assert all(json.loads(r["provenance_json"])["url"] for r in rows)


def test_two_grounds_telling_the_same_claim_produce_a_duplicates_edge(conn, monkeypatch):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    _source(conn, "ground_b", "https://example.org/b")
    mc.run(budget_s=30, max_sources=5, conn=conn)
    edges = [dict(r) for r in conn.execute("SELECT * FROM claim_edges")]
    assert any(e["relation"] == "DUPLICATES" for e in edges)


def test_opposite_directions_on_one_topic_produce_a_contradicts_edge():
    rows = [
        {"claim_id": "a", "doc_id": "d1", "source_id": "s1", "instruments": ["XAUUSD"],
         "text": "gold rises into the London fix on month-end sessions"},
        {"claim_id": "b", "doc_id": "d2", "source_id": "s2", "instruments": ["XAUUSD"],
         "text": "gold falls into the London fix on month-end sessions"},
    ]
    relations = {rel for _a, _b, rel in mc._edges(rows)}
    assert relations == {"CONTRADICTS"}


def test_an_edge_is_written_once_however_many_passes_see_it(conn, monkeypatch):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    _source(conn, "ground_b", "https://example.org/b")
    mc.run(budget_s=30, max_sources=5, conn=conn)
    before = conn.execute("SELECT COUNT(*) FROM claim_edges").fetchone()[0]
    mc.run(budget_s=30, max_sources=5, conn=conn)
    assert conn.execute("SELECT COUNT(*) FROM claim_edges").fetchone()[0] == before


# --------------------------------------------------------------------------- the pass
def test_sources_are_chosen_by_roi_then_by_the_oldest_last_crawled(conn):
    _source(conn, "rich", "https://example.org/rich", last_crawled="2026-09-16T00:00:00Z")
    _source(conn, "stale", "https://example.org/stale", last_crawled="2020-01-01T00:00:00Z")
    _source(conn, "never", "https://example.org/never")
    _source(conn, "walled", "https://example.org/walled", status="walled")
    conn.execute("INSERT INTO source_yield(source_id, independent_survivors, compute_s) "
                 "VALUES(?,?,?)", ("rich", 3, 10.0))
    conn.commit()
    chosen = [r["source_id"] for r in mc.choose_sources(conn, 10)]
    assert chosen[0] == "rich", "measured ROI leads"
    assert chosen[1] == "never", "a never-crawled ground outranks one already mined to nothing"
    assert chosen[2] == "stale"
    assert "walled" not in chosen, "only active/candidate-cleared grounds are fetched"


def test_roi_is_lexicographic_so_claim_volume_can_never_outrank_a_survivor():
    assert mc.source_roi(None) == (0.0, 0.0, 0.0)
    chatty = mc.source_roi({"claims": 10_000, "compute_s": 100.0})
    useful = mc.source_roi({"independent_survivors": 1, "compute_s": 100.0})
    assert chatty < useful, "ten thousand claims must not outrank one independent survivor"
    tie_a = mc.source_roi({"independent_survivors": 1, "claims": 5, "compute_s": 100.0})
    assert useful < tie_a, "claims break a tie between equal survivor rates"


def test_the_budget_stops_the_pass_before_it_fetches(conn, monkeypatch):
    _explode(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    report = mc.run(budget_s=0.0, max_sources=5, conn=conn)
    assert report["budget_stopped"] is True
    assert report["sources_visited"] == 0 and report["captures_new"] == 0


def test_a_dry_run_plans_the_pass_and_fetches_nothing(conn, monkeypatch, moat):
    _explode(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a", kind="pdf")
    report = mc.run(budget_s=30, max_sources=5, dry_run=True, conn=conn)
    assert report["dry_run"] is True
    assert [p["source"] for p in report["planned"]] == ["ground_a"]
    assert report["planned"][0]["media_type"] == "pdf"
    assert report["planned"][0]["roi"] == [0.0, 0.0, 0.0]
    assert report["sources_visited"] == 0 and report["captures_new"] == 0
    assert not (moat / "moat").exists(), "a dry run writes nothing at all"
    assert conn.execute("SELECT last_crawled FROM sources").fetchone()[0] is None


def test_a_source_with_no_url_is_refused_by_name(conn, monkeypatch):
    _explode(monkeypatch)
    _source(conn, "urlless", "")
    report = mc.run(budget_s=30, max_sources=5, conn=conn)
    assert report["refused"] == [{"source": "urlless", "why": "source row carries no url"}]


def test_a_refused_ground_is_still_stamped_so_it_cannot_starve_the_rotation(conn, monkeypatch):
    _explode(monkeypatch)
    _source(conn, "barred", "https://www.youtube.com/api/timedtext?v=q", kind="transcript")
    report = mc.run(budget_s=30, max_sources=5, conn=conn)
    assert report["refused"][0]["source"] == "barred"
    assert "robots.txt" in report["refused"][0]["why"]
    stamped = conn.execute("SELECT last_crawled FROM sources").fetchone()[0]
    assert stamped, "a ground refused every pass would otherwise sort first for ever"


def test_a_fetch_failure_is_a_measurement_and_never_ends_the_pass(conn, monkeypatch):
    _stub_text(monkeypatch, "", status=503, err="HTTPError 503")
    _source(conn, "down", "https://example.org/down")
    _source(conn, "also", "https://example.org/also")
    report = mc.run(budget_s=30, max_sources=5, conn=conn)
    assert report["sources_visited"] == 2
    assert set(report["unmeasured"]["by_source"]) == {"down", "also"}


def test_every_visited_source_gets_a_fresh_last_crawled_and_a_manifest(conn, monkeypatch, moat):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    mc.run(budget_s=30, max_sources=5, conn=conn)
    assert conn.execute("SELECT last_crawled FROM sources").fetchone()[0]
    manifests = list(mc.sources_dir().glob("*.json"))
    assert len(manifests) == 1
    written = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert written["source_id"] == "ground_a" and written["url"] == "https://example.org/a"
    assert written["media_type"] == "html" and written["captures"] == 1


def test_the_store_lays_out_sources_raw_and_normalised(conn, monkeypatch, moat):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    mc.run(budget_s=30, max_sources=5, conn=conn)
    raw = list(mc.raw_dir().rglob("*.html"))
    norm = list(mc.normalized_dir().rglob("*.json"))
    assert len(raw) == 1 and len(norm) == 1
    assert raw[0].stem == norm[0].stem, "the normalised document is named by its capture sha"
    doc = json.loads(norm[0].read_text(encoding="utf-8"))
    assert doc["capture_sha"] == raw[0].stem
    assert doc["doc_id"] and doc["source_id"] == "ground_a" and doc["media_type"] == "html"
    assert doc["rule"] == mc.RULE


def test_an_immutable_refusal_is_reported_and_the_pass_carries_on(conn, monkeypatch, moat):
    _stub_text(monkeypatch)
    _source(conn, "ground_a", "https://example.org/a")
    mc.run(budget_s=30, max_sources=5, conn=conn)
    captured = next(iter(mc.raw_dir().rglob("*.html")))
    captured.write_bytes(b"tampered")
    report = mc.run(budget_s=30, max_sources=5, conn=conn)
    assert report["refused"] and "immutable capture refused" in report["refused"][0]["why"]
    assert captured.read_bytes() == b"tampered"
