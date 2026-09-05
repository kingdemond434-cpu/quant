"""Where the next trial goes is decided by evidence, and the decision stays reversible.

    python -m pytest desks/mt5/tests/test_trial_allocator.py -q

WHAT THIS ALLOCATOR IS FOR. Measured 2026-09-05 on the desk's own judged docket: 46,835 cards,
49 certificates, 0.105%. 55.2% of every trial ever spent went to `discovered x equity`, which
certifies at 0.031%; 0.26% went to `overnight_gap_decay x fx_exotic`, which certifies at 14.75%.
The gauntlet was not refusing good candidates -- it was being handed candidates from ground where
it has never certified anything.

THE FOUR PROPERTIES THAT MAKE RAISING A CONVERSION RATE THIS WAY LEGITIMATE, and each has a test
below because each is what separates this from the forbidden repair:

  1. THE BAR NEVER MOVES. Only order and budget share change; a candidate from any class faces
     the identical ten gates. Nothing here reads, writes or scales a threshold.
  2. THE ESTIMATE IS SHRUNK. Allocation reads the Wilson lower bound, so a lucky 2-for-2 cannot
     outrank a measured 18-for-122 and the search cannot chase its own noise.
  3. THE DEMOTION IS REVERSIBLE. A fixed share of every budget is split equally over every known
     cell type forever, so the evidence that demoted a class keeps being refreshed.
  4. COVERAGE STAYS A CYCLE. Every symbol still comes back; what changes is how often.
"""
from __future__ import annotations

import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent.parent / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import trial_allocator as ta  # noqa: E402

Y = ta.CellYield


def _classes(symbols: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in symbols:
        out[_CLASS_OF[s]] = out.get(_CLASS_OF[s], 0) + 1
    return out


#: A toy universe with the real shape: one big low-yield class, one small high-yield one.
_CLASS_OF = {**{f"EQ{i}": "equity" for i in range(20)},
             **{f"FX{i}": "fx_exotic" for i in range(4)},
             **{f"CR{i}": "fx_cross" for i in range(6)}}
_SYMBOLS = sorted(_CLASS_OF)


def _class_of(sym: str) -> str:
    return _CLASS_OF.get(sym, "unknown")


# ------------------------------------------------- 2. the estimate is shrunk

def test_a_lucky_two_of_two_never_outranks_a_measured_eighteen_of_one_twenty_two() -> None:
    """The property PRIOR_TRIALS exists to buy, pinned as a property and not as a constant.

    Raw rates say 100% beats 14.8% and the search would chase the coin flip. AN INTERVAL ALONE
    DOES NOT FIX THAT and this test is the reason we know: the plain Wilson lower bound of 2/2 is
    34% against 9.5% for 18/122, so the coin flip still wins. Only shrinking toward the desk's own
    0.1% base rate first reverses it. Whoever tunes PRIOR_TRIALS must keep this true.
    """
    lucky = Y("lucky", "fx_exotic", tried=2, certified=2)
    measured = Y("overnight_gap_decay", "fx_exotic", tried=122, certified=18)
    assert lucky.rate > measured.rate
    assert ta.wilson_lower(2, 2) > ta.wilson_lower(18, 122), (
        "the unshrunk bound really does prefer the coin flip -- that is why shrinkage is here")
    assert lucky.lower < measured.lower
    w = ta.weights([lucky, measured])
    assert w[measured.key] > w[lucky.key]


def test_a_type_with_no_trials_is_not_a_zero() -> None:
    """"never tested" and "tested and dead" are opposite facts."""
    assert ta.wilson_lower(0, 0) == 0.0
    untried = Y("new_family", "bond", tried=0, certified=0)
    tried_dead = Y("dead_family", "bond", tried=900, certified=0)
    w = ta.weights([untried, tried_dead, Y("good", "fx_exotic", 122, 18)])
    # Both sit on the explore floor -- the allocator has no evidence that separates them, and
    # inventing one would be the guess this desk forbids.
    assert w[untried.key] == w[tried_dead.key] > 0.0


# ------------------------------------------------- 3. the demotion is reversible

def test_no_cell_type_is_ever_starved_to_zero_so_a_demotion_stays_reversible() -> None:
    """Without a standing explore share the allocator freezes its first opinion into the only
    evidence it will ever collect about the ground it demoted."""
    ys = [Y("good", "fx_exotic", 122, 18), Y("bad", "equity", 25876, 8),
          Y("worse", "index", 962, 0)]
    w = ta.weights(ys)
    assert all(v > 0.0 for v in w.values())
    assert abs(sum(w.values()) - 1.0) < 1e-9
    # The explore mass is split equally, so the worst type still holds a real, named share.
    assert w[("worse", "index")] >= ta.EXPLORE_SHARE / len(ys) - 1e-9


def test_no_single_cell_type_can_take_the_whole_budget() -> None:
    """A 14.8% lead is a lead, not a licence to stop looking anywhere else."""
    ys = [Y("dominant", "fx_exotic", 200, 190), Y("a", "equity", 5000, 1),
          Y("b", "index", 5000, 1)]
    w = ta.weights(ys)
    assert w[("dominant", "fx_exotic")] <= ta.MAX_SHARE + 1e-9
    assert abs(sum(w.values()) - 1.0) < 1e-9, "capping must redistribute, never shrink the budget"


def test_with_nothing_measured_the_allocation_is_the_incumbent_uniform_one() -> None:
    """An allocator with no evidence must not invent a preference."""
    ys = [Y("a", "equity", 10, 0), Y("b", "fx_exotic", 10, 0)]
    w = ta.weights(ys)
    assert w[("a", "equity")] == w[("b", "fx_exotic")] == 0.5
    assert ta.weights([]) == {}


# ------------------------------------------------- 4. coverage stays a cycle

def test_reordering_is_always_a_permutation_so_no_symbol_is_ever_dropped() -> None:
    ordered = ta.order_symbols(_SYMBOLS, {"equity": 0.05, "fx_exotic": 0.6, "fx_cross": 0.35},
                               class_of=_class_of)
    assert sorted(ordered) == sorted(_SYMBOLS)


def test_a_bounded_prefix_carries_every_class_in_proportion() -> None:
    """Every generator here is bounded, so the only thing an ordering decides is what a run
    REACHES. A sort by weight would reach one class and never leave it."""
    w = {"equity": 0.10, "fx_exotic": 0.60, "fx_cross": 0.30}
    ordered = ta.order_symbols(_SYMBOLS, w, class_of=_class_of)
    head = _classes(ordered[:10])
    assert head.get("fx_exotic", 0) >= head.get("equity", 0)
    assert set(head) == {"equity", "fx_exotic", "fx_cross"}, (
        "a bounded run must still touch every class, or the explore share is a fiction")


def test_relative_order_inside_a_class_is_preserved_exactly() -> None:
    """The caller's own cursor, mined-ground priority and staleness rule must survive; this
    decides only how the classes interleave."""
    ordered = ta.order_symbols(_SYMBOLS, {"equity": 0.2, "fx_exotic": 0.5, "fx_cross": 0.3},
                               class_of=_class_of)
    for cls in ("equity", "fx_exotic", "fx_cross"):
        before = [s for s in _SYMBOLS if _class_of(s) == cls]
        after = [s for s in ordered if _class_of(s) == cls]
        assert before == after


def test_each_class_keeps_its_own_cursor_so_the_long_run_mix_actually_moves() -> None:
    """THE POINT THAT ORDERING ALONE COULD NOT REACH.

    One cursor over one list gives every symbol exactly one search per cycle whatever the order,
    so re-sorting cannot move the long-run class mix by a single trial. Per-class cursors can:
    the high-yield class comes round more often. This is the test that would fail if someone
    "simplified" the allocator back to a sort.
    """
    w = {"equity": 0.05, "fx_exotic": 0.60, "fx_cross": 0.35}
    cursors: dict[str, int] = {}
    seen: dict[str, int] = {}
    for _ in range(12):
        chosen, cursors = ta.allocate_symbols(_SYMBOLS, 6, w, cursors, class_of=_class_of)
        for s in chosen:
            seen[_class_of(s)] = seen.get(_class_of(s), 0) + 1
    assert seen["fx_exotic"] > seen["equity"], (
        "the small high-yield class must be searched MORE OFTEN than the big low-yield one")


def test_every_class_receives_at_least_one_symbol_per_run() -> None:
    """The floor at the symbol level: no class is ever declared finished."""
    w = {"equity": 0.98, "fx_exotic": 0.01, "fx_cross": 0.01}
    chosen, _ = ta.allocate_symbols(_SYMBOLS, 6, w, {}, class_of=_class_of)
    assert set(_classes(chosen)) == {"equity", "fx_exotic", "fx_cross"}


def test_every_symbol_in_a_class_comes_back_because_coverage_is_a_cycle() -> None:
    """A class is searched less often, never abandoned -- the cursor walks all of it."""
    w = {"equity": 0.05, "fx_exotic": 0.60, "fx_cross": 0.35}
    cursors: dict[str, int] = {}
    seen: set[str] = set()
    for _ in range(60):
        chosen, cursors = ta.allocate_symbols(_SYMBOLS, 6, w, cursors, class_of=_class_of)
        seen.update(chosen)
    assert seen == set(_SYMBOLS)


def test_a_budget_larger_than_the_universe_takes_everything_once() -> None:
    chosen, _ = ta.allocate_symbols(_SYMBOLS, 999, {"equity": 1.0}, {}, class_of=_class_of)
    assert sorted(chosen) == sorted(_SYMBOLS)


# ------------------------------------------------- 1. the bar never moves

def test_the_allocator_declares_no_authority_and_touches_no_gate() -> None:
    """It decides order and budget share. A component that could also move a bar would."""
    assert ta.CAPABILITY_NODE["authority"] == ()
    src = (RESEARCH / "trial_allocator.py").read_text(encoding="utf-8")
    for forbidden in ("DSR_THRESHOLD", "PBO_THRESHOLD", "SPA_ALPHA", "MIN_TRADE_DAYS",
                      "COST_SCENARIO", "TRIALS_MULTIPLIER"):
        assert forbidden not in src, (
            f"{forbidden} must not appear here: raising a conversion rate by moving a bar "
            f"converts worse candidates, and it is the one repair this desk forbids")


def test_the_capability_node_names_the_paths_this_module_really_touches() -> None:
    """The graph registry lives outside this tree, so the declaration is kept beside the code it
    describes and checked against it -- exactly what the UNDECLARED check does upstream."""
    src = (RESEARCH / "trial_allocator.py").read_text(encoding="utf-8")
    for path in (*ta.CAPABILITY_NODE["writes"], *ta.CAPABILITY_NODE["reads"]):
        leaf = path.rsplit("/", 1)[-1]
        assert leaf in src, f"declared path {path} is not touched by the module"
    assert ta.CAPABILITY_NODE["module"] == "desks/mt5/research/trial_allocator.py"


# ------------------------------------------------- the rent line

def test_the_rent_line_names_its_unit_and_refuses_to_invent_log_wealth() -> None:
    """No exchange rate exists from a certificate to E[log W] at this stage of the funnel, and
    fabricating one would fabricate the desk's own objective."""
    r = ta.rent([Y("good", "fx_exotic", 122, 18), Y("bad", "equity", 25876, 8)])
    assert r["unit"] == "certificates per 1000 gauntlet trials"
    assert r["rent_logw_per_day"] is None
    assert r["rent_logw_why"]
    assert r["basis"] == "EX_ANTE_COUNTERFACTUAL_ON_JUDGED_DOCKET"
    assert r["forward_verdict"] == "UNMEASURED", (
        "a projection on already-collected evidence is never forward evidence")


def test_the_rent_is_positive_only_when_the_allocation_beats_what_the_docket_received() -> None:
    ys = [Y("good", "fx_exotic", 122, 18), Y("bad", "equity", 25876, 8)]
    assert ta.rent(ys)["verdict"] == "EARNS"
    # A docket already spent where it pays leaves nothing for the allocator to earn.
    even = [Y("good", "fx_exotic", 1000, 150), Y("also_good", "equity", 1000, 150)]
    assert ta.rent(even)["rent"] == 0.0
    assert ta.rent(even)["verdict"] == "NOT_BINDING"


def test_an_absent_docket_is_unmeasured_and_not_a_zero_rent() -> None:
    assert ta.rent([])["verdict"] == "UNMEASURED"
    assert ta.rent([])["rent_logw_per_day"] is None


# ------------------------------------------------- the generators degrade, never die

def test_both_generators_fall_back_to_their_previous_order_if_the_allocator_cannot_measure() -> (
        None):
    """A measurement outage must cost the sweep its ordering, never its run."""
    for name, marker in (("edge_search.py", "class-balanced rotation"),
                         ("orthogonal_sweep.py", "alphabetical")):
        src = (RESEARCH / name).read_text(encoding="utf-8")
        # ANCHOR ON THE IMPORT, NOT THE FIRST MENTION (2026-09-05). This sliced from
        # `src.index("trial_allocator")`, which is a PROSE mention in whichever docstring happens
        # to come first -- so explaining the allocator in a docstring pushed the guard out of the
        # 1,400-character window and failed a module whose guard was three lines below. The
        # property being pinned is about the CALL SITE; anchor there and the check cannot be
        # broken (or satisfied) by a comment.
        head = src[src.index("import trial_allocator"):]
        assert "except Exception" in head[:1400], f"{name} must not die on a measurement outage"
        assert marker in head[:1800], f"{name} must name what it falls back to"
