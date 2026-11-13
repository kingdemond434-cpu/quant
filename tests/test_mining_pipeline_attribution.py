"""MT5_GLOBAL_MINING_V1 tests, continued from tests/test_mining_pipeline_roster.py (split for
size): source attribution, the producer map and the registry's ACTIVE/COLD rules.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.mining import acquirer as acq
from libs.mining.pit_store import iso
from tests.test_mining_pipeline import MS, ROOT, T0, _pipe

#: The module that owns PRODUCER_ORGANS and reads it (mining_supervisor re-exports it).
WIRING = sys.modules["research.mining_supervisor_wiring"]


def test_a_lane_owned_source_is_active_only_through_a_judged_docket_cell(tmp_path: Path) -> None:
    """Credit comes from a DECLARED seat or the longest proper URL prefix; a host-only registry
    URL never captures other pages, a cross-jurisdiction tie credits nobody, one page within one
    jurisdiction is its seat-declaring row's, an undeclared seat is nobody's -- and ACTIVE also
    needs the source's own fetcher to have run."""
    def src(sid: str, key: str, **kw: Any) -> acq.Source:
        return acq.Source(id=sid, fetcher=kw.pop("fetcher", "owned"), kind="text",
                          uses=["direct_cells"], url_key=key, **kw)
    owned = [src("rbnz_series", "rbnz.govt.nz/statistics", seats=["miner:asia:rbnz_series"]),
             src("smart_lab_blog", "smart-lab.ru/blog", owner="scout:world_crawler"),
             src("smart_lab_home", "smart-lab.ru"),
             src("twin_a", "x.org/p", region="pe"),
             src("twin_b", "x.org/p", region="bo"),
             src("dup_a", "y.org/q", region="cn", seats=["miner:dup_a_lane"],
                 consumer="desks/mt5/research/orthogonal_sweep.py"),
             src("dup_b", "y.org/q"),
             src("boj_listing", "boj.or.jp/en/statistics", fetcher="html_listing")]
    pipe = _pipe(tmp_path, sources=owned)
    rows = [
        {"symbol": "NZDUSD", "family": "carry", "params": {"k": 1},
         "source": "miner:asia:rbnz_series", "source_url": "https://www.rbnz.govt.nz/x"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 2},
         "source": "miner:world_crawler", "source_url": "https://smart-lab.ru/blog/123.php"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 3},
         "source": "miner:world_crawler", "source_url": "https://smart-lab.ru/forum/9"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 4},
         "source": "miner:discovery_compiler", "source_url": "https://x.org/p/1"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 5},
         "source": "miner:smart_lab_blog", "source_url": ""},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 6},
         "source": "orthogonal_sweep:carry", "source_url": "https://y.org/q/7"},
        {"symbol": "USDJPY", "family": "carry", "params": {"k": 7},
         "source": "miner:world_crawler", "source_url": "https://www.boj.or.jp/en/statistics/a"}]
    pipe.docket.write_text(json.dumps(rows), "utf-8")
    assert pipe.source_status(T0)["rbnz_series"]["status"] == "COLD"   # nothing judged yet
    pipe.gate_ledger.write_text("".join(json.dumps(
        {"cell": pipe.hooks.gauntlet_cell(r), "passed": False, "terminal_gate": "pbo",
         "at": iso(T0 - timedelta(days=2))}) + "\n" for r in rows), "utf-8")
    pipe.index_judged(now=T0)
    st = pipe.source_status(T0)
    assert st["rbnz_series"]["evaluated_via"] == {"mining": 0, "docket": 1}   # by its seat
    assert st["smart_lab_blog"]["evaluated_cells_30d"] == 1   # the URL; not the undeclared seat
    assert st["smart_lab_blog"]["fetch_evidence"] == "producer:world_crawler"
    assert st["smart_lab_home"]["status"] == "COLD"           # host-only is not a wildcard
    assert st["twin_a"]["status"] == st["twin_b"]["status"] == "COLD"      # a tie credits nobody
    assert st["dup_a"]["status"] == "ACTIVE" and st["dup_b"]["evaluated_cells_30d"] == 0
    # judged and credited, but its registered fetcher (the pipeline) never ran it
    assert st["boj_listing"]["evaluated_cells_30d"] == 1
    assert st["boj_listing"]["cold_reason"] == "no fetcher of it ran in 30 days"
    att = pipe._attribution
    assert att["credited_by"] == {"seat": 1, "url": 3}
    assert att["producer_map_error"] == ""
    asia = MS.producer_of("miner:asia:rbnz_series", MS._scout_seats())
    assert att["by_producer"][asia] == {"judged": 1, "credited": 1}
    assert att["by_producer"]["orthogonal_sweep"] == {"judged": 1, "credited": 1}
    assert st["rbnz_series"]["producers"] == {asia: 1}
    assert MS.producer_of("miner:world:x", {"world": "world_crawler"}) == "world_crawler"
    assert MS.producer_of("ext_forexfactory_GBPUSD_srb", MS._scout_seats()) == \
        "convert_to_hypotheses_v4"
    assert att["unattributed_judged_rows"] == 3
    assert att["unattributed_top_producers"] == {"miner:world_crawler": 1,
                                                 "miner:discovery_compiler": 1,
                                                 "miner:smart_lab_blog": 1}
    # credited, but by an organ the row does not register: another organ citing the page is
    # not this source's fetcher running
    assert st["smart_lab_home"]["fetch_evidence"] == ""
    pipe.store.log_run("boj_listing", "ok", 3, 3, "", now=T0 - timedelta(days=1))
    assert pipe.source_status(T0)["boj_listing"]["status"] == "ACTIVE"
    assert pipe.source_status(T0 + timedelta(days=40))["rbnz_series"]["status"] == "COLD"
    assert pipe.register_cursors(now=T0) == 8 and pipe.register_cursors(now=T0) == 0
    assert pipe.cursors.get("twin_a")["registered"]["canonical_id"] == "twin_a"
    st = pipe.source_status(T0)
    summary = pipe.registry_summary(st)
    assert summary["active"] == 4 and summary["schema"].endswith("source_registry.schema.json")
    assert summary["cold_by_reason"]["no cell EVALUATED in 30 days"] == [
        "dup_b", "smart_lab_home", "twin_a", "twin_b"]
    col = summary["url_collisions"]
    assert (col["keys"], col["rows"], col["same_region_owned"], col["cross_region_ties"]) == (
        2, 4, 1, 1)
    assert col["by_source"]["dup_b"] == [{"url_key": "y.org/q", "owner": "dup_a",
                                          "with": "dup_a"}]
    assert col["by_source"]["twin_a"][0]["owner"] == ""


def test_the_producer_map_names_real_organs_and_fails_loudly(monkeypatch: Any) -> None:
    """Every internal producer seat names a file that exists and stamps that seat; a map that
    will not load is an error in the attribution basis, never an all-`unmapped` silence."""
    doc = json.loads(MS.PRODUCER_ORGANS.read_text("utf-8"))
    for seat, path in {**doc["seats"], **doc["prefixes"], **doc["retired"]}.items():
        text = (ROOT / path).read_text("utf-8")
        assert f'"{seat}' in text or f"'{seat}" in text, (seat, path)
    for seat, path in (doc.get("landing") or {}).items():       # organ still in an open PR
        if (ROOT / path).exists():
            text = (ROOT / path).read_text("utf-8")
            assert f'"{seat}' in text or f"'{seat}" in text, (seat, path)
        assert MS.producer_of(seat, MS._scout_seats()) == Path(path).stem
    assert MS.producer_of("mql5_prospector", MS._scout_seats()) == "retired:mql5_prospector"
    organ_of = MS._scout_seats()
    assert MS.producer_of("miner:broker_swaps", organ_of) == "seed_miners"
    assert MS.producer_of("miner:world_crawler", organ_of) == "world_crawler"
    assert MS.producer_of("miner:central_bank", organ_of) == "central_bank_miner"
    assert MS.producer_of("session_chart_equivalent:ny_mid@H1", organ_of) == \
        "session_chart_equivalents"
    monkeypatch.setattr(WIRING, "PRODUCER_ORGANS", ROOT / "no" / "such.json")
    with pytest.raises(OSError):
        MS._scout_seats()


def test_the_live_roster_is_one_registry() -> None:
    got = acq.load_roster(root=ROOT)
    ids = [s.id for s in got]
    assert len(ids) == len(set(ids))
    owners = {s.owner.split("/")[0] for s in got}
    assert {"deep_forest", "asia_desk", "firm_mining", "country_pack",
            "global_mining"} <= owners
    schema = json.loads((ROOT / "libs" / "mining" / "source_registry.schema.json")
                        .read_text("utf-8"))
    assert schema["schema"] == "source_registry/1"


def test_archive_captures_config_urls_and_named_seats_on_the_same_site(tmp_path: Path) -> None:
    """An archive capture is judged as the page it archived; the pipeline's own rows are keyed
    by the URLs in their fetcher config; a seat named as a registry id credits it only when the
    row's URL is on that source's own site."""
    row = {"id": "mql5_forum_en", "fetcher": "html_listing", "config": {"listing": [
        {"url": "https://www.mql5.com/en/forum/page{page}",
         "page1": "https://www.mql5.com/en/forum"}]}}
    src = acq.normalise_row(row, origin="t")
    assert src is not None and "mql5.com/en/forum" in src.url_keys
    darwinex = acq.Source(id="darwinex", fetcher="owned", url_key="api.darwinex.com",
                          url_keys=["api.darwinex.com"])
    pipe = _pipe(tmp_path, sources=[src, darwinex])
    idx, seats = pipe._url_index(), pipe._seat_index()
    assert pipe.attribute_url("https://web.archive.org/web/2019/https://www.mql5.com/en/forum/9",
                              idx) == "mql5_forum_en"
    assert pipe.attribute_url("https://www.mql5.com/en/code/1", idx) == ""
    boj = {"boj.or.jp": [("boj.or.jp/en/statistics/index.htm", "boj_stats")]}
    # an index page scopes its directory
    assert pipe.attribute_url("http://www.boj.or.jp/en/statistics/set/x.pdf", boj) == "boj_stats"
    dx = "https://web.archive.org/web/20191210165044/https://www.darwinex.com/darwin/AJG.4.21"
    assert pipe.attribute_source({"source": "miner:darwinex", "source_url": dx}, idx, seats) \
        == ("darwinex", "seat+site")
    assert pipe.attribute_source({"source": "miner:darwinex", "source_url":
                                  "https://youtube.com/watch?v=1"}, idx, seats) == ("", "")


def test_a_derived_docket_row_traces_to_its_parents_declared_seat(tmp_path: Path) -> None:
    """discovery_compiler's donation carries its parent's URL and seat; the candidate compiler
    keeps them; the registry credits the parent's DECLARED seat, never an undeclared one."""
    dc = importlib.import_module("research.discovery_compiler")
    mcc = importlib.import_module("research.miner_candidate_compiler")
    parent = {"discovery_id": "d1", "symbol": "NZDUSD", "source_url": "https://rbnz.govt.nz/a",
              "lineage_intake": "intel:asia_rbnz:x.json", "lineage_generator": "seat:asia_rbnz"}
    child = {"family": "carry", "symbol": "NZDUSD", "chart": "H1", "content_hash": "h"}
    don = dc._donation_row(child, parent)
    assert (don["url"], don["origin_seat"], don["origin_intake"]) == (
        "https://rbnz.govt.nz/a", "asia_rbnz", "intel:asia_rbnz:x.json")
    cand = mcc._candidate("NZDUSD", "carry", {}, "discovery_compiler", don, "carry")
    assert cand["source_url"] == "https://rbnz.govt.nz/a" and cand["origin_seat"] == "asia_rbnz"
    pipe = _pipe(tmp_path, sources=[acq.Source(
        id="rbnz", fetcher="owned", kind="text", uses=["direct_cells"],
        seats=["miner:asia_rbnz"])])
    row = {"source": "miner:discovery_compiler", "source_url": "", "origin_seat": "asia_rbnz"}
    seats = pipe._seat_index()
    assert pipe.attribute_source(row, pipe._url_index(), seats) == ("rbnz", "lineage")
    assert pipe.attribute_source({**row, "origin_seat": "nobody"}, pipe._url_index(),
                                 seats) == ("", "")


def test_a_lane_that_describes_its_uses_by_key_keeps_them() -> None:
    """The free stack writes `uses: {direct: {...}, indirect: {...}, allocation: {...}}`; read
    as a list it filtered to nothing and every free-stack source served no use."""
    row = acq.normalise_row({"id": "x", "uses": {"direct": {"families": ["a"]}, "indirect": {},
                                                  "allocation": {"organ": "o"}}},
                            origin="t", defaults={"fetcher": "owned", "kind": "text"})
    assert row is not None and row.uses == ["direct_cells", "allocation_intel"]


def test_audit_round_two_attribution_rules(tmp_path: Path) -> None:
    """Two seat-declaring rows on one page tie; a registered organ is needed for owned evidence;
    a derived row inherits its parent's seat+site credit; every YouTube spelling is one key; a
    producer map that will not load is named in the COLD reason."""
    for u in ("https://www.youtube-nocookie.com/embed/AbC?rel=0", "https://youtube.com/live/AbC",
              "https://youtube.com/v/AbC", "https://m.youtube.com/embed/AbC"):
        assert acq.canonical_url(u) == "youtube.com/watch?v=AbC", u
    srcs = [acq.Source(id="cn_rail", fetcher="owned", kind="text", uses=["direct_cells"],
                       url_key="stats.gov.cn/sj", seats=["miner:rail"]),
            acq.Source(id="cn_power", fetcher="owned", kind="text", uses=["direct_cells"],
                       url_key="stats.gov.cn/sj", seats=["miner:power"]),
            acq.Source(id="boj", fetcher="owned", kind="text", uses=["direct_cells"],
                       url_key="boj.or.jp/en/statistics")]
    pipe = _pipe(tmp_path, sources=srcs)
    idx, seats = pipe._url_index(), pipe._seat_index()
    assert pipe.attribute_url("https://stats.gov.cn/sj/x", idx) == ""          # two seats: tie
    assert pipe.url_collisions()["by_kind"] == {"seated_tie": 1}             # one region: no
    assert pipe.url_collisions()["cross_region_ties"] == 0                   # cross-region label
    row = {"source": "miner:discovery_compiler", "origin_seat": "boj",
           "source_url": "https://www.boj.or.jp/en/x"}
    assert pipe.attribute_source(row, idx, seats) == ("boj", "lineage")
    assert MS.fetch_evidence({}, {"world_crawler": 2}, T0, "owned", 0, {"asia_collector"}) == ""
    assert MS.fetch_evidence({}, {"asia_collector": 2}, T0, "owned", 0,
                             {"asia_collector"}) == "producer:asia_collector"
    assert MS.fetch_evidence({}, {"retired:x": 2}, T0, "owned", 0, None) == ""
    pipe.docket.write_text(json.dumps([{"symbol": "USDJPY", "family": "carry", "params": {},
                                        "source": "miner:x", "source_url":
                                        "https://boj.or.jp/en/statistics/a"}]), "utf-8")
    pipe.gate_ledger.write_text(json.dumps(
        {"cell": pipe.hooks.gauntlet_cell({"symbol": "USDJPY", "family": "carry",
                                           "params": {}}),
         "passed": False, "terminal_gate": "pbo", "at": iso(T0)}) + "\n", "utf-8")
    pipe.index_judged(now=T0)
    orig = WIRING.PRODUCER_ORGANS
    try:
        WIRING.PRODUCER_ORGANS = ROOT / "no" / "such.json"
        st = pipe.source_status(T0)
    finally:
        WIRING.PRODUCER_ORGANS = orig
    assert st["boj"]["evaluated_cells_30d"] == 1
    assert st["boj"]["cold_reason"].startswith("no fetcher of it ran in 30 days (PRODUCER MAP")
    assert pipe._attribution["producer_map_error"].startswith("PRODUCER MAP FAILED")


def test_seatless_rows_sharing_a_page_are_distinct_datasets_and_tie(tmp_path: Path) -> None:
    """Two seatless rows on one page in one jurisdiction are distinct datasets (the acquirer folds
    same-named duplicates into aliases first), so neither is credited by the first-definer guess:
    the two e-Stat series registered on the bare getStatsData endpoint (audit 2026-10-01)."""
    key = acq.canonical_url("https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData")
    srcs = [acq.Source(id=i, fetcher="owned", kind="text", uses=["direct_cells"], url_key=key,
                       region="JP") for i in ("jp_estat_immigration", "jp_tokyo_cpi")]
    pipe = _pipe(tmp_path, sources=srcs)
    idx = pipe._url_index()
    assert pipe.attribute_url("https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData", idx) == ""
    col = pipe.url_collisions()
    assert col["by_kind"] == {"seatless_tie": 1} and col["same_region_owned"] == 0
    assert col["by_source"]["jp_tokyo_cpi"][0]["owner"] == ""


def test_a_ground_another_organ_reads_registers_it_by_fetched_by() -> None:
    """The BoJ statistics ground's bond PDFs reach the docket from central_bank_miner; the row
    names it in `fetched_by`, so that organ's credited rows are its fetch evidence (audit
    2026-10-01)."""
    row = acq.normalise_row({"id": "ground:jp:boj", "url": "https://www.boj.or.jp/statistics/",
                             "fetched_by": ["central_bank_miner"]}, origin="t",
                            defaults={"fetcher": "owned",
                                      "consumer": "desks/mt5/research/deep_forest_miner.py"})
    assert row is not None
    assert MS.registered_organs(row, {}) == {"deep_forest_miner", "central_bank_miner"}


def test_a_producer_named_source_id_is_credited_only_to_a_row_that_registers_it(
        tmp_path: Path) -> None:
    """alt_proxies emits every row under one seat with no URL and names its source in
    `provenance.source_id`; the compiler carries it as `origin_source_id`, and the registry credits
    that id only when its row registers the producing organ (2026-10-06)."""
    for p in (ROOT / "desks" / "mt5", ROOT / "desks" / "mt5" / "research"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from research import miner_candidate_compiler as mcc
    cand = mcc._candidate("EURUSD", "carry", {}, "alt_proxies",
                          {"source": "alt_proxies", "provenance": {"source_id": "kr_card"}}, "m")
    assert cand["origin_source_id"] == "kr_card"
    assert "origin_source_id" not in mcc._candidate("EURUSD", "carry", {}, "x", {}, "m")
    stamped = {"source": "news_event_stream", "origin_source_id": "gdelt_events_country"}
    assert mcc._candidate("EURUSD", "carry", {}, "x", stamped, "m")["origin_source_id"] == \
        "gdelt_events_country"
    srcs = [acq.Source(id="kr_card", fetcher="owned", kind="text", uses=["direct_cells"],
                       consumer="desks/mt5/research/alt_proxies.py"),
            acq.Source(id="other_lane", fetcher="owned", kind="text", uses=["direct_cells"],
                       consumer="desks/mt5/research/source_fixer.py")]
    pipe = _pipe(tmp_path, sources=srcs)
    pipe._organ_of = MS._scout_seats()
    idx, seats = pipe._url_index(), pipe._seat_index()
    row = {"source": "miner:alt_proxies", "source_url": "", "origin_source_id": "kr_card"}
    assert pipe.attribute_source(row, idx, seats) == ("kr_card", "provenance")
    stolen = {**row, "origin_source_id": "other_lane"}         # another organ fetches it
    assert pipe.attribute_source(stolen, idx, seats) == ("", "")
    assert pipe.attribute_source({**row, "origin_source_id": "nope"}, idx, seats) == ("", "")
