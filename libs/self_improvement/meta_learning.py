"""Meta-learning engine — learn relationships; deploy NOTHING without the gauntlet.

Learns which regimes favour which alphas. Per the meta-learning governance directive, no learned
policy may be deployed automatically: an insight is ``deployable`` only after it passes CPCV,
PBO, DSR, and walk-forward validation (the verdicts are supplied by the validation layer).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.self_improvement.models import MetaInsight


def meta_learning_governance_gate(
    *, cpcv_pass: bool, dsr_pass: bool, pbo_pass: bool, walk_forward_pass: bool
) -> bool:
    """A learned relationship is deployable only if every validation gate passes."""
    return bool(cpcv_pass and dsr_pass and pbo_pass and walk_forward_pass)


class MetaLearningEngine:
    """Learns regime->alpha affinity as a non-deployable insight until governed."""

    def learn_regime_affinity(
        self, regime_labels: Sequence[str], returns_by_alpha: Mapping[str, np.ndarray]
    ) -> MetaInsight:
        regimes = sorted(set(regime_labels))
        labels = np.asarray(regime_labels)
        relationship: dict[str, dict[str, float]] = {}
        for alpha_id, returns in returns_by_alpha.items():
            arr = np.asarray(returns, dtype="float64")
            per_regime: dict[str, float] = {}
            for regime in regimes:
                mask = labels == regime
                per_regime[regime] = float(arr[mask].mean()) if mask.any() else 0.0
            relationship[alpha_id] = per_regime
        return MetaInsight(
            description="regime->alpha mean-return affinity",
            relationship=relationship,
            evidence={"n_observations": len(labels), "regimes": regimes},
            deployable=False,
        )

    def govern(
        self,
        insight: MetaInsight,
        *,
        cpcv_pass: bool,
        dsr_pass: bool,
        pbo_pass: bool,
        walk_forward_pass: bool,
    ) -> MetaInsight:
        """Return the insight with ``deployable`` set only if all gates pass."""
        deployable = meta_learning_governance_gate(
            cpcv_pass=cpcv_pass, dsr_pass=dsr_pass, pbo_pass=pbo_pass,
            walk_forward_pass=walk_forward_pass,
        )
        return insight.model_copy(update={"deployable": deployable})
