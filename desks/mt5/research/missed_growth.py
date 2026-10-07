"""The missed-growth ledger: what every rail cost, or saved, in forward log-wealth.

    OpportunityCost(rail) = E[log W without rail] - E[log W with rail]

THE ANTI-TIMID MECHANISM. Every veto, shrinkage, cap, gate and inertia threshold on the desk is
registered in `libs.portfolio.rails`; this measures each one from the ledgers the desk already
keeps and gives it a verdict:

    EARNS_ITS_PLACE   removing the rail would have cost robust forward E[log W]
    COSTS_GROWTH      the rail is reducing growth without proving itself
    NOT_BINDING       the rail did not fire in the window, so it cost nothing and saved nothing
    UNMEASURED        the ledger it needs does not exist on this host (said, never assumed)

A COSTS_GROWTH verdict on a TUNABLE rail moves its multiplier one step toward weaker inside the
rail's declared bounds (`data/rail_calibration.json`, read by the rail on its next pass); on a
binary rail it writes a `rail_review` task for the research queue. A rail is never strengthened
by this loop: the only direction the calibration moves on evidence is toward more growth, and a
rail that earns its place is left exactly as it is.

UNITS. Log-wealth per day, so vetoes (R avoided x heat per trade), inertia (turnover cost saved
minus growth forgone), curve gaps (growth at one heat minus another) and proof fallbacks
(dynamic minus baseline growth) are comparable and summable.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio.rails import CALIBRATION, RAILS, Rail, calibration  # noqa: E402

LEDGER = BASE / "data" / "missed_growth.jsonl"
OUT = BASE / "reports" / "MISSED_GROWTH.json"
ALLOC = BASE / "reports" / "pf_allocation.json"
PROOF = BASE / "reports" / "ALLOCATOR_PROOF.json"
FILTER_VALUE = BASE / "reports" / "FILTER_VALUE.json"
#: The counterfactual world's veto table. It carries the SAME field names FILTER_VALUE does
#: (n_vetoed_and_triggered, mean_avoided_r, filter_value_r, t, verdict), and it prices every
#: decision minute on ONE axis with the desk's own cost posterior rather than only the not-taken
#: brackets a replay could reach. So where both exist this one wins, and FILTER_VALUE stays the
#: fallback for a box that has not replayed yet.
COUNTERFACTUAL = BASE / "reports" / "COUNTERFACTUAL_WORLD.json"
STATE_ADM = BASE / "reports" / "STATE_ADMISSION.json"
EARNS, COSTS, NOT_BINDING, UNMEASURED = ("EARNS_ITS_PLACE", "COSTS_GROWTH", "NOT_BINDING",
                                         "UNMEASURED")
MIN_N = 10
STEP = 0.10


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _veto_evidence() -> dict:
    """The per-reason veto table the rails are judged on: the counterfactual world's VETO_ALPHA
    where it has measured a reason, FILTER_VALUE's row where it has not.

    WHY A MERGE AND NOT A SWAP. `counterfactual_markout` replays only the not-taken brackets it
    can reach; the counterfactual world prices every decision minute, both sides, against every
    alternative, on one axis. A reason the world has measured is therefore the better evidence --
    but a box that has not run the replay must not lose the veto verdicts it already had.
    """
    fv = _json(FILTER_VALUE)
    filters = dict(fv.get("filters") or {})
    arms = (((_json(COUNTERFACTUAL).get("alphas") or {}).get("VETO_ALPHA") or {})
            .get("arms") or {})
    for reason, row in arms.items():
        if not isinstance(row, dict) or row.get("n_vetoed_and_triggered") is None:
            continue
        filters[str(reason)] = {**row, "source": "COUNTERFACTUAL_WORLD.VETO_ALPHA",
                                "d_elog_per_veto": row.get("mean")}
    return {**fv, "filters": filters,
            "source": "FILTER_VALUE + COUNTERFACTUAL_WORLD.VETO_ALPHA"}


def _num(v: Any) -> float | None:
    """A finite float or None. A rail priced from a string, a NaN or a None is UNMEASURED, and
    saying so is the whole discipline: a rail that cannot be measured must not read as free."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _curve(alloc: dict) -> dict[float, float]:
    try:
        return {float(h): float(g) for h, g in (alloc.get("heat") or {}).get("curve") or []}
    except (TypeError, ValueError):
        return {}


def _growth_at(curve: dict[float, float], heat: float) -> float | None:
    if not curve:
        return None
    h = min(curve, key=lambda x: abs(x - heat))
    return curve[h] if abs(h - heat) <= 0.05 else None


# --------------------------------------------------------------------------- measurements
def measure_veto(r, alloc: dict, fv: dict) -> dict[str, Any]:
    row = (fv.get("filters") or {}).get(r.name)
    if not row:
        return {"verdict": UNMEASURED, "why": "no replayed vetoes for this reason yet"}
    n = int(row.get("n_vetoed_and_triggered", 0))
    if n == 0:
        return {"verdict": NOT_BINDING, "n": 0}
    # R avoided per vetoed trade x the heat one trade carries = log-wealth saved per veto.
    q = float(np.mean(list((alloc.get("book") or {}).values()) or [0.0]))
    per_veto = float(row.get("mean_avoided_r", 0.0)) * q
    t = row.get("t")
    verdict = (EARNS if (row.get("verdict") == "EARNS_ITS_PLACE") else
               (COSTS if row.get("verdict") == "COSTS_EDGE" else UNMEASURED))
    return {"verdict": verdict, "n": n, "value_logw_per_veto": round(per_veto, 6),
            "avoided_r_total": row.get("filter_value_r"), "t": t}


def measure_inertia(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    nt = alloc.get("no_trade") or {}
    if not nt:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    cost = float(nt.get("cost", 0.0))
    benefit = float(nt.get("benefit_over_horizon", 0.0))
    horizon = float(nt.get("horizon_days", 1.0)) or 1.0
    if nt.get("verdict") == "REBALANCE":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    # Holding saved the turnover cost and forwent the growth: positive when the rail earned.
    return {"verdict": "SAMPLE", "value_logw_per_day": round((cost - benefit) / horizon, 8),
            "sample": True}


def measure_shrinkage(r, _alloc: dict, _fv: dict) -> dict[str, Any]:
    adm = _json(STATE_ADM)
    verdicts = adm.get("verdicts") or {}
    if not verdicts:
        return {"verdict": UNMEASURED, "why": "no STATE_ADMISSION.json"}
    admitted = {k: v for k, v in verdicts.items() if str(v.get("verdict", "")).startswith("ADMIT")}
    buried = [k for k, v in verdicts.items() if v.get("verdict") == "GRAVEYARD"]
    return {"verdict": (EARNS if admitted else NOT_BINDING),
            "admitted": {k: v.get("t_deflated", v.get("t")) for k, v in admitted.items()},
            "buried": buried,
            "why": "shrinkage is judged by the admission gauntlet: an admitted dimension "
                   "improved out-of-sample likelihood at k_state=40; a buried one is not used"}


def measure_bounds(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    fill = alloc.get("floor_fill") or {}
    if not alloc:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    relaxed = fill.get("relaxed")
    mine = {"per_sleeve_bounds": "drawdown_bound", "sleeve_share_cap": "share_cap",
            "family_cap": "family_cap"}[r.name]
    if not fill.get("needed"):
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    if relaxed == mine or (relaxed == "proportional" and mine == "share_cap"):
        return {"verdict": "SAMPLE", "bound_when_filled": True,
                "value_logw_per_day": -abs(float(fill.get("growth_gap", 0.0))), "sample": True,
                "why": "the floor could not be funded until this bound was relaxed"}
    return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}


def measure_ceiling(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    heat = alloc.get("heat") or {}
    if not heat:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if heat.get("binding") != "ceiling":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    curve = _curve(alloc)
    g_free = _growth_at(curve, float(heat.get("free_optimum", 0.0)))
    g_cap = _growth_at(curve, float(heat.get("hard_ceiling", 0.0)))
    if g_free is None or g_cap is None:
        return {"verdict": UNMEASURED, "why": "curve does not cover the free optimum"}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(g_cap - g_free, 8), "sample": True}


def measure_survival_ceiling(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    """What survival cost in growth: the curve at the survival bar against what growth wanted.

    THIS RAIL IS BILLED AND NEVER WALKED DOWN, and the asymmetry is deliberate. Every tunable
    rail on this desk is walked toward looseness when its ledger shows it persistently costing
    forward E[log W]; that is the growth governance working as designed. A survival bar must not
    be in that population: the whole point of it is to be expensive in the worlds where being
    cheap would end the account, so "it cost growth again this month" is the bar doing its job
    rather than evidence against it. What the number IS for is the research agenda -- a survival
    ceiling that costs a lot of growth is the strongest possible statement that the book needs
    independent breadth, because breadth is the only thing that moves this bar outward.
    """
    heat = alloc.get("heat") or {}
    if not heat:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if heat.get("binding") != "survival_ceiling":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    surv = heat.get("envelope", {}).get("survival_ceiling")
    if not isinstance(surv, (int, float)):
        return {"verdict": UNMEASURED, "why": "the pass bound on survival without recording it"}
    curve = _curve(alloc)
    wanted = max(float(heat.get("free_optimum", 0.0)), float(heat.get("state_optimum", 0.0)))
    g_want = _growth_at(curve, min(wanted, float(heat.get("hard_ceiling", 0.30))))
    g_cap = _growth_at(curve, float(surv))
    if g_want is None or g_cap is None:
        return {"verdict": UNMEASURED, "why": "curve does not cover the survival bar"}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(g_cap - g_want, 8), "sample": True}


def measure_effective_ceiling(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    """What the four-heat ceiling cost: growth at the earned cap vs growth at what was wanted.

    `heat_policy.effective_ceiling` caps NOMINAL heat at target * sqrt(N_eff / 2.26), N_eff from
    max(covariance, factor, tail). It binds only ABOVE the floor, so a pass that ran the floor
    anyway paid nothing and says NOT_BINDING rather than a silent zero.
    """
    heat = alloc.get("heat") or {}
    if not heat:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if heat.get("binding") != "effective_ceiling":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    curve = _curve(alloc)
    # What growth WANTED: the free optimum, or the state curve's argmax when that was higher.
    wanted = min(max(float(heat.get("free_optimum", 0.0)),
                     float(heat.get("state_optimum", 0.0))),
                 float(heat.get("hard_ceiling", 0.30)))
    g_want = _growth_at(curve, wanted)
    g_cap = _growth_at(curve, float(heat.get("effective_ceiling", 0.0)))
    if g_want is None or g_cap is None:
        return {"verdict": UNMEASURED, "why": "curve does not cover the wanted heat"}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(g_cap - g_want, 8), "sample": True}


def measure_floor(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    heat = alloc.get("heat") or {}
    if not heat:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if heat.get("binding") != "mandate":
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    curve = _curve(alloc)
    g_free = _growth_at(curve, float(heat.get("free_optimum", 0.0)))
    g_floor = _growth_at(curve, float(heat.get("floor", 0.0)))
    if g_free is None or g_floor is None:
        return {"verdict": UNMEASURED, "why": "curve does not cover the free optimum"}
    # The mandate forces heat ABOVE the optimum: positive when the curve's flat top makes that
    # free, negative when it costs. Reported, never tuned: it is the principal's order.
    return {"verdict": "SAMPLE", "value_logw_per_day": round(g_floor - g_free, 8),
            "sample": True, "principal_order": True}


def measure_proof(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    proof = alloc.get("proof") or {}
    scores = proof.get("scores") or {}
    if not proof:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if proof.get("passed"):
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True}
    dyn = scores.get("dynamic")
    best = scores.get(str(proof.get("best_baseline")))
    if dyn is None or best is None:
        return {"verdict": UNMEASURED, "why": "proof scores not carried on the artifact"}
    # The floor was sized with the baseline: the rail cost (dynamic - baseline) if the dynamic
    # book was genuinely better and only missed the margin, and saved the reverse.
    return {"verdict": "SAMPLE", "value_logw_per_day": round(float(best) - float(dyn), 8),
            "sample": True}


def measure_ramp(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": UNMEASURED,
            "why": "needs the live ledger's deployed fractions per sleeve (box only); the ramp "
                   "no longer applies to allocator-book sleeves"}


def measure_fade(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": UNMEASURED, "why": "needs live fills of faded vs unfaded sleeves (box)"}


def measure_cost_stress(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0,
            "why": "stressed costs are validation-only; live allocation charges the measured "
                   "per-trade cost (SleeveEvidence.cost_r) with the world's cost uncertainty draw"}


def measure_factor_floor(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    return {"verdict": UNMEASURED, "why": "needs the live ledger's factor exposures (box)"}


def measure_hazard_shrink(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    """The PRE-RETIREMENT SHRINK: the book scored with the hazard tilt against without it.

        "allocation changes BEFORE the formal retirement threshold"      -- the principal

    `drift_monitor.hazard_by_sleeve` publishes P(edge breaks next horizon | history) per sleeve
    into reports/DRIFT.json, and the allocator shrinks a sleeve's posterior mean by (1 - hazard)
    before any retirement rule fires. That is a RAIL by this desk's definition -- a mechanism
    that reduces exposure -- so it is billed like every other one: growth of the book WITH the
    tilt minus growth WITHOUT, on the same sampled worlds, in log-wealth per day.

    THE ONLY HONEST WAY TO BILL IT. Scoring the two books on the same world population at the
    same total heat is the comparison in which the difference is the TILT and not the sizing;
    anything else would charge the shrink for a heat change it did not make. Until the allocator
    writes that pair the rail is UNMEASURED with the exact field names it needs -- a shrink that
    cannot be measured must not read as free.

    A SHRINK THAT DID NOT FIRE COST NOTHING. When no sleeve carried a hazard above the tilt's
    line the rail is NOT_BINDING, which is a real zero and not a missing measurement.

    NOT YET REGISTERED. `run()` bills the rails in `libs.portfolio.rails.RAILS`, and the tilt's
    Rail entry lands with the allocator patch that applies it -- the measurement is here first so
    the mechanism cannot reach the book ahead of the ledger that bills it, which is the order
    every other rail on this desk was built in.
    """
    hs = alloc.get("hazard_shrink") or {}
    if not alloc:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if not hs:
        return {"verdict": UNMEASURED,
                "why": ("pf_allocation.json carries no hazard_shrink block; needs "
                        "hazard_shrink.growth_with and hazard_shrink.growth_without (mean log "
                        "per day of the same book on the same sampled worlds, with and without "
                        "the (1 - hazard) tilt) plus hazard_shrink.applied {sleeve: hazard}")}
    applied = hs.get("applied") or {}
    if not applied:
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True,
                "why": "no sleeve carried a hazard above the tilt's line this pass"}
    with_, without = _num(hs.get("growth_with")), _num(hs.get("growth_without"))
    if with_ is None or without is None:
        return {"verdict": UNMEASURED, "n_shrunk": len(applied),
                "why": ("hazard_shrink names the shrunk sleeves but carries no with/without "
                        "growth pair to price them")}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(with_ - without, 8), "sample": True,
            "n_shrunk": len(applied),
            "max_hazard": max((_num(v) or 0.0) for v in applied.values()),
            "why": "growth of the tilted book minus the untilted one, same worlds, same heat"}


def measure_decay_posterior(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    """The PER-SLEEVE decay haircut against the blanket, on the same worlds and the same book.

    `pf_allocator.apply_decay_posterior` hands each sleeve the drift monitor's hazard as its own
    `decay_prob_i`, capped at the blanket 30%, instead of tilting its posterior mean post hoc.
    The allocator scores the FUNDED book on its own worlds (`growth_with`) and on a population
    drawn identically except that every sleeve carries the blanket (`growth_without`); the
    difference is what the per-sleeve posterior is worth in log-wealth per day. No sleeve
    relieved this pass is a real zero, not a missing measurement.
    """
    dp = alloc.get("decay_posterior") or {}
    if not alloc:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if not dp:
        return {"verdict": UNMEASURED,
                "why": ("pf_allocation.json carries no decay_posterior block; needs "
                        "decay_posterior.growth_with and .growth_without (mean log per day of "
                        "the same book, same worlds, per-sleeve decay vs the blanket) plus "
                        ".by_sleeve {sleeve: {hazard, decay_prob_i}}")}
    if str(dp.get("mode") or "") != "decay_posterior" or not int(dp.get("n_from_hazard") or 0):
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True,
                "why": (f"mode={dp.get('mode')!r}, {int(dp.get('n_from_hazard') or 0)} sleeve(s) "
                        "carried a measured hazard: every sleeve paid the blanket this pass")}
    with_, without = _num(dp.get("growth_with")), _num(dp.get("growth_without"))
    if with_ is None or without is None:
        return {"verdict": UNMEASURED, "n_relieved": int(dp.get("n_from_hazard") or 0),
                "why": "decay_posterior names the relieved sleeves but carries no with/without "
                       "growth pair to price them"}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(with_ - without, 8), "sample": True,
            "n_relieved": int(dp.get("n_from_hazard") or 0),
            "blanket": dp.get("blanket"),
            "why": "growth of the funded book under per-sleeve decay minus under the blanket, "
                   "same book, same worlds"}


def measure_explore(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    """What lending a slice of the book to ambiguous candidates cost, or earned, this pass.

    `admission.explore` is the Thompson draw inside the admission margin: candidates whose
    dE[log W] sat inside the noise margin, funded from within the book's total. The allocator
    scores the explored book and the un-explored one on the same worlds; the difference is the
    rail's own line. A pass that lent nothing (no ambiguous candidate, every draw negative, or a
    funding rule that could not be satisfied) is NOT_BINDING with the reason the block gives.
    """
    ex = (alloc.get("admission") or {}).get("explore") or {}
    if not alloc:
        return {"verdict": UNMEASURED, "why": "no allocator pass on this host"}
    if not ex:
        return {"verdict": UNMEASURED,
                "why": ("pf_allocation.json carries no admission.explore block; needs "
                        "explore.status, explore.applied, explore.growth_with and "
                        "explore.growth_without")}
    if str(ex.get("status") or "") != "FUNDED" or not ex.get("applied"):
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True,
                "why": str(ex.get("why") or "no exploration heat was lent this pass")}
    with_, without = _num(ex.get("growth_with")), _num(ex.get("growth_without"))
    if with_ is None or without is None:
        return {"verdict": UNMEASURED, "n_explored": len(ex.get("band") or {}),
                "why": "explore was applied but carries no with/without growth pair"}
    return {"verdict": "SAMPLE", "value_logw_per_day": round(with_ - without, 8), "sample": True,
            "n_explored": len(ex.get("band") or {}),
            "explore_heat_total": ex.get("explore_heat_total"),
            "why": "growth of the explored book minus the un-explored one, same worlds, same "
                   "total heat"}


def measure_ruin_guard(r, alloc: dict, _fv: dict) -> dict[str, Any]:
    note = str((alloc.get("growth") or {}).get("annual_growth_pct", ""))
    heat = alloc.get("heat") or {}
    if heat.get("binding") == "catastrophe":
        return {"verdict": "SAMPLE", "value_logw_per_day": 0.0, "fired": True, "sample": True,
                "why": "the objective's own constraint; measured, never tuned"}
    return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True, "note": note}


def measure_causal_invariance(r: Any, _alloc: dict[str, Any],
                              _fv: dict[str, Any]) -> dict[str, Any]:
    """What the invariance gate's DEPRIORITISATION costs, in candidates delayed (Tier-1 B16).

    THE RAIL, PRECISELY. `research/causal_invariance.py` judges whether a cell's effect survives
    a change of session, year and volatility regime; `miner_candidate_compiler.expand_axes` sorts
    a NON_INVARIANT mechanism's cells one step later in the queue and DROPS NOTHING. So this rail
    cannot destroy a candidate, and the only thing it can cost is time-to-verdict.

    NOT_BINDING IS A REAL ZERO HERE, and it is the common case: a pass where no judged mechanism
    came back NON_INVARIANT reordered nothing and cost nothing.

    WHAT IT WOULD TAKE TO PRICE THE DELAY IN LOG-WEALTH, said rather than invented. The value is
    (probability a delayed cell would have certified) x (dE[log W] it would have carried) x (the
    delay in days), and the desk has the first two only after the delayed cells have been judged:
    the registry must carry certification outcomes tagged with the invariance verdict they were
    deprioritised under. Until that population exists this is UNMEASURED with the count of what
    was delayed, because an invented number here would make a rail that reorders the whole
    research queue look free.

    THE OTHER SIDE IS ALSO MEASURED, and it is the reason the rail is expected to EARN its place:
    the same artifact carries how many judged cells were INVARIANT, and those are the cells the
    reordering moves forward. A rail that only ever delayed would be a brake.
    """
    doc = _json(BASE / "reports" / "CAUSAL_INVARIANCE.json") or {}
    if not doc:
        return {"verdict": UNMEASURED,
                "why": ("no reports/CAUSAL_INVARIANCE.json on this host: the causal organ has "
                        "not judged a cell, so nothing has been deprioritised")}
    _c = doc.get("counts")
    counts: dict[str, Any] = dict(_c) if isinstance(_c, dict) else {}
    delayed = int(counts.get("NON_INVARIANT") or 0)
    advanced = int(counts.get("INVARIANT") or 0)
    if not delayed:
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True,
                "n_judged": int(doc.get("n_cells") or 0), "n_advanced": advanced,
                "why": (f"{doc.get('n_cells')} cell(s) judged and none came back NON_INVARIANT: "
                        f"the queue was not reordered this pass")}
    return {"verdict": UNMEASURED, "n_delayed": delayed, "n_advanced": advanced,
            "n_judged": int(doc.get("n_cells") or 0),
            "why": (f"{delayed} mechanism(s) sort one step later and {advanced} sort earlier; "
                    f"pricing the delay needs certification outcomes tagged with the invariance "
                    f"verdict the cell was queued under (registry field "
                    f"`causal_invariance.verdict` on a judged candidate), which no cell carries "
                    f"yet. No candidate was refused: the rail can only cost queue position.")}


def measure_tier_s_block(r: Any, alloc: dict[str, Any],
                         _fv: dict[str, Any]) -> dict[str, Any]:
    """What the Tier S promotion door withheld, priced by the forward expectancy it carried.

    Each withheld row's clock had a forward mean R (`exp_r`) when it was refused. A door whose
    refusals carry POSITIVE forward R on average is costing growth (those were paying clocks);
    one whose refusals carry NEGATIVE R is earning its place. Per refusal, log-wealth forgone is
    mean R x the heat one sleeve carries in the current book -- the same unit `measure_veto`
    uses. Fewer than ten priced refusals is UNMEASURED, said with the count."""
    rows: list[dict[str, Any]] = []
    try:
        for line in (BASE / "data" / "tier_s" / "promotion_blocks.jsonl").read_text(
                "utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (OSError, ValueError):
        rows = []
    if not rows:
        return {"verdict": NOT_BINDING, "n": 0, "value_logw_per_day": 0.0,
                "why": "the Tier S door has withheld no promotion on this host"}
    by: dict[str, int] = {}
    for x in rows:
        by[str(x.get("reason"))] = by.get(str(x.get("reason")), 0) + 1
    q = float(np.mean(list((alloc.get("book") or {}).values()) or [0.0]))
    door_error = _bill_door_error(rows, q)
    rs = [float(x["exp_r"]) for x in rows if isinstance(x.get("exp_r"), (int, float))]
    if len(rs) < 10:
        return {"verdict": UNMEASURED, "n": len(rows), "by_reason": by,
                "door_error": door_error,
                "why": f"{len(rs)} withheld row(s) carry a forward R; ten are needed to price"}
    m = float(np.mean(rs))
    return {"verdict": COSTS if m > 0 else EARNS, "n": len(rows), "by_reason": by,
            "door_error": door_error,
            "mean_withheld_r": round(m, 5), "value_logw_per_veto": round(-m * q, 6)}


def _bill_door_error(rows: list[dict[str, Any]], heat_per_sleeve: float) -> dict[str, Any]:
    """THE COST OF FAILING CLOSED, BILLED PER INPUT (gap E, 2026-09-30).

    The door withholds every new row while one of its verdict inputs is absent or stale
    (`DOOR_ERROR`, never relaxed). On a box's first adoption that is EVERY row until tier_s writes
    its verdict files. Each such withhold is a ledger line here: the input it names, the window
    it was missing over (first/last withhold, the input's own last stamp) and the forward R the
    withheld clocks carried, priced like every door refusal (mean R x one sleeve's heat)."""
    lines: dict[str, dict[str, Any]] = {}
    for x in rows:
        if str(x.get("reason")) != "DOOR_ERROR":
            continue
        de = x.get("door_error") if isinstance(x.get("door_error"), dict) else {}
        key = str(de.get("input") or "unattributed")
        ln = lines.setdefault(key, {"input": key, "input_file": de.get("input_file"),
                                    "n_withheld": 0, "names": [], "first_withheld": None,
                                    "last_withheld": None, "input_last_stamp": None,
                                    "input_state": None, "window_start": None,
                                    "sum_withheld_r": 0.0, "n_priced": 0})
        ln["n_withheld"] += 1
        if x.get("name") and x["name"] not in ln["names"] and len(ln["names"]) < 50:
            ln["names"].append(x["name"])
        at = x.get("at")
        if at and (ln["first_withheld"] is None or str(at) < ln["first_withheld"]):
            ln["first_withheld"] = str(at)
        if at and (ln["last_withheld"] is None or str(at) > ln["last_withheld"]):
            ln["last_withheld"] = str(at)
        ws = de.get("window_start")
        if ws and (ln["window_start"] is None or str(ws) < ln["window_start"]):
            ln["window_start"] = str(ws)
        ln["input_last_stamp"] = de.get("last_stamp") or ln["input_last_stamp"]
        ln["input_state"] = de.get("state") or ln["input_state"]
        if isinstance(x.get("exp_r"), (int, float)):
            ln["sum_withheld_r"] += float(x["exp_r"])
            ln["n_priced"] += 1
    for ln in lines.values():
        ln["window"] = {"from": ln["window_start"] or ln["first_withheld"],
                        "to": ln["last_withheld"]}
        ln["logw_forgone"] = round(max(0.0, ln["sum_withheld_r"]) * heat_per_sleeve, 8)
        ln["sum_withheld_r"] = round(ln["sum_withheld_r"], 6)
        ln["verdict"] = (UNMEASURED if ln["n_priced"] == 0
                         else COSTS if ln["sum_withheld_r"] > 0 else EARNS)
    return {"n": sum(v["n_withheld"] for v in lines.values()),
            "lines": sorted(lines.values(), key=lambda v: -v["n_withheld"]),
            "rule": "every DOOR_ERROR withhold billed to the input it names, over the window "
                    "that input was absent/stale; fail-closed stands, its cost is a number"}
#: E8 gold's intents journal: the duplicate guard journals each block as RAIL_BLOCKED there.
E8_INTENTS = BASE / "data" / "e8_gold_intents.jsonl"


def measure_e8_unowned_block(r: Any, _alloc: dict[str, Any],
                             _fv: dict[str, Any]) -> dict[str, Any]:
    """What E8 gold's duplicate guard stood aside from, read from the lane's own journal.

    Each RAIL_BLOCKED row is a dropped bracket leg NOT re-sent because an unowned same-side
    position opened after the failed send may have been that send. If it was, the block saved a
    doubled position; if not, it forwent the leg's certified risk (`missed_growth_risk_usd`).
    Which one it was is not observable from the journal, so the verdict stays UNMEASURED with
    the count and the undeployed risk published. That figure is the risk the blocked legs would
    have carried, NOT a bound on the growth forgone: a leg that ran to target earns its R:R
    multiple of that risk, so the forgone profit can exceed it several times over."""
    rows: list[dict[str, Any]] = []
    try:
        for line in E8_INTENTS.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict) and row.get("status") == "RAIL_BLOCKED" \
                    and row.get("rail") == r.name:
                rows.append(row)
    except (OSError, ValueError):
        return {"verdict": UNMEASURED, "why": "the E8 intents journal is missing or unreadable"}
    if not rows:
        return {"verdict": NOT_BINDING, "n": 0,
                "why": "the guard has not blocked a re-send on this host"}
    risk = [float(x["missed_growth_risk_usd"]) for x in rows
            if isinstance(x.get("missed_growth_risk_usd"), (int, float))]
    return {"verdict": UNMEASURED, "n": len(rows),
            "undeployed_risk_usd": round(sum(risk), 2),
            "last_at": rows[-1].get("at"),
            "why": ("each block leaves the leg's certified risk undeployed only if the blocking "
                    "position was not the lost send; the journal cannot tell which. The figure "
                    "is risk, not forgone profit, which can be R:R times larger; it is "
                    "published rather than priced as zero")}


#: The enrolment census: its `held` rows are what the research-integrity door deferred.
FORWARD_ENROLMENT = BASE / "reports" / "FORWARD_ENROLMENT.json"


def measure_replication_hold(r: Any, _alloc: dict[str, Any],
                             _fv: dict[str, Any]) -> dict[str, Any]:
    """What the replication hold defers (rail `replication_hold`, PENDING_SEAL_RAILS until the
    sealed register carries it): forward clocks NOT started while a certificate of a
    family with a written replication rule waits for its REPLICATED verdict.

    THE RAIL, PRECISELY. `admission_integrity.IntegrityGate.hold` keeps a NEW certificate off its
    forward clock until an independent rebuild agrees; a family with no rule proceeds, so this
    only ever defers families the lane can judge. A clock deploys no capital, so the direct cost
    is EVIDENCE TIME: `deferred_clock_hours` sums each held certificate's clockless hours. Turning
    that into log-wealth needs the forward expectancy those clocks would have shown and the
    promotion lag it adds, which no held row carries yet -- so a binding hold is UNMEASURED with
    the count and the hours published, never priced as zero. Placebo-alarm holds are a statement
    about the certifier and are reported apart (`n_placebo_held`), not billed to this rail.
    """
    doc = _json(FORWARD_ENROLMENT)
    if not doc:
        return {"verdict": UNMEASURED,
                "why": "no reports/FORWARD_ENROLMENT.json on this host: the census has not run, "
                       "so what the hold deferred is unknown"}
    rows = [x for x in (doc.get("held") or []) if isinstance(x, dict)]
    repl = [x for x in rows if not str(x.get("held") or "").startswith("HELD_PLACEBO")]
    placebo = len(rows) - len(repl)
    _i = doc.get("integrity")
    integ: dict[str, Any] = _i if isinstance(_i, dict) else {}
    proceeded = integ.get("n_proceeded_without_rule")
    if not repl:
        return {"verdict": NOT_BINDING, "value_logw_per_day": 0.0, "sample": True, "n_held": 0,
                "n_placebo_held": placebo, "n_proceeded_without_rule": proceeded,
                "why": "no certificate is waiting on a replication verdict this pass"}
    hours = [float(x["clockless_hours"]) for x in repl
             if isinstance(x.get("clockless_hours"), (int, float))]
    fams: dict[str, int] = {}
    for x in repl:
        f = str(x.get("family") or "")
        fams[f] = fams.get(f, 0) + 1
    return {"verdict": UNMEASURED, "n_held": len(repl), "n_placebo_held": placebo,
            "n_proceeded_without_rule": proceeded, "held_by_family": fams,
            "deferred_clock_hours": round(sum(hours), 2),
            "max_wait_hours": round(max(hours), 2) if hours else None,
            "names": [str(x.get("key")) for x in repl[:50]],
            "ledger_line": {"n_held": len(repl), "deferred_clock_hours": round(sum(hours), 2),
                            "held_by_family": fams, "n_proceeded_without_rule": proceeded,
                            "unit": "forward clock-hours deferred"},
            "why": (f"{len(repl)} certificate(s) of replicable families wait for a REPLICATED "
                    f"verdict, {sum(hours):.1f} forward clock-hours deferred; pricing that in "
                    f"log-wealth needs the forward expectancy the deferred clocks would carry, "
                    f"which no held row has yet. Published, not priced as zero.")}


MEASURES = {name: fn for name, fn in globals().items() if name.startswith("measure_")}

#: RAILS AWAITING THE SEALED REGISTER. `libs/portfolio/rails.py` is in the immutable manifest, so a
#: cloud session cannot add a rail to it; a rail listed here is measured and ledgered by this loop
#: exactly as a registered one is until the desktop pass registers it there (patch
#: `patches/audit-governance/rails_replication_hold.patch`), after which the register's own entry
#: wins and this one is skipped by name. Growth Governance asks for the ledger line NOW, not after
#: the seal.
PENDING_SEAL_RAILS: tuple[Rail, ...] = (
    Rail("replication_hold", "gate",
         "admission_integrity.IntegrityGate.hold <- replication_civilization verdicts",
         "measure_replication_hold"),
)


def all_rails() -> tuple[Rail, ...]:
    """The register plus every rail still awaiting it, never twice."""
    have = {r.name for r in RAILS}
    return (*RAILS, *(r for r in PENDING_SEAL_RAILS if r.name not in have))


# --------------------------------------------------------------------------- the ledger
def _rows() -> list[dict]:
    try:
        return [json.loads(ln) for ln in LEDGER.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def _verdict_from_samples(samples: list[float]) -> tuple[str, dict[str, Any]]:
    arr = np.asarray(samples, dtype=float)
    if arr.size < MIN_N:
        return UNMEASURED, {"n": int(arr.size), "why": f"under {MIN_N} daily samples"}
    if np.all(arr == 0.0):
        return NOT_BINDING, {"n": int(arr.size), "mean_logw_per_day": 0.0}
    se = float(arr.std(ddof=1) / math.sqrt(arr.size)) if arr.size > 1 else 0.0
    t = float(arr.mean() / se) if se > 0 else (float("inf") if arr.mean() != 0 else 0.0)
    v = EARNS if t > 2.0 else (COSTS if t < -2.0 else UNMEASURED)
    return v, {"n": int(arr.size), "mean_logw_per_day": round(float(arr.mean()), 8),
               "t": round(t, 2), "annualised_logw": round(float(arr.mean()) * 252.0, 6)}


def run(write: bool = True, today: str | None = None) -> dict[str, Any]:
    alloc = _json(ALLOC)
    fv = _veto_evidence()
    day = today or datetime.now(tz=UTC).date().isoformat()
    # 1. today's samples, appended once per day per rail
    existing = _rows()
    have_today = {(r.get("rail"), r.get("day")) for r in existing}
    new = []
    live: dict[str, dict[str, Any]] = {}
    rails_now = all_rails()
    for r in rails_now:
        m = MEASURES[r.measure](r, alloc, fv)
        live[r.name] = m
        if m.get("sample") and (r.name, day) not in have_today:
            new.append({"day": day, "rail": r.name,
                        "value": float(m.get("value_logw_per_day", 0.0)),
                        "at": datetime.now(tz=UTC).isoformat()})
        elif isinstance(m.get("ledger_line"), dict) and (r.name, day) not in have_today:
            # A BINDING RAIL THAT CANNOT BE PRICED YET still gets its line: what it deferred, in
            # its own units, with `value: null` -- never a 0.0 that would read as "cost nothing".
            new.append({"day": day, "rail": r.name, "value": None, "unpriced": True,
                        **m["ledger_line"], "at": datetime.now(tz=UTC).isoformat()})
    if new and write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for row in new:
                fh.write(json.dumps(row) + "\n")
    rows = existing + new
    # 2. verdicts from the accumulated samples (or the direct measurement for vetoes)
    verdicts: dict[str, dict[str, Any]] = {}
    for r in rails_now:
        m = live[r.name]
        if r.measure == "measure_veto" or r.measure == "measure_shrinkage":
            verdicts[r.name] = {"kind": r.kind, **m}
            continue
        # unpriced lines (value null) are a record of what was deferred, not a sample
        samples = [float(x["value"]) for x in rows if x.get("rail") == r.name
                   and isinstance(x.get("value"), (int, float))]
        if m.get("verdict") == UNMEASURED and not samples:
            verdicts[r.name] = {"kind": r.kind, **m}
            continue
        v, stats = _verdict_from_samples(samples)
        verdicts[r.name] = {"kind": r.kind, "verdict": v, **stats,
                            "today": {k: val for k, val in m.items() if k != "sample"}}
    # 3. calibration: weaken tunable rails that cost growth, within bounds; never strengthen.
    cal = calibration()
    changed = []
    tasks = []
    for r in rails_now:
        v = verdicts[r.name].get("verdict")
        if v != COSTS:
            continue
        if r.tunable:
            cur = float(cal.get(r.name, 1.0))
            # WHICH WAY IS LOOSER DEPENDS ON THE RAIL. For a shrink or an inertia, less of it is
            # weaker and the walk goes DOWN. For a CAP, more room is weaker and it goes UP --
            # walking a cap down would TIGHTEN it every time it proved expensive, which is the
            # growth governance running backwards. Rails without a direction keep "down", so
            # every rail that existed before this behaves exactly as it did.
            if getattr(r, "weaken_dir", "down") == "up":
                nxt = min(r.hi, cur * (1.0 + STEP))
                moved = nxt > cur + 1e-9
            else:
                nxt = max(r.lo, cur * (1.0 - STEP))
                moved = nxt < cur - 1e-9
            if moved:
                cal[r.name] = round(nxt, 4)
                changed.append({"rail": r.name, "from": cur, "to": round(nxt, 4),
                                "dir": getattr(r, "weaken_dir", "down"),
                                "means": r.weaken_means})
        else:
            tasks.append({"source": "missed_growth", "kind": "rail_review",
                          "title": f"Rail {r.name} costs growth: {verdicts[r.name]}",
                          "description": (f"The {r.kind} rail {r.name} ({r.where}) has a "
                                          f"measured opportunity cost in forward log-wealth. "
                                          "Under the growth governance a rail that does not "
                                          "prove it raises robust forward E[log W] is weakened "
                                          "or removed. Propose the removal or the continuous "
                                          "replacement, with the evidence."),
                          "rail": r.name, "status": None, "consumer": "principal / research"})
    if write and changed:
        CALIBRATION.parent.mkdir(parents=True, exist_ok=True)
        CALIBRATION.write_text(json.dumps({"generated_utc": datetime.now(tz=UTC).isoformat(),
                                           "multipliers": cal, "changes": changed}, indent=1),
                               "utf-8")
    if write and tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(tasks, source="missed_growth")
        except Exception:
            pass
    aggression = alloc.get("aggression") or {}
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "day": day,
           "ledger_rows": len(rows), "new_samples": len(new), "rails": verdicts,
           "veto_evidence_source": fv.get("source"),
           "costs_growth": sorted(k for k, v in verdicts.items() if v.get("verdict") == COSTS),
           "earns": sorted(k for k, v in verdicts.items() if v.get("verdict") == EARNS),
           "unmeasured": sorted(k for k, v in verdicts.items() if v.get("verdict") == UNMEASURED),
           "calibration": cal, "calibration_changes": changed, "review_tasks": len(tasks),
           "aggression_verdict": aggression.get("verdict"),
           "unused_upside_heat": aggression.get("unused_upside_heat"),
           "rule": ("OpportunityCost(rail) = E[log W without] - E[log W with]; a rail that "
                    "COSTS_GROWTH is weakened within its bounds (tunable) or queued for review "
                    "(binary); a rail is never strengthened by this loop")}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    d = run(write=not a.no_write)
    print(f"MISSED GROWTH  {d['ledger_rows']} ledger rows (+{d['new_samples']} today)  "
          f"costs={d['costs_growth']} earns={d['earns']}")
    for name, v in d["rails"].items():
        extra = "".join(f" {k}={v[k]}" for k in ("n", "t", "mean_logw_per_day") if k in v)
        print(f"  {name:26s} {v.get('kind', ''):9s} {v.get('verdict', ''):16s}{extra}")
    if d["calibration_changes"]:
        print(f"  calibration: {d['calibration_changes']}")
    if d.get("aggression_verdict"):
        print(f"  aggression: {d['aggression_verdict']} unused_upside={d['unused_upside_heat']}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
