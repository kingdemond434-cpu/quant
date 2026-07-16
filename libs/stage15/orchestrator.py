"""Research orchestrator — the end-to-end live alpha pipeline.

Threads each candidate through: Discovery -> Validation -> Walk-Forward -> Shadow -> Paper ->
Allocation, gated by the alpha governance gate and overseen by the research kill-switch. It
consumes the verdicts/scores produced by the existing engines (gauntlet, walk-forward governance,
shadow deployment) — it does not re-implement them — and routes each alpha to the furthest stage it
has earned. Recommend-only: it never trades or allocates capital itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.stage15.audit import ResearchAudit
from libs.stage15.governance import ResearchGovernanceEngine, alpha_governance_gate
from libs.stage15.models import (
    AlphaScores,
    PipelineRecord,
    PipelineStage,
    ResearchPipelineResult,
)
from libs.stage15.scoring import alpha_quality_score
from libs.validation.gauntlet import GauntletResult


class AlphaPipelineInput(BaseModel):
    """One candidate's evaluated state, as produced by the discovery + validation engines."""

    model_config = ConfigDict(frozen=True)

    alpha_id: str
    scores: AlphaScores
    cpcv_passed: bool = False
    pbo_acceptable: bool = False
    dsr_passed: bool = False
    reality_check_passed: bool = False
    economic_mechanism_present: bool = False
    capacity_acceptable: bool = False
    fragility_acceptable: bool = False
    walk_forward_passed: bool = False
    shadow_ready: bool = False

    @classmethod
    def from_gauntlet(
        cls,
        alpha_id: str,
        gauntlet: GauntletResult,
        scores: AlphaScores,
        *,
        economic_mechanism_present: bool,
        capacity_acceptable: bool,
        fragility_acceptable: bool,
        walk_forward_passed: bool,
        shadow_ready: bool = False,
    ) -> AlphaPipelineInput:
        """Bridge a real gauntlet verdict into the pipeline (the gauntlet runs CPCV/PBO/DSR/SPA)."""
        passed = gauntlet.passed
        return cls(
            alpha_id=alpha_id, scores=scores,
            cpcv_passed=passed, pbo_acceptable=passed, dsr_passed=passed,
            reality_check_passed=passed,
            economic_mechanism_present=economic_mechanism_present,
            capacity_acceptable=capacity_acceptable,
            fragility_acceptable=fragility_acceptable,
            walk_forward_passed=walk_forward_passed, shadow_ready=shadow_ready,
        )


class ResearchOrchestrator:
    """Routes candidates through the live research pipeline under research governance."""

    def __init__(
        self,
        *,
        min_allocation_quality: float = 70.0,
        governance: ResearchGovernanceEngine | None = None,
        audit: ResearchAudit | None = None,
    ) -> None:
        self.min_allocation_quality = min_allocation_quality
        self.governance = governance or ResearchGovernanceEngine()
        self.audit = audit

    def run(
        self,
        candidates: Sequence[AlphaPipelineInput],
        *,
        false_discovery_rate: float = 0.0,
        validation_pass_rate: float = 1.0,
        discovery_quality: float = 100.0,
        decay_rate: float = 0.0,
    ) -> ResearchPipelineResult:
        kill = self.governance.evaluate(
            false_discovery_rate=false_discovery_rate,
            validation_pass_rate=validation_pass_rate,
            discovery_quality=discovery_quality, decay_rate=decay_rate,
        )

        records: list[PipelineRecord] = []
        allocated: list[str] = []
        rejected: list[str] = []
        for cand in candidates:
            quality = alpha_quality_score(cand.scores).score
            verdict = alpha_governance_gate(
                cpcv_passed=cand.cpcv_passed, pbo_acceptable=cand.pbo_acceptable,
                dsr_passed=cand.dsr_passed, reality_check_passed=cand.reality_check_passed,
                economic_mechanism_present=cand.economic_mechanism_present,
                capacity_acceptable=cand.capacity_acceptable,
                fragility_acceptable=cand.fragility_acceptable,
                walk_forward_passed=cand.walk_forward_passed,
            )
            if not verdict.accepted:
                stage, accepted, note = PipelineStage.REJECTED, False, ", ".join(
                    verdict.rejected_reasons
                )
                rejected.append(cand.alpha_id)
            elif kill.halt:
                # Validated, but research is halted -> hold in shadow, no new capital.
                stage, accepted, note = PipelineStage.SHADOW, True, "research halt: no new capital"
            elif not cand.shadow_ready:
                stage, accepted, note = PipelineStage.SHADOW, True, "awaiting shadow completion"
            elif quality < self.min_allocation_quality:
                stage, accepted, note = PipelineStage.PAPER, True, (
                    f"quality {quality:.1f} < {self.min_allocation_quality} -> paper trade"
                )
            else:
                stage, accepted, note = PipelineStage.ALLOCATION, True, "cleared for allocation"
                allocated.append(cand.alpha_id)
            records.append(
                PipelineRecord(
                    alpha_id=cand.alpha_id, stage=stage, quality_score=quality,
                    accepted=accepted, note=note,
                )
            )

        result = ResearchPipelineResult(
            records=records, allocated=allocated, rejected=rejected, kill=kill
        )
        if self.audit is not None:
            self.audit.record_pipeline(result)
        return result
