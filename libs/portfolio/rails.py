"""Every mechanism that can reduce the desk's exposure, registered so each one can be billed.

    OpportunityCost(rail) = E[log W without rail] - E[log W with rail]

is the number the growth governance demands of every rail: a veto, a shrinkage, a cap, an
inertia threshold, a gate. `research/missed_growth.py` measures it from the desk's own ledgers
and writes the verdict; a rail that persistently COSTS growth is weakened within its declared
bounds (continuous rails) or queued for removal (binary ones). This file is only the register:
what the rails are, where they live, whether they may be tuned, and by how much.

BOUNDS ARE DECLARED, NOT DISCOVERED. A tunable rail's multiplier lives in
`data/rail_calibration.json` and is clipped to `[lo, hi]` on every read, so the calibration loop
can weaken a rail that is costing growth but can never switch it off or double it by drift.
Integrity rails (broker down, stale prices, margin anomaly, ruin in a sampled world) are
registered with `tunable=False`: they are the constraints the objective itself keeps.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
CALIBRATION = DESK / "data" / "rail_calibration.json"


@dataclass(frozen=True)
class Rail:
    name: str
    #: veto | gate | shrink | cap | inertia | integrity | mandate
    kind: str
    where: str
    #: name of the measurement in research/missed_growth.py
    measure: str
    tunable: bool = False
    lo: float = 1.0
    hi: float = 1.0
    #: what a multiplier BELOW 1 does to this rail ("weakens" it), for the reader
    weaken_means: str = ""
    #: WHICH WAY "WEAKER" IS for this rail's multiplier -- "down" for a shrink or an inertia
    #: (less of it applied), "up" for a CAP (more room allowed). The calibration loop walks a
    #: rail that costs growth toward looseness, and until 2026-09-07 it only knew how to walk
    #: DOWN, so a cap could not be made tunable at all: the walk would have TIGHTENED it every
    #: time it proved expensive, which is the opposite of the growth governance. Existing rails
    #: keep the default and behave exactly as before.
    weaken_dir: str = "down"


RAILS: tuple[Rail, ...] = (
    Rail("regime_hibernate", "veto", "gateway.regime_hibernate <- regime_monitor",
         "measure_veto"),
    Rail("state_gate", "gate", "gateway.state_allows", "measure_veto"),
    Rail("margin_guard", "integrity", "gateway.margin_ok", "measure_veto"),
    Rail("entry_inside_freeze_band", "integrity", "gateway.place_bracket freeze band",
         "measure_veto"),
    Rail("position_inertia", "inertia", "pf_allocator.no_trade", "measure_inertia",
         tunable=True, lo=0.5, hi=2.0,
         weaken_means="turnover is charged at a smaller multiple, so the book rebalances sooner"),
    Rail("state_shrinkage", "shrink", "robust_elog._posterior_mu k_state=40",
         "measure_shrinkage", tunable=True, lo=0.5, hi=2.0,
         weaken_means="k_state is smaller, so a state's own evidence moves the posterior more"),
    Rail("per_sleeve_bounds", "cap", "heat_policy.per_sleeve_bounds (drawdown leg)",
         "measure_bounds"),
    # THE TWO CAPS NOW RE-CERTIFY THEMSELVES (principal, 2026-09-07: "eventually even 60%
    # shouldn't be sacred -- let the cap continuously re-certify itself"). They were binary rails,
    # so a measured growth cost produced a review TASK and the constant stood until somebody read
    # it. They are now tunable in the loosening direction only, walked by `missed_growth` exactly
    # like every other tunable rail: only on a MEASURED opportunity cost, one STEP per pass, and
    # never in the tightening direction.
    #
    # THE BOUND ON THE BOUND IS WHAT KEEPS THIS A RE-CERTIFICATION AND NOT A REMOVAL. `hi` caps
    # how far evidence may loosen the cap -- 1.4x on the sleeve share (25% -> 35% of the book in
    # one name) and 1.25x on the family (60% -> 75% in one mechanism). A rail that can walk to
    # "no rail" is not a rail, and the desk has already measured that concentration past 60%
    # worsened its tail characteristics. `lo = 1.0` means neither can ever be walked TIGHTER by
    # this loop: strengthening a rail is a decision, not a side effect.
    Rail("sleeve_share_cap", "cap", "heat_policy.per_sleeve_bounds (MAX_SLEEVE_HEAT_SHARE)",
         "measure_bounds", tunable=True, lo=1.0, hi=1.4, weaken_dir="up",
         weaken_means="one sleeve may hold a larger share of the book before the cap trims it"),
    Rail("family_cap", "cap", "heat_policy.enforce_family_cap (MAX_FAMILY_HEAT_SHARE)",
         "measure_bounds", tunable=True, lo=1.0, hi=1.25, weaken_dir="up",
         weaken_means="one mechanism may hold a larger share of total heat before it is scaled"),
    # THE GROWTH CEILING. No longer the 30% constant (principal, 2026-09-07): it is
    # `heat_policy.measured_ceiling`'s reading of THIS pass's growth curve -- the highest heat
    # still within tolerance of the peak growth rate, never past the last heat sampled. It moves
    # every pass, in both directions, and the recorded constant is only what holds when the curve
    # cannot be read at all.
    Rail("hard_ceiling", "cap", "heat_policy.resolve <- measured_ceiling(growth curve)",
         "measure_ceiling"),
    # THE SURVIVAL CEILING, and it is INTEGRITY rather than a cap on purpose. `kelly_surface.
    # envelope` bounds heat where P(ruin) stops being zero, where P(drawdown > the principal's
    # 35% tolerance) leaves the CVaR fraction, where margin becomes infeasible or where capacity
    # runs out. It is billed like every other rail so the desk can see what survival costs in
    # growth -- but it carries no `tunable` band, because a rail that can be walked down when it
    # proves expensive is exactly the wrong shape for the one bar that keeps the account alive.
    Rail("survival_ceiling", "integrity",
         "heat_policy.resolve <- kelly_surface.envelope (ruin / drawdown / margin / capacity)",
         "measure_survival_ceiling"),
    # THE CEILING THAT COUNTS EFFECTIVE HEAT. `heat_policy.effective_ceiling` caps NOMINAL heat at
    # the heat the book's independent risk earns -- target * sqrt(N_eff / 2.26) with N_eff from
    # max(covariance, factor, tail) -- so four sleeves that are one hidden USD factor cannot buy
    # the room four independent bets would. It can never pull the book below the 20% floor, which
    # is why it is a cap on the UPSIDE band and not a de-risking mechanism.
    Rail("effective_heat_ceiling", "cap",
         "heat_policy.resolve/effective_ceiling: max(covariance, factor, tail) heat",
         "measure_effective_ceiling"),
    Rail("hazard_shrink", "shrink",
         "pf_allocator.apply_hazard_shrink <- drift_monitor hazard_by_sleeve",
         "measure_hazard_shrink", tunable=True, lo=0.5, hi=1.0,
         weaken_means="a smaller fraction of the hazard is applied, so a sleeve keeps more of "
                      "its posterior mean while the question resolves"),
    Rail("floor_mandate", "mandate", "heat_policy.resolve HEAT_TARGET 20% floor",
         "measure_floor"),
    Rail("proof_fallback", "gate", "gateway.allocator_book <- allocator_proof",
         "measure_proof"),
    Rail("authority_ramp", "shrink", "gateway.promoted_lot ramp (non-book sleeves only)",
         "measure_ramp"),
    Rail("fade", "shrink", "mt5desk.sizing.decay_factor", "measure_fade"),
    Rail("cost_stress", "gate", "validation only: 1.5x/2x cost in the gauntlet",
         "measure_cost_stress"),
    Rail("factor_k_floor", "cap", "independence._floor_by_factor", "measure_factor_floor"),
    Rail("ruin_guard", "integrity", "pf_allocator: book wiped out in a sampled world -> zero",
         "measure_ruin_guard"),
)

_CACHE: dict[str, Any] = {"mtime": None, "doc": {}}


def rail(name: str) -> Rail:
    for r in RAILS:
        if r.name == name:
            return r
    raise KeyError(name)


def calibration() -> dict[str, float]:
    try:
        m = CALIBRATION.stat().st_mtime
        if _CACHE["mtime"] != m:
            _CACHE["doc"] = json.loads(CALIBRATION.read_text("utf-8")).get("multipliers") or {}
            _CACHE["mtime"] = m
        return dict(_CACHE["doc"])
    except (OSError, ValueError):
        return {}


def rail_multiplier(name: str) -> float:
    """The calibrated multiplier for a tunable rail, clipped to its bounds; 1.0 otherwise."""
    try:
        r = rail(name)
    except KeyError:
        return 1.0
    if not r.tunable:
        return 1.0
    try:
        v = float(calibration().get(name, 1.0))
    except (TypeError, ValueError):
        return 1.0
    return float(min(r.hi, max(r.lo, v)))
