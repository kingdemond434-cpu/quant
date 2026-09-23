"""Side-Channels Package — Market Side-Channel Atlas.

All miners for hunting information created by market machinery rather than price charts.

Miners:
- operational_calendar_miner     - forced participant behavior around deadlines
- leadership_atlas              - information propagation leadership
- failed_reaction_miner         - markets refusing to react as expected
- negative_space_miner          - silence as a state
- synthetic_residual_miner      - fair value deviations
- broker_physics_miner          - execution microstructure alpha
- swap_table_miner              - carry/swap regime alpha
- opening_atlas_miner           - session transition dynamics
- forced_participant_miner      - who must trade even when they don't want to
- macro_revision_miner          - revision vector alpha
- language_change_miner         - central bank linguistic deltas
- delayed_reaction_miner        - information half-life curves
- failure_mining                - negative alpha inversion
- ensemble_disagreement_miner   - model disagreement entropy
- intersection_hunter           - multi-axis reinforcement
- alpha_periodic_table          - mechanism x axis matrix
- unknown_unknown_miner         - novel data source discovery
- stale_relationship_miner      - driver staleness detection
- low_capacity_hunter           - edges too small for institutions
- economic_constraint_graph     - constraint cascade hypotheses
- truth_social_miner            - Trump policy shock alpha
- mql5_codebase                 - MQL5 public code mining
- mql5_articles                 - MQL5 articles mining
- mql5_signals                  - MQL5 signals/track records mining
- mql5_forum                    - MQL5 forum mining
"""
from __future__ import annotations

from .base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

__all__ = [
    "SideChannelAxis",
    "SideChannelHypothesis",
    "generate_id",
    "save_hypothesis",
    "DATA_DIR",
]