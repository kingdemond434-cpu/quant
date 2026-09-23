"""The experiment spine on a temporary desk: each source kind converts, a prose-only row is a
recorded defect with its blocker, credit reaches the right ancestor, the priors move with the
verdicts, the never-tried frontier is published, and the funnel arithmetic is the measured one."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import experiment_graph as G  # noqa: E402
from libs.research import research_priors as P  # noqa: E402
from research import experiment_spine as SP  # noqa: E402


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole temporary desk: registry, reports, universe bars, prior store."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    reports = tmp_path / "reports"
    reports.mkdir()
    universe = tmp_path / "universe"
    universe.mkdir()
    (universe / "AUDJPY_H1.parquet").write_bytes(b"not a real parquet, only an mtime")
    priors_dir = tmp_path / "research_priors"
    monkeypatch.setattr(P, "STATE_DIR", priors_dir)
    monkeypatch.setattr(SP, "REPORTS", reports)
    monkeypatch.setattr(SP, "UNIVERSE", universe)
    monkeypatch.setattr(SP, "ROOT", tmp_path)
    monkeypatch.setattr(SP, "OUT", reports / "EXPERIMENT_SPINE.json")
    monkeypatch.setattr(SP, "FUNNEL_OUT", reports / "RESEARCH_FUNNEL.json")
    monkeypatch.setattr(SP, "PRIOR_CURSOR", priors_dir / "charged.json")
    monkeypatch.setattr(SP, "ALLOCATION", reports / "pf_allocation.json")
    monkeypatch.setattr(SP, "RESEARCH_PNL", reports / "RESEARCH_PNL.json")
    monkeypatch.setattr(SP, "LIVE_LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(SP, "SHADOW", (reports / "shadow" / "shadow_state.json",))
    monkeypatch.setattr(SP, "ARTIFACT_SOURCES", (
        (reports / "DISCOVERY_COMPILER.json", "world_lead", "mechanisms", "discovery_compiler"),
        (tmp_path / "miner_candidates.json", "world_lead", "hypotheses",
         "miner_candidate_compiler"),
        (reports / "GLOBAL_RESEARCH_OS.json", "country_mechanism", "mechanisms",
         "global_research_os"),
    ))
    yield tmp_path
    R.set_path(None)


def _seed_discovery(**over: object) -> str:
    fields: dict[str, object] = {
        "assets": ["AUDJPY"], "horizons": ["1d"], "sessions": ["asia"],
        "required_data": ["universe/AUDJPY_H1.parquet"],
        "falsifier": "later bars stop clearing the gates",
        "exact_rule_if_known": json.dumps({"family": "carry_unwind", "lookback": 20}),
        "payload": {"family": "carry_unwind", "chart": "H1"},
        "information": "positioning",
    }
    fields.update(over)
    did, _ = R.record_discovery(source_id="src_7ho", source_type="forum_thread",
                                mechanism="carry_unwind on JPY crosses -> fade",
                                origin="EXTERNAL", generator="deep_forest_miner", **fields)
    return did


def test_every_source_kind_converts_into_the_campaign_queue(desk: Path) -> None:
    _seed_discovery()
    (desk / "miner_candidates.json").write_text(json.dumps({"hypotheses": [
        {"symbol": "AUDJPY", "family": "retail_overlap_reversal", "params": {},
         "source": "miner:reddit"}]}), encoding="utf-8")
    (desk / "reports" / "GLOBAL_RESEARCH_OS.json").write_text(json.dumps({"mechanisms": [
        {"instruments": ["AUDJPY"], "family": "session_range_breakout", "timeframe": "H1",
         "mechanism": "tokyo range", "producer": "jp_lab"}]}), encoding="utf-8")
    doc = SP.run(budget_s=60.0)
    c = doc["conversion"]
    assert c["rows_read"] >= 3 and c["converted"] >= 3 and c["enqueued"] >= 3
    kinds = doc["graph"]["census"]["by_kind"]
    assert kinds.get("world_lead", 0) >= 2 and kinds.get("country_mechanism", 0) >= 1
    # the enrichment is what let the bare miner rows compile, and it is NAMED, never silent
    assert all(s["defects"] == 0 for name, s in c["by_source"].items()
               if name in ("miner_candidates.json", "GLOBAL_RESEARCH_OS.json"))
    # every converted row reached the registry's queue with its provenance
    assert R.candidates(limit=50)
    assert doc["graph"]["census"]["edges"] > 0


def test_a_prose_only_row_is_a_recorded_defect_with_a_named_blocker(desk: Path) -> None:
    _seed_discovery(assets=[], exact_rule_if_known=None, payload={},
                    mechanism_note="the Bank of Japan intervenes when the yen is weak")
    doc = SP.run(budget_s=60.0)
    debt = doc["conversion"]["conversion_debt"]
    assert debt["unconverted_rows"] >= 1
    assert set(debt["by_reason"]) <= set(
        __import__("libs.research.experiment_spec", fromlist=["x"]).DEFECT_REASONS)
    assert debt["examples"] and debt["examples"][0]["reason"] in debt["by_reason"]
    assert "zero" in debt["rule"].lower()


def test_the_second_pass_does_not_reconvert_the_first_passes_rows(desk: Path) -> None:
    _seed_discovery()
    first = SP.run(budget_s=60.0)["conversion"]
    second = SP.run(budget_s=60.0)["conversion"]
    assert first["converted"] >= 1
    assert second["already_in_graph"] >= first["converted"]
    assert second["converted"] == 0


def test_credit_flows_to_the_ancestor_that_produced_the_survivor(desk: Path) -> None:
    _seed_discovery()
    SP.run(budget_s=60.0)
    node = G.experiments(limit=5)[0]
    R.mark_candidate(str(node["candidate_id"]), "survived", survived=1)
    (desk / "reports" / "shadow").mkdir()
    (desk / "reports" / "shadow" / "shadow_state.json").write_text(json.dumps({
        "AUDJPY.carry": {"exp_r": 0.4, "n": 25, "family": "carry_unwind"}}), encoding="utf-8")
    doc = SP.run(budget_s=60.0)
    credit = doc["credit"]
    assert credit["ancestors"] > 0 and credit["rows_written"] > 0
    conn = R.connect()
    try:
        rows = {(r["ancestor_kind"], r["ancestor_id"]): dict(r)
                for r in conn.execute("SELECT * FROM research_credit")}
    finally:
        conn.close()
    # the SOURCE that suggested the mechanism and the MINER that found it are both credited
    assert ("source", "src_7ho") in rows
    assert ("miner", "deep_forest_miner") in rows
    assert rows[("source", "src_7ho")]["survivors"] >= 1
    assert rows[("source", "src_7ho")]["forward_r"] == pytest.approx(10.0)
    # independence is measured, never the raw count
    assert rows[("source", "src_7ho")]["independent_survivors"] > 0
    # and an unrelated ancestor got nothing
    assert ("source", "src_other") not in rows


def test_priors_move_with_the_verdicts_and_are_charged_once(desk: Path) -> None:
    _seed_discovery()
    SP.run(budget_s=60.0)
    node = G.experiments(limit=5)[0]
    R.mark_candidate(str(node["candidate_id"]), "survived", survived=1)
    first = SP.run(budget_s=60.0)["priors"]
    assert first["experiments_charged"] == 1
    assert first["by_outcome_class"] == {"survived": 1}
    assert P.posterior_mean("family", "carry_unwind") > 0.5
    assert P.posterior_mean("operator", "deep_forest_miner") > 0.5
    before = P.prior_for("family", "carry_unwind").a
    second = SP.run(budget_s=60.0)["priors"]
    assert second["experiments_charged"] == 0                 # a verdict is charged ONCE
    assert P.prior_for("family", "carry_unwind").a == before


def test_the_never_tried_frontier_is_published_for_the_proposers(desk: Path) -> None:
    _seed_discovery()
    SP.run(budget_s=60.0)
    node = G.experiments(limit=5)[0]
    R.mark_candidate(str(node["candidate_id"]), "survived", survived=1)
    doc = SP.run(budget_s=60.0)
    frontier = doc["graph"]["never_tried_frontier"]
    assert frontier and frontier[0]["survivors"] >= 1
    assert frontier[0]["coverage"] is not None
    assert "never_tried" in doc["consumers"]


def test_the_funnel_arithmetic_is_the_measured_one(desk: Path) -> None:
    _seed_discovery()
    SP.run(budget_s=60.0)
    node = G.experiments(limit=5)[0]
    R.mark_candidate(str(node["candidate_id"]), "survived", survived=1)
    doc = SP.run(budget_s=60.0)
    f = doc["funnel"]
    num, den, rates = f["numerator"], f["denominator"], f["rates"]
    assert num["forward_valid_discoveries"] == 1
    assert 0 < num["independent_forward_valid"] <= num["forward_valid_discoveries"]
    assert den["data_units"] >= 1 and den["time_days"] == f["window_days"]
    if den["compute_hours"]:
        assert rates["per_compute_hour"] == pytest.approx(
            num["independent_forward_valid"] / den["compute_hours"], rel=1e-6)
    assert rates["per_day"] == pytest.approx(
        num["independent_forward_valid"] / den["time_days"], rel=1e-6)
    assert rates["per_data_unit"] == pytest.approx(
        num["independent_forward_valid"] / den["data_units"], rel=1e-6)
    assert (desk / "reports" / "RESEARCH_FUNNEL.json").exists()
    assert (desk / "reports" / "EXPERIMENT_SPINE.json").exists()


def test_a_dry_run_writes_nothing(desk: Path) -> None:
    _seed_discovery()
    doc = SP.run(budget_s=60.0, dry_run=True)
    assert doc["conversion"]["converted"] >= 1 and doc["conversion"]["enqueued"] == 0
    assert not (desk / "reports" / "EXPERIMENT_SPINE.json").exists()
    assert not (desk / "reports" / "RESEARCH_FUNNEL.json").exists()
    assert R.candidates(limit=5) == []


def test_the_row_cap_is_derived_from_measured_memory_never_a_machine_size() -> None:
    assert SP.max_rows_per_pass() >= SP.MAX_ROWS_FLOOR
    assert SP.main(["--once", "--budget-s", "5", "--dry-run"]) == 0
