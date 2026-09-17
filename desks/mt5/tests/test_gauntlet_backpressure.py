"""The gauntlet's backpressure: every measure on a planted fixture, every message on its trigger.

Nothing here touches the box's artifacts. The graph, the verdict ledger, the gauntlet's report and
its source are redirected into `tmp_path`; the canonical registry is a fresh sqlite file with its
backup pointed at a path that does not exist, so `connect()` builds an empty schema rather than
restoring the moat copy; and `axis_registry.asset_class_of` is replaced by a synthetic broker
registry, because an organ that reads the real universe in a test is measuring the box.

The shape of every message test is the same and it is the point: a BASELINE fixture fires nothing,
each scenario perturbs exactly one thing, and the assertion is on the WHOLE fired set. A test that
only checks its own code would pass while the organ shouted six other messages at the miners.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parent.parent), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import axis_registry as ar  # noqa: E402
import gauntlet_backpressure as gb  # noqa: E402

from libs.moat import registry as R  # noqa: E402

#: A synthetic broker registry: the real one is a box artifact and a test that reads it is a test
#: about the box. `axis_cell` calls this by module global, so replacing it is enough.
_CLASSES = {"EURUSD": "forex", "GBPUSD": "forex", "AUDUSD": "forex", "USDCHF": "forex",
            "XAUUSD": "commodities", "XAGUSD": "commodities",
            "US500": "indices", "GER40": "indices",
            "BTCUSD": "crypto", "ETHUSD": "crypto",
            "USB10Y": "bonds", "USB02Y": "bonds"}

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def organ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The organ pointed at an empty synthetic tree and an empty registry."""
    paths = {
        "GRAPH": tmp_path / "data" / "hypothesis_graph.jsonl",
        "GATE_LEDGER": tmp_path / "data" / "hypotheses" / "gate_verdict_ledger.jsonl",
        "GAUNTLET_REPORT": tmp_path / "reports" / "universal_gates_external.json",
        "GAUNTLET_SOURCE": tmp_path / "scripts" / "external_gauntlet.py",
        "NOVELTY": tmp_path / "reports" / "NOVELTY_GATE.json",
        "OUT": tmp_path / "reports" / "GAUNTLET_BACKPRESSURE.json",
    }
    for name, p in paths.items():
        monkeypatch.setattr(gb, name, p)
    monkeypatch.setattr(ar, "asset_class_of", lambda s: _CLASSES.get(str(s).upper(), "UNKNOWN"))
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield paths
    R.set_path(None)


def _born(sym: str, family: str, *, n: int, hours_ago: float = 1.0, session: str = "all",
          pit: bool = True, source: str = "miner:youtube", params: dict[str, Any] | None = None,
          fate: str = "BORN") -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": f"{sym}.{family}.{n}", "symbol": sym, "family": family,
        "params": params if params is not None else {"i": n, "session": session},
        "source": source, "fate": fate,
        "at": (NOW - timedelta(hours=hours_ago)).isoformat(),
    }
    if pit:
        row["available_time"] = (NOW - timedelta(hours=hours_ago)).isoformat()
    return row


def _verdict(sym: str, family: str, *, n: int, gate: str = "in_sample_screen",
             passed: bool = False, hours_ago: float = 0.5) -> dict[str, Any]:
    return {"at": (NOW - timedelta(hours=hours_ago)).isoformat(),
            "cell": f"{sym}.{family}.p={n:04d}", "sym": sym, "family": family,
            "passed": passed, "terminal_gate": ("PASSED" if passed else gate),
            "downstream_status": None}


def _plant(paths: dict[str, Path], born: list[dict[str, Any]],
           verdicts: list[dict[str, Any]]) -> None:
    for key, rows in (("GRAPH", born), ("GATE_LEDGER", verdicts)):
        p = paths[key]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _baseline_born() -> list[dict[str, Any]]:
    """Ten cells that trip nothing: 20% fx/H1/asia, 20% event, 20% off the top-3 classes, PIT."""
    return [
        _born("EURUSD", "carry", n=1, session="asia"),
        _born("GBPUSD", "carry", n=2, session="asia"),
        _born("EURUSD", "mean_reversion_rsi", n=3),
        _born("GBPUSD", "mean_reversion_rsi", n=4),
        _born("XAUUSD", "forced_flow", n=5),
        _born("XAGUSD", "forced_flow", n=6),
        _born("US500", "session_range_breakout", n=7),
        _born("GER40", "session_range_breakout", n=8),
        _born("BTCUSD", "mean_reversion_rsi", n=9),
        _born("USB10Y", "carry", n=10),
    ]


def _dup_rows(n: int) -> list[dict[str, Any]]:
    """`n` cells with DISTINCT ids and the content of baseline row 9: the same rule re-donated."""
    return [_born("BTCUSD", "mean_reversion_rsi", n=90 + k, params={"i": 9, "session": "all"})
            for k in range(n)]


def _baseline_verdicts(n: int = 6, gate: str = "in_sample_screen") -> list[dict[str, Any]]:
    return [_verdict("EURUSD", "carry", n=i, gate=gate) for i in range(n)]


def _fired(paths: dict[str, Path], born: list[dict[str, Any]],
           verdicts: list[dict[str, Any]]) -> set[str]:
    _plant(paths, born, verdicts)
    return set(gb.build(now=NOW)["fired"])


# ----------------------------------------------------------------------------- the measurements
def test_intake_and_testing_rates_are_measured_per_window(organ):
    born = [*_baseline_born(), _born("EURUSD", "carry", n=50, hours_ago=100.0)]
    _plant(organ, born, _baseline_verdicts(4))
    doc = gb.build(now=NOW)
    w24, w7d = doc["windows"]["24h"], doc["windows"]["7d"]
    assert w24["intake"]["born_cells"] == 10          # the 100h-old row is outside 24h
    assert w7d["intake"]["born_cells"] == 11
    assert w24["intake"]["per_hour"] == pytest.approx(10 / 24, abs=1e-3)
    assert w24["testing"]["verdicts"] == 4 and w24["testing"]["cells_judged"] == 4
    assert w24["testing"]["per_hour"] == pytest.approx(4 / 24, abs=1e-3)


def test_a_cell_is_born_once_however_often_its_fate_moves(organ):
    born = [_born("EURUSD", "carry", n=1, hours_ago=100.0),
            {**_born("EURUSD", "carry", n=1, hours_ago=1.0), "fate": "FAILED"}]
    _plant(organ, born, [])
    doc = gb.build(now=NOW)
    assert doc["windows"]["24h"]["intake"]["born_cells"] == 0
    assert doc["windows"]["7d"]["intake"]["born_cells"] == 1


def test_backlog_is_born_minus_judged_and_names_the_prior_window(organ):
    born = [*_baseline_born(), _born("US500", "carry", n=60, hours_ago=30.0)]
    _plant(organ, born, _baseline_verdicts(6))
    w = gb.build(now=NOW)["windows"]["24h"]
    assert w["backlog"]["born_minus_judged"] == 4
    assert w["backlog"]["capacity_cells"] == 6
    assert w["backlog"]["prior_window"] == 1          # the 30h-old cell, unjudged then
    assert w["backlog"]["growing"] is True


def test_capacity_reads_the_declared_constants_and_the_measured_sweep(organ):
    organ["GAUNTLET_SOURCE"].parent.mkdir(parents=True, exist_ok=True)
    organ["GAUNTLET_SOURCE"].write_text(
        'FRESH_BUILD_BUDGET_SEC = float(os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", "2700"))\n'
        "DECLARED_NEED_MB = 1200\n"
        'PER_WORKER_MB = float(os.environ.get("GAUNTLET_PER_WORKER_MB", "768"))\n',
        encoding="utf-8")
    organ["GAUNTLET_REPORT"].parent.mkdir(parents=True, exist_ok=True)
    organ["GAUNTLET_REPORT"].write_text(json.dumps(
        {"swept_at": (NOW - timedelta(hours=2)).isoformat(), "n_cells": 2143, "n_judged": 1395,
         "n_unmeasured": 748, "n_cells_deferred_build_budget": 3490, "workers": 1}),
        encoding="utf-8")
    _plant(organ, _baseline_born(), _baseline_verdicts())
    cap = gb.build(now=NOW)["capacity"]
    assert cap["declared"]["fresh_build_budget_sec"] == 2700.0
    assert cap["declared"]["declared_need_mb"] == 1200.0
    assert cap["declared"]["per_worker_mb"] == 768.0
    assert cap["measured"]["n_judged"] == 1395 and cap["measured"]["age_h"] == 2.0


def test_every_terminal_gate_lands_in_its_declared_failure_class(organ):
    v = [_verdict("EURUSD", "carry", n=1, gate="stress_costs"),
         _verdict("EURUSD", "carry", n=2, gate="swap_cost"),
         _verdict("EURUSD", "carry", n=3, gate="walk_forward"),
         _verdict("EURUSD", "carry", n=4, gate="pbo"),
         _verdict("EURUSD", "carry", n=5, gate="cpcv"),
         _verdict("EURUSD", "carry", n=6, gate="symbol_eligibility"),
         _verdict("EURUSD", "carry", n=7, gate="in_sample_screen"),
         _verdict("EURUSD", "carry", n=8, gate="observations"),
         _verdict("EURUSD", "carry", n=9, gate="UNKNOWN")]
    _plant(organ, _baseline_born(), v)
    mix = gb.build(now=NOW)["windows"]["24h"]["failure_mix"]
    assert mix["by_class"] == {"cost_killed": 2, "unstable": 2, "regime_specific": 1,
                               "wrong_asset": 1, "no_edge": 1}
    # observations and UNKNOWN name no class: too few observations is work not done, never a
    # refutation, and it must not be laundered into `no_edge`.
    assert mix["unmeasured_gates"] == {"observations": 1, "UNKNOWN": 1}
    assert mix["cost_killed_share"] == pytest.approx(2 / 7, abs=1e-4)
    assert set(gb.GATE_FAILURE_CLASS.values()) - {None} <= set(R.FAILURE_CLASSES)


def test_duplicates_are_counted_by_content_hash_and_by_the_registry(organ):
    born = _baseline_born() + _dup_rows(5)
    _plant(organ, born, _baseline_verdicts())
    dup = gb.build(now=NOW)["windows"]["24h"]["duplicates"]
    assert dup["content_hash"]["repeated_rows"] == 5
    assert dup["share"] == pytest.approx(1 / 3, abs=1e-4)
    assert dup["basis"] == "window content hashes"
    assert dup["registry"]["status"] == "UNMEASURED"        # nothing has synced the registry
    # ... and once the registry HAS rows, it is the basis, because it counts a re-enqueue the
    # window never saw.
    for _ in range(3):
        R.enqueue_candidate(family="carry", symbol="EURUSD", params={"a": 1}, origin="EXTERNAL")
    R.enqueue_candidate(family="carry", symbol="GBPUSD", params={"a": 2}, origin="EXTERNAL")
    dup = gb.build(now=NOW)["windows"]["24h"]["duplicates"]
    assert dup["registry"] == {"status": "MEASURED", "n_candidates": 2,
                               "n_search_count_gt_1": 1, "share": 0.5}
    assert dup["basis"] == "registry.search_count" and dup["share"] == 0.5


def test_novelty_gate_redundancy_is_read_when_it_exists(organ):
    organ["NOVELTY"].parent.mkdir(parents=True, exist_ok=True)
    organ["NOVELTY"].write_text(json.dumps({"n_screened": 5000, "n_redundant": 1883,
                                            "threshold": 0.9}), encoding="utf-8")
    _plant(organ, _baseline_born(), _baseline_verdicts())
    ng = gb.build(now=NOW)["windows"]["24h"]["duplicates"]["novelty_gate"]
    assert ng["status"] == "MEASURED" and ng["redundant_share"] == pytest.approx(0.3766, abs=1e-4)


def test_concentration_pit_and_cross_asset_novelty_are_measured(organ):
    _plant(organ, _baseline_born(), _baseline_verdicts())
    w = gb.build(now=NOW)["windows"]["24h"]
    assert w["concentration"]["fx_h1_asia"] == 2
    assert w["concentration"]["fx_h1_asia_share"] == 0.2
    assert len(w["concentration"]["top_grid_cells"]) == 3
    assert w["concentration"]["top3_grid_share"] >= 0.5
    assert w["pit"]["share"] == 1.0 and w["pit"]["n_stamped"] == 10
    assert w["cross_asset_novelty"]["share"] == 0.2
    assert set(w["cross_asset_novelty"]["top3_asset_classes"]) == {"forex", "commodities",
                                                                  "indices"}
    assert w["event_mechanisms"]["share"] == 0.2


# --------------------------------------------------------------------------------- the messages
def test_the_baseline_fires_nothing(organ):
    assert _fired(organ, _baseline_born(), _baseline_verdicts()) == set()


def test_too_many_duplicates_fires_only_on_its_trigger(organ):
    born = _baseline_born() + _dup_rows(5)
    assert _fired(organ, born, _baseline_verdicts()) == {"too_many_duplicates"}


def test_too_many_cost_killed_fires_only_on_its_trigger(organ):
    v = [_verdict("EURUSD", "carry", n=i, gate="stress_costs") for i in range(4)]
    v.append(_verdict("EURUSD", "carry", n=4, gate="swap_cost"))
    v.append(_verdict("EURUSD", "carry", n=5, gate="in_sample_screen"))
    fired = _fired(organ, _baseline_born(), v)
    assert fired == {"too_many_cost_killed"}
    doc = gb.build(now=NOW)
    msg = next(m for m in doc["messages"] if m["code"] == "too_many_cost_killed")
    assert "lower-frequency charts" in msg["instruction"] and msg["measured"]["share"] > 0.5


def test_too_much_fx_h1_asia_fires_only_on_its_trigger(organ):
    born = [_born(sym, "carry", n=i, session="asia")
            for i, sym in enumerate(["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "EURUSD",
                                     "GBPUSD", "AUDUSD", "USDCHF", "EURUSD", "GBPUSD"])]
    born += [_born("BTCUSD", "mean_reversion_rsi", n=20 + i) for i in range(3)]
    born += [_born("USB10Y", "carry", n=30 + i) for i in range(3)]
    born += [_born("XAUUSD", "forced_flow", n=40 + i) for i in range(3)]
    born += [_born("US500", "session_range_breakout", n=50 + i) for i in range(3)]
    fired = _fired(organ, born, _baseline_verdicts(9))
    assert fired == {"too_much_fx_h1_asia"}
    msg = next(m for m in gb.build(now=NOW)["messages"] if m["code"] == "too_much_fx_h1_asia")
    assert msg["measured"]["share"] > gb.CONCENTRATION_TRIGGER
    assert "novelty gate raises the bar" in msg["instruction"]


def test_not_enough_event_mechanisms_fires_only_on_its_trigger(organ):
    born = [r for r in _baseline_born() if r["family"] != "forced_flow"]
    born += [_born("XAUUSD", "mean_reversion_rsi", n=5), _born("XAGUSD", "mean_reversion_rsi",
                                                               n=6)]
    assert _fired(organ, born, _baseline_verdicts()) == {"not_enough_event_mechanisms"}


def test_weak_pit_compliance_fires_at_the_declared_edge(organ):
    born = _baseline_born()
    born[0] = _born("EURUSD", "carry", n=1, session="asia", pit=False)
    # exactly 0.9 is NOT under the floor: the trigger is `<`, and a boundary that fires is a
    # trigger nobody can reason about.
    assert _fired(organ, born, _baseline_verdicts()) == set()
    born[1] = _born("GBPUSD", "carry", n=2, session="asia", pit=False)
    assert _fired(organ, born, _baseline_verdicts()) == {"weak_pit_compliance"}


def test_weak_cross_asset_novelty_fires_only_on_its_trigger(organ):
    born = [r for r in _baseline_born() if r["symbol"] not in ("BTCUSD", "USB10Y")]
    born += [_born("AUDUSD", "mean_reversion_rsi", n=9), _born("USDCHF", "carry", n=10)]
    assert _fired(organ, born, _baseline_verdicts()) == {"weak_cross_asset_novelty"}


def test_backlog_growing_fires_only_when_it_grows_and_exceeds_capacity(organ):
    born = _baseline_born() + [{**r, "id": r["id"] + "b", "params": {**r["params"], "j": 1}}
                               for r in _baseline_born()]
    assert _fired(organ, born, _baseline_verdicts(5)) == {"backlog_growing"}
    msg = next(m for m in gb.build(now=NOW)["messages"] if m["code"] == "backlog_growing")
    assert "READY_PRIORITY" in msg["instruction"]
    assert msg["measured"]["backlog"] == 15 and msg["measured"]["capacity_cells"] == 5
    # the same intake with capacity to match it is not a backlog
    assert _fired(organ, born, _baseline_verdicts(9)) == set()


def test_messages_fall_back_to_the_next_window_and_name_it(organ):
    """A day with no intake is not a clean day. The first window WITH one is used, and said."""
    born = [_born(r["symbol"], r["family"], n=i, hours_ago=100.0, pit=False)
            for i, r in enumerate(_baseline_born())]
    _plant(organ, born, [_verdict("EURUSD", "carry", n=i, hours_ago=100.0) for i in range(6)])
    doc = gb.build(now=NOW)
    assert doc["windows"]["24h"]["intake"]["born_cells"] == 0
    assert doc["messages_window"] == "7d"
    assert all(m["window"] == "7d" for m in doc["messages"])
    assert "weak_pit_compliance" in doc["fired"]          # measured on the 7d rows, not on zero
    assert "measured on 7d instead" in doc["unmeasured"]["messages_intake"]
    # and with intake in the primary window the primary is what speaks
    _plant(organ, _baseline_born(), _baseline_verdicts())
    doc = gb.build(now=NOW)
    assert doc["messages_window"] == "24h" and all(m["window"] == "24h" for m in doc["messages"])


def test_every_message_carries_a_reading_and_an_instruction(organ):
    _plant(organ, _baseline_born(), _baseline_verdicts())
    msgs = gb.build(now=NOW)["messages"]
    assert {m["code"] for m in msgs} >= {
        "too_many_duplicates", "too_many_cost_killed", "too_much_fx_h1_asia",
        "not_enough_event_mechanisms", "weak_pit_compliance", "weak_cross_asset_novelty",
        "backlog_growing"}
    for m in msgs:
        assert m["trigger"] and m["instruction"] and "measured" in m
        assert isinstance(m["fired"], bool)


# ------------------------------------------------------------------------------- cold and priors
def test_cold_share_is_measured_against_the_explore_floor(organ):
    import negative_knowledge as nk
    warm = [_verdict("EURUSD", "carry", n=1, passed=True),                 # forex|carry_rollover
            _verdict("EURUSD", "mean_reversion_rsi", n=2, passed=True),    # forex|range_reversion
            _verdict("XAUUSD", "forced_flow", n=3, passed=True),           # commodities|forced
            _verdict("US500", "session_range_breakout", n=4, passed=True),  # indices|breakout
            _verdict("BTCUSD", "mean_reversion_rsi", n=5, passed=True),    # crypto|range_reversion
            _verdict("USB10Y", "carry", n=6, passed=True)]                 # bonds|carry_rollover
    _plant(organ, _baseline_born(), warm)
    doc = gb.build(now=NOW)
    assert doc["cold"]["explore_floor"] == nk.EXPLORE_FLOOR
    assert doc["cold_share"] == 0.0 and doc["cold"]["under_floor"] is True
    assert "cold_exploration_under_floor" in doc["fired"]
    # leave two classes cold and the floor is met -- 0.2 is not UNDER 0.2
    _plant(organ, _baseline_born(), warm[:4])
    doc = gb.build(now=NOW)
    assert doc["cold_share"] == 0.2 and doc["cold"]["under_floor"] is False
    assert "cold_exploration_under_floor" not in doc["fired"]


def test_priors_are_written_per_bucket_over_the_floor_and_read_back(organ):
    v = [_verdict("EURUSD", "carry", n=i, gate="deflated_sharpe") for i in range(20)]
    v += [_verdict("EURUSD", "carry", n=100 + i, passed=True) for i in range(5)]
    v += [_verdict("US500", "session_range_breakout", n=200 + i) for i in range(10)]
    _plant(organ, _baseline_born(), v)
    doc = gb.build(now=NOW)
    keys = {p["memory_key"] for p in doc["priors"]}
    assert keys == {"prior:carry|H1|forex"}            # the 10-row bucket is under the floor
    row = doc["priors"][0]
    assert row["n_judged"] == 25 and row["n_passed"] == 5
    assert row["p_edge_prior"] == pytest.approx(5.5 / 26, abs=1e-6)
    assert row["dominant_failure_class"] == "no_edge"
    assert row["failure_class_shares"] == {"no_edge": 1.0}

    res = gb.write_priors(doc["priors"], doc["at"])
    assert res["written"] == 1 and res["status"] == "OK"
    mem = R.memories(category="candidate_prior")
    assert len(mem) == 1 and mem[0]["memory_key"] == "prior:carry|H1|forex"
    metrics = json.loads(mem[0]["metrics_json"])
    assert metrics["p_edge_prior"] == pytest.approx(5.5 / 26, abs=1e-6)
    assert metrics["family"] == "carry" and metrics["asset_class"] == "forex"
    # the key makes it an UPSERT: a second pass refreshes the row, never duplicates it
    gb.write_priors(doc["priors"], doc["at"])
    assert len(R.memories(category="candidate_prior")) == 1


#: The replicated registry's OWN research_memory DDL, constraint included. A test built on
#: `CANON`'s plain-TEXT column cannot see this, and the first real run of this organ wrote 0 of 27
#: priors because of it while the whole suite was green.
_REPLICATED_MEMORY_DDL = """
CREATE TABLE research_memory (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, category TEXT NOT NULL,
    statement TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('pending', 'success', 'failure')),
    failure_cause TEXT, failure_reason TEXT, success_reason TEXT, failure_stage TEXT,
    lessons TEXT, metrics_json TEXT, predecessor_id TEXT)
"""


def test_priors_clear_the_replicated_registrys_result_constraint(organ):
    """The restored file constrains `result` to three values; the fresh one does not."""
    path = R.path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(_REPLICATED_MEMORY_DDL)
    conn.commit()
    conn.close()
    v = [_verdict("EURUSD", "carry", n=i, gate="deflated_sharpe") for i in range(25)]
    v += [_verdict("US500", "session_range_breakout", n=100 + i, passed=True) for i in range(20)]
    _plant(organ, _baseline_born(), v)
    doc = gb.build(now=NOW)
    res = gb.write_priors(doc["priors"], doc["at"])
    assert res["status"] == "OK" and res["written"] == 2
    rows = {r["memory_key"]: r for r in R.memories(category="candidate_prior")}
    # the FILE's vocabulary, read onto the bucket: a bucket that has produced a pass is a
    # success, one that judged its floor and produced none is a failure.
    assert rows["prior:carry|H1|forex"]["result"] == "failure"
    assert rows["prior:session_range_breakout|H1|indices"]["result"] == "success"
    assert set(gb._RESULT_VOCAB) == {"pending", "success", "failure"}


def test_a_bucket_under_the_floor_is_never_written(organ):
    v = [_verdict("EURUSD", "carry", n=i) for i in range(gb.MIN_BUCKET_JUDGED - 1)]
    _plant(organ, _baseline_born(), v)
    doc = gb.build(now=NOW)
    assert doc["priors"] == []
    assert gb.write_priors(doc["priors"], doc["at"])["written"] == 0
    assert R.memories(category="candidate_prior") == []


# -------------------------------------------------------------------------------- the bandit
def test_the_bandit_is_read_through_its_evidence_path_and_never_run(organ, monkeypatch):
    from libs.research import bandit

    def _boom(*a, **k):  # pragma: no cover - the assertion is that it is never reached
        raise AssertionError("gauntlet_backpressure must not run the bandit or write its budget")

    monkeypatch.setattr(bandit, "run", _boom)
    _plant(organ, _baseline_born(), _baseline_verdicts())
    b = gb.build(now=NOW)["bandit"]
    assert b["status"] == "MEASURED"
    assert b["arms"]["alt_data_hypothesis"]["born"] == 10      # miner:* -> the catch-all arm
    assert b["intended_feedback"]["applied"] is False
    assert "research_pnl.py" in b["intended_feedback"]["why"]
    assert b["intended_feedback"]["failure_class_shares"]


# --------------------------------------------------------------------------------- the CLI
def test_dry_run_writes_no_report_and_no_prior(organ, capsys):
    v = [_verdict("EURUSD", "carry", n=i) for i in range(25)]
    _plant(organ, _baseline_born(), v)
    assert gb.main(["--dry-run"]) == 0
    assert not organ["OUT"].exists()
    assert R.memories(category="candidate_prior") == []
    assert "nothing written" in capsys.readouterr().out


def test_main_writes_the_report_with_the_declared_schema(organ):
    v = [_verdict("EURUSD", "carry", n=i) for i in range(25)]
    _plant(organ, _baseline_born(), v)
    assert gb.main([]) == 0
    doc = json.loads(organ["OUT"].read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "windows", "messages", "priors_written", "cold_share", "capacity",
                        "unmeasured", "rule"}
    assert set(doc["windows"]) == {"24h", "7d"}
    assert doc["priors_written"] == 1 == len(R.memories(category="candidate_prior"))
    assert "the gauntlet talks back" in doc["rule"]
    assert doc["prior_contract"]["read_with"] == 'registry.memories(category="candidate_prior")'


def test_absent_inputs_are_named_unmeasured_rather_than_read_as_clean(organ):
    doc = gb.build(now=NOW)
    assert doc["unmeasured"]["hypothesis_graph.jsonl"] == "ABSENT"
    assert doc["unmeasured"]["gate_verdict_ledger.jsonl"] == "ABSENT"
    assert "messages_intake" in doc["unmeasured"]
    assert doc["fired"] == []                     # absence never fires a message
    assert doc["cold_share"] is None
    assert doc["windows"]["24h"]["pit"]["share"] is None
