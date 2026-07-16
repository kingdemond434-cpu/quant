"""Alpha governance gate and the research kill-switch (both fail-closed).

``alpha_governance_gate`` is the hard barrier into Stage 13.5: an alpha is REJECTED unless every
gate passes (CPCV, PBO, DSR, Reality Check, economic mechanism, capacity, fragility, walk-forward).
``ResearchGovernanceEngine`` protects *research* capital the way risk engines protect trading
capital: if overfitting / discovery quality / validation integrity degrade, it halts research.
"""

from __future__ import annotations

from libs.stage15.models import AlphaGovernanceVerdict, ResearchKillDecision


def alpha_governance_gate(
    *,
    cpcv_passed: bool,
    pbo_acceptable: bool,
    dsr_passed: bool,
    reality_check_passed: bool,
    economic_mechanism_present: bool,
    capacity_acceptable: bool,
    fragility_acceptable: bool,
    walk_forward_passed: bool,
) -> AlphaGovernanceVerdict:
    """Return ACCEPT/REJECT. An alpha may enter Stage 13.5 only if every gate passes."""
    gates = {
        "cpcv": cpcv_passed,
        "pbo": pbo_acceptable,
        "dsr": dsr_passed,
        "reality_check": reality_check_passed,
        "economic_mechanism": economic_mechanism_present,
        "capacity": capacity_acceptable,
        "fragility": fragility_acceptable,
        "walk_forward": walk_forward_passed,
    }
    rejected_reasons = [f"{name} failed" for name, ok in gates.items() if not ok]
    return AlphaGovernanceVerdict(
        accepted=not rejected_reasons, gates=gates, rejected_reasons=rejected_reasons
    )


class ResearchGovernanceEngine:
    """The research kill-switch: halts research if discovery integrity degrades (fail-closed)."""

    def __init__(
        self,
        *,
        max_false_discovery_rate: float = 0.10,
        min_validation_pass_rate: float = 0.02,
        min_discovery_quality: float = 40.0,
        max_decay_rate: float = 0.50,
    ) -> None:
        self.max_false_discovery_rate = max_false_discovery_rate
        self.min_validation_pass_rate = min_validation_pass_rate
        self.min_discovery_quality = min_discovery_quality
        self.max_decay_rate = max_decay_rate

    def evaluate(
        self,
        *,
        false_discovery_rate: float,
        validation_pass_rate: float,
        discovery_quality: float,
        decay_rate: float,
    ) -> ResearchKillDecision:
        reasons: list[str] = []
        if false_discovery_rate > self.max_false_discovery_rate:
            reasons.append(
                f"FDR {false_discovery_rate:.2f} > {self.max_false_discovery_rate}"
            )
        if validation_pass_rate < self.min_validation_pass_rate:
            reasons.append(
                f"validation pass rate {validation_pass_rate:.3f} < {self.min_validation_pass_rate}"
            )
        if discovery_quality < self.min_discovery_quality:
            reasons.append(
                f"discovery quality {discovery_quality:.1f} < {self.min_discovery_quality}"
            )
        if decay_rate > self.max_decay_rate:
            reasons.append(f"decay rate {decay_rate:.2f} > {self.max_decay_rate}")
        return ResearchKillDecision(halt=bool(reasons), reasons=reasons)
