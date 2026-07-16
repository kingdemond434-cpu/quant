"""Alpha governance gate, research kill-switch, and the end-to-end orchestrator pipeline."""

from __future__ import annotations

from tests.stage15.conftest import good_scores, passing_candidate

from libs.stage15.governance import ResearchGovernanceEngine, alpha_governance_gate
from libs.stage15.models import PipelineStage
from libs.stage15.orchestrator import AlphaPipelineInput, ResearchOrchestrator
from libs.validation.gauntlet import GauntletResult

_GATE_OK = {
    "cpcv_passed": True, "pbo_acceptable": True, "dsr_passed": True,
    "reality_check_passed": True, "economic_mechanism_present": True,
    "capacity_acceptable": True, "fragility_acceptable": True, "walk_forward_passed": True,
}


def test_governance_gate_accepts_only_when_all_pass() -> None:
    assert alpha_governance_gate(**_GATE_OK).accepted  # type: ignore[arg-type]
    for failing in _GATE_OK:
        verdict = alpha_governance_gate(**{**_GATE_OK, failing: False})  # type: ignore[arg-type]
        assert not verdict.accepted
        assert any(failing.split("_")[0] in r for r in verdict.rejected_reasons)


def test_research_kill_switch_fail_closed() -> None:
    eng = ResearchGovernanceEngine(max_false_discovery_rate=0.1, min_discovery_quality=40.0)
    healthy = eng.evaluate(false_discovery_rate=0.05, validation_pass_rate=0.2,
                           discovery_quality=80.0, decay_rate=0.1)
    assert not healthy.halt
    overfit = eng.evaluate(false_discovery_rate=0.5, validation_pass_rate=0.2,
                           discovery_quality=80.0, decay_rate=0.1)
    assert overfit.halt
    collapsed = eng.evaluate(false_discovery_rate=0.05, validation_pass_rate=0.2,
                             discovery_quality=10.0, decay_rate=0.1)
    assert collapsed.halt
    low_pass = eng.evaluate(false_discovery_rate=0.05, validation_pass_rate=0.0,
                            discovery_quality=80.0, decay_rate=0.1)
    assert low_pass.halt
    high_decay = eng.evaluate(false_discovery_rate=0.05, validation_pass_rate=0.2,
                              discovery_quality=80.0, decay_rate=0.9)
    assert high_decay.halt


def test_orchestrator_allocates_clean_candidate() -> None:
    result = ResearchOrchestrator(min_allocation_quality=60.0).run([passing_candidate("a")])
    assert result.allocated == ["a"]
    assert result.records[0].stage is PipelineStage.ALLOCATION


def test_orchestrator_rejects_failed_gate() -> None:
    result = ResearchOrchestrator().run([passing_candidate("a", dsr_passed=False)])
    assert result.rejected == ["a"]
    assert result.records[0].stage is PipelineStage.REJECTED


def test_orchestrator_holds_in_shadow_until_ready() -> None:
    result = ResearchOrchestrator().run([passing_candidate("a", shadow_ready=False)])
    assert result.allocated == []
    assert result.records[0].stage is PipelineStage.SHADOW


def test_orchestrator_paper_trades_low_quality() -> None:
    low = passing_candidate("a", scores=good_scores(survival_score=55.0, stability_score=40.0,
                                                    economic_score=40.0, capacity_score=40.0))
    result = ResearchOrchestrator(min_allocation_quality=80.0).run([low])
    assert result.records[0].stage is PipelineStage.PAPER
    assert result.allocated == []


def test_from_gauntlet_bridges_verdict() -> None:
    gauntlet = GauntletResult(
        candidate_id="c1", hypothesis_id="h1", passed=True, verdict="PASS", n_trials=10, stages=[]
    )
    cand = AlphaPipelineInput.from_gauntlet(
        "alpha_g", gauntlet, good_scores(), economic_mechanism_present=True,
        capacity_acceptable=True, fragility_acceptable=True, walk_forward_passed=True,
        shadow_ready=True,
    )
    assert cand.cpcv_passed and cand.dsr_passed and cand.reality_check_passed
    result = ResearchOrchestrator(min_allocation_quality=60.0).run([cand])
    assert result.allocated == ["alpha_g"]


def test_orchestrator_research_halt_blocks_allocation() -> None:
    # A clean, allocation-ready candidate is held in shadow when research is halted.
    result = ResearchOrchestrator(min_allocation_quality=60.0).run(
        [passing_candidate("a")], false_discovery_rate=0.9
    )
    assert result.kill.halt
    assert result.allocated == []
    assert result.records[0].stage is PipelineStage.SHADOW
    assert "no new capital" in result.records[0].note
