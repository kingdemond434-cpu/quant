"""GROUND DEPTH: the ranking, the five acts, the shapes and the verdicts.

Every test here is offline. The organ's only network calls live in `harvest` and `fetch_deep`,
and both are monkeypatched -- a test that reached the open internet would measure the weather.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import ground_depth as gd  # noqa: E402


# ------------------------------------------------------------------ the five acts
@pytest.mark.parametrize("url", [
    "https://x.com/login", "https://x.com/en/sign-in", "https://x.com/subscribe",
    "https://x.com/my-account/orders", "https://x.com/checkout/cart"])
def test_access_doors_are_refused_and_named(url: str) -> None:
    act = gd.refusal(url)
    assert act, url
    assert "access control" in act


@pytest.mark.parametrize("url", [
    "https://www.sgx.com/derivatives/products/iron-ore",
    "https://www.bis.org/statistics/rpfx2026.htm",
    "https://example.org/data/series.csv"])
def test_open_pages_are_never_refused(url: str) -> None:
    """Everything reachable on the open internet is fetched. Only the five acts refuse."""
    assert gd.refusal(url) == ""


# ------------------------------------------------------------------ the ranking
def test_a_data_endpoint_outranks_site_furniture() -> None:
    data = gd.link_score("https://sgx.com/data/settlement-prices.csv", "Download CSV", "sgx.com")
    chrome = gd.link_score("https://sgx.com/privacy-policy", "Privacy", "sgx.com")
    assert data > chrome
    assert chrome < 0                      # a negative score is still a RANK, not a refusal


def test_same_host_is_preferred_but_offsite_is_never_dropped() -> None:
    here = gd.link_score("https://sgx.com/research/report", "Report", "sgx.com")
    away = gd.link_score("https://other.com/research/report", "Report", "sgx.com")
    assert here > away


def test_ranked_links_dedupe_keep_refusals_and_sort_best_first() -> None:
    harvests = [{"url": "https://g.com/", "endpoints": ["https://g.com/series.csv"],
                 "links": [("https://g.com/login", "Sign in"),
                           ("https://g.com/privacy", "Privacy"),
                           ("https://g.com/series.csv", "csv again"),
                           ("https://g.com/statistics/table", "Statistics table")]}]
    rows = gd.ranked_links(harvests, "g.com")
    urls = [r["url"] for r in rows]
    assert len(urls) == len(set(urls))                      # deduped across links and endpoints
    assert rows[0]["url"].endswith(".csv")                  # the series is the best link
    refused = [r for r in rows if r["refused"]]
    assert [r["url"] for r in refused] == ["https://g.com/login"]
    assert rows[0]["series"] is True


def test_is_series_endpoint() -> None:
    assert gd.is_series_endpoint("https://g.com/a/b.csv")
    assert gd.is_series_endpoint("https://g.com/api/v1/series")
    assert not gd.is_series_endpoint("https://g.com/about")


# ------------------------------------------------------------------ the shapes
def test_shape_names_the_reader_job() -> None:
    assert gd.page_shape({}, "", 0, 403, "https://g.com/x").startswith("access_controlled")
    assert "binary_document" in gd.page_shape({}, "x", 10, 200, "https://g.com/a.pdf")
    assert "javascript_rendered" in gd.page_shape({}, "hi", 50_000, 200, "https://g.com/app")
    assert gd.page_shape({}, "a" * 900, 40_000, 200, "https://g.com/page") == ""


# ------------------------------------------------------------------ the verdicts
def test_verdict_prefers_a_named_instrument() -> None:
    v, why = gd.verdict_of([{"named": ["XAUUSD"], "shape": ""}, {"named": [], "shape": ""}], [], 9)
    assert v == "NAMES_AN_INSTRUMENT"
    assert "XAUUSD" in why


def test_verdict_records_a_series_when_no_symbol_is_named() -> None:
    v, _ = gd.verdict_of([{"named": [], "shape": ""}], ["https://g.com/a.csv"], 9)
    assert v == "NAMES_A_SERIES"


def test_verdict_names_the_missing_reader() -> None:
    v, why = gd.verdict_of([{"named": [], "shape": "javascript_rendered: 40000 bytes"}], [], 9)
    assert v == "READER_MISSING"
    assert "javascript_rendered" in why


def test_failure_is_a_measured_verdict_not_a_pending_job() -> None:
    v, why = gd.verdict_of([{"named": [], "shape": ""}, {"named": [], "shape": ""}], [], 31)
    assert v == "DEEPER_PAGES_NAME_NOTHING"
    assert "2 deeper page(s)" in why and "31 link(s)" in why
    job = gd.next_job_for(v, [], attempts=3, pages=24)
    assert "MEASURED EXHAUSTION" in job and "3 pass(es)" in job


def test_next_job_is_empty_only_when_the_ground_converted() -> None:
    assert gd.next_job_for("NAMES_AN_INSTRUMENT", [], 1, 8) == ""
    assert "REGISTER THE SERIES" in gd.next_job_for("NAMES_A_SERIES", [], 1, 8)
    assert "WRITE THE READER" in gd.next_job_for("READER_MISSING", ["pdf_only"], 1, 8)


# ------------------------------------------------------------------ the pass
def test_claims_that_name_an_instrument_are_written_first(monkeypatch: Any) -> None:
    """The ladder reads a ground's FIRST claims, so order decides whether it resolves."""
    rows = [{"text": "Navigation menu and cookie notice"},
            {"text": "XAUUSD traded higher after the fix"},
            {"text": "Contact us"}]
    assert gd.order_claims(rows)[0]["text"].startswith("XAUUSD")
    assert len(gd.order_claims(rows)) == 3                          # nothing is ever dropped


def test_deepen_walks_ranked_links_and_records_what_it_found(monkeypatch: Any) -> None:
    seen: list[str] = []

    def fake_landing(sid: str, url: str) -> list[str]:
        return ["https://g.com/"]

    def fake_harvest(url: str, lang: str = "") -> dict[str, Any]:
        return {"url": url, "error": "", "status": 200, "body_bytes": 1000, "text_len": 900,
                "endpoints": ["https://g.com/prices.csv"],
                "links": [("https://g.com/login", "Sign in"),
                          ("https://g.com/statistics", "Statistics")]}

    def fake_fetch(sid: str, url: str, lang: str, budget: float) -> dict[str, Any]:
        seen.append(url)
        named = ["XAUUSD"] if url.endswith(".csv") else []
        return {"url": url, "error": "", "claims": [{"text": f"page {url}"}], "named": named,
                "shape": "", "http_status": 200, "text_chars": 900, "title": "t"}

    monkeypatch.setattr(gd, "landing_urls", fake_landing)
    monkeypatch.setattr(gd, "harvest", fake_harvest)
    monkeypatch.setattr(gd, "fetch_deep", fake_fetch)
    monkeypatch.setattr(gd, "seed_frontier", lambda links, lang="": len(links))
    written: list[list[dict[str, Any]]] = []

    def fake_write(rows: list[dict[str, Any]]) -> tuple[int, int, str]:
        written.append(rows)
        return len(rows), 0, ""

    monkeypatch.setattr(gd, "write_claims", fake_write)
    monkeypatch.setattr(gd, "_pc", lambda: None)            # the ladder is not consulted offline
    res = gd.deepen({"id": "g", "url": "https://g.com/"}, budget_s=30.0, offset=0)
    assert res["verdict"] == "NAMES_AN_INSTRUMENT"
    assert res["instruments_named"] == ["XAUUSD"]
    assert "https://g.com/login" not in seen                       # the one refused act
    assert res["links_refused"] == 1
    assert res["refusals"][0]["act"].startswith("access control")
    assert res["links_followed"] == 2
    assert seen[0].endswith(".csv")                                # best-ranked link first
    assert res["next_offset"] == 2
    assert res["claims_written"] == 2 and len(written) == 1


def test_dry_run_fetches_nothing_and_earns_no_verdict(monkeypatch: Any) -> None:
    monkeypatch.setattr(gd, "landing_urls", lambda sid, url: ["https://g.com/"])
    monkeypatch.setattr(gd, "harvest", lambda url, lang="": {
        "url": url, "error": "", "endpoints": [], "links": [("https://g.com/data", "Data")]})

    def boom(*a: Any, **k: Any) -> dict[str, Any]:
        raise AssertionError("a dry run must not fetch")

    monkeypatch.setattr(gd, "fetch_deep", boom)
    res = gd.deepen({"id": "g", "url": "https://g.com/"}, budget_s=30.0, dry_run=True)
    assert res["verdict"] == "DRY_RUN"
    assert res["links_followed"] == 0


def test_build_writes_verdicts_and_a_cursor(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(gd, "VERDICTS", tmp_path / "verdicts.json")
    monkeypatch.setattr(gd, "CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(gd, "targets", lambda limit=60: (
        [{"id": "g1", "url": "https://g1.com/", "n_documents": 12}], 106, 121, ""))
    monkeypatch.setattr(gd, "deepen", lambda row, budget, dry_run=False, offset=0: {
        "id": row["id"], "verdict": "DEEPER_PAGES_NAME_NOTHING", "why": "nothing named",
        "landing_pages": ["https://g1.com/"], "landing_errors": [], "links_offered": 40,
        "links_followed": 8, "links_refused": 1, "refusals": [], "series_endpoints": [],
        "pages": [{"url": "https://g1.com/a", "named": [], "text_chars": 10, "shape": "",
                   "error": "", "title": ""}],
        "instruments_named": [], "claims_written": 3, "claim_edges": 0, "frontier_seeded": 4,
        "shapes": [], "next_offset": 8, "seconds": 1.0})
    doc = gd.build(budget_s=30.0)
    assert doc["headline"]["grounds_walked_this_pass"] == 1
    assert doc["headline"]["naming_an_instrument_before"] == 106
    assert doc["by_verdict"] == {"DEEPER_PAGES_NAME_NOTHING": 1}
    assert doc["still_unmapped_ranked"][0]["next_job"].startswith("MEASURED EXHAUSTION")
    assert (tmp_path / "verdicts.json").exists() and (tmp_path / "cursor.json").exists()
    import json
    hist = json.loads((tmp_path / "verdicts.json").read_text(encoding="utf-8"))
    assert hist["g1"]["attempts"] == 1
    assert hist["g1"]["tried_urls"] == ["https://g1.com/a"]
    # a second pass ACCUMULATES rather than overwriting: exhaustion is counted, never asserted
    doc2 = gd.build(budget_s=30.0)
    hist2 = json.loads((tmp_path / "verdicts.json").read_text(encoding="utf-8"))
    assert hist2["g1"]["attempts"] == 2
    assert doc2["still_unmapped_ranked"][0]["pages_total"] == 16


def test_the_leg_is_clocked_and_layered() -> None:
    """DONE MEANS WIRED: a clock in the hourly cycle and a layer in the registry."""
    from libs.research import layers
    assert layers.LEG_LAYER["ground_depth"] == "information"
    cycle = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("ground_depth"' in cycle
    assert '"research/ground_depth.py"' in cycle
    assert '"ground_depth": gdp' in cycle
