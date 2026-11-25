"""Every seat the box measured DEAD with no named alternative on 2026-11-24 now carries a decision.

The census law: a dead producer with no named replacement is an open decision, which is the
defect. The 6h pass of 2026-11-25 (I11) found 29 such seats on the box; each is declared here as
RETIRED (cannot write again by design, reason cites the line) or as a REPLACEMENT naming a live
inheritor. A replacement naming a retired seat, or itself, would be no replacement.
"""
from __future__ import annotations

from scripts import check_producer_yield as fence

TRIAGED_2026_11_25 = (
    "alpha_periodic_table", "axis_registry", "cell_emitter", "conversion_maximiser",
    "culture_gap", "equiti_copy", "factor_residual", "firm_mining", "followme_cn", "frontier",
    "hfm_pamm", "joint_evolution", "mathlab", "mechanism_genome", "minfx_jp",
    "missed_trade_archaeologist", "octa_masters", "physics_lab", "recombinants", "residual_queue",
    "specialist_cell", "srb_uncorrelated_sweep", "statarb",
)
#: Dead only because the box's clock never reached them (old code) or a code fix is owed: these
#: keep no declaration on purpose, so the census keeps flagging them until they write again.
OWED_A_RUN = ("alpha_recombination", "anomalies", "axis_registry", "qd_frontier",
              "graveyard_resurrection", "trajectory_evolution", "ftmo_allocator")


def test_every_triaged_seat_is_retired_or_names_an_inheritor() -> None:
    open_ = [s for s in TRIAGED_2026_11_25 if s not in OWED_A_RUN
             and s not in fence.RETIRED_SEATS and s not in fence.REPLACEMENTS]
    assert open_ == [], f"dead seats with no decision: {open_}"


def test_no_replacement_names_a_retired_seat_or_itself() -> None:
    bad = {k: fence.replacement_target(v) for k, v in fence.REPLACEMENTS.items()
           if fence.replacement_target(v) in fence.RETIRED_SEATS
           or fence.replacement_target(v) == k}
    assert bad == {}, bad


def test_a_seat_is_never_both_retired_and_replaced() -> None:
    assert set(fence.RETIRED_SEATS) & set(fence.REPLACEMENTS) == set()
