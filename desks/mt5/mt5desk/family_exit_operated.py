"""THE EXIT OPERATOR AS A CELL: any existing entry, with a state-conditional exit bolted on.

WHY THIS EXISTS AND `family_htf_anchor_trend` IS NOT ENOUGH. The volatility-expansion exit --
flat when current ATR exceeds `expansion_mult` x the ATR observed at entry -- is not an entry
claim. It is an operator over exits, and its interesting question is not "does it help the one
trend entry the video happened to pair it with" but "does it help ANY of the entries this desk
already owns". There are 65 registered families and not one of them conditions an exit on
volatility relative to its own value at the moment of entry. Writing the rule only inside a new
trend family would have answered the narrow question and left the broad one untested, which is
the failure this desk files as a mechanism that could describe a trade and never propose one.

WHAT A CELL OF THIS FAMILY IS. `(base_family, base_params)` names an ordinary cell the desk can
already build; `expansion_mult` and `exit_on_anchor_flip` name the operator applied to its
signals. The identity is the whole tuple, so a certificate says exactly which entry was operated
on with which multiple, and the un-operated cell is an ordinary candidate of the base family
already in the docket -- the control arm is not something this family has to manufacture.

NOT A SECOND DOOR, in the sense `family_ensemble`'s docstring means it. The wrapper is registered
as a family, compiled, merged, judged, clocked forward and allocated exactly as anything else. It
gets no privileged path and its multiplicity charge is paid in the same budget.

WHAT IT CANNOT WRAP, said out loud rather than discovered as a silent zero. The base family is
resolved through `mt5desk.families.get_family_func` and called with `base_params` and the bars in
hand -- nothing else. A base family that needs a peer frame, a factor set, a COT frame, a macro
series, a tape series, an event calendar or an ensemble runner is NOT resolvable here and the
wrapper returns []. That is roughly a dozen of the 65; the rest are price-only and wrap cleanly.
`_UNWRAPPABLE` names them so a producer can refuse to mint the cell instead of minting one that
returns nothing and reads as a mechanism that never fires (WS-005: absence read as a verdict).
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from mt5desk.exit_operators import anchor_direction, apply_exit_operators
from mt5desk.families import Signal, _h1, get_family_func, register_family

#: Families whose signals cannot be rebuilt from `(bars, params)` alone -- they need a runtime
#: input that `external_gauntlet.build_cell` injects for THEM and not for a wrapper around them.
#: Mirrors the branches of `mt5desk.family_inputs.resolve`.
_UNWRAPPABLE: frozenset[str] = frozenset({
    "carry", "ensemble", "formula", "lead_lag", "style_premia", "relative_value",
    "cross_asset_residual", "pca_residual", "execution_state", "liquidity_regime",
    "orderflow_imbalance", "macro_conditional", "cot_positioning", "cot_net_fade",
    "cot_change_fade", "cot_change_momentum", "cot_comm_follow", "event_reaction",
    "cross_sectional", "discovered", "generic", "joint_genome",
})


def wrappable(name: str) -> bool:
    """Can `name` be rebuilt from bars and params alone? Producers ask before minting a cell."""
    return bool(name) and name not in _UNWRAPPABLE and get_family_func(name) is not None


@register_family(
    param_grid={
        # The video's 4.0 is one point and carries no standing of its own; a constant lifted from
        # one person's search over one single-name equity is a borrowed overfit.
        "expansion_mult": [1.25, 1.5, 2.0, 3.0, 4.0, 6.0],
        "exit_on_anchor_flip": [False, True],
        "anchor_mult": [4],
    },
    tags=["exit_operator", "composable", "conditional_exit", "public_claim"],
)
def family_exit_operated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    expansion_mult: float = 4.0,
    exit_on_anchor_flip: bool = False,
    anchor_mult: int = 4,
    anchor_n: int = 50,
    atr_n: int = 14,
) -> list[Signal]:
    """`base_family`'s own signals, with their holds truncated by the exit operator.

    With `expansion_mult <= 0` and `exit_on_anchor_flip=False` this is the base family exactly,
    which would be a duplicate cell carrying a second multiplicity charge for no new question --
    so that combination returns [] rather than quietly re-testing something already in the docket.
    """
    if not base_family or base_family in _UNWRAPPABLE:
        return []
    if expansion_mult <= 0 and not exit_on_anchor_flip:
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = dict(base_params or {})
    # The same identity keys `external_gauntlet.build_cell` strips before calling a family: they
    # name the chart and the session filter, they are not family arguments, and leaving one in
    # raises TypeError on every family.
    for k in ("timeframe", "session"):
        params.pop(k, None)
    d = _h1(df)
    try:
        sigs = fn(d, side=1, **params)
    except TypeError:
        try:
            sigs = fn(d, **params)
        except Exception:
            return []
    except Exception:
        return []
    sigs = [s for s in (sigs or []) if isinstance(s, Signal)]
    if not sigs:
        return []
    anchor = None
    if exit_on_anchor_flip:
        anchor = anchor_direction(d, anchor_mult=max(2, int(anchor_mult)), anchor_n=int(anchor_n))
    return apply_exit_operators(
        d, sigs,
        expansion_mult=float(expansion_mult),
        exit_on_anchor_flip=bool(exit_on_anchor_flip),
        anchor=anchor,
        atr_n=int(atr_n),
    )
