"""DATA-07 / DATA-38 / DATA-10: the per-source ledger, the research-only fence and the
producer-level measurer registry, on fixtures with no network."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import dataset_use as U  # noqa: E402
from research import dataset_use_census as C  # noqa: E402
from research import measurer_registry as M  # noqa: E402
from research import research_only_fence as F  # noqa: E402

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


def _contract(uses: list[str], admitted: bool = True) -> dict:
    return {"contract": {"permitted_uses": uses, "acquisition_method": "fetch_x.py",
                         "licence_version": "CC BY 4.0", "provenance_state": "CLEAR"},
            "admission": {"admitted": admitted, "reasons": [] if admitted else ["shut"]}}


# ------------------------------------------------------------------------------- DATA-07 ---
@pytest.fixture
def box(tmp_path, monkeypatch):
    (tmp_path / "axes").mkdir()
    (tmp_path / "axes" / "cot.json").write_text(json.dumps(
        {"source": "https://cftc.test/cot.txt", "at": "2026-10-07T10:00:00+00:00",
         "n_rows": 400, "knowable_lag_days": 3}))
    lake = tmp_path / "lake"
    lake.mkdir()
    (lake / "kr_power.parquet").write_bytes(b"x" * 100)
    (lake / "alt_kr__load.parquet").write_bytes(b"x" * 100)
    reg = {"series": {
        "good": {"url": "https://stat.test/a.csv", "host": "stat.test", "rows": 120,
                 "first": "2016-10-01", "last": "2026-09-01",
                 "refreshed_at": "2026-10-07T09:00:00+00:00", "pit_authority": True,
                 "schema_hash": "abc"},
        "noauth": {"url": "https://stat.test/b.csv", "host": "stat.test", "rows": 30,
                   "first": "2024-01-01", "last": "2026-06-01",
                   "refreshed_at": "2026-10-07T09:00:00+00:00", "pit_authority": False,
                   "pit_blocking": ["selection UNMEASURED"]}},
        "by_url": {"https://stat.test/a.csv": {"status": "SUCCESS", "series": ["good"]},
                   "https://stat.test/b.csv": {"status": "REFUSED",
                                               "refusal": "no PIT authority"}}}
    (tmp_path / "reg.json").write_text(json.dumps(reg))
    (tmp_path / "chain.json").write_text(json.dumps({"by_source": {
        "kr_power": {"stage_reached": "represented", "stops_at": "cells_emitted",
                     "collected": True, "n_rows": 50, "why": "represented and no cell"}}}))
    (tmp_path / "asia.json").write_text(json.dumps(
        {"sources": [{"id": "kr_power", "url": "https://kpx.test", "cadence": "daily"}]}))
    (tmp_path / "genomes.json").write_text(json.dumps(
        {"genomes": {"f1": {"dataset": "axis:cot"}, "f2": {"dataset": "axis:cot"},
                     "f3": {"dataset": "acquired:stat.test"}}}))
    (tmp_path / "contracts.json").write_text(json.dumps({"contracts": {
        "axis:cot": _contract(["research", "backtest", "live_signal"]),
        "acquired:stat.test": _contract(["research", "backtest", "live_signal"]),
        "lake:kr_power": _contract(["research", "backtest"])}}))
    # One child conditioned on lake:alt_kr__load judged beside its unconditioned parent.
    parent = {"cell": "P", "family": "fam", "sym": "EURUSD", "params": {"w": 3},
              "passed": False, "sharpe": 0.4}
    child = {"cell": "P|alt", "family": "fam", "sym": "EURUSD",
             "params": {"w": 3, "conditioner": "alt:alt_kr__load:pace:gt:0"},
             "passed": True, "sharpe": 0.9}
    stranger = {"cell": "Q|alt", "family": "fam", "sym": "EURUSD",
                "params": {"w": 4, "conditioner": "alt:alt_kr__load:pace:lt:0"},
                "passed": True}
    (tmp_path / "verdicts.json").write_text(json.dumps({"verdicts": [parent, child, stranger]}))
    for name, rel in (("DRAIN_REPORT", "none.json"), ("CHAIN_STATE", "chain.json"),
                      ("ASIA_SOURCES", "asia.json"), ("GENOMES", "genomes.json"),
                      ("GATE_VERDICTS", "verdicts.json"), ("CONTRACTS_STORE", "contracts.json")):
        monkeypatch.setattr(C, name, tmp_path / rel)
    U.record_reads("world_model", {"axis:cot": "2026-10-07"}, use="regime_state",
                   root=tmp_path / "use", now=NOW)
    U.record_reads("pack_cells", {"axis:cot": "2026-10-07"}, use="new_hypotheses",
                   root=tmp_path / "use", now=NOW)
    return tmp_path


def _ledger(box: Path) -> dict[str, dict]:
    doc = C.build(NOW, use_root=box / "use", acquired=box / "reg.json", axes=box / "axes",
                  lake=box / "lake", research_roi=box / "none.json")
    return {r["dataset"]: r for r in doc["ledger"]}, doc["ledger_summary"]


def test_ledger_publishes_every_field_per_source_dataset_version(box):
    rows, summary = _ledger(box)
    assert set(rows) == {"acquired:good", "acquired:noauth", "axis:cot", "lake:kr_power",
                         "lake:alt_kr__load"}
    cot = rows["axis:cot"]
    assert cot["consumers"] == ["pack_cells", "world_model"]
    assert cot["non_cell_utility"] == ["regime_state"]          # a read that is not a cell
    assert cot["features"] == 2 and cot["production_eligible"] is True
    assert cot["pit_status"] == "KNOWABLE_LAG_3D" and cot["blocker"] == "NONE"
    good = rows["acquired:good"]
    assert good["version"].startswith("2026-10-07T09:00:00") and good["access_state"] == "SUCCESS"
    assert good["history_depth_days"] > 3600 and good["pit_status"] == "AUTHORITY"
    assert good["features"] == 1                                 # credited through its host
    assert good["freshness"]["status"] == "FRESH" and good["licence"] == "CC BY 4.0"
    assert good["blocker"].startswith("CONSUMPTION")             # nobody read it
    noauth = rows["acquired:noauth"]
    assert noauth["blocker"].startswith("ACCESS: REFUSED")
    assert noauth["production_eligible"] is False                # NO_PIT_AUTHORITY
    for f in C.LEDGER_FIELDS:                                    # every field present by name
        assert f in good
    assert summary["datasets"] == 5


def test_lake_rows_read_the_drain_chain_and_name_missing_fields(box):
    rows, _ = _ledger(box)
    kr = rows["lake:kr_power"]
    assert kr["source"] == "https://kpx.test" and kr["stops_at"] == "cells_emitted"
    assert kr["blocker"].startswith("CHAIN: stops at cells_emitted")
    assert kr["production_eligible"] is False                    # research + backtest only
    assert "consumers" in kr["missing_fields"] and "latest_release" in kr["missing_fields"]


def test_baseline_vs_data_only_where_child_and_parent_were_both_judged(box):
    rows, summary = _ledger(box)
    alt = rows["lake:alt_kr__load"]["baseline_vs_data"]
    assert alt["status"] == "MEASURED" and alt["n_pairs"] == 1  # the w=4 child has no parent
    pair = alt["pairs"][0]
    assert pair["delta_passed"] == 1 and pair["delta_metric"] == pytest.approx(0.5)
    assert rows["axis:cot"]["baseline_vs_data"]["status"] == "UNMEASURED"
    assert summary["baseline_measured"] == 1


# ------------------------------------------------------------------------------- DATA-38 ---
def _fence_box(tmp_path: Path, contracts: dict, *, cond: str = "alt:alt_kr__load:pace:gt:0"):
    sleeves = {"sleeves": [
        {"name": "live_cond", "symbol": "EURUSD", "status": "LIVE",
         "certificate": {"cell": "C1"}},
        {"name": "standby_plain", "symbol": "XAUUSD", "status": "STANDBY",
         "certificate": {"cell": "C2"}},
        {"name": "retired_cond", "symbol": "EURUSD", "status": "RETIRED",
         "certificate": {"cell": "C1"}},
        {"name": "ghost", "symbol": "GBPUSD", "status": "LIVE", "certificate": {"cell": "C9"}},
    ]}
    surv = {"survivors": {
        "external.C1": {"shadow_spec": {"symbol": "EURUSD", "family": "f",
                                        "params": {"conditioner": cond}}},
        "C2": {"shadow_spec": {"symbol": "XAUUSD", "family": "g", "condition": "NORMAL_DAY",
                               "params": {"input_symbol": "XAGUSD"}}}}}
    for name, doc in (("sleeves.json", sleeves), ("surv.json", surv),
                      ("contracts.json", {"contracts": contracts}),
                      ("reg.json", {"series": {}})):
        (tmp_path / name).write_text(json.dumps(doc))
    return F.build(NOW, sleeves_path=tmp_path / "sleeves.json",
                   survivors_path=tmp_path / "surv.json",
                   contracts_path=tmp_path / "contracts.json", acquired_path=tmp_path / "reg.json")


def test_research_only_dataset_feeding_a_live_sleeve_is_a_named_violation(tmp_path):
    doc = _fence_box(tmp_path, {"lake:alt_kr__load": _contract(["research", "backtest"])})
    assert doc["status"] == "VIOLATION" and doc["n_violations"] == 1
    v = doc["violations"][0]
    assert (v["sleeve"], v["dataset"], v["kind"]) == ("live_cond", "lake:alt_kr__load",
                                                      "RESEARCH_ONLY")
    assert doc["lineage_unmeasured"] == ["ghost"]            # spec not on host: named
    plain = next(s for s in doc["sleeves"] if s["sleeve"] == "standby_plain")
    assert plain["inputs"] == ["bars:XAGUSD", "bars:XAUUSD"] and plain["eligible"]
    assert all(s["sleeve"] != "retired_cond" for s in doc["sleeves"])


def test_uncontracted_and_inadmissible_inputs_fail_closed(tmp_path):
    assert _fence_box(tmp_path, {})["violations"][0]["kind"] == "UNCONTRACTED"
    shut = _fence_box(tmp_path, {"lake:alt_kr__load": _contract(
        ["research", "live_signal"], admitted=False)})
    assert shut["violations"][0]["kind"] == "INADMISSIBLE"
    ok = _fence_box(tmp_path, {"lake:alt_kr__load": _contract(["research", "live_signal"])})
    assert ok["status"] == "OK" and ok["n_violations"] == 0


def test_dataset_ids_place_every_declared_input_shape():
    assert F.dataset_ids("alt:alt_x__y:pace:gt:0") == ["lake:alt_x__y"]
    assert F.dataset_ids("desks/mt5/data/lake/series/cn_pmi.parquet") == ["lake:cn_pmi"]
    assert F.dataset_ids("data/acquired/s1.parquet") == ["acquired:s1"]
    assert F.dataset_ids("cot=high") == ["axis:cot"]
    assert F.dataset_ids("axis:fred:extra") == ["axis:fred"]
    assert F.dataset_ids("NORMAL_DAY") == []
    assert F.dataset_ids("who knows / what") == ["conditioner:who knows / what"]


def test_check_script_exits_one_on_a_violation(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_research_only_data", ROOT / "scripts" / "check_research_only_data.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc_bad = _fence_box(tmp_path, {})
    monkeypatch.setattr(mod.F, "build", lambda: doc_bad)
    monkeypatch.setattr(mod.F, "REPORT", tmp_path / "RESEARCH_ONLY_DATA.json")
    monkeypatch.setattr(mod.F, "write", lambda doc, path=None: None)
    assert mod.main([]) == 1
    monkeypatch.setattr(mod.F, "build", lambda: {"status": "UNMEASURED", "why": "x"})
    assert mod.main(["--require-state"]) == 2


# ------------------------------------------------------------------------------- DATA-10 ---
def test_classify_reads_the_level_from_the_sources_own_words():
    assert M.classify("Port of Rotterdam throughput")[0] == "facility"
    assert M.classify("Murray-Darling Basin Authority storage")[0] == "basin"
    assert M.classify("Panama Canal transits")[0] == "corridor"
    assert M.classify("New South Wales state budget papers")[0] == "province"
    assert M.classify("Reserve Bank of Australia releases") == ("national", "central_bank")
    assert M.classify("an untitled feed")[0] == M.UNMEASURED      # never defaulted to national


def test_registry_merges_packs_roster_and_seed_with_subnational_coverage(tmp_path):
    roster = {"portals": [
        {"id": "au_nsw", "country": "AU", "subnational": "AU-NSW", "producer_type":
         "subnational_portal", "producer": "NSW", "base": "https://data.nsw.test"},
        {"id": "us_nyc", "country": "US", "subnational": "US-NY/New York City",
         "producer_type": "subnational_portal", "producer": "NYC", "base": "https://nyc.test"},
        {"id": "au_abs", "country": "AU", "producer_type": "statistics_office",
         "producer": "ABS", "base": "https://abs.test"}]}
    seed = {"measurers": [{"id": "au_port", "country": "AU", "level": "facility",
                           "producer_type": "port", "producer": "Port X",
                           "root": "https://port.test"}]}
    state = {"portals": {"au_nsw": {"last_visit_at": "2026-10-07", "status": "OK"}}}
    for n, d in (("roster.json", roster), ("seed.json", seed), ("state.json", state)):
        (tmp_path / n).write_text(json.dumps(d))
    (tmp_path / "countries").mkdir()                       # no packs in this fixture
    doc = M.build(NOW, seed_path=tmp_path / "seed.json", roster_path=tmp_path / "roster.json",
                  state_path=tmp_path / "state.json", countries=tmp_path / "countries")
    au = doc["coverage"]["AU"]
    assert au["by_level"]["province"] == 1 and au["by_level"]["facility"] == 1
    assert au["subnational_levels_covered"] == ["province", "facility"]
    assert au["subnational_coverage"] == 0.4 and au["verified"] == 1
    assert doc["coverage"]["US"]["by_level"]["municipality"] == 1
    assert M.coverage([], ["ZZ"])["ZZ"]["status"] == M.UNMEASURED


def test_the_real_packs_seed_the_registry():
    doc = M.build(NOW)
    assert doc["by_origin"]["countries/"] > 500
    assert doc["by_origin"]["data/measurer_registry"] >= 10
    assert doc["coverage"]["AU"]["subnational_measurers"] >= 5      # NSW, VIC, QLD, SA, WA
    seed = json.loads(M.SEED.read_text("utf-8"))
    assert {m["level"] for m in seed["measurers"]} <= set(M.SUBNATIONAL)
