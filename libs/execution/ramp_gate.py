"""§6 numeric ramp gate: size steps up on arithmetic, never on confidence.

The spec's wording is "no discretionary language", and that is the entire design constraint. A
size increase is permitted only when ALL FIVE hold over the trailing 8 weeks:

  (a) realized cost <= 1.25x modeled
  (b) live Sharpe >= 0.6x the same-period backtest
  (c) slippage KS-test p > 0.05 vs model
  (d) drill pass-streak >= 8 weeks
  (e) calibration MAE falling 2 consecutive months

Down-steps are unlimited and immediate, and that asymmetry is deliberate: the cost of an
unnecessary down-step is a little foregone return, the cost of a delayed one is the book.

The gate is FAIL-CLOSED on missing evidence. Every condition reads its input with a default that
fails, so an absent metric blocks the step-up rather than waving it through -- an evidence
pipeline that breaks silently must not read as five satisfied conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# the size ladder, as fractions of the stage's authorized capital. Steps are multiplicative-ish
# but enumerated rather than computed so "what size are we allowed" is always a lookup, never
# an expression someone can re-derive differently in another file.
SIZE_STEPS: tuple[float, ...] = (0.10, 0.20, 0.35, 0.55, 0.80, 1.00)

COST_RATIO_MAX = 1.25
SHARPE_RATIO_MIN = 0.6
KS_P_MIN = 0.05
DRILL_STREAK_WEEKS_MIN = 8
MAE_FALLING_MONTHS_MIN = 2
TRAILING_WEEKS_REQUIRED = 8.0


def _f(evidence: dict[str, Any], key: str, fail_default: float) -> float:
    """Read a float, defaulting to a value that FAILS its condition. Never raises."""
    try:
        v = evidence.get(key)
        return fail_default if v is None else float(v)
    except (TypeError, ValueError):
        return fail_default


@dataclass(frozen=True)
class RampDecision:
    may_step_up: bool
    checks: dict[str, bool]
    reason: str

    @property
    def failed(self) -> list[str]:
        return sorted(k for k, ok in self.checks.items() if not ok)


def step_up_conditions(evidence: dict[str, Any]) -> dict[str, bool]:
    """The five spec conditions, each independently evaluable and each fail-closed."""
    return {
        "window_ge_8_weeks": _f(evidence, "trailing_weeks", 0.0) >= TRAILING_WEEKS_REQUIRED,
        "a_cost_le_1_25x": _f(evidence, "cost_ratio", 999.0) <= COST_RATIO_MAX,
        "b_live_sharpe_ge_0_6x_backtest": (
            _f(evidence, "live_sharpe", -999.0)
            >= SHARPE_RATIO_MIN * _f(evidence, "backtest_sharpe", 999.0)
        ),
        "c_slippage_ks_p_gt_0_05": _f(evidence, "slippage_ks_p", 0.0) > KS_P_MIN,
        "d_drill_streak_ge_8w": _f(evidence, "drill_pass_streak_weeks", 0.0)
        >= DRILL_STREAK_WEEKS_MIN,
        "e_mae_falling_2_months": _f(evidence, "calibration_mae_falling_months", 0.0)
        >= MAE_FALLING_MONTHS_MIN,
    }


def may_step_up(evidence: dict[str, Any]) -> RampDecision:
    checks = step_up_conditions(evidence)
    ok = all(checks.values())
    failed = sorted(k for k, v in checks.items() if not v)
    return RampDecision(
        may_step_up=ok,
        checks=checks,
        reason="all ramp conditions met" if ok else f"blocked by: {', '.join(failed)}",
    )


def next_step(current: float, evidence: dict[str, Any]) -> tuple[float, str]:
    """The size fraction now authorized. Returns (fraction, why).

    Steps UP by at most one rung and only on a clean gate. An unrecognised current fraction
    snaps DOWN to the nearest authorized rung rather than up -- an unknown state is not a
    licence to grow.
    """
    decision = may_step_up(evidence)
    below = [s for s in SIZE_STEPS if s <= current + 1e-12]
    if not below:
        # BELOW the floor rung (a hand-edited state file, a fresh install, a partial write).
        # Snapping to the floor is a step UP in absolute terms, so it must not ALSO consume a
        # rung: returning here is what stops 0.01 becoming 0.20 in a single tick.
        return SIZE_STEPS[0], (f"size {current:.4f} is below the floor rung -- "
                               f"snapped to {SIZE_STEPS[0]:.2f}, no step this tick")
    idx = SIZE_STEPS.index(max(below))
    floor = SIZE_STEPS[idx]
    if floor < current - 1e-12:
        return floor, f"unrecognised size {current:.4f} -- snapped down to rung {floor:.2f}"
    if not decision.may_step_up:
        return floor, decision.reason
    if idx >= len(SIZE_STEPS) - 1:
        return floor, "already at the top rung"
    return SIZE_STEPS[idx + 1], "all ramp conditions met -- one rung up"


def step_down(current: float, reason: str) -> tuple[float, str]:
    """Immediate one-rung down-step. Never gated, never rate-limited, never refused."""
    below = [s for s in SIZE_STEPS if s < current - 1e-12]
    target = max(below) if below else 0.0
    return target, f"down-step to {target:.2f}: {reason}"
