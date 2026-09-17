"""The canonical research registry: restore, evolve, constitution, dedupe, score, discoveries,
provenance, the trials chain and the desk bridge."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from libs.moat import registry as R


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "alpha_registry.sqlite"
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(p)
    yield p
    R.set_path(None)


def _fake_backup(path: Path) -> None:
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE alpha_cards (id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, "
              "name TEXT, market TEXT, category TEXT, thesis TEXT, entry_logic TEXT, "
              "exit_logic TEXT, expected_cagr REAL, expected_sharpe REAL, expected_drawdown REAL,"
              " dsr REAL, pbo REAL, cpcv_json TEXT, walk_forward_json TEXT, holdout_json TEXT, "
              "deployment_date TEXT, retirement_date TEXT, live_cagr REAL, live_sharpe REAL, "
              "live_drawdown REAL, decay_score REAL, status TEXT, successor_id TEXT, "
              "predecessor_id TEXT, extra_json TEXT)")
    c.execute("CREATE TABLE alpha_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, "
              "alpha_id TEXT, created_at TEXT, event_type TEXT, from_status TEXT, to_status TEXT,"
              " detail_json TEXT, actor TEXT)")
    c.execute("CREATE TABLE research_candidates (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT "
              "UNIQUE, created_at TEXT, campaign_id TEXT, family TEXT, subtype TEXT, symbol TEXT,"
              " params_json TEXT, content_hash TEXT, status TEXT, mechanism TEXT, "
              "annual_sharpe REAL, dsr REAL, pbo REAL, reality_p REAL, oos_sharpe REAL, "
              "capacity_usd REAL, fragility REAL, survived INTEGER, rejection_reason TEXT, "
              "updated_at TEXT)")
    c.execute("INSERT INTO alpha_cards(id, name, market, status) VALUES('a1', 'crypto::funding',"
              " 'BINANCE-PERP', 'candidate')")
    c.execute("INSERT INTO alpha_cards(id, name, market, status) VALUES('a2', 'gold_asia', "
              "'XAUUSD', 'live')")
    c.execute("INSERT INTO alpha_events(id, alpha_id, event_type) VALUES('e1', 'a1', 'creation')")
    c.commit()
    c.close()


def test_restore_from_backup_keeps_rows_evolves_schema_and_retires_crypto(tmp_path, monkeypatch):
    backup = tmp_path / "backup_registry"
    _fake_backup(backup)
    monkeypatch.setattr(R, "BACKUP", backup)
    R.set_path(tmp_path / "data" / "alpha_registry.sqlite")
    try:
        n = R.counts()
        assert n["alpha_cards"] == 2 and n["alpha_events"] == 2     # +1 retirement event
        cards = {c["id"]: c for c in R.cards()}
        assert cards["a1"]["status"] == "retired" and cards["a2"]["status"] == "live"
        assert "discoveries" in n and "provenance" in n and "trials_ledger" in n
        conn = R.connect()
        cols = R._columns(conn, "research_candidates")
        assert "origin" in cols and "grid_cell" in cols and "discovery_id" in cols
        conn.close()
        ev = R.events("a1")
        assert ev[-1]["event_type"] == "retire" and "mandate" in ev[-1]["detail_json"]
    finally:
        R.set_path(None)


def test_fresh_file_has_every_canonical_and_moat_table(reg):
    n = R.counts()
    for t in list(R.CANON) + list(R.MOAT_TABLES):
        assert t in n, t
    assert all(v == 0 for k, v in n.items() if k != "schema_migrations")


def test_constitution_triggers_refuse_edits_to_immutable_tables(reg):
    R.record_trial("cell1", family="f", method="gauntlet", params={"a": 1}, passed=False,
                   terminal_gate="cost")
    conn = R.connect()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE trials_ledger SET passed=1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM trials_ledger")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM provenance")
    conn.close()


def test_candidate_dedupe_search_count_and_priority_order(reg):
    a, created = R.enqueue_candidate(family="f", symbol="XAUUSD", params={"w": 20}, origin="MOAT",
                                     mechanism="m", chart="H1", p_edge=0.8, novelty_vs_live=0.9,
                                     novelty_vs_graveyard=0.9)
    assert created
    a2, created2 = R.enqueue_candidate(family="f", symbol="XAUUSD", params={"w": 20},
                                       origin="EXTERNAL", mechanism="m", chart="H1")
    assert a2 == a and not created2
    row = R.candidates()[0]
    assert row["search_count"] == 2 and row["origin"] == "MOAT"
    b, _ = R.enqueue_candidate(family="f", symbol="EURUSD", params={"w": 20}, origin="MOAT",
                               mechanism="m", chart="H1", p_edge=0.2)
    top = R.claim_candidates("discovery", 1)
    assert [r["id"] for r in top] == [a]                         # best score first
    assert R.candidates(status="claimed")[0]["claimed_by"] == "discovery"
    assert R.queue_depth()["MOAT"] == {"claimed": 1, "queued": 1}
    assert R.mark_candidate(b, "judged", failure_class="cost_killed")
    assert R.candidates(status="judged")[0]["failure_class"] == "cost_killed"


def test_score_uses_priors_for_unmeasured_and_empty_cell_bonus(reg):
    base = {"p_edge": 0.5, "novelty_vs_live": 0.5, "novelty_vs_graveyard": 0.5,
            "expected_return_independence": 0.5, "data_quality": 0.5, "mechanism_strength": 0.5,
            "expected_capacity": 0.5, "expected_info_gain": 0.5}
    s_measured = R.score_candidate(base, cell_empty=False)
    s_unmeasured = R.score_candidate({}, cell_empty=False)
    assert s_measured == pytest.approx(s_unmeasured)              # the prior IS 0.5, not 1.0
    assert R.score_candidate(base, cell_empty=True) == pytest.approx(s_measured * 1.5)
    assert R.score_candidate({**base, "p_edge": 1.0}, False) > s_measured
    assert R.score_candidate({**base, "research_cost": 4.0}, False) < s_measured
    assert R.grid_cell({"asset_class": "FX", "chart": "H1"}) == \
        "fx|unknown|unknown|unknown|h1|unknown|unknown|unknown"


def test_discovery_state_machine_conversion_debt_and_provenance(reg):
    did, created = R.record_discovery(source_id="src1", source_type="paper", mechanism="month-end",
                                      origin="EXTERNAL", assets=["USDJPY"], actor="hedgers")
    assert created
    same, created2 = R.record_discovery(source_id="src1", source_type="paper",
                                        mechanism="month-end", origin="EXTERNAL",
                                        assets=["USDJPY"])
    assert same == did and not created2
    with pytest.raises(ValueError):
        R.set_discovery_state(did, "BLOCKED")                      # a reason is mandatory
    with pytest.raises(ValueError):
        R.set_discovery_state(did, "NOT_A_STATE")
    R.set_discovery_state(did, "INTERPRETED", mechanism_id="mech1")
    R.set_discovery_state(did, "EXPANDED", possible_cells=12, generated_cells=8, blocked_cells=2)
    cid, _ = R.enqueue_candidate(family="f", symbol="USDJPY", params={}, origin="EXTERNAL",
                                 mechanism="month-end", discovery_id=did,
                                 transformation="transfer")
    R.set_discovery_state(did, "COMPILED", compiled_cells=8)
    debt = R.conversion_debt()
    assert debt["by_state"] == {"COMPILED": 1}
    assert debt["possible_cells"] == 12 and debt["unexplained_missing_cells"] == 2
    assert debt["conversion_coverage"] == pytest.approx(10 / 12)
    R.record_trial(cid, family="f", method="gauntlet", params={}, passed=True,
                   terminal_gate="ten_gates", candidate_id=cid)
    anc = R.provenance_of("cell", cid)
    kinds = {(e["from_kind"], e["to_kind"]) for e in anc}
    assert ("discovery", "cell") in kinds and ("source", "discovery") in kinds
    fwd = {(e["from_kind"], e["to_kind"]) for e in R.descendants_of("discovery", did)}
    assert ("discovery", "mechanism") in fwd and ("discovery", "cell") in fwd
    desc = R.descendants_of("source", "src1")
    assert any(e["to_kind"] == "verdict" for e in desc)
    with pytest.raises(ValueError):
        R.link("planet", "x", "cell", cid, "bad")


def test_trial_chain_verifies_and_memory_upserts(reg):
    for i in range(3):
        R.record_trial(f"c{i}", family="f", method="gauntlet", params={"i": i}, passed=i == 2)
    ok, n = R.verify_trial_chain()
    assert ok and n == 3
    m1 = R.remember("failure_cluster", "cost kills M1 breakouts", kind="cluster",
                    memory_key="cluster:m1-cost", metrics={"n": 40})
    m2 = R.remember("failure_cluster", "cost kills M1 breakouts (n=55)", kind="cluster",
                    memory_key="cluster:m1-cost", metrics={"n": 55})
    assert m1 == m2
    rows = R.memories(kind="cluster")
    assert len(rows) == 1 and json.loads(rows[0]["metrics_json"])["n"] == 55


def test_workers_runs_campaigns_metrics_returns_and_yields(reg):
    R.worker_heartbeat("dept:intel", kind="department_resident", department="intel", pid=42)
    R.worker_heartbeat("scout:china", kind="scout", beat="zh", status="stopped")
    alive = R.workers_alive()
    assert [w["worker_id"] for w in alive] == ["dept:intel"]
    R.record_run("run1", name="hourly_cycle", status="ok", organ="hourly_cycle", compute_s=12.5)
    R.record_run("run1", name="hourly_cycle", status="failed", organ="hourly_cycle")
    assert R.counts()["research_runs"] == 1
    R.campaign_upsert("camp1", spec={"kind": "closure"}, priority=2)
    R.campaign_upsert("camp1", spec={"kind": "closure"}, status="done", worker_id="dept:intel")
    R.metric("candidates_per_hour", 12.0, {"origin": "MOAT"})
    ck = R.record_candidate_returns("cand1", "oos", "2026-09", np.arange(5, dtype=float), "H1")
    kind, epoch, arr = R.candidate_returns("cand1")[0]
    assert kind == "oos" and epoch == "2026-09" and arr.tolist() == [0, 1, 2, 3, 4]
    assert len(ck) == 32
    R.generator_yield_update("graveyard_resurrection", generated=10, donated=8)
    R.generator_yield_update("graveyard_resurrection", independent_survivors=2, delta_n_eff=0.3)
    y = R.generator_yields()[0]
    assert y["generated"] == 10 and y["yield"] == pytest.approx(0.2)
    assert y["delta_n_eff"] == pytest.approx(0.3)
    R.kpi("2026-09-17", "orthogonal_candidates_per_day", 7.0)
    assert R.kpis()[0]["value"] == 7.0


def _desk(tmp_path: Path) -> Path:
    d = tmp_path / "desk"
    (d / "data" / "hypotheses").mkdir(parents=True)
    (d / "reports").mkdir()
    (d / "data" / "locks").mkdir()
    graph = [{"id": "cell_a", "symbol": "XAUUSD", "family": "session_range", "params": {"w": 3},
              "source": "deep_forest_miner:zh", "fate": "", "at": "2026-09-16T00:00:00+00:00"},
             {"id": "cell_b", "symbol": "EURUSD", "family": "carry", "params": {},
              "source": "moat:graveyard", "fate": "failed", "parent": "cell_a", "why": "m"}]
    (d / "data" / "hypothesis_graph.jsonl").write_text(
        "\n".join(json.dumps(r) for r in graph) + "\n", encoding="utf-8")
    (d / "data" / "hypotheses" / "gate_verdict_ledger.jsonl").write_text(
        json.dumps({"cell": "cell_b", "family": "carry", "sym": "EURUSD", "passed": False,
                    "terminal_gate": "cost", "at": "2026-09-16T01:00:00+00:00"}) + "\n",
        encoding="utf-8")
    (d / "data" / "compute_ledger.jsonl").write_text(
        json.dumps({"at": "2026-09-16T02:00:00+00:00", "run": "stop", "kind": "hourly_cycle",
                    "outcome": "ok", "wall_s": 30.0, "cpu_s": 3.0}) + "\n", encoding="utf-8")
    (d / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "gold_asia", "symbol": "XAUUSD", "family": "session_range", "status": "LIVE",
         "timeframe": "M5", "stop_atr": 1.0}]}), encoding="utf-8")
    (d / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps({"n": 1, "survivors": {
        "h.c1": {"cell": "c1", "sym": "XAGUSD", "status": "certified",
                 "shadow_spec": {"family": "carry", "params": {"k": 1}, "chart": "H1"}}}}),
        encoding="utf-8")
    (d / "data" / "locks" / "dept_intel.lock").write_text("777 2026-09-17T00:00:00+00:00\n")
    return d


def test_sync_from_desk_pours_the_record_in_and_is_idempotent(reg, tmp_path):
    d = _desk(tmp_path)
    lessons = tmp_path / "lessons.jsonl"
    lessons.write_text(json.dumps({"id": "L0001", "lesson": "measure first", "cost": "blind",
                                   "evidence": "x"}) + "\n", encoding="utf-8")
    out = R.sync_from_desk(d, lessons=lessons)
    assert out == {"candidates": 2, "trials": 1, "runs": 1, "cards": 2, "events": 2,
                   "memories": 1, "workers": 1}
    cands = {c["id"]: c for c in R.candidates()}
    assert cands["cell_a"]["origin"] == "EXTERNAL" and cands["cell_a"]["status"] == "donated"
    assert cands["cell_b"]["origin"] == "MOAT" and cands["cell_b"]["status"] == "judged"
    assert cands["cell_b"]["terminal_gate"] == "cost" and cands["cell_b"]["survived"] == 0
    assert json.loads(cands["cell_b"]["parent_ids_json"]) == ["cell_a"]
    cards = {c["id"]: c for c in R.cards()}
    assert cards["sleeve:gold_asia"]["status"] == "live" and cards["cell:c1"]["lane"] == "forward"
    assert R.workers_alive(stale_s=10 ** 9)[0]["worker_id"] == "dept:intel"
    assert R.memories(kind="lesson")[0]["memory_key"] == "lesson:L0001"
    again = R.sync_from_desk(d, lessons=lessons)
    assert again == {"candidates": 0, "trials": 0, "runs": 0, "cards": 2, "events": 0,
                     "memories": 0, "workers": 1}
    ok, n = R.verify_trial_chain()
    assert ok and n == 1
    # a status change on a sleeve is one more immutable event
    sl = json.loads((d / "data" / "sleeves.json").read_text())
    sl["sleeves"][0]["status"] = "RETIRED"
    (d / "data" / "sleeves.json").write_text(json.dumps(sl))
    assert R.sync_from_desk(d, lessons=lessons)["events"] == 1
    assert R.events("sleeve:gold_asia")[-1]["to_status"] == "retired"


def test_origin_classifier():
    assert R.origin_of("moat:graveyard_resurrection") == "MOAT"
    assert R.origin_of("deep_forest_miner:zh") == "EXTERNAL"
    assert R.origin_of("breadth_sweep") == "DESK"


def test_cli_counts_and_debt(reg, capsys):
    assert R.main(["--counts"]) == 0
    assert "research_candidates" in capsys.readouterr().out
    assert R.main(["--debt"]) == 0
    assert "unexplained_missing_cells" in capsys.readouterr().out
