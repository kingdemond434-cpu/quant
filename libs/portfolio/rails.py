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
    Rail("sleeve_share_cap", "cap", "heat_policy.per_sleeve_bounds (MAX_SLEEVE_HEAT_SHARE)",
         "measure_bounds"),
    Rail("family_cap", "cap", "heat_policy.enforce_family_cap (MAX_FAMILY_HEAT_SHARE)",
         "measure_bounds"),
    Rail("hard_ceiling", "cap", "heat_policy.resolve HEAT_HARD_CEILING 30%", "measure_ceiling"),
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
