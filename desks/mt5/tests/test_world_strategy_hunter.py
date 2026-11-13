"""The world strategy hunter: map, gap, grow, count -- and never a socket or a judge path."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deep_forest_miner as dfm  # noqa: E402
import world_strategy_hunter as wsh  # noqa: E402

WORLD = {
    "countries": [
        {"iso": "jp", "name": "Japan", "cluster": "jp", "languages": ["ja"], "prior": 1.5,
         "market": "JP"},
        {"iso": "ir", "name": "Iran", "cluster": "mena", "languages": ["fa"], "prior": 0.9,
         "market": "IR"},
    ],
    "kinds": {
        "forum": {"weight": 1.3, "sites": [], "templates": ["{forex} {strategy} {forum}"],
                  "from_ground_kinds": ["forum", "community"]},
        "video": {"weight": 1.0, "sites": ["youtube.com"], "templates": ["{forex} {strategy}"],
                  "from_ground_kinds": ["video"]},
    },
    "vocab": {"ja": {"strategy": "手法", "forex": "FX", "gold": "ゴールド",
                     "backtest": "バックテスト", "forum": "掲示板", "system": "売買ルール"}},
}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    paths = {"MAP": tmp_path / "map.json", "CURATED": tmp_path / "deep_forest_sources.json",
             "MINTED": tmp_path / "world_hunter_grounds.json",
             "FRONTIER": tmp_path / "frontier.json", "CLAIMS": tmp_path / "claims.jsonl",
             "PASSES": tmp_path / "passes.jsonl", "REPORT": tmp_path / "REPORT.json"}
    for k, v in paths.items():
        monkeypatch.setattr(wsh, k, v)
    paths["MAP"].write_text(json.dumps(WORLD, ensure_ascii=False), "utf-8")
    paths["CURATED"].write_text(json.dumps({"grounds": [
        {"name": "5ch", "region": "jp", "language": "ja", "route": "search", "kind": "forum",
         "site": "5ch.net", "queries": ["x"]},
        {"name": "jp dataset", "region": "jp", "language": "ja", "route": "http",
         "kind": "dataset", "url": "https://data.example.jp/"},
    ]}), "utf-8")
    monkeypatch.setattr(wsh, "extractable_languages", lambda: frozenset({"ja", "en"}))
    return paths


def test_cells_are_country_language_kind_and_datasets_sit_outside_the_map(world) -> None:
    rep = wsh.run(dry_run=True, now=datetime(2026, 10, 29, tzinfo=UTC))
    # 2 countries x 1 language x 2 kinds; the dataset ground places in no cell
    assert rep["cells"]["total"] == 4
    assert rep["cells"]["by_state"]["NAMED_ONLY"] >= 1


def test_a_gap_cell_is_minted_as_a_native_search_ground_per_platform_site(world) -> None:
    rep = wsh.run(now=datetime(2026, 10, 29, tzinfo=UTC))
    grounds = json.loads(world["MINTED"].read_text("utf-8"))["grounds"]
    by = {g["name"]: g for g in grounds}
    v = by["WSH jp/ja/video@youtube.com"]
    assert v["route"] == "search" and v["site"] == "youtube.com" and v["language"] == "ja"
    assert v["queries"] == ["FX 手法"] and v["kind"] == "video" and v["market"] == "JP"
    assert v["route"] in dfm.ROUTES
    # the curated forum cell is not re-minted; the Persian cells cannot be read, so not minted
    assert not any(n.startswith("WSH jp/ja/forum") for n in by)
    assert not any("/fa/" in n for n in by)
    assert set(rep["extractor_gaps"]) == {"fa"}
    assert rep["this_pass"]["new_civilizations"] == 1
    assert json.loads(world["PASSES"].read_text("utf-8").splitlines()[-1])["cells"] == 4


def test_minting_is_idempotent_and_never_removes_a_ground(world) -> None:
    wsh.run(now=datetime(2026, 10, 29, tzinfo=UTC))
    first = json.loads(world["MINTED"].read_text("utf-8"))["grounds"]
    rep = wsh.run(now=datetime(2026, 10, 29, 1, tzinfo=UTC))
    second = json.loads(world["MINTED"].read_text("utf-8"))["grounds"]
    assert [g["name"] for g in second] == [g["name"] for g in first]
    assert rep["this_pass"]["new_civilizations"] == 0


def test_a_worked_cell_counts_toward_place_coverage(world) -> None:
    world["FRONTIER"].write_text(json.dumps({"vectors": {
        "5ch": {"outcome": "EMPTY", "last_attempt": "2026-10-28T00:00:00+00:00"}}}), "utf-8")
    rep = wsh.run(dry_run=True)
    assert rep["coverage"]["place_pct"] == 25.0
    assert rep["by_region"]["jp"]["worked"] == 1


def test_an_unregistered_host_that_keeps_yielding_becomes_an_emergent_ground(world) -> None:
    rows = [{"url": f"https://www.newfx.example/p/{i}", "claim_hash": str(i), "lang": "ja",
             "region": "jp", "cluster": "jp", "ground_kind": "blog", "mechanism_key": f"k{i}",
             "ground": "5ch", "title": f"t{i}"} for i in range(3)]
    rows.append({"url": "https://sub.5ch.net/x", "claim_hash": "z", "ground": "5ch",
                 "mechanism_key": "k0"})
    world["CLAIMS"].write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    rep = wsh.run(dry_run=True)
    assert rep["this_pass"]["emergent_places"] == ["newfx.example"]  # 5ch.net is registered


def test_redirectors_search_engines_and_caches_are_never_places() -> None:
    for h in ("t.co", "news.google.com", "google.co.jp", "web.archive.org", "x.translate.goog"):
        assert wsh._not_a_place(h), h
    assert not wsh._not_a_place("newfx.example")


def test_yield_is_split_minted_against_curated() -> None:
    grounds = [{"name": "a"}, {"name": "m", "minted_by": wsh.MINTED_BY}]
    vec = {"a": {"outcome": "YIELDED"}, "m": {"outcome": "EMPTY"}}
    out = wsh.minted_yield(grounds, vec, [{"ground": "a"}, {"ground": "a"}])
    assert out["curated"]["claims_per_worked_ground"] == 2.0
    assert out["minted"] == {"grounds": 1, "worked": 1, "claims": 0,
                             "claims_per_worked_ground": 0.0}


def test_strategy_coverage_is_chao1_over_mechanism_keys() -> None:
    out = wsh.chao1([1, 1, 1, 1, 2, 2, 3])
    assert out["observed"] == 7 and out["f1"] == 4 and out["f2"] == 2
    assert out["estimated"] == 7 + 16 / 4
    assert wsh.chao1([])["coverage_pct"] is None


def test_a_worked_minted_ground_is_deepened_once_per_attempt() -> None:
    g = {"name": "WSH jp/ja/forum", "language": "ja", "queries": ["a"], "depth": 0}
    vec = {"WSH jp/ja/forum": {"last_attempt": "2026-10-29T00:00:00+00:00"}}
    assert wsh.deepen(WORLD, g, vec) is True
    assert g["queries"] == ["a", "手法 XAUUSD"] and g["depth"] == 1
    assert wsh.deepen(WORLD, g, vec) is False


def test_the_miner_loads_minted_grounds_beside_the_curated_file(tmp_path, monkeypatch) -> None:
    src = tmp_path / "deep_forest_sources.json"
    src.write_text(json.dumps({"grounds": [{"name": "a", "route": "http"}]}), "utf-8")
    (tmp_path / dfm.MINTED_NAME).write_text(json.dumps({"grounds": [
        {"name": "a", "route": "search"}, {"name": "b", "route": "search"},
        {"name": "c", "route": "nonsense"}]}), "utf-8")
    monkeypatch.setattr(dfm, "SOURCES", src)
    names = [(g["name"], g["route"]) for g in dfm._load_sources()["grounds"]]
    assert names == [("a", "http"), ("b", "search")]


def test_the_shipped_world_map_mints_only_readable_languages() -> None:
    world = wsh.load_world(wsh.MAP)
    from libs.research import mechanism_claims as mc
    assert set(world["vocab"]) <= set(mc.LANGUAGES)
    keys = set(world["vocab_keys"])
    assert all(set(v) == keys and all(v.values()) for v in world["vocab"].values())
    assert all(c["iso"] and c["languages"] and c["market"] for c in world["countries"])
    assert all(c["cluster"] in set(dfm.REGION_CLUSTER.values()) for c in world["countries"])


def test_the_hunter_opens_no_socket() -> None:
    src = (_DESK / "research" / "world_strategy_hunter.py").read_text("utf-8")
    for banned in ("urllib.request", "requests", "polite_fetch", "socket", "http.client"):
        assert f"import {banned}" not in src and f"from {banned}" not in src
