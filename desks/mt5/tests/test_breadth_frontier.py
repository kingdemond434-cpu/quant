"""The breadth frontier: a coverage map that never reads absence as empty or an undeclared axis as
coverage, fringe families whose terms fail closed, and an unknown-unknown frontier that only grows.

Fixtures only; nothing here touches the network (the organ imports no fetcher at all)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import breadth_frontier as bf  # noqa: E402

MODULE = DESK / "research" / "breadth_frontier.py"


def _w(path: Path, doc: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), "utf-8")
    return path


def _point(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    """Every input of the organ under a tmp desk, all absent until a test writes one."""
    for name, rel in (("ALT_DATA_YIELD", "reports/ALT_DATA_YIELD.json"),
                      ("DEEP_FOREST", "data/deep_forest_sources.json"),
                      ("FREE_STACK", "data/free_stack_sources.json"),
                      ("FREE_STACK_YIELD", "reports/FREE_STACK_YIELD.json"),
                      ("DISCOVERED_CATALOGUE", "data/free_stack/discovered_catalogue.json"),
                      ("UNIVERSE_MAP", "repo_data/data_universe_map.json"),
                      ("DATA_REGISTRY", "data/data_registry.json"),
                      ("DATASET_HUNT", "reports/DATASET_HUNT.json"),
                      ("FORGE_REPORT", "reports/REPRESENTATION_FORGE.json"),
                      ("FRINGE", "data/fringe_families.json"),
                      ("UNIVERSE", "data/universe/universe.json"),
                      ("OUT", "reports/BREADTH_FRONTIER.json"),
                      ("STATE", "data/breadth_frontier/state.json")):
        monkeypatch.setattr(bf, name, tmp / rel)
    monkeypatch.setattr(bf, "WORLD_DISCOVERIES", tmp / "data" / "intelligence" / "world")
    monkeypatch.setattr(bf, "BASE", tmp)
    monkeypatch.setattr(bf, "REPO", tmp)


REGIONS = {"jp": {"name": "Japan", "languages": ["ja"]},
           "de": {"name": "Germany", "languages": ["de"]}}


def _forest(tmp: Path, grounds: list[dict]) -> None:
    _w(tmp / "data" / "deep_forest_sources.json", {"regions": REGIONS, "grounds": grounds})


def test_every_input_absent_reads_unmeasured_never_empty(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    rep = bf.run()
    cm = rep["coverage_map"]
    assert cm["status"] == bf.UNMEASURED
    assert cm["empty"] == bf.UNMEASURED and cm["filled"] == bf.UNMEASURED
    assert set(cm["inputs_unmeasured"]) >= {"alt_data_yield", "deep_forest", "free_stack"}
    assert rep["fringe_families"]["status"] == bf.UNMEASURED
    assert rep["representation_discovery"]["status"] == bf.UNMEASURED
    assert rep["dataset_discovery"]["world_hunt_datasets_discovered"] == bf.UNMEASURED
    assert rep["dataset_discovery"]["crawler_endpoints_distinct"] == bf.UNMEASURED
    assert (tmp_path / "reports" / "BREADTH_FRONTIER.json").exists()


def test_undeclared_axis_reaches_thin_only_and_declared_yield_fills(monkeypatch,
                                                                    tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    # a Japanese forum naming no asset: it reaches every asset, but THIN at most
    _forest(tmp_path, [{"name": "jp board", "region": "jp", "language": "ja", "kind": "forum",
                        "why": "general chatter", "url": "https://example.jp/"}])
    # a fully declared, measured-yield German exchange source on gold, daily
    _w(tmp_path / "data" / "free_stack_sources.json", {"sources": [
        {"id": "de_gold", "kind": "cn_exchange", "region": "de", "language": "de",
         "cadence": "daily", "participant_structure": "settlement_constrained",
         "name": "gold settlement prices"}]})
    _w(tmp_path / "reports" / "FREE_STACK_YIELD.json",
       {"sources": {"de_gold": {"successes": 3}}})
    cm = bf.run()["coverage_map"]
    assert cm["status"] == "measured"
    assert cm["filled"] + cm["thin"] + cm["empty"] == cm["size"]
    assert cm["filled"] == 1          # de x de x professional_trader x metals x daily only
    assert cm["thin"] > 0             # the forum's undeclared assets and horizons
    jp_forum_filled = [t for t in cm["top_empty"]
                       if t["cell"]["geography"] == "jp" and t["cell"]["language"] == "ja"
                       and t["cell"]["source"] == "community_forum"
                       and t["cell"]["actor"] == "retail"]
    assert not jp_forum_filled, "a cell the forum reaches is THIN, never ranked as EMPTY"


def test_unmeasured_yield_never_fills(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _forest(tmp_path, [])
    _w(tmp_path / "data" / "free_stack_sources.json", {"sources": [
        {"id": "de_gold", "kind": "cn_exchange", "region": "de", "language": "de",
         "cadence": "daily", "participant_structure": "settlement_constrained",
         "name": "gold settlement prices"}]})
    cm = bf.run()["coverage_map"]           # no FREE_STACK_YIELD: one source, yield unmeasured
    assert cm["filled"] == 0 and cm["thin"] == 1
    assert cm["rows_without_yield_measure"] == 1


def test_legacy_crypto_native_categories_are_set_aside(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _forest(tmp_path, [])
    _w(tmp_path / "repo_data" / "data_universe_map.json", {"sources": {
        "cex_trades_ohlcv": [{"name": "x"}], "onchain": [{"name": "y"}],
        "boj_stat_search": {"grade": "adopted", "provides": "JPY fx daily"}}})
    cm = bf.run()["coverage_map"]
    assert cm["legacy_crypto_native_set_aside"] == 2
    assert cm["rows_by_origin"] == {"universe_map": 1}


def test_top_empty_is_ranked_diverse_and_argued(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _forest(tmp_path, [{"name": "g", "region": "jp", "language": "ja", "kind": "forum"}])
    top = bf.run()["coverage_map"]["top_empty"]
    assert top and all(set(t["factors"]) == {"asset_weight", "geo_relevance", "novelty",
                                             "source_prior"} for t in top)
    scores = [t["score"] for t in top]
    assert scores == sorted(scores, reverse=True)
    keys = [tuple(t["cell"].values()) for t in top]
    assert len(keys) == len(set(keys)), "one row per cell, horizons listed inside it"


# ------------------------------------------------------------------------------ fringe terms

def test_live_access_requires_a_read_quote_and_stage_is_derived(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    (tmp_path / "owner.py").write_text("", "utf-8")
    monkeypatch.delenv("BF_TEST_KEY", raising=False)
    _w(tmp_path / "data" / "fringe_families.json", {"families": [
        {"id": "f_ok", "mt5_mapping": {"instruments": ["XAUUSD"], "channel": "c"}, "sources": [
            {"id": "a", "access_status": "API_PERMITTED", "terms_read": "READ",
             "quote": ["you may use the API"], "owner": "owner.py"},
            {"id": "k", "access_status": "NEEDS_KEY", "terms_read": "READ",
             "quote": ["free API with a key"], "key_env": "BF_TEST_KEY"}]},
        {"id": "f_noquote", "mt5_mapping": {}, "sources": [
            {"id": "b", "access_status": "API_PERMITTED", "terms_read": "UNREAD"}]},
        {"id": "f_ideas", "mt5_mapping": {}, "sources": [
            {"id": "c", "access_status": "IDEAS_ONLY", "terms_read": "UNREAD",
             "status_reason": "unread"},
            {"id": "m", "access_status": "METHOD_BLOCKED", "terms_read": "READ",
             "status_reason": "login wall"}]}]})
    ff = bf.run()["fringe_families"]
    fams = {f["id"]: f for f in ff["families"]}
    src = {s["id"]: s for f in ff["families"] for s in f["sources"]}
    assert fams["f_ok"]["stage"] == "COLLECTOR_EXISTS"
    assert src["a"]["access"] == "API_PERMITTED"
    assert src["k"]["access"] == "NEEDS_KEY", "a missing key reads NEEDS_KEY, never zero"
    assert src["b"]["access"] == "IDEAS_ONLY", "UNREAD terms are never live input"
    assert fams["f_noquote"]["stage"] == "NAMED"
    assert src["m"]["access"] == "METHOD_BLOCKED" and src["m"]["reason"] == "login wall"
    assert ff["with_live_source"] == 1 and ff["ideas_only"] == 2
    assert ff["sources_by_access"]["IDEAS_ONLY"] == 2
    monkeypatch.setenv("BF_TEST_KEY", "x")
    src = {s["id"]: s for f in bf.run()["fringe_families"]["families"] for s in f["sources"]}
    assert src["k"]["access"] == "API_PERMITTED"


def test_the_real_fringe_registry_uses_the_access_statuses() -> None:
    doc = json.loads((DESK / "data" / "fringe_families.json").read_text("utf-8"))
    fams = doc["families"]
    assert len(fams) == 10 and len({f["id"] for f in fams}) == 10
    universe = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    for f in fams:
        assert f["id"].startswith("fringe_")
        m = f["mt5_mapping"]
        assert m["channel"] and m["instruments"]
        assert set(m["instruments"]) <= set(universe), f["id"]
        assert f["sources"]
        for s in f["sources"]:
            assert "terms_status" not in s, "no source is banned or HELD as a category"
            assert s["access_status"] in bf.ACCESS_STATUSES
            assert s["terms_read"] in ("READ", "UNREAD")
            if s["access_status"] in ("API_PERMITTED", "NEEDS_KEY", "PUBLIC_PAGE"):
                assert s["terms_read"] == "READ"
                assert s["quote"] and all(isinstance(q, str) and q for q in s["quote"])
                assert s["terms_url"].startswith("https://")
            else:
                assert s.get("status_reason"), s["id"]
            if s["terms_read"] == "UNREAD":
                assert s["access_status"] == "IDEAS_ONLY"


def test_access_is_a_census_and_never_changes_a_cell(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    ground = {"name": "jp board", "region": "jp", "language": "ja", "kind": "forum"}
    _forest(tmp_path, [ground])
    _w(tmp_path / "reports" / "ALT_DATA_YIELD.json", {"vectors": {"rows_by_vector": {
        "jp board": {"outcome": "BLOCKED", "last_error": "bing returned an anti-bot shell"}}}})
    cm = bf.run()["coverage_map"]
    assert cm["access_census"]["METHOD_BLOCKED"] == 1
    _w(tmp_path / "reports" / "ALT_DATA_YIELD.json", {"vectors": {"rows_by_vector": {}}})
    cm2 = bf.run()["coverage_map"]
    assert cm2["access_census"]["IDEAS_ONLY"] == 1
    assert (cm["filled"], cm["thin"], cm["empty"]) == (cm2["filled"], cm2["thin"], cm2["empty"])


# ----------------------------------------------------------------------- the unknown frontier

def _disc(tmp: Path, name: str, rows: list[dict]) -> None:
    _w(tmp / "data" / "intelligence" / "world" / f"discoveries_{name}.json", rows)


def test_unknown_frontier_proposes_unnamed_terms_and_never_forgets(monkeypatch,
                                                                    tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    rows = [{"kind": "prose", "host": f"h{i}.org", "dataset_class": "dark_pool_prints",
             "endpoints": [f"https://h{i}.org/stats/turbine_vibration.csv",
                           f"https://h{i}.org/feed/data.netcdf",
                           f"https://h{i}.org/style/site.css",
                           "http://127.0.0.1:8000/zzlocalonly.csv"]}
            for i in range(3)]
    _disc(tmp_path, "20261013_0000", rows)
    uk = bf.run()["unknown_unknown_frontier"]
    by = {(p["kind"], p["term"]): p for p in uk["proposals"]}
    assert by[("field_name", "turbine")]["proposed_to_ontology"] is True
    assert by[("field_name", "vibration")]["hosts"] == 3
    assert ("feed_type", "netcdf") in by
    assert ("publisher_kind", "dark_pool_prints") in by
    assert ("publisher_kind", "prose") not in by, "a crawler row type is not a publisher kind"
    assert ("feed_type", "css") not in by, "page furniture is never a feed type"
    assert ("field_name", "zzlocalonly") not in by, "a loopback host is never evidence"
    assert ("field_name", "stats") not in by
    first = uk["terms_ever_seen"]
    assert uk["new_this_pass"] == uk["terms_observed"]
    # second pass, nothing new crawled: nothing is new, nothing is forgotten
    uk2 = bf.run()["unknown_unknown_frontier"]
    assert uk2["new_this_pass"] == 0 and uk2["terms_ever_seen"] == first
    # the crawler then finds less: the ontology still holds every term it ever saw
    _disc(tmp_path, "20261013_0000", [])
    uk3 = bf.run()["unknown_unknown_frontier"]
    assert uk3["terms_ever_seen"] == first


def test_dataset_discovery_counts_new_endpoints_once(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _disc(tmp_path, "a", [{"host": "x.org", "endpoints": ["https://x.org/a.csv",
                                                           "https://x.org/b.csv"]}])
    _w(tmp_path / "reports" / "DATASET_HUNT.json",
       {"totals": {"datasets_discovered": 7}, "pass": {"new_datasets": 2}})
    d1 = bf.run()["dataset_discovery"]
    assert d1["crawler_endpoints_distinct"] == 2 and d1["crawler_endpoints_new_this_pass"] == 2
    assert d1["world_hunt_datasets_discovered"] == 7 and d1["world_hunt_new_datasets"] == 2
    assert bf.run()["dataset_discovery"]["crawler_endpoints_new_this_pass"] == 0


def test_representation_forge_is_read_not_rebuilt(monkeypatch, tmp_path) -> None:
    _point(monkeypatch, tmp_path)
    _w(tmp_path / "reports" / "REPRESENTATION_FORGE.json", {
        "at": "t", "minted": 4, "store": {"n_total": 40}, "inputs": {"series": 9},
        "grammar": {"registered": ["z", "surprise", "pace"]},
        "counts_by_transform": {"z": 30, "surprise": 10}})
    rd = bf.run()["representation_discovery"]
    assert rd["status"] == "measured" and rd["store_total"] == 40
    assert rd["transforms_never_used"] == ["pace"]


# --------------------------------------------------------------------------------- wiring

def test_no_network_and_wired_as_an_hourly_leg() -> None:
    src = MODULE.read_text("utf-8")
    assert not re.search(r"^(import (urllib\.request|requests|socket|http\.client)|"
                         r"from (urllib\.request|requests|socket|http\.client) )", src, re.M)
    cycle = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("breadth_frontier"' in cycle
    assert '"research/breadth_frontier.py", "--once"' in cycle
    assert '"breadth_frontier": bfr' in cycle
    sys.path.insert(0, str(REPO))
    from libs.research import layers
    assert layers.LEG_LAYER["breadth_frontier"] == "information"
    import importlib
    hc = importlib.import_module("research.hourly_cycle")
    assert hc.LEG_BUDGET_SEC["breadth_frontier"] >= 60
    assert hc.LEG_DEPARTMENT["breadth_frontier"] == "intel"
