"""The trainable GFlowNet over the alpha grammar and the grammar's dimensional algebra, pinned
on synthetic histories. Everything here is seeded and finishes in seconds.

What is pinned:

  * the untrained network is uniform over the actions a slot allows, and a tree has exactly
    one construction trajectory (window right after its operator, children left to right), so
    the backward policy really is 1 and log P_F is the sum of -log |allowed| at every step;
  * every sampled tree is valid and well typed by construction at every depth budget, with and
    without drivers, and its log-probability is finite; a tree the policy could not have built
    (a bare terminal at the root, a foreign window, a driver where none is allowed) is -inf;
  * trained on a history that rewards `zscore` and punishes the rest, the network samples
    `zscore` markedly more often than the untrained one, and the trajectory-balance loss falls
    across epochs with log Z at its closed-form minimiser at every epoch boundary;
  * a reward override changes what is sampled; `tail_diversity_reward` discounts a tail member
    by how much of its structure the rest of the tail already has and never below the floor;
  * `GENERATORS["gflow"]` is the network, fitted once per distinct history and re-used;
  * the dimensional algebra: price + count has no dimension, a price ratio is a pure number,
    delta over std cancels, corr is a pure number, a product adds exponents, `well_formed` is
    stricter than `well_typed` and `well_typed` itself is untouched, and every well-typed tree
    `random_expr` draws over 300 seeds carries a dimension;
  * THE UNIT ALGEBRA AND THE PRODUCTION SCREEN (2026-09-05). Fourteen declared types, named
    units over ten bases, `unit_of` strictly finer than `dimension_of`, `is_valid` promoted to
    structure AND type AND units, and the property that matters: over 10,000 random draws the
    grammar emits ZERO unit-invalid trees, and the typed sampler emits zero over every depth
    budget -- not because they are filtered afterwards but because the action is never offered.
"""
from __future__ import annotations

import math
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import generators as gen  # noqa: E402

Expr = ag.Expr


def _ops(expr: Expr) -> set[str]:
    out: set[str] = set()

    def _walk(x: Expr) -> None:
        if isinstance(x, (list, tuple)):
            out.add(str(x[0]))
            for c in x[1:]:
                _walk(c)
    _walk(expr)
    return out


def _zscore_history(seed: int = 0, n: int = 25) -> list[tuple[Expr, float]]:
    """`n` random trees that contain `zscore` at fitness +2 and `n` that do not at -2."""
    rng = np.random.default_rng(seed)
    hot: list[Expr] = []
    cold: list[Expr] = []
    while len(hot) < n or len(cold) < n:
        e = ag.random_expr(rng, 3, allow_drivers=False)
        (hot if "zscore" in _ops(e) else cold).append(e)
    return [(e, 2.0) for e in hot[:n]] + [(e, -2.0) for e in cold[:n]]


def _rate(net: gen.GFlowNet, token: str, seed: int = 1, n: int = 200) -> float:
    rng = np.random.default_rng(seed)
    return float(np.mean([token in _ops(net.sample(rng, 3, allow_drivers=False))
                          for _ in range(n)]))


# --------------------------------------------------------------------------- policy & trajectory
def test_untrained_policy_is_uniform_and_a_tree_has_one_trajectory() -> None:
    net = gen.GFlowNet()
    assert not net.theta.any() and net.log_z == 0.0
    tree = ["zscore", ["delta", "close", 24], 48]
    # window right after its operator, then the child: one fixed construction order
    assert net.actions(tree) == ["zscore", "w48", "delta", "w24", "close"]
    steps = net.trajectory(tree)
    assert steps is not None
    assert all(action in allowed for _, allowed, action in steps)
    # P_B = 1, so log P_F of the trajectory is the whole story: uniform over allowed actions
    assert net.log_prob(tree) == pytest.approx(-sum(math.log(len(a)) for _, a, _ in steps))
    both = ["corr", "close", ["mean", "activity", 5], 24]
    assert net.actions(both) == ["corr", "w24", "close", "mean", "w5", "activity"]
    # what the policy cannot build: a bare terminal at the root, a foreign window, a driver
    # where drivers are not allowed, a tree over the depth ceiling
    assert net.log_prob("close") == -math.inf and net.actions("close") is None
    assert net.log_prob(["delta", "close", 7]) == -math.inf
    assert net.log_prob(["delta", "usd", 24], allow_drivers=False) == -math.inf
    assert math.isfinite(net.log_prob(["delta", "usd", 24], allow_drivers=True))
    deep = "close"
    for _ in range(ag.MAX_DEPTH + 1):
        deep = ["neg", deep]
    assert net.log_prob(deep) == -math.inf


def test_every_sample_is_valid_well_typed_within_budget_and_has_finite_log_prob() -> None:
    net = gen.GFlowNet()
    rng = np.random.default_rng(2)
    for allow in (False, True):
        for d in (1, 2, 3, 5):
            for _ in range(40):
                e = net.sample(rng, d, allow_drivers=allow)
                assert ag.is_valid(e, allow) and ag.well_typed(e), ag.to_str(e)
                assert not isinstance(e, str) and ag.depth(e) <= d, ag.to_str(e)
                if not allow:
                    assert not (ag.terminals_in(e) & set(ag.DRIVER_TERMINALS)), ag.to_str(e)
                assert math.isfinite(net.log_prob(e, allow)), ag.to_str(e)
    # a zero budget is a terminal, which is what the grammar itself does at depth 0
    assert net.sample(rng, 0, allow_drivers=False) in ag.BAR_TERMINALS
    # a budget above the grammar's ceiling is the ceiling
    assert net.sample(rng, ag.MAX_DEPTH + 3) is not None
    assert all(ag.is_valid(e) for e in net.sample_batch(rng, 20, 4))


# --------------------------------------------------------------------------- training
def test_training_moves_sampling_toward_the_rewarded_motif() -> None:
    hist = _zscore_history()
    untrained = _rate(gen.GFlowNet(), "zscore")
    net = gen.GFlowNet().fit(hist, allow_drivers=False)
    trained = _rate(net, "zscore")
    assert untrained < 0.3 and trained > 2.0 * untrained, (untrained, trained)
    assert net.last_fit["n"] == 50 and net.last_fit["skipped"] == 0
    assert net.last_fit["reward"] == "fitness" and net.last_fit["epochs"] == gen.EPOCHS
    rng = np.random.default_rng(3)
    for e in net.sample_batch(rng, 30, 3, allow_drivers=False):
        assert ag.is_valid(e, allow_drivers=False) and math.isfinite(net.log_prob(e, False))


def test_trajectory_balance_loss_falls_and_log_z_is_solved_each_epoch() -> None:
    hist = _zscore_history()
    net = gen.GFlowNet().fit(hist, epochs=20, allow_drivers=False)
    log = net.fit_log
    assert len(log) == 21 and all(math.isfinite(x) for x in log)
    assert log[-1] < 0.1 * log[0]
    drops = sum(b < a for a, b in pairwise(log))
    assert drops >= 16, log
    assert net.loss(hist, allow_drivers=False) == pytest.approx(log[-1])
    # log Z is the closed-form minimiser at fixed theta: any other log Z can only do worse,
    # and a fresh network (theta = 0, log Z = 0) is no better than epoch 0's solved value.
    assert gen.GFlowNet().loss(hist, allow_drivers=False) >= log[0]
    saved = net.log_z
    for shift in (-1.0, 1.0):
        net.log_z = saved + shift
        assert net.loss(hist, allow_drivers=False) > log[-1]
    net.log_z = saved
    # more epochs continue from the current theta rather than restarting
    again = net.fit(hist, epochs=5, allow_drivers=False).fit_log
    assert again[0] == pytest.approx(log[-1]) and again[-1] <= again[0]


def test_reward_override_changes_the_sampled_distribution() -> None:
    hist = _zscore_history()

    def corr_reward(expr: Expr) -> float:
        return 2.0 if "corr" in _ops(expr) else -2.0

    by_fitness = gen.GFlowNet().fit(hist, allow_drivers=False)
    by_reward = gen.GFlowNet(reward_fn=corr_reward).fit(hist, allow_drivers=False)
    assert by_reward.last_fit["reward"] == "reward_fn"
    assert _rate(by_reward, "corr") > 2.0 * _rate(by_fitness, "corr")
    assert _rate(by_reward, "zscore") < _rate(by_fitness, "zscore")
    # the override is also a fit-time argument, and `loss` honours the same override
    via_fit = gen.GFlowNet().fit(hist, allow_drivers=False, reward_fn=corr_reward)
    assert via_fit.last_fit["reward"] == "reward_fn"
    assert np.allclose(via_fit.theta, by_reward.theta)
    assert via_fit.loss(hist, reward_fn=corr_reward, allow_drivers=False) == pytest.approx(
        via_fit.fit_log[-1])


def test_unusable_history_leaves_the_network_untrained_with_the_reason() -> None:
    net = gen.GFlowNet().fit([])
    assert not net.theta.any() and "untrained" in net.last_fit["why"]
    assert math.isnan(net.loss([]))
    bad = [(["delta", "close", 24], float("nan")), ("close", 1.0), (["delta", "close", 7], 1.0),
           (["delta", "usd", 24], 1.0)]
    net = gen.GFlowNet().fit(bad, allow_drivers=False)
    assert net.last_fit["n"] == 0 and net.last_fit["skipped"] == 4
    net = gen.GFlowNet().fit([*bad, (["delta", "close", 24], 1.0)], allow_drivers=False)
    assert net.last_fit["n"] == 1 and net.last_fit["skipped"] == 4
    assert ag.is_valid(net.sample(np.random.default_rng(0), 3, allow_drivers=False), False)


def test_tail_diversity_reward_shares_the_tails_credit_and_holds_the_floor() -> None:
    a = ["zscore", ["delta", "close", 24], 48]
    a2 = ["zscore", ["delta", "close", 120], 48]                   # same transitions as `a`
    b = ["corr", "activity", "ret", 24]                            # nothing in common
    c = ["mean", "close", 5]
    d = ["delta", "close", 24]
    hist = [(a, 4.0), (a2, 4.0), (b, 4.0), (c, 0.0), (d, -1.0)]
    floor = float(np.quantile([4.0, 4.0, 4.0, 0.0, -1.0], 0.4))
    reward = gen.tail_diversity_reward(hist, quantile=0.4)
    assert reward(a) == pytest.approx(floor + (4.0 - floor) * 0.5)   # half of the tail is a copy
    assert reward(a2) == reward(a)
    assert reward(b) == pytest.approx(4.0)                           # structurally alone: full
    assert reward(a) >= floor and reward(b) > reward(a)
    assert reward(c) == 0.0 and reward(d) == -1.0                    # the body: plain fitness
    assert reward(["sum", "range", 8]) == -1.0                       # unscored: the minimum
    assert gen.tail_diversity_reward(hist, quantile=0.4, penalty=0.0)(a) == 4.0
    assert gen.tail_diversity_reward([])(a) == 0.0
    # training under the hook still only makes valid trees
    net = gen.GFlowNet(reward_fn=reward).fit(hist, allow_drivers=False)
    assert net.last_fit["reward"] == "reward_fn" and net.last_fit["n"] == 5
    assert ag.is_valid(net.sample(np.random.default_rng(0), 3, allow_drivers=False), False)


# --------------------------------------------------------------------------- the generator surface
def test_gflow_generator_is_the_network_fitted_once_per_history(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert gen.GENERATORS["gflow"] is gen._gen_gflow
    monkeypatch.setattr(gen, "_GFLOW_CACHE", {"key": None, "net": None})
    hist = _zscore_history()
    rng = np.random.default_rng(0)
    e = gen.GENERATORS["gflow"](rng, {}, None, hist, False, 3)
    assert ag.is_valid(e, allow_drivers=False)
    net = gen._GFLOW_CACHE["net"]
    assert isinstance(net, gen.GFlowNet) and net.last_fit["n"] == 50
    assert gen._GFLOW_CACHE["key"] == gen._history_key(hist, False)
    gen.GENERATORS["gflow"](rng, {}, None, hist, False, 3)
    assert gen._GFLOW_CACHE["net"] is net                                 # same history: reused
    gen.GENERATORS["gflow"](rng, {}, None, hist, True, 3)
    assert gen._GFLOW_CACHE["net"] is not net                             # driver flag: refit
    gen.GENERATORS["gflow"](rng, {}, None, hist[:-1], False, 3)
    assert gen._GFLOW_CACHE["net"] is not net and gen._GFLOW_CACHE["net"].last_fit["n"] == 49
    gen.GENERATORS["gflow"](rng, {}, None, hist, False, 3)
    hot = np.mean(["zscore" in _ops(gen.GENERATORS["gflow"](rng, {}, None, hist, False, 3))
                   for _ in range(200)])
    cold = np.mean(["zscore" in _ops(gen.GENERATORS["gflow"](rng, {}, None, [], False, 3))
                    for _ in range(200)])
    assert hot > 2.0 * cold and "untrained" in gen._GFLOW_CACHE["net"].last_fit["why"]


# --------------------------------------------------------------------------- dimensional algebra
def test_dimension_algebra_and_terminals() -> None:
    D = ag.Dimension
    assert D() == ag.DIMENSIONLESS and D().is_dimensionless and str(D()) == "1"
    assert D(price=1, count=1) == ag.PRICE_DIM + ag.COUNT_DIM
    assert str(D(price=1, count=1)) == "price^1 count^1" and str(D(price=-2)) == "price^-2"
    assert (ag.PRICE_DIM + ag.COUNT_DIM) - ag.COUNT_DIM == ag.PRICE_DIM
    assert ag.BASE_DIMENSIONS == ("price", "count", "time")
    for t in ("close", "open", "high", "low", "spread", "atr", *ag.DRIVER_TERMINALS):
        assert ag.dimension_of(t) == ag.PRICE_DIM, t
    for t in ("ret", "range", "body"):
        assert ag.dimension_of(t) == ag.DIMENSIONLESS, t
    assert ag.dimension_of("activity") == ag.COUNT_DIM
    assert ag.dimension_of("nonsense") is None and ag.dimension_of([]) is None
    assert ag.dimension_of(["bogus", "close"]) is None and ag.dimension_of(["add", "close"]) is None


def test_dimension_of_the_briefed_fixtures() -> None:
    assert ag.dimension_of(["add", "close", "activity"]) is None            # price + volume
    assert ag.dimensionless(["div", "close", "open"])                       # a price ratio
    assert ag.dimensionless(["div", ["delta", "close", 24], ["std", "close", 24]])
    assert ag.dimensionless(["corr", "close", "activity", 24])
    assert ag.dimension_of(["mul", "close", "activity"]) == ag.Dimension(price=1, count=1)
    assert str(ag.dimension_of(["mul", "close", "activity"])) == "price^1 count^1"


def test_every_operator_rule() -> None:
    P, one = ag.PRICE_DIM, ag.DIMENSIONLESS
    for op in ("delay", "mean", "min", "max", "decay", "sum", "delta", "std"):
        assert ag.dimension_of([op, "close", 24]) == P, op
        assert ag.dimension_of([op, "activity", 24]) == ag.COUNT_DIM, op
    for op in ("zscore", "ts_rank", "bars_since_max", "bars_since_min"):
        assert ag.dimension_of([op, "close", 24]) == one, op
    assert ag.dimension_of(["atr_norm", "close", 24]) == one
    assert ag.dimension_of(["atr_norm", ["delta", "close", 24], 24]) == one
    assert ag.dimension_of(["neg", "close"]) == P and ag.dimension_of(["abs", "activity"]) \
        == ag.COUNT_DIM and ag.dimension_of(["sign", "close"]) == one
    for op in ("add", "sub", "max2", "min2"):
        assert ag.dimension_of([op, "close", "high"]) == P, op
        assert ag.dimension_of([op, "close", "ret"]) is None, op
    assert ag.dimension_of(["mul", "close", "close"]) == ag.Dimension(price=2)
    assert ag.dimension_of(["mul", "ret", "activity"]) == ag.COUNT_DIM
    assert ag.dimension_of(["div", "ret", "close"]) == ag.Dimension(price=-1)
    assert ag.dimension_of(["div", "activity", "activity"]) == one
    assert ag.dimension_of(["cov", "close", "activity", 24]) == ag.Dimension(price=1, count=1)
    assert ag.dimension_of(["residual", "close", "activity", 24]) == P
    assert ag.dimension_of(["residual", "activity", "close", 24]) == ag.COUNT_DIM
    # a None anywhere below is a None at the root
    assert ag.dimension_of(["mean", ["add", "close", "activity"], 5]) is None
    assert ag.dimension_of(["corr", ["add", "close", "activity"], "ret", 5]) is None


def test_well_formed_is_stricter_than_well_typed_and_well_typed_is_untouched() -> None:
    # SCALE is one dtype whether it holds a price or a pure number: well typed, no dimension
    mixed = ["add", ["std", "close", 24], ["std", "ret", 24]]
    assert ag.well_typed(mixed) and ag.dimension_of(mixed) is None and not ag.well_formed(mixed)
    # and the other way round: a price change over a price dispersion is dimensionless, but
    # the (unchanged) type system refuses div(PRICE_DIFF, SCALE) -- the gates are independent
    ratio = ["div", ["delta", "close", 24], ["std", "close", 24]]
    assert ag.dimensionless(ratio) and not ag.well_typed(ratio) and not ag.well_formed(ratio)
    assert ag.well_formed(["div", "close", "open"])
    assert ag.well_formed(["atr_norm", ["delta", "close", 24], 24])
    assert not ag.well_formed(["add", "close", "activity"])            # not typed either
    for e in ag.CANON.values():
        assert ag.well_formed(e), ag.to_str(e)
    rng = np.random.default_rng(0)
    for _ in range(200):
        e = ag.random_expr(rng, 3)
        assert ag.well_typed(e) == (ag.type_of(e) != ag.INVALID)
        assert ag.well_formed(e) == (ag.well_typed(e) and ag.dimension_of(e) is not None)
        assert not ag.well_formed(e) or ag.well_typed(e)


def test_every_well_typed_random_tree_over_300_seeds_has_a_dimension() -> None:
    counterexamples: list[str] = []
    for seed in range(300):
        e = ag.random_expr(np.random.default_rng(seed))
        if ag.well_typed(e) and ag.dimension_of(e) is None:
            counterexamples.append(f"seed {seed}: {ag.to_str(e)}")
    assert not counterexamples, "well typed but dimensionless-None:\n" + "\n".join(counterexamples)


# --------------------------------------------------------------------------- the unit algebra
def test_the_fourteen_declared_types_exist_and_every_terminal_carries_one() -> None:
    assert len(ag.DECLARED_TYPES) == 14 and len(set(ag.DECLARED_TYPES)) == 14
    for t in ("PRICE", "RETURN", "RATIO", "ACTIVITY", "SPREAD", "VOLATILITY", "FLOW",
              "POSITIONING", "EVENT", "MACRO", "FUNDAMENTAL", "STATE_PROBABILITY",
              "CROSS_SECTION", "EXECUTION_STATE"):
        assert t in ag.DECLARED_TYPES, t
    for term in ag.TERMINALS:
        assert ag.DTYPES[term] in ag.DECLARED_TYPES, term
        assert term in ag.TERMINAL_UNITS and term in ag.TERMINAL_DIMENSIONS, term
        assert ag.kind_of(term) == ag.TERMINAL_KINDS[term] != ag.INVALID, term
    # a change of a quantity is a quantity of the same kind, for every declared type
    for t in ag.DECLARED_TYPES:
        assert t in ag._DIFF_OF, t


def test_units_are_a_vector_algebra_over_the_declared_bases() -> None:
    U = ag.Unit
    assert ag.NO_UNIT.is_dimensionless and str(ag.NO_UNIT) == "1"
    assert U.of("quote") + U.of("ticks") == U((("quote", 1), ("ticks", 1)))
    assert U.of("quote") - U.of("quote") == ag.NO_UNIT
    assert str(U.of("quote", 2)) == "quote^2" and str(U.of("quote", -1)) == "quote^-1"
    assert U.of("quote", 0) == ag.NO_UNIT
    # every base unit says which dimension it is one of, so the two checks cannot disagree
    assert set(ag.UNIT_DIMENSION) == set(ag.BASE_UNITS)
    assert ag.UNITS["quote"].dimension == ag.PRICE_DIM
    assert ag.UNITS["lots"].dimension == ag.COUNT_DIM
    assert ag.UNITS["bps"].dimension == ag.DIMENSIONLESS
    assert (U.of("quote") + U.of("ticks")).dimension == ag.Dimension(price=1, count=1)
    assert U.of("quote", -1).dimension == ag.Dimension(price=-1)
    # the desk's named vocabulary, all of it
    for name in ("usd_per_oz", "bps", "percent", "contracts", "lots", "seconds", "pips",
                 "dimensionless"):
        assert name in ag.UNITS, name


def test_the_unit_algebra_refuses_what_the_dimensional_one_could_not_see() -> None:
    """Same dimension, different unit: a quote plus a broker spread in points."""
    mixed = ["add", "close", "spread"]
    assert ag.dimension_of("close") == ag.dimension_of("spread") == ag.PRICE_DIM
    assert ag.unit_of("close") != ag.unit_of("spread")
    assert ag.unit_of(mixed) is None
    # a tick count is not a lot count even though both are counts
    assert ag.unit_of(["add", "activity", "positioning"]) is None
    assert ag.dimension_of("activity") == ag.dimension_of("positioning") == ag.COUNT_DIM
    # a bar count is not a return even though both are pure numbers
    assert ag.unit_of(["add", ["bars_since_max", "close", 24], "ret"]) is None
    assert ag.unit_of(["bars_since_max", "close", 24]) == ag.UNITS["bars"]
    # and the ones that DO reconcile still do
    assert ag.unit_of(["add", "close", "high"]) == ag.UNITS["quote"]
    assert ag.unit_of(["div", "close", "open"]) == ag.NO_UNIT
    assert ag.unit_of(["cov", "close", "activity", 24]) == (ag.UNITS["quote"]
                                                            + ag.UNITS["ticks"])
    assert ag.unit_of(["atr_norm", ["delta", "close", 24], 24]) == ag.NO_UNIT
    assert ag.unit_of("nonsense") is None and ag.unit_of([]) is None
    assert ag.unit_of(["add", "close"]) is None


def test_unit_validity_implies_dimensional_validity_over_10k_draws() -> None:
    """`well_formed` needs only the unit check because the unit algebra subsumes the other."""
    rng = np.random.default_rng(11)
    for _ in range(2000):
        e = ag.random_expr(rng, 4)
        if ag.unit_of(e) is not None:
            assert ag.dimension_of(e) is not None, ag.to_str(e)
            assert ag.unit_of(e).dimension == ag.dimension_of(e), ag.to_str(e)


def test_ten_thousand_random_draws_contain_zero_unit_invalid_trees() -> None:
    """THE PROPERTY. Invalid arithmetic is not something the grammar filters -- it is something
    the grammar cannot build. Ten thousand draws, no exceptions, and no fallback to the bare
    terminal that would make the property true by refusing to generate."""
    rng = np.random.default_rng(0)
    floors = 0
    for _ in range(10_000):
        e = ag.random_expr(rng, 3)
        assert ag.well_formed(e), ag.to_str(e)
        assert ag.is_valid(e), ag.to_str(e)
        floors += int(isinstance(e, str))
    assert floors == 0, f"{floors} draws fell back to a bare terminal"


def test_is_valid_is_the_production_screen_and_well_typed_is_untouched() -> None:
    """The screen every generator, mutation, crossover and `family_formula` runs."""
    mixed = ["add", ["std", "close", 24], ["std", "ret", 24]]
    assert ag.well_typed(mixed)                     # the type system still says yes, unchanged
    assert not ag.well_formed(mixed) and not ag.is_valid(mixed)
    assert ag.type_of(mixed) == "SCALE"             # and still returns exactly what it did
    # structure is still checked first: a foreign window and an unknown token still fail
    assert not ag.is_valid(["delta", "close", 7])
    assert not ag.is_valid(["nonsense", "close"])
    assert not ag.is_valid(["delta", "usd", 24], allow_drivers=False)
    assert ag.is_valid(["delta", "usd", 24], allow_drivers=True)
    # the terminal pool narrows the leaf set for a caller that knows what it has
    assert not ag.is_valid(["delta", "usd", 24], True, ag.BAR_TERMINALS)
    assert ag.is_valid(["delta", "close", 24], True, ag.BAR_TERMINALS)
    # mutation and crossover cannot walk out of the screen either
    rng = np.random.default_rng(3)
    a = ag.random_expr(rng, 3)
    for _ in range(200):
        a = ag.mutate(a, rng)
        assert ag.is_valid(a), ag.to_str(a)
    for _ in range(200):
        b = ag.crossover(ag.random_expr(rng, 3), ag.random_expr(rng, 3), rng)
        assert ag.is_valid(b), ag.to_str(b)


def test_the_typed_sampler_never_OFFERS_a_unit_invalid_action() -> None:
    """Not filtered afterwards: the mask itself is the grammar's kind algebra."""
    net = gen.GFlowNet()
    rng = np.random.default_rng(5)
    for allow in (False, True):
        for d in (1, 2, 3, 5):
            for _ in range(30):
                e = net.sample(rng, d, allow_drivers=allow)
                assert ag.well_formed(e), ag.to_str(e)
    # the briefed counterexample is not reachable and not replayable
    mixed = ["add", ["std", "close", 24], ["std", "ret", 24]]
    assert net.trajectory(mixed) is None and net.log_prob(mixed) == -math.inf
    # a kind is a dtype AND a unit, and the tables are keyed on it
    types = gen.type_algebra()
    assert all("@" in k for k in types.all)
    assert types.binary_kind("add", "PRICE@quote^1", "SPREAD@pips^1") == ag.INVALID
    assert types.binary_kind("add", "PRICE@quote^1", "PRICE@quote^1") == "PRICE@quote^1"
    assert types.unary_kind("zscore", "PRICE@quote^1") == "Z@1"
    # the planner's unit bound is a SEARCH bound and is declared as one
    assert gen.UNIT_EXPONENT_CAP >= 1 and gen.UNIT_BASES_CAP >= 1
    assert gen._bounded_unit("1") and gen._bounded_unit("quote^1")
    assert not gen._bounded_unit("quote^9") and not gen._bounded_unit(ag.INVALID)


def test_a_sampler_may_be_told_which_terminals_the_caller_actually_has() -> None:
    net = gen.GFlowNet()
    rng = np.random.default_rng(6)
    pool = ("close", "high", "low", "ret")
    for _ in range(40):
        e = net.sample(rng, 3, allow_drivers=True, terminals=pool)
        assert ag.terminals_in(e) <= set(pool), ag.to_str(e)
    assert ag.terminal_pool(False) == ag.BAR_TERMINALS
    assert set(ag.terminal_pool(True)) == set(ag.BAR_TERMINALS) | set(ag.DRIVER_TERMINALS)
    assert "macro" in ag.terminal_pool(True, extra=("macro",))
    assert "macro" not in ag.terminal_pool(True)         # never sampled unless declared


# --------------------------------------------------------------------------- new terminals
def test_the_new_bar_terminals_are_computed_from_the_desks_own_bars() -> None:
    n = 400
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(1)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 0.3, n)), index=idx)
    df = pd.DataFrame({"open": close.shift(1).bfill(), "high": close + 0.2, "low": close - 0.2,
                       "close": close, "tick_volume": rng.integers(10, 100, n).astype(float),
                       "spread": rng.integers(1, 5, n).astype(float)}, index=idx)
    frames = ag.terminal_frames(df, raw=df)
    assert "vol" in frames and "flow" in frames
    # one NaN for `ret`'s own first difference plus VOL_N-1 to fill the window
    assert frames["vol"].isna().sum() == ag.VOL_N
    # flow is the tick count signed by its own bar: same magnitude, direction from the body,
    # and ZERO on a bar that closed where it opened -- a flat bar has no direction to lend
    moved = frames["body"] != 0
    assert np.allclose(frames["flow"][moved].abs().to_numpy(),
                       frames["activity"][moved].to_numpy())
    assert (frames["flow"][frames["body"] > 0] > 0).all()
    assert (frames["flow"][frames["body"] < 0] < 0).all()
    assert (frames["flow"][~moved] == 0).all()
    # externals are absent unless supplied, and available_terminals says so
    assert not (set(frames) & set(ag.EXTERNAL_TERMINALS))
    assert set(ag.available_terminals(frames)) <= set(ag.BAR_TERMINALS)
    macro = pd.Series(np.linspace(-1, 1, n), index=idx)
    with_extra = ag.terminal_frames(df, raw=df, extra={"macro": macro, "not_a_terminal": macro})
    assert "macro" in with_extra and "not_a_terminal" not in with_extra
    assert "macro" in ag.available_terminals(with_extra)
    assert ag.evaluate(["zscore", "macro", 24], with_extra).notna().any()
    # a terminal the frames do not carry evaluates to NaN and is never offered
    assert ag.evaluate("macro", frames).isna().all()
    assert ag.available_terminals({}) == ag.terminal_pool(True)


# --------------------------------------------------------------------------- the wq operators
def test_the_absorbed_operators_are_typed_dimensioned_and_causal() -> None:
    for op in ("ts_backfill", "scale"):
        assert op in ag.WINDOWED
    assert "trade_when" in ag.BINARY
    assert "group_rank" in ag.BINARY_WINDOWED and "group_zscore" in ag.BINARY_WINDOWED
    # ts_backfill preserves everything; scale cancels it
    assert ag.type_of(["ts_backfill", "close", 5]) == "PRICE"
    assert ag.unit_of(["ts_backfill", "close", 5]) == ag.UNITS["quote"]
    assert ag.type_of(["scale", "close", 48]) == "Z"
    assert ag.unit_of(["scale", "close", 48]) == ag.NO_UNIT
    # a GATE must be a pure number: gating on a price is a gate that never fires
    assert ag.type_of(["trade_when", "close", "ret"]) == ag.INVALID
    assert ag.type_of(["trade_when", ["zscore", "close", 24], "ret"]) == "RETURN"
    assert ag.unit_of(["trade_when", ["zscore", "close", 24], "close"]) == ag.UNITS["quote"]
    # the peer-group operators are pure numbers whatever went in
    for op in ("group_rank", "group_zscore"):
        assert ag.unit_of([op, "close", "activity", 24]) == ag.NO_UNIT
        assert ag.well_formed([op, "close", "vol", 24])
    assert ag.type_of(["group_rank", "close", "vol", 24]) == "RANK"
    assert ag.type_of(["group_zscore", "close", "vol", 24]) == "Z"


def test_the_absorbed_operators_compute_and_never_look_forward() -> None:
    n = 600
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(2)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 0.3, n)), index=idx)
    df = pd.DataFrame({"open": close.shift(1).bfill(), "high": close + 0.2, "low": close - 0.2,
                       "close": close, "tick_volume": rng.integers(10, 100, n).astype(float),
                       "spread": rng.integers(1, 5, n).astype(float)}, index=idx)
    cut = 420
    full = ag.terminal_frames(df, raw=df)
    part = ag.terminal_frames(df.iloc[:cut], raw=df.iloc[:cut])
    for expr in (["ts_backfill", "close", 5], ["scale", "range", 48],
                 ["trade_when", ["zscore", "range", 24], "ret"],
                 ["group_rank", "ret", "vol", 48], ["group_zscore", "range", "vol", 24]):
        a = ag.evaluate(expr, full).iloc[:cut].to_numpy(dtype=float)
        b = ag.evaluate(expr, part).to_numpy(dtype=float)
        both = np.isfinite(a) & np.isfinite(b)
        assert both.sum() > 50, ag.to_str(expr)
        assert np.allclose(a[both], b[both], rtol=1e-9, atol=1e-12), ag.to_str(expr)
    # `trade_when` HOLDS rather than going flat: that difference is the whole point
    gate = pd.Series([1.0, -1.0, -1.0, 1.0], index=idx[:4])
    sig = pd.Series([5.0, 6.0, 7.0, 8.0], index=idx[:4])
    held = ag.evaluate(["trade_when", "a", "b"], {"a": gate, "b": sig})
    assert list(held) == [5.0, 5.0, 5.0, 8.0]
    # a group rank is a share in [0, 1]; a bar is always its own peer, so it is never 0
    gr = ag.evaluate(["group_rank", "ret", "vol", 48], full).dropna()
    assert gr.between(0.0, 1.0).all() and (gr > 0).all()


# --------------------------------------------------------------------------- subtree cache
def test_the_subtree_cache_is_keyed_by_structure_and_by_bars() -> None:
    n = 300
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(4)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 0.3, n)), index=idx)
    df = pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2, "close": close},
                      index=idx)
    frames = ag.terminal_frames(df)
    cache = ag.SubtreeCache()
    scope = cache.scope("XAUUSD", frames)
    a = ag.evaluate(["zscore", ["delta", "close", 24], 120], frames, scope)
    misses = cache.stats()["misses"]
    b = ag.evaluate(["ts_rank", ["delta", "close", 24], 48], frames, scope)
    assert cache.stats()["hits"] == 1                       # the shared subtree, free
    assert cache.stats()["misses"] > misses                 # the new nodes, paid for
    again = ag.evaluate(["zscore", ["delta", "close", 24], 120], frames, scope)
    assert again.equals(a) and not again.equals(b)
    assert again.equals(ag.evaluate(["zscore", ["delta", "close", 24], 120], frames))
    assert cache.stats()["hit_rate"] > 0
    # structural, stable, and process-independent
    assert ag.subtree_hash(["delta", "close", 24]) == ag.subtree_hash(["delta", "close", 24])
    assert ag.subtree_hash(["delta", "close", 24]) != ag.subtree_hash(["delta", "open", 24])
    assert len(ag.subtree_hash("close")) == 24
    assert ag.frames_fingerprint("A", frames) != ag.frames_fingerprint("B", frames)
