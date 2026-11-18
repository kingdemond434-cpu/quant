"""The paid-replica map (principal 2026-11-18): every paid catalogue row rebuilt, queued or
blocked -- never unattempted -- and the ranking re-run on the engine's hourly clock.

Pinned here:
  * every committed catalogue row gets exactly one of BUILT / QUEUED / BLOCKED, and the hourly
    artifact carries the coverage figure;
  * a BUILT state cites a working fetcher, a QUEUED one names free inputs, a BLOCKED one names
    the host, the clause and the missed growth;
  * a product newly catalogued (here, by the listing crawl) is in the ranked output on the very
    next pass of the paid_substitute_engine leg, and the build tasks reach the forest queue that
    deep_forest_miner reads;
  * instruments are admitted through universe_policy (fail closed) and the Bloomberg Terminal is
    ranked as its own row, function by function.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paid_substitute_engine as pse  # noqa: E402

from research import paid_replica_map as prm  # noqa: E402

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def _doc() -> dict:
    return prm.run(pse.load_catalogue(), now=NOW, write=False)


def test_every_catalogue_row_has_exactly_one_state() -> None:
    doc = _doc()
    rows = doc["rows"]
    assert len(rows) == doc["catalogue_rows"] >= pse.catalogue_floor()
    for r in rows:
        assert r["state"] in prm.STATES, r
    assert doc["rows_without_state"] == 0
    assert sum(doc["row_states"].values()) == len(rows)
    assert isinstance(doc["coverage_built_or_queued"], float)
    assert doc["built_share"] <= doc["coverage_built_or_queued"] <= 1.0


def test_each_state_carries_what_backs_it() -> None:
    for r in _doc()["rows"]:
        if r["state"] == "BUILT":
            assert r["fetchers"] and all(f["fetcher"] for f in r["fetchers"]), r
        elif r["state"] == "QUEUED":
            assert r["inputs"] and r["build_tasks"], r
        else:
            b = r["blocked"]
            assert b["host"] and b["clause"] and b["missed_growth"], r


def test_every_category_resolves_to_a_state_and_every_class_is_routed() -> None:
    doc = _doc()
    assert all(t["state"] in prm.STATES for t in doc["ranked"])
    classes = set(pse.load_classes()["classes"])
    owned = {c for cat in prm.load_map()["categories"] for c in cat.get("classes") or []}
    assert classes <= owned, classes - owned


def test_built_citations_are_live_file_and_line() -> None:
    doc = _doc()
    by = {t["id"]: t for t in doc["ranked"]}
    jobs = {f["source_id"]: f["fetcher"] for f in by["jobs"]["fetchers"]}
    crop = {f["source_id"]: f["fetcher"] for f in by["sat_crop"]["fetchers"]}
    lines = (_DESK / "research" / "alt_proxies.py").read_text("utf-8").splitlines()
    for sid, cite in {**jobs, **crop}.items():
        path, _, line = cite.rpartition(":")
        assert path == "desks/mt5/research/alt_proxies.py"
        assert f'id="{sid}"' in lines[int(line) - 1]
    assert set(jobs) == {"jobs_indeed_postings"} and set(crop) == {"sat_s2_crop_green"}


def test_a_dead_or_unconfirmed_source_is_not_built() -> None:
    cat = {"id": "x", "built": [{"source_id": "a"}, {"source_id": "b"}], "free_inputs": [
        {"name": "n", "url": "https://example.org", "terms": "confirmed"}]}
    ok, bad = prm.resolve_built(cat, sources={"a": {"terms": "to_confirm", "dead": False},
                                             "b": {"terms": "confirmed", "dead": True}},
                                lines={})
    assert ok == [] and len(bad) == 2
    assert prm.category_state(cat, ok) == "QUEUED"


def test_instruments_are_admitted_through_universe_policy_fail_closed() -> None:
    cat = {"edge": 0.5, "buildability": 1.0, "effort_days": 1, "instruments": {"AAA": 1,
                                                                             "BBB": 1}}

    def may(s: str) -> bool:
        if s == "BBB":
            raise RuntimeError("registry unreadable")
        return True

    sc = prm.score(cat, values={}, default_value=1.0, n_rows=0, gain=None, may=may)
    assert sc["instruments_admitted"] == ["AAA"] and sc["instruments_refused"] == ["BBB"]
    assert sc["roi"] == 0.5
    up = prm.score(cat, values={}, default_value=1.0, n_rows=0, gain="PASS", may=lambda s: True)
    assert up["edge_basis"].startswith("measured PASS") and up["roi"] > 1.0


def test_bloomberg_terminal_is_its_own_ranked_row_with_five_functions() -> None:
    doc = _doc()
    bb = doc["parents"]["bloomberg_terminal"]
    assert len(bb["functions"]) == 5 and bb["paid_rows"] >= 1
    funcs = {t["id"]: t for t in doc["ranked"] if t.get("parent") == "bloomberg_terminal"}
    for t in funcs.values():
        assert t["primary_source"] and t["latency_gap"], t["id"]
    terminal_rows = [r for r in doc["rows"] if r["category"] == "terminal:bloomberg_terminal"]
    assert terminal_rows and all(r["state"] in ("BUILT", "QUEUED") for r in terminal_rows)


def test_routing_prefers_the_specific_subcategory_inside_its_class() -> None:
    cats = prm.load_map()["categories"]
    assert prm.route({"class": "satellite", "dataset": "Oil storage (floating roof) index"},
                     cats) == "sat_oil_storage"
    assert prm.route({"class": "rates_curves", "dataset": "Government bond yields"},
                     cats) == "rates_credit"
    assert prm.route({"class": "UNSTATED", "dataset": "crop yield analytics"},
                     cats) == "sat_crop"
    assert prm.route({"class": "UNSTATED", "dataset": "zzz"}, cats) == prm.UNCLASSIFIED


def _paths(tmp: Path) -> dict[str, Path]:
    return {"crawled": tmp / "crawled.json", "state": tmp / "state.json",
            "seeds": tmp / "seeds.json", "enrolled": tmp / "enrolled.json",
            "roster": tmp / "rosters" / "paid_substitutes.json",
            "forest": tmp / "forest" / "paid_substitutes.json", "intel": tmp / "intel",
            "lake": tmp / "lake", "acquired": tmp / "acquired.json",
            "report": tmp / "reports" / "PAID.json", "report_md": tmp / "reports" / "PAID.md",
            "world_state": tmp / "reports" / "WORLD_STATE_INPUTS.json",
            "asia_table": tmp / "absent" / "paid_data_substitutes_asia_blocked.json"}


def test_a_newly_catalogued_product_is_ranked_on_the_next_pass(tmp_path: Path) -> None:
    p = _paths(tmp_path)
    conns = [sqlite3.connect(":memory:"), sqlite3.connect(":memory:")]
    kw = {"now": NOW, "fetch": False, "paths": p, "environ": {}, "asia_globs": [],
          "registry_conn": conns[0], "door": lambda **k: ("c", True)}
    try:
        _two_passes(tmp_path, p, kw, conns)
    finally:
        for c in conns:
            c.close()


def _two_passes(tmp_path: Path, p: dict, kw: dict, conns: list) -> None:
    first = pse.run(**kw)
    rep = tmp_path / "reports" / "PAID_REPLICA_MAP.json"
    before = json.loads(rep.read_text("utf-8"))
    assert first["replica_map"]["rows_without_state"] == 0
    assert first["replica_map"]["coverage_built_or_queued"] == before["coverage_built_or_queued"]
    new_id = "crawl:example_listing:orbital_tanks"
    p["crawled"].write_text(json.dumps({"entries": [{
        "id": new_id, "vendor": "Example Orbital", "dataset": "Crude oil storage tanks index",
        "class": "UNSTATED", "region": "global", "seed_source": "crawl:https://example.org"}]}),
        "utf-8")
    kw["registry_conn"] = conns[1]
    pse.run(**kw)
    after = json.loads(rep.read_text("utf-8"))
    assert after["catalogue_rows"] == before["catalogue_rows"] + 1
    row = next(r for r in after["rows"] if r["id"] == new_id)
    assert row["category"] == "sat_oil_storage" and row["state"] == "QUEUED"
    oil = next(t for t in after["ranked"] if t["id"] == "sat_oil_storage")
    assert oil["paid_rows"] == next(t for t in before["ranked"]
                                    if t["id"] == "sat_oil_storage")["paid_rows"] + 1
    # the build tasks reach the queue deep_forest_miner reads, in its ground shape
    q = json.loads((tmp_path / "forest" / "paid_replica_builds.json").read_text("utf-8"))
    assert q["grounds"] and all(g["name"] and g["route"] == "search" for g in q["grounds"])
    from research import deep_forest_miner as dfm
    got = dfm.queued_grounds(queue_dir=tmp_path / "forest")
    assert any(g["name"].startswith("paidreplica|") for g in got)


def test_the_map_names_the_ranked_gap_categories_the_principal_listed() -> None:
    ids = {c["id"] for c in prm.load_map()["categories"]}
    assert {"card_transactions", "e_receipts", "web_traffic", "app_data", "jobs",
            "sat_retail_parking", "sat_oil_storage", "sat_crop", "sat_night_lights",
            "sat_industrial", "shipping_ais", "flight_air_cargo", "news_sentiment", "esg",
            "supply_chain_customs", "weather", "energy_grid", "options_positioning",
            "consensus_estimates", "expert_networks"} <= ids
