"""FORCED QUOTAS AND COVERAGE -- the two ways a self-tuning allocator quietly stops exploring.

Both failures below are made of individually correct decisions, which is why neither is visible
without a test naming it:

  1. THE RUT. Reweight toward what worked; exploitation succeeds more because it is searched more;
     reweight further. The desk optimises itself into a local maximum one reasonable step at a
     time and the telemetry looks excellent throughout. FLOORS are the refusal to let that loop
     close, and a floor that does not survive renormalisation is not a floor.

  2. THE EMPTY EXPLOITATION. With zero survivors -- this desk's actual state, 434 candidates and 0
     survivors -- three of the five modes have nothing to act on. An allocator that still hands
     them 75% of the budget reports a full allocation while doing a quarter of the work, and every
     percentage still sums to one, so nothing looks wrong.

And one for the coverage side: an underpowered cell counted as covered makes the report say the
space was searched when it was skimmed, then points the next batch AWAY from the region that most
needs it.
"""

from __future__ import annotations

import pytest

from libs.alpha_factory.research_budget import (
    DEFAULT_QUOTAS,
    EXHAUSTION_AXES,
    EXHAUSTION_BAR,
    FLOORS,
    MODES,
    adaptive_portfolios,
    allocate,
    apply_floors,
    coverage_report,
    exhaustion_claim,
    gap_lines,
)

_SPACE = {
    "operator": ["interaction", "condition", "divergence", "ratio", "lead"],
    "horizon": ["1h", "4h", "1d", "1w"],
    "regime": ["all", "high_vol", "low_vol", "trending", "ranging"],
}


# ------------------------------------------------------------------------------- the split itself

def test_THE_DEFAULT_QUOTAS_SUM_TO_ONE() -> None:
    """A split that does not sum to 1 either under-spends the budget or double-books it, and both
    are silent."""
    assert sum(DEFAULT_QUOTAS.values()) == pytest.approx(1.0)
    assert set(MODES) == set(DEFAULT_QUOTAS)


def test_EVERY_EXPERIMENT_IS_ALLOCATED_EXACTLY_ONCE() -> None:
    """Integer division loses a remainder. Losing it silently shrinks the real search below the
    reported budget -- which then flows into the trial count and understates the hurdle."""
    for total in (1, 7, 100, 501, 16_560):
        a = allocate(total, n_survivors=5)
        assert a.allocated == total, f"lost or invented experiments at total={total}"


def test_THE_ROUNDING_REMAINDER_GOES_TO_EXPLORATION() -> None:
    """Rounding is small; a rounding RULE is a standing bias. A bias toward exploration is the one
    that cannot trap the desk in a rut, so it is the one to have."""
    base = allocate(100, n_survivors=5).counts["exploration"]
    assert allocate(103, n_survivors=5).counts["exploration"] > base


def test_A_ZERO_BUDGET_IS_NOT_AN_ERROR() -> None:
    a = allocate(0, n_survivors=5)
    assert a.allocated == 0 and all(v == 0 for v in a.counts.values())


def test_A_NEGATIVE_BUDGET_RAISES() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        allocate(-1)


def test_PORTFOLIOS_START_AT_THE_TRACKED_FIFTY_FIFTY_PRIOR_WITHOUT_EVIDENCE() -> None:
    a = adaptive_portfolios({})
    assert a.weights == pytest.approx({"exploitation": 0.5, "exploration": 0.5})
    assert a.evidence_used is False


def test_PORTFOLIOS_MOVE_ONLY_ON_TWO_SIDED_ECONOMIC_EVIDENCE() -> None:
    a = adaptive_portfolios({"exploitation": (9.0, 3.0), "exploration": (1.0, 3.0)})
    assert a.evidence_used is True
    assert a.weights["exploitation"] == pytest.approx(0.6)
    assert sum(a.weights.values()) == pytest.approx(1.0)


def test_PORTFOLIO_NUMBERS_LIVE_IN_POLICY_NOT_IMPLEMENTATION() -> None:
    policy = {
        "portfolio_prior": {"exploitation": 0.2, "exploration": 0.8},
        "portfolio_bounds": {"exploitation": [0.1, 0.3], "exploration": [0.7, 0.9]},
        "prior_strength": 2.0,
    }
    a = adaptive_portfolios({}, policy=policy)
    assert a.weights == pytest.approx({"exploitation": 0.2, "exploration": 0.8})


# -------------------------------------------------------------------------- the anti-rut floors

def test_EXPLORATION_CANNOT_BE_STARVED_BY_A_WINNING_STREAK() -> None:
    """THE RUT, DIRECTLY. A run of exploitation success reweights toward exploitation, which
    produces more exploitation success, which reweights further. Every step is locally correct and
    the destination is a local maximum the desk can no longer see out of. The floor is what makes
    that loop impossible to close."""
    greedy = {"exploitation": 0.97, "recombination": 0.03, "exploration": 0.0,
              "falsification": 0.0, "wildcard": 0.0}
    w = apply_floors(greedy)
    assert w["exploration"] >= FLOORS["exploration"]
    assert w["falsification"] >= FLOORS["falsification"]
    assert sum(w.values()) == pytest.approx(1.0)

    a = allocate(1000, weights=greedy, n_survivors=5)
    assert a.counts["exploration"] >= 100, "a winning streak starved exploration to nothing"


def test_A_FLOOR_SURVIVES_RENORMALISATION() -> None:
    """The subtle bug this is here for: raising a mode to its floor and then renormalising
    EVERYTHING scales it straight back down, so the floor silently does not hold. Only the
    remainder may be renormalised."""
    w = apply_floors({"exploitation": 1.0, "recombination": 0.0, "exploration": 0.0,
                      "falsification": 0.0, "wildcard": 0.0})
    assert w["exploration"] == pytest.approx(FLOORS["exploration"])
    assert w["falsification"] == pytest.approx(FLOORS["falsification"])


def test_WEIGHTS_ALREADY_ABOVE_THEIR_FLOOR_ARE_NOT_DRAGGED_DOWN_TO_IT() -> None:
    """A floor is a minimum, not a target -- the same distinction L1.50 makes about the coverage
    ratchet. An allocator that pinned exploration AT 10% would cap the very thing it protects."""
    generous = {"exploitation": 0.2, "recombination": 0.2, "exploration": 0.5,
                "falsification": 0.05, "wildcard": 0.05}
    assert apply_floors(generous)["exploration"] == pytest.approx(0.5)


def test_ALL_ZERO_WEIGHTS_FALL_BACK_TO_EVEN_RATHER_THAN_DIVIDING_BY_ZERO() -> None:
    w = apply_floors(dict.fromkeys(MODES, 0.0))
    assert sum(w.values()) == pytest.approx(1.0)
    assert all(v > 0 for v in w.values())


# ----------------------------------------------------------------- exploitation of an empty set

def test_WITH_NO_SURVIVORS_THE_BUDGET_MOVES_TO_MODES_THAT_CAN_RUN() -> None:
    """THE DESK'S ACTUAL STATE: 434 candidates, 0 survivors. `exploitation`, `recombination` and
    `falsification` all act on EXISTING survivors, so with none they cannot run at all. Handing
    them 75% of the budget would report a full allocation while doing a quarter of the work -- and
    the percentages would still sum to one, so nothing would look wrong."""
    a = allocate(1000, n_survivors=0)
    assert a.counts["exploitation"] == 0
    assert a.counts["recombination"] == 0
    assert a.counts["falsification"] == 0
    assert a.allocated == 1000, "the freed budget vanished instead of being reassigned"
    assert a.counts["exploration"] > 0
    assert any("NO SURVIVORS" in n for n in a.notes), "the reassignment must be stated, not silent"


def test_WITH_SURVIVORS_THE_DEFAULT_SPLIT_IS_UNCHANGED() -> None:
    """The other half of the bar: the empty-set branch must not fire when there IS something to
    exploit, or the allocator would permanently refuse to deepen a real seam."""
    a = allocate(1000, n_survivors=3)
    assert a.counts["exploitation"] == 400
    assert not a.notes


def test_NOTHING_RUNNABLE_REPORTS_NOT_MEASURED_RATHER_THAN_ZERO() -> None:
    """No survivors AND no survivor-independent mode carries weight. Emitting a tidy all-zero
    allocation would read as 'nothing to do'; it means 'this cannot be computed'. L1.28a."""
    a = allocate(100, weights={"exploitation": 1.0, "recombination": 0.0, "exploration": 0.0,
                               "falsification": 0.0, "wildcard": 0.0},
                 n_survivors=0, floors={})
    assert a.allocated == 0
    assert any("NOT MEASURED" in n for n in a.notes)


# ------------------------------------------------------------------------ coverage vs knowledge

def test_AN_UNDERPOWERED_CELL_IS_NOT_COVERAGE() -> None:
    """A cell tested on 8 bars taught the desk nothing. Counting it as covered makes the report
    claim the space was searched when it was skimmed -- and then `weakest` points the next batch
    away from the region that most needs it."""
    tested = [{"operator": "ratio", "horizon": "1d", "regime": "all", "n": 8}]
    rep = coverage_report(_SPACE, tested, min_n=30)
    assert rep.underpowered == 1
    assert rep.n_tested_cells == 0
    assert rep.by_dimension["operator"] == 0.0
    assert "ratio" in rep.uncovered["operator"]


def test_A_POWERED_CELL_COUNTS() -> None:
    tested = [{"operator": "ratio", "horizon": "1d", "regime": "all", "n": 500}]
    rep = coverage_report(_SPACE, tested, min_n=30)
    assert rep.n_tested_cells == 1
    assert rep.by_dimension["operator"] == pytest.approx(1 / 5)
    assert rep.by_dimension["horizon"] == pytest.approx(1 / 4)
    assert "ratio" in rep.covered["operator"]


def test_A_MISSING_OR_JUNK_N_IS_TREATED_AS_UNPOWERED() -> None:
    """A row with no observation count is a row that cannot demonstrate power. Defaulting it to
    'covered' would let any malformed result inflate the coverage number."""
    for row in ({"operator": "lead"}, {"operator": "lead", "n": None},
                {"operator": "lead", "n": "many"}):
        rep = coverage_report(_SPACE, [row], min_n=30)
        assert rep.underpowered == 1
        assert rep.by_dimension["operator"] == 0.0


def test_AN_EMPTY_HISTORY_IS_ZERO_COVERAGE_NOT_AN_ERROR() -> None:
    """The desk's starting state, and the state after a transport blocker. It must report zero
    across the board rather than raise inside a reporting pass."""
    rep = coverage_report(_SPACE, [])
    assert all(v == 0.0 for v in rep.by_dimension.values())
    assert rep.n_tested_cells == 0 and rep.underpowered == 0


def test_THE_WEAKEST_DIMENSION_IS_DETERMINISTIC() -> None:
    """A report that reorders between runs cannot be diffed, and this one is meant to be read
    every cycle."""
    tested = [{"operator": o, "horizon": "1d", "regime": "all", "n": 99}
              for o in ("interaction", "condition", "divergence", "ratio", "lead")]
    rep = coverage_report(_SPACE, tested, min_n=30)
    assert rep.by_dimension["operator"] == pytest.approx(1.0)
    assert rep.weakest in ("horizon", "regime")
    assert rep.weakest == coverage_report(_SPACE, tested, min_n=30).weakest


def test_UNKNOWN_VALUES_IN_HISTORY_DO_NOT_INFLATE_COVERAGE() -> None:
    """A tested row naming an operator outside the declared space must not push coverage above
    100% -- coverage is a fraction OF THE DECLARED SPACE, and a value nobody declared is a schema
    drift to notice, not a cell to credit."""
    tested = [{"operator": "quantum_entanglement", "horizon": "1d", "regime": "all", "n": 99}]
    rep = coverage_report(_SPACE, tested, min_n=30)
    assert rep.by_dimension["operator"] == 0.0
    assert all(v <= 1.0 for v in rep.by_dimension.values())


def test_gap_lines_NAMES_THE_UNDERPOWERED_COUNT_OUT_LOUD() -> None:
    """The number has to reach the human reading the report, or the distinction between 'searched'
    and 'skimmed' exists only inside the dataclass."""
    tested = [{"operator": "ratio", "horizon": "1d", "regime": "all", "n": 3}]
    lines = "\n".join(gap_lines(coverage_report(_SPACE, tested, min_n=30)))
    assert "underpowered" in lines and "EXCLUDED" in lines
    assert "WEAKEST DIMENSION" in lines


# ------------------------------------------------------- exhaustion is a claim, not a default

def test_A_BARE_EXHAUSTION_CLAIM_IS_REJECTED() -> None:
    """THE INVALID INFERENCE THIS EXISTS TO BLOCK: "we tested every combination expressible from
    our current feature set" -> "there are no worthwhile hypotheses left". A feature set is not a
    hypothesis space; it is the alphabet. Four series support levels, changes, ratios, ranks,
    z-scores, acceleration, persistence, interactions, conditional and nonlinear and
    regime-dependent and lead/lag relationships, and combinations of all of them."""
    v = exhaustion_claim("funding family", {})
    assert v.accepted is False
    assert len(v.missing_axes) == len(EXHAUSTION_AXES)
    assert any("UNEXAMINED" in r for r in v.reasons)


def test_AN_AXIS_ABSENT_FROM_THE_EVIDENCE_IS_NOT_AN_AXIS_AT_100() -> None:
    """SILENCE IS HOW THIS CHECK GETS DEFEATED. A caller submits the three axes it happens to
    measure, all clear the bar, and the claim passes while interaction depth, cross-domain
    transfer and model class were never considered at all."""
    v = exhaustion_claim("momentum", {"feature": 1.0, "operator": 1.0, "horizon": 1.0})
    assert v.accepted is False
    assert "interaction_depth" in v.missing_axes
    assert "cross_domain" in v.missing_axes
    assert v.unsupported == (), "a missing axis must not be reported as a failing one"


def test_MISSING_AND_WEAK_ARE_REPORTED_SEPARATELY() -> None:
    """They mean different things: unfinished work versus unexamined work, and the response to
    each is different."""
    cov = dict.fromkeys(EXHAUSTION_AXES, 1.0)
    cov["regime"] = 0.30
    del cov["model"]
    v = exhaustion_claim("carry", cov)
    assert v.unsupported == ("regime",)
    assert v.missing_axes == ("model",)
    assert not v.accepted


def test_A_GENUINELY_SATURATED_REGION_CAN_BE_RETIRED() -> None:
    """The claim is not always wrong, and a rule of "never stop generating" would burn the budget
    on a dead seam forever -- ten thousand variants of RSI-plus-momentum genuinely add nothing.
    The standard is DEMONSTRATED, per axis, at a named scope."""
    v = exhaustion_claim("rsi x momentum", dict.fromkeys(EXHAUSTION_AXES, 0.99))
    assert v.accepted is True
    assert any("THIS REGION only" in r for r in v.reasons)
    assert any("reopens it" in r for r in v.reasons), (
        "an accepted claim must state its own expiry -- a new feature, venue, regime or "
        "transformation reopens the region, and an acceptance with no expiry becomes permanent")


def test_THE_BAR_IS_SHORT_OF_TOTALITY_ON_PURPOSE() -> None:
    """Demanding literal 100% would make exhaustion unfalsifiable in the other direction, and a
    region genuinely worked to 95% should be abandonable."""
    assert 0.9 <= EXHAUSTION_BAR < 1.0
    assert exhaustion_claim("x", dict.fromkeys(EXHAUSTION_AXES, 0.96)).accepted is True
    assert exhaustion_claim("x", dict.fromkeys(EXHAUSTION_AXES, 0.94)).accepted is False


def test_THE_SCOPE_TRAVELS_WITH_THE_VERDICT() -> None:
    """"Exhausted" with no named scope is the unfalsifiable version of the claim. The scope is what
    makes it checkable later."""
    v = exhaustion_claim("funding x OI at 1h", dict.fromkeys(EXHAUSTION_AXES, 1.0))
    assert v.scope == "funding x OI at 1h"
    assert "funding x OI at 1h" in " ".join(v.reasons)
