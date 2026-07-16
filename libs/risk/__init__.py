"""``libs.risk`` — the CRO authority in code.

Kelly sizing (fractional / Bayesian / adaptive), volatility targeting, risk budgeting, factor
caps, correlation controls, heat controls, the drawdown governor, tail risk (VaR/CVaR/gap/stress),
crisis controls, equity preservation, the dynamic global scalar, position-size synthesis, and the
mandatory risk gate. Risk overrides alpha — structurally.
"""

from __future__ import annotations

from libs.risk.config import (
    CorrelationLimits,
    CrisisConfig,
    DrawdownLadder,
    ExposureLimits,
    HeatLimits,
    KellyLimits,
    PreservationConfig,
    RiskConfig,
    TailLimits,
    VolConfig,
)
from libs.risk.correlation import (
    CorrelationResult,
    average_off_diagonal,
    check_correlation_limits,
    correlation_clusters,
    correlation_scalar,
    diversification_score,
    rolling_correlation,
    stressed_correlation,
)
from libs.risk.crisis import CrisisResponse, crisis_controller
from libs.risk.drawdown import DrawdownLevel, DrawdownResponse, compute_drawdown, drawdown_governor
from libs.risk.errors import RiskError, RiskGateError
from libs.risk.factor_caps import FactorExposureResult, check_factor_exposure
from libs.risk.gate import AccountState, OrderIntent, RiskDecision, risk_gate
from libs.risk.heat import HeatResult, PositionHeat, calculate_heat, check_heat_limits
from libs.risk.instruments import TIER1, TIER2, TIER3, Factor, get_factor, tier_of
from libs.risk.kelly import (
    AlphaStage,
    KellyScaling,
    adaptive_kelly_fraction,
    calculate_bayesian_kelly,
    calculate_kelly,
)
from libs.risk.preservation import (
    PreservationMode,
    PreservationResponse,
    equity_preservation_controller,
)
from libs.risk.risk_budget import (
    BudgetEnforcement,
    allocate_risk_budget,
    enforce_risk_budget,
    risk_contributions,
)
from libs.risk.scaling import GlobalScalar, global_risk_scalar
from libs.risk.sizing import PositionSizeResult, calculate_position_size
from libs.risk.tail import (
    StressScenario,
    StressTestResult,
    calculate_cvar,
    calculate_var,
    default_stress_scenarios,
    gap_through_stop_loss,
    stress_test_portfolio,
)
from libs.risk.vol_target import (
    adjust_for_volatility,
    ewma_volatility,
    realized_volatility,
    regime_adjusted_volatility,
    vol_target,
)

__all__ = [  # noqa: RUF022  # grouped by subsystem
    # config
    "RiskConfig", "KellyLimits", "VolConfig", "HeatLimits", "DrawdownLadder",
    "CorrelationLimits", "TailLimits", "CrisisConfig", "PreservationConfig", "ExposureLimits",
    # instruments / factors
    "Factor", "get_factor", "tier_of", "TIER1", "TIER2", "TIER3",
    # kelly
    "AlphaStage", "KellyScaling", "calculate_kelly", "calculate_bayesian_kelly",
    "adaptive_kelly_fraction",
    # vol targeting
    "realized_volatility", "ewma_volatility", "regime_adjusted_volatility", "vol_target",
    "adjust_for_volatility",
    # risk budgeting
    "risk_contributions", "allocate_risk_budget", "enforce_risk_budget", "BudgetEnforcement",
    # factor caps
    "check_factor_exposure", "FactorExposureResult",
    # correlation
    "rolling_correlation", "stressed_correlation", "correlation_clusters",
    "diversification_score", "average_off_diagonal", "correlation_scalar",
    "check_correlation_limits", "CorrelationResult",
    # heat
    "PositionHeat", "calculate_heat", "check_heat_limits", "HeatResult",
    # drawdown
    "compute_drawdown", "drawdown_governor", "DrawdownResponse", "DrawdownLevel",
    # tail
    "calculate_var", "calculate_cvar", "gap_through_stop_loss", "stress_test_portfolio",
    "StressScenario", "StressTestResult", "default_stress_scenarios",
    # crisis
    "crisis_controller", "CrisisResponse",
    # preservation
    "equity_preservation_controller", "PreservationResponse", "PreservationMode",
    # scaling / sizing
    "global_risk_scalar", "GlobalScalar", "calculate_position_size", "PositionSizeResult",
    # gate
    "risk_gate", "OrderIntent", "AccountState", "RiskDecision",
    # errors
    "RiskError", "RiskGateError",
]
