"""Research ROI Monitor — learn where research effort actually yields validated alpha.

Measures productivity by family (tested, rejected, validation pass rate, survivors, survivor rate)
straight from the durable candidate ledger, and recommends allocating future effort toward the
highest validated-alpha yield. Success is validated survivors, not backtests run — this monitor
makes that measurable and is honest when yield is zero everywhere.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import CandidateStatus

_REACHED_VALIDATION = {
    CandidateStatus.SHADOW.value, CandidateStatus.PAPER.value, CandidateStatus.REGISTRY.value,
}


class FamilyYield(BaseModel):
    model_config = ConfigDict(frozen=True)

    family: str
    tested: int
    rejected: int
    reached_validation: int
    survivors: int
    survivor_rate: float


class ResearchROIReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_tested: int
    total_survivors: int
    validation_pass_rate: float          # reached shadow+ / tested
    survivor_rate: float                 # registry / tested
    by_family: list[FamilyYield] = Field(default_factory=list)
    recommended_focus: list[str] = Field(default_factory=list)


class ResearchROIMonitor:
    """Computes per-family research yield and the effort-allocation recommendation."""

    def __init__(self, store: CandidateStore) -> None:
        self.store = store

    def report(self) -> ResearchROIReport:
        records = self.store.all()
        total = len(records)
        agg: dict[str, dict[str, int]] = {}
        for r in records:
            f = agg.setdefault(r.family, {"tested": 0, "rejected": 0, "reached": 0, "survivors": 0})
            f["tested"] += 1
            if r.status is CandidateStatus.REJECTED:
                f["rejected"] += 1
            if r.status.value in _REACHED_VALIDATION:
                f["reached"] += 1
            if r.survived:
                f["survivors"] += 1

        families = [
            FamilyYield(
                family=name, tested=d["tested"], rejected=d["rejected"],
                reached_validation=d["reached"], survivors=d["survivors"],
                survivor_rate=d["survivors"] / d["tested"] if d["tested"] else 0.0,
            )
            for name, d in agg.items()
        ]
        survivors = sum(f.survivors for f in families)
        reached = sum(f.reached_validation for f in families)
        # Allocate future effort toward the highest-yield families (survivor rate, then reach).
        ranked = sorted(families, key=lambda f: (f.survivor_rate, f.reached_validation),
                        reverse=True)
        return ResearchROIReport(
            total_tested=total, total_survivors=survivors,
            validation_pass_rate=reached / total if total else 0.0,
            survivor_rate=survivors / total if total else 0.0,
            by_family=ranked, recommended_focus=[f.family for f in ranked[:5]],
        )
