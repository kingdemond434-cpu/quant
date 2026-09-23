"""P(valuable | miner, domain): the posterior, the routing, the specialities and the floors.

Everything is planted. The graph, the verdict ledger, the routing contract and the report live in
`tmp_path`, the registry is an empty sqlite file with no backup behind it, and the broker's asset
classes are a synthetic dict -- an organ measured against the real universe is a test about the
box, not about the organ.

THE FIXTURE IS BUILT SO THE ARITHMETIC IS CHECKABLE BY HAND. Eighteen verdicts put the median gate
depth at `cpcv`; two miners each produce twelve judged cells, one of them in a domain that dies at
gate 0 and one in a domain that reaches gate 8, so every posterior below can be read off the
counts rather than trusted.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parent.parent), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import axis_registry as ar  # noqa: E402
import miner_specialisation as ms  # noqa: E402

from libs.moat import registry as R  # noqa: E402

_CLASSES = {"EURUSD": "forex", "GBPUSD": "forex", "XAUUSD": "commodities",
            "XAGUSD": "commodities", "US500": "indices", "BTCUSD": "crypto"}
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def organ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = {
        "GRAPH": tmp_path / "data" / "hypothesis_graph.jsonl",
        "GATE_LEDGER": tmp_path / "data" / "hypotheses" / "gate_verdict_ledger.jsonl",
        "ROUTING": tmp_path / "data" / "miner_routing.json",
        "OUT": tmp_path / "reports" / "MINER_SPECIALISATION.json",
    }
    for name, p in paths.items():
        monkeypatch.setattr(ms, name, p)
    monkeypatch.setattr(ar, "asset_class_of", lambda s: _CLASSES.get(str(s).upper(), "UNKNOWN"))
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield paths
    R.set_path(None)


def _g(rid: str, sym: str, family: str, source: str, fate: str) -> dict[str, Any]:
    return {"id": rid, "symbol": sym, "family": family, "params": {}, "source": source,
            "fate": fate, "at": (NOW - timedelta(hours=2)).isoformat()}


def _v(sym: str, family: str, n: int, gate: str) -> dict[str, Any]:
    return {"at": (NOW - timedelta(hours=1)).isoformat(), "cell": f"{sym}.{family}.p={n:04d}",
            "sym": sym, "family": family, "passed": False, "terminal_gate": gate,
            "downstream_status": None}


def _ledger() -> list[dict[str, Any]]:
    """Depths 8, 7 and 0 in equal parts -- the median lands on `cpcv` (7) by construction."""
    rows = [_v("EURUSD", "carry", i, "walk_forward") for i in range(6)]
    rows += [_v("US500", "session_range_breakout", 10 + i, "cpcv") for i in range(6)]
    rows += [_v("XAUUSD", "forced_flow", 20 + i, "symbol_eligibility") for i in range(6)]
    return rows


def _graph() -> list[dict[str, Any]]:
    rows = [_g(f"df_fx_{i}", "EURUSD", "carry", "deep_forest", "FAILED") for i in range(12)]
    rows += [_g(f"df_xau_{i}", "XAUUSD", "forced_flow", "deep_forest", "FAILED")
             for i in range(12)]
    rows += [_g(f"wc_idx_{i}", "US500", "session_range_breakout", "world_crawler", "FAILED")
             for i in range(12)]
    rows += [_g(f"df_q_{i}", "EURUSD", "carry", "deep_forest", "BORN") for i in range(10)]
    rows += [_g(f"wc_q_{i}", "US500", "session_range_breakout", "world_crawler", "BORN")
             for i in range(2)]
    return rows


def _plant(paths: dict[str, Path], graph: list[dict[str, Any]],
           ledger: list[dict[str, Any]]) -> None:
    for key, rows in (("GRAPH", graph), ("GATE_LEDGER", ledger)):
        p = paths[key]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


# ------------------------------------------------------------------------------ the posterior
def test_posterior_is_jeffreys_and_its_interval_brackets_the_mean():
    rng = np.random.default_rng(ms.SEED)
    p = ms.posterior(3, 10, rng)
    assert p["alpha"] == 3.5 and p["beta"] == 7.5
    assert p["p"] == pytest.approx(3.5 / 11.0, abs=1e-5)
    assert p["sd"] == pytest.approx(float(np.sqrt(3.5 * 7.5 / (11.0**2 * 12.0))), abs=1e-5)
    assert p["ci"][0] < p["p"] < p["ci"][1]
    # a cell with nothing judged is the PRIOR, not a zero: Jeffreys puts it at one half
    assert ms.posterior(0, 0, rng)["p"] == pytest.approx(0.5, abs=1e-6)
    # and a perfect record is never certainty
    assert ms.posterior(12, 12, rng)["p"] < 1.0


def test_gate_depth_and_the_median_come_from_the_ledger(organ):
    exact, coarse, median = ms.depth_index(_ledger())
    assert median == 7.0
    assert coarse["EURUSD|carry"] == 8.0 and coarse["XAUUSD|forced_flow"] == 0.0
    assert exact["EURUSD.carry.p=0000"] == 8
    assert ms.gate_depth("walk_forward") == 8 and ms.gate_depth("PASSED") == len(ms.GATE_ORDER)
    assert ms.gate_depth("not_a_gate") is None


def test_valuable_is_a_pass_or_a_death_at_or_beyond_the_median_depth(organ):
    exact, coarse, median = ms.depth_index(_ledger())
    judged = [
        {"id": "a", "generator": "", "source": "m", "symbol": "EURUSD", "family": "carry",
         "params": {}, "cell": "", "passed": False, "terminal_gate": None, "judged": True},
        {"id": "b", "generator": "", "source": "m", "symbol": "XAUUSD", "family": "forced_flow",
         "params": {}, "cell": "", "passed": False, "terminal_gate": None, "judged": True},
        {"id": "c", "generator": "", "source": "m", "symbol": "BTCUSD", "family": "carry",
         "params": {}, "cell": "", "passed": True, "terminal_gate": None, "judged": True},
    ]
    counts = ms.cells(judged, exact, coarse, median)
    # EURUSD/carry dies at 8 >= 7 -> valuable; XAUUSD/forced_flow dies at 0 -> not; a pass is
    # valuable whatever the gate says.
    assert counts[("m", "asset:forex")]["valuable"] == 1
    assert counts[("m", "asset:commodities")]["valuable"] == 0
    assert counts[("m", "asset:crypto")]["valuable"] == 1
    assert counts[("m", "asset:forex")]["join"]["coarse"] == 1
    assert counts[("m", "asset:crypto")]["join"]["none"] == 1


def test_a_row_belongs_to_its_asset_its_mechanism_and_its_language():
    doms = ms.domains_of({"symbol": "EURUSD", "family": "carry", "source": "deep_forest_jp:x"})
    assert doms == ["asset:forex", "mechanism:carry_rollover", "language:ja"]
    # a source that names no language gets no language domain -- which is not the same as English
    assert ms.domains_of({"symbol": "US500", "family": "session_range_breakout",
                          "source": "world_crawler"}) == ["asset:indices",
                                                          "mechanism:breakout_liquidity"]


# -------------------------------------------------------------------------------- the routing
def test_routing_is_measured_per_domain_and_ordered_by_posterior(organ):
    _plant(organ, _graph(), _ledger())
    doc = ms.build(now=NOW)
    assert doc["evidence"]["judged_basis"] == "hypothesis_graph.fate"
    assert doc["evidence"]["median_gate"] == "cpcv"
    r = doc["routing_top"]
    assert r["asset:forex"][0]["miner"] == "deep_forest"
    assert r["asset:forex"][0]["p"] == pytest.approx(12.5 / 13.0, abs=1e-4)
    assert r["asset:forex"][0]["n"] == 12
    assert r["asset:indices"][0]["miner"] == "world_crawler"
    assert r["asset:commodities"][0]["p"] == pytest.approx(0.5 / 13.0, abs=1e-4)
    assert r["language:zh"][0]["n"] == 24
    assert r["language:zh"][0]["p"] == pytest.approx(12.5 / 25.0, abs=1e-4)
    lo, hi = r["asset:forex"][0]["ci"]
    assert 0.0 < lo < r["asset:forex"][0]["p"] < hi <= 1.0


def test_a_cell_under_the_minimum_is_unmeasured_and_never_routed(organ):
    graph = [_g(f"df_fx_{i}", "EURUSD", "carry", "deep_forest", "FAILED")
             for i in range(ms.MIN_JUDGED - 1)]
    _plant(organ, graph, _ledger())
    doc = ms.build(now=NOW)
    assert doc["routing_top"] == {}
    assert doc["measured_cells"] == 0 and doc["n_cells"] == 3
    assert doc["unmeasured"]["cells_below_min_judged"]["n"] == 3
    # one more judged cell and the same domain becomes MEASURED
    graph.append(_g("df_fx_extra", "EURUSD", "carry", "deep_forest", "FAILED"))
    _plant(organ, graph, _ledger())
    doc = ms.build(now=NOW)
    assert doc["routing_top"]["asset:forex"][0]["n"] == ms.MIN_JUDGED


def test_specialities_need_two_domains_and_a_full_sd_of_daylight(organ):
    _plant(organ, _graph(), _ledger())
    doc = ms.build(now=NOW)
    spec = doc["specialities"]
    assert set(spec["deep_forest"][0].keys()) >= {"domain", "p", "own_average", "sd", "excess"}
    assert {h["domain"] for h in spec["deep_forest"]} == {"asset:forex",
                                                          "mechanism:carry_rollover"}
    for h in spec["deep_forest"]:
        assert h["excess"] > h["sd"]
    # world_crawler is equally good at both of its domains, so it has no SPECIALITY -- being
    # uniformly strong is not the same claim.
    assert "world_crawler" not in spec


# -------------------------------------------------------------------------------- the elastic
def test_every_miner_keeps_a_floor_and_the_excess_follows_the_hottest_queue(organ):
    _plant(organ, _graph(), _ledger())
    doc = ms.build(now=NOW)
    ela = doc["elastic"]
    assert set(ela) == {"deep_forest", "world_crawler"}
    assert all(v["floor"] > 0 for v in ela.values())
    assert all(v["floor"] == pytest.approx(ms.FLOOR_BUDGET / 2) for v in ela.values())
    assert sum(v["suggested_share"] for v in ela.values()) == pytest.approx(1.0, abs=1e-5)
    # the deep queue under the strong posterior gets the excess; the other still runs
    assert ela["deep_forest"]["suggested_share"] > ela["world_crawler"]["suggested_share"]
    assert ela["world_crawler"]["suggested_share"] > ela["world_crawler"]["floor"]
    assert ela["deep_forest"]["heat"] > ela["world_crawler"]["heat"] > 0
    assert ela["deep_forest"]["hottest"][0]["queue"] == 10
    assert doc["evidence"]["queue_basis"] == "hypothesis_graph.fate == BORN"


def test_with_nothing_hot_the_excess_is_split_and_nobody_is_starved(organ):
    graph = [r for r in _graph() if r["fate"] != "BORN"]      # judged record, empty queue
    _plant(organ, graph, _ledger())
    ela = ms.build(now=NOW)["elastic"]
    assert all(v["basis"].startswith("UNMEASURED") for v in ela.values())
    assert all(v["suggested_share"] == pytest.approx(0.5) for v in ela.values())
    assert sum(v["suggested_share"] for v in ela.values()) == pytest.approx(1.0, abs=1e-5)


# ------------------------------------------------------------------------- evidence precedence
def test_the_registry_is_the_evidence_when_it_carries_rows(organ):
    for i in range(12):
        cid, _ = R.enqueue_candidate(family="carry", symbol="EURUSD", params={"i": i},
                                     origin="EXTERNAL", generator="deep_forest")
        R.mark_candidate(cid, "judged", terminal_gate="walk_forward", survived=0)
    for i in range(4):
        R.enqueue_candidate(family="carry", symbol="EURUSD", params={"q": i}, origin="EXTERNAL",
                            generator="deep_forest")
    _plant(organ, _graph(), _ledger())
    doc = ms.build(now=NOW)
    assert doc["evidence"]["judged_basis"] == "registry.research_candidates"
    assert doc["evidence"]["n_judged_rows"] == 12
    assert doc["evidence"]["depth_join"]["exact"] == 36        # three domains x twelve rows
    assert doc["evidence"]["queue_basis"].startswith("registry.research_candidates")
    assert doc["routing_top"]["asset:forex"][0]["miner"] == "deep_forest"
    assert doc["elastic"]["deep_forest"]["hottest"][0]["queue"] == 4


def test_without_a_ledger_valuable_collapses_to_passed_and_says_so(organ):
    graph = [*[_g(f"df_fx_{i}", "EURUSD", "carry", "deep_forest", "FAILED") for i in range(11)],
             _g("df_cert", "EURUSD", "carry", "deep_forest", "CERTIFIED")]
    _plant(organ, graph, [])
    doc = ms.build(now=NOW)
    assert "gate_depth" in doc["unmeasured"]
    assert doc["routing_top"]["asset:forex"][0]["p"] == pytest.approx(1.5 / 13.0, abs=1e-4)
    assert doc["evidence"]["depth_join"] == {"exact": 0, "coarse": 0, "none": 36}


# ------------------------------------------------------------------------------------ the CLI
def test_dry_run_writes_neither_the_contract_nor_the_report(organ, capsys):
    _plant(organ, _graph(), _ledger())
    assert ms.main(["--dry-run"]) == 0
    assert not organ["ROUTING"].exists() and not organ["OUT"].exists()
    assert "nothing written" in capsys.readouterr().out


def test_main_writes_the_contract_and_the_report(organ):
    _plant(organ, _graph(), _ledger())
    assert ms.main([]) == 0
    contract = json.loads(organ["ROUTING"].read_text(encoding="utf-8"))
    assert set(contract) >= {"at", "routing", "specialities", "elastic"}
    assert contract["routing"]["asset:forex"][0]["miner"] == "deep_forest"
    assert set(contract["routing"]["asset:forex"][0]) == {"miner", "p", "ci", "n"}
    assert contract["specialities"]["deep_forest"] == ["asset:forex", "mechanism:carry_rollover"]
    assert contract["elastic"]["world_crawler"]["floor"] > 0
    assert contract["writer"].endswith("miner_specialisation.py")
    doc = json.loads(organ["OUT"].read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "n_miners", "n_domains", "measured_cells", "routing_top",
                        "specialities", "elastic", "unmeasured", "rule"}
    assert doc["n_miners"] == 2 and doc["measured_cells"] >= 5
    assert "every department stays on" in doc["rule"]


def test_an_empty_tree_is_unmeasured_by_name(organ):
    doc = ms.build(now=NOW)
    assert doc["n_miners"] == 0 and doc["routing_top"] == {} and doc["elastic"] == {}
    assert doc["unmeasured"]["hypothesis_graph.jsonl"] == "ABSENT"
    assert doc["unmeasured"]["judged_record"]
