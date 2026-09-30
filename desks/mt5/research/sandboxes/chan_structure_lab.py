"""PIT-safe hierarchical price-structure challenger rebuilt from public documentation.

Source snapshot: neil-pan-s/one-quant-doc@7231f5d5353cf118890de7e186f56c5a7727ea41.
The repository documents a Chan/缠论 ontology but does not publish its engine or a licence.
No upstream code is copied or executed.  The useful contribution is treated as a representation
language and translated into registered, gauntlet-bound families.  Source doctrine and chart
examples are priors, never profitability evidence.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "chan_structure_lab"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "representation_learning"
UPSTREAM = ("one_quant_doc",)
FALLBACK = "desk-owned PIT structural geometry; no foreign code, network, or order authority"
SOURCE = "https://github.com/neil-pan-s/one-quant-doc"
PIN = "7231f5d5353cf118890de7e186f56c5a7727ea41"

ATOMS: tuple[dict[str, Any], ...] = (
    {"id": "confirmed_fractal_reversal", "family": "failed_breakout",
     "mechanism": "confirmed local price rejection can reveal exhausted directional inventory",
     "recipe": "three-bar fractal; usable only after the right-hand confirming bar closes"},
    {"id": "recursive_leg_continuation", "family": "trend_ma_cross",
     "mechanism": "persistent directional inventory can survive coarse-graining across legs",
     "recipe": "alternating confirmed fractals form legs; condition on slope, length and ATR"},
    {"id": "central_zone_reentry", "family": "range_reversion",
     "mechanism": "failed acceptance outside an overlapping multi-leg value zone traps entrants",
     "recipe": "intersection of three completed leg ranges; exit then confirmed close back inside"},
    {"id": "central_zone_breakout", "family": "level_breakout",
     "mechanism": "repeated two-sided trade builds inventory that must rebalance after acceptance",
     "recipe": ("confirmed close outside a completed overlap zone, normalized by zone width "
                "and ATR")},
    {"id": "structural_momentum_exhaustion", "family": "failed_breakout",
     "mechanism": "greater price extension with lower momentum expenditure signals weakening flow",
     "recipe": "compare price distance and absolute MACD-area efficiency across completed legs"},
    {"id": "zone_expansion_vol_transition", "family": "vol_transition",
     "mechanism": "widening recursive equilibrium zones reveal a transition in risk and liquidity",
     "recipe": "change in completed-zone width, dwell and interactions, all ATR normalized"},
)


def confirmed_fractals(high: tuple[float, ...], low: tuple[float, ...]) -> list[dict[str, Any]]:
    """Return strict three-bar fractals with the first legal decision timestamp.

    A center at i is unknowable until i+1 closes.  This primitive never revises prior objects;
    richer stroke/segment builders must preserve the same availability discipline.
    """
    out: list[dict[str, Any]] = []
    for i in range(1, min(len(high), len(low)) - 1):
        if high[i] > high[i - 1] and high[i] > high[i + 1]:
            out.append({"kind": "top", "object_index": i, "first_known_index": i + 1,
                        "confirmed_index": i + 1, "revised_index": None})
        if low[i] < low[i - 1] and low[i] < low[i + 1]:
            out.append({"kind": "bottom", "object_index": i, "first_known_index": i + 1,
                        "confirmed_index": i + 1, "revised_index": None})
    return out


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    del ctx
    frames = [frame for frame in bundle.bars.values() if len(frame) >= 100]
    # Rotate through actual symbol/timeframe observations; do not invent missing intraday bars.
    selected = frames[:12]
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for frame in selected:
        pivots = confirmed_fractals(frame.high, frame.low)
        diagnostics.append({"symbol": frame.symbol, "timeframe": frame.timeframe,
                            "bars": len(frame), "confirmed_fractals": len(pivots),
                            "last_first_known": (pivots[-1]["first_known_index"]
                                                 if pivots else None)})
        for atom in ATOMS:
            candidates.append(A.candidate(
                atom["family"], [frame.symbol],
                f"{atom['id']} on {frame.timeframe}: {atom['mechanism']}; rule: {atom['recipe']}; "
                "falsifier: no incremental net held-out value over its registered family baseline",
                horizon=frame.timeframe, source=f"{SOURCE}@{PIN}",
                evidence={"source_claim_is_prior_only": True, "source_commit": PIN,
                          "timeframe": frame.timeframe, "confirmation_clock":
                          "object_index < first_known_index <= decision_index",
                          "extraction": "independent mathematical reimplementation"}))
    representations = ({
        "kind": "PIT_HIERARCHICAL_PRICE_GEOMETRY", "source": f"{SOURCE}@{PIN}",
        "objects": ["fractal", "leg", "segment", "overlap_zone", "structural_state"],
        "availability_fields": ["object_time", "first_known", "confirmed", "revised"],
        "diagnostics": diagnostics,
    }, {
        "kind": "STRUCTURAL_MOMENTUM_EFFICIENCY", "source": f"{SOURCE}@{PIN}",
        "formula": "abs(price_delta) / max(abs(MACD_area), epsilon)",
        "comparison": "completed leg versus prior same-direction completed leg",
    })
    methods = (
        {"kind": "REPAINTING_PLACEBO", "arms": ["hindsight_finalized", "PIT_incremental"],
         "rule": "only PIT_incremental may donate a candidate; divergence quantifies leakage"},
        {"kind": "MULTISCALE_MARGINAL_ABLATION",
         "arms": ["small_frame_only", "small_plus_large_confirmed_state"],
         "metric": "held-out incremental information and dElogW after costs"},
        {"kind": "ONTOLOGY_EXPLOSION_GUARD",
         "rule": "explode structural states, assets, frames and regimes; dedupe economic exposure "
                 "before expensive testing; every descendant pays multiplicity"},
    )
    mechanisms = tuple({"kind": "MECHANISM_ATOM", "source": f"{SOURCE}@{PIN}", **atom}
                       for atom in ATOMS)
    return A.packet(SYSTEM, bundle, trials=0, candidates=candidates,
                    representations=representations, mechanisms=mechanisms,
                    research_methods=methods,
                    note="documentation donor only; PIT descendants receive the ordinary gates")
