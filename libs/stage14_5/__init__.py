"""``libs.stage14_5`` — portfolio hedging, crisis alpha & exposure management.

Institutional protection of long-term geometric growth: alpha/factor/regime diversification, tail-
risk control, correlation-shock fragility, crisis alpha, and governed, lifecycle-managed hedges.
Never retail offsets; never cosmetic volatility reduction. Survival dominates return.

Reuses Architecture v1.0: ``libs.discovery`` (tail risk, regime diversification), ``libs.risk``
(crisis, CVaR/VaR), and ``libs.portfolio`` (Herfindahl concentration). No duplicate abstractions.
"""

from __future__ import annotations

from libs.stage14_5.concentration import ConcentrationEngine
from libs.stage14_5.correlation_shock import CorrelationShockEngine
from libs.stage14_5.crisis_alpha import CrisisAlphaEngine
from libs.stage14_5.errors import HedgeGovernanceError, Stage14_5Error
from libs.stage14_5.factor_exposure import FactorExposureEngine
from libs.stage14_5.hedging import (
    HedgeLifecycleEngine,
    PortfolioHedgingEngine,
    hedge_effectiveness_score,
    hedge_governance_gate,
)
from libs.stage14_5.models import (
    AlphaFamily,
    ConcentrationResult,
    CorrelationShockResult,
    CrisisAlphaResult,
    FactorExposureResult,
    Hedge,
    HedgeEffectiveness,
    HedgeGovernanceVerdict,
    HedgeLifecycleDecision,
    HedgeProposal,
    HedgeType,
    RegimeExposureResult,
    TailRiskResult,
)
from libs.stage14_5.regime_exposure import RegimeExposureEngine
from libs.stage14_5.tail_risk import PortfolioTailRiskEngine

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "HedgeType",
    "AlphaFamily",
    "FactorExposureResult",
    "TailRiskResult",
    "CorrelationShockResult",
    "ConcentrationResult",
    "RegimeExposureResult",
    "CrisisAlphaResult",
    "HedgeProposal",
    "HedgeEffectiveness",
    "HedgeGovernanceVerdict",
    "Hedge",
    "HedgeLifecycleDecision",
    # engines
    "FactorExposureEngine",
    "PortfolioTailRiskEngine",
    "CorrelationShockEngine",
    "ConcentrationEngine",
    "RegimeExposureEngine",
    "CrisisAlphaEngine",
    "PortfolioHedgingEngine",
    "HedgeLifecycleEngine",
    "hedge_governance_gate",
    "hedge_effectiveness_score",
    # errors
    "Stage14_5Error",
    "HedgeGovernanceError",
]
