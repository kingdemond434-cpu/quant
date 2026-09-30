"""Desk-owned challenger distilled from archived Quantrade architecture.

Source snapshot: TalaikisInc/Quantrade@7835b476ab5efa78153ea2d0cb95d23743f59fc8.
No upstream code runs.  Its absent private strategies and historical rankings are not evidence.
Only incremental research patterns are donated; existing desk GARCH, block-bootstrap, MAE/MFE,
cost and marginal-admission organs remain canonical consumers.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "quantrade_challenger"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "research_reproduction"
UPSTREAM = ("quantrade",)
FALLBACK = "desk-owned cards routed to canonical volatility, excursion and marginal-admission"
SOURCE = "https://github.com/TalaikisInc/Quantrade"
PIN = "7835b476ab5efa78153ea2d0cb95d23743f59fc8"

ATOMS = (
    {"id": "directional_causal_inversion", "family": "trend_ma_cross",
     "mechanism": ("the same observable may encode persistent inventory or temporary dislocation; "
                   "testing signed and inverted rules distinguishes the causal interpretations"),
     "falsifier": ("neither direction adds net OOS value, or both are unstable after "
                    "selection cost")},
    {"id": "asymmetric_long_short_decomposition", "family": "momentum_volgate",
     "mechanism": ("funding, crash risk and participant constraints make long and short response "
                   "distributions asymmetric even for one state variable"),
     "falsifier": "separate directions add no held-out value over a symmetric baseline"},
    {"id": "volatility_conditioned_activation", "family": "vol_transition",
     "mechanism": ("conditional variance changes stop distance, participation and breakout versus "
                   "reversion economics; a volatility forecast may improve activation"),
     "falsifier": "canonical volatility state adds no net held-out marginal value over EWMA"},
)


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    del ctx
    frames = [frame for frame in bundle.bars.values() if len(frame) >= 100][:12]
    candidates = [
        A.candidate(atom["family"], [frame.symbol],
                    f"{atom['id']} on {frame.timeframe}: {atom['mechanism']}; "
                    f"falsifier: {atom['falsifier']}", horizon=frame.timeframe,
                    source=f"{SOURCE}@{PIN}", evidence={
                        "source_claim_is_prior_only": True, "source_commit": PIN,
                        "timeframe": frame.timeframe, "arms": ["signed", "inverted", "null"],
                        "consumer": "canonical gauntlet and marginal admission",
                    })
        for frame in frames for atom in ATOMS
    ]
    methods = (
        {"kind": "CAUSAL_INVERSION_MATRIX",
         "rule": ("every directional rule exposes signed, inverted and null arms under one "
                  "trial family")},
        {"kind": "DEPENDENCE_PRESERVING_NULL_ROUTING",
         "consumers": ["portfolio_evidence", "market_posteriors", "portfolio_bootstrap"],
         "rejected": "iid Student-t cumulative-price worlds as sufficient evidence"},
        {"kind": "EXCURSION_RESEARCH_ROUTING", "consumers": [
            "excursions", "exit_study", "exit_accounts", "execution_twin"],
         "rule": "MAE/MFE propose exits; they do not modify live exits without held-out evidence"},
        {"kind": "PORTFOLIO_VS_CHAMPION_ABLATION",
         "consumer": "marginal_admission",
         "metric": "incremental held-out dElogW and effective breadth, not standalone Sortino"},
        {"kind": "LEGACY_DEFECT_NEGATIVE_CONTROL",
         "defects": ["no sealed OOS", "commission-variable mixup", "identity comparison",
                     "non-annualized selected-return Sharpe"]},
    )
    mechanisms = tuple({"kind": "MECHANISM_ATOM", "source": f"{SOURCE}@{PIN}", **atom}
                       for atom in ATOMS)
    return A.packet(SYSTEM, bundle, trials=0, candidates=candidates, mechanisms=mechanisms,
                    research_methods=methods,
                    note="ideas only; all descendants pay ordinary multiplicity and gates")
