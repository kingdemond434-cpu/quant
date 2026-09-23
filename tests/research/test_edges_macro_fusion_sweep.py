"""Pricing the account correctly triples the candidate flow, and the sweep that shows it was dead.

`run_edges_macro_fusion_sweep` re-ranks the desk's real chart-edge library under three cost
regimes. It had never run, and not because nobody scheduled it: FOUR of the twelve families it
was written against no longer exist on `mt5desk.families`, so the module raised AttributeError on
IMPORT -- before any scheduler could have reached it, and long enough ago that its absence read
as "not wired" rather than "broken".

FIRST RUN, 2026-09-10, 10 families x 4 symbols x 3 regimes:

    WIDE   3 of 36 cells clear the t >= 1.96 screening bar
    RAW    9 of 36
    ZERO  10 of 36

Every earlier sweep used `Costs.from_symbol(meta, mult=2.0)` -- WIDE -- which this module's own
header calls "roughly five times the real cost on gold" on a raw-spread/commission account. And
ZERO returns only one more cell than RAW, so the gain is NOT an artifact of running to the
optimistic bound: RAW captures nearly all of it.

WHAT THESE TESTS PIN:

    A MISSING FAMILY IS DROPPED AND NAMED, NEVER SUBSTITUTED. Two of the four are unambiguous
    renames and are mapped; two are genuinely gone. Filling those with the nearest-looking family
    would report a result for a strategy nobody ran, so the artifact carries the coverage and a
    reader can tell "did not rank" from "was not tested".

    THE COST MODEL IS THE ENGINE'S. The sweep hand-rolled its own Costs with
    `commission_per_lot=3.50` -- a round-turn figure in a per-side field -- and no
    `quote_per_account`, while its own docstring correctly said commission is contractual and
    never scaled. It contradicted itself in adjacent lines.

    COMMISSION IS NEVER SCALED BY THE REGIME. The regime multiplies the SPREAD. A regime that
    also widened commission would be modelling a fee schedule that does not exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from desks.mt5.research import run_edges_macro_fusion_sweep as sweep  # noqa: E402


def test_the_module_imports_at_all():
    """It did not, for long enough that the failure read as 'never wired'."""
    assert sweep.EDGES, "no family resolved"
    assert len(sweep.EDGE_NAMES) == 12


def test_a_family_that_no_longer_exists_is_dropped_and_named():
    """Substituting the nearest-looking family reports a result for a strategy nobody ran."""
    assert set(sweep.MISSING_EDGES) == {"order_block", "spread_state_avoidance"}
    assert not (set(sweep.EDGES) & set(sweep.MISSING_EDGES))
    assert len(sweep.EDGES) + len(sweep.MISSING_EDGES) == len(sweep.EDGE_NAMES)


def test_the_two_renames_are_mapped_to_the_same_mechanism():
    """ICT's FVG IS the fair value gap; family_comex_settlement is the settlement effect."""
    from mt5desk import families
    assert sweep.EDGE_NAMES["fair_value_gap"] == "family_ict_fvg"
    assert sweep.EDGE_NAMES["comex_settlement"] == "family_comex_settlement"
    assert sweep.EDGES["fair_value_gap"] is families.family_ict_fvg
    assert sweep.EDGES["comex_settlement"] is families.family_comex_settlement


def test_the_regimes_are_the_canonical_ones():
    from libs.portfolio import fusion_cost as fc
    assert sweep.COST_REGIMES == fc.COST_REGIMES
    assert sweep.FUSION_COMMISSION_PER_SIDE == fc.COMMISSION_PER_LOT_PER_SIDE


def test_the_regime_scales_the_spread_and_never_the_commission():
    """A regime that widened commission would model a fee schedule that does not exist."""
    meta = {"tick_size": 1e-5, "contract_size": 1e5, "tick_value": 1.0,
            "median_spread_pts": 12.0}
    wide = sweep._costs(meta, sweep.COST_REGIMES["WIDE"])
    raw = sweep._costs(meta, sweep.COST_REGIMES["RAW"])
    assert wide.commission_per_lot == raw.commission_per_lot == sweep.FUSION_COMMISSION_PER_SIDE
    assert wide.spread_per_lot > raw.spread_per_lot


def test_the_cost_model_goes_through_from_symbol():
    """It hand-rolled a Costs with a round-turn commission in a per-side field, next to a
    docstring that correctly said commission is contractual."""
    src = (_DESK / "research" / "run_edges_macro_fusion_sweep.py").read_text(encoding="utf-8")
    assert "Costs.from_symbol" in src
    import ast
    literals = {n.value for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert 3.50 not in literals, "the round-turn commission is still in the code"


def test_a_jpy_cross_gets_its_commission_converted():
    """Without quote_per_account the commission is 184x too little on exactly the crosses where
    this desk's surviving edges live."""
    jpy = {"tick_size": 0.001, "contract_size": 1e5, "tick_value": 0.54,
           "median_spread_pts": 15.0}
    same = dict(jpy, tick_value=1.0)
    assert sweep._costs(jpy, 0.2).quote_per_account != sweep._costs(same, 0.2).quote_per_account


def test_the_screening_bar_is_unchanged():
    """Cheaper costs make more candidates RANK; they do not lower the bar. Stage A only."""
    assert sweep.SCREEN_BAR == 1.96
