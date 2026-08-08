"""BEHAVIORAL tests for the anti-round-trip engine — the specification asked for behaviour, not
imports, and the difference matters here more than anywhere else on the desk.

An import test on this module would pass on a version that returned 1.0 from every function. What
these pin is the ECONOMICS: that a full round trip scores zero however high the peak was, that
prior gains buy no risk privilege, that cash can win, and that an unmeasured edge cannot be sized.
"""

from __future__ import annotations

import math

import pytest

from libs.portfolio.wealth_retention import (
    MIN_PATH_FOR_A_VERDICT,
    NavPath,
    RiskyProposal,
    gain_retention_ratio,
    kelly_fraction,
    marginal_verdict,
    maximum_giveback,
    realized_log_growth,
    reserve_option_value,
    round_trip_ratio,
    summarise,
    wealth_at_risk,
)


def _ramp(start: float, end: float, n: int) -> list[float]:
    """Geometric path from start to end in n marks."""
    step = (end / start) ** (1.0 / (n - 1))
    return [start * step ** i for i in range(n)]


# --------------------------------------------------------------- the round trip itself

def test_a_full_round_trip_scores_zero_log_growth_however_high_the_peak() -> None:
    """THE HEADLINE CLAIM. 1x -> 30x -> 1x has a magnificent maximum and produced nothing.

    Every metric except realised log growth calls this path a success. If this test ever fails
    because the growth is positive, the module has started measuring the peak."""
    up = _ramp(1000.0, 30_000.0, 40)
    down = _ramp(30_000.0, 1000.0, 40)[1:]
    path = NavPath(nav=tuple(up + down))
    g = realized_log_growth(path)
    assert g is not None
    assert abs(g) < 1e-9, f"a completed round trip produced {g}, which is not zero"
    assert round_trip_ratio(path) == pytest.approx(1.0, abs=1e-6)
    assert gain_retention_ratio(path) == pytest.approx(0.0, abs=1e-6)


def test_a_partial_giveback_is_measured_not_rounded_away() -> None:
    path = NavPath(nav=tuple(_ramp(1000.0, 4000.0, 30) + _ramp(4000.0, 2500.0, 20)[1:]))
    rt = round_trip_ratio(path)
    assert rt is not None
    # peak index 4.0 => peak gain 3.0; final index 2.5 => final gain 1.5.
    # Half the accumulated gain handed back, and half retained.
    assert rt == pytest.approx(0.5, abs=0.02)
    assert (gain_retention_ratio(path) or 0.0) == pytest.approx(0.5, abs=0.02)


def test_maximum_giveback_is_a_property_of_the_policy_not_of_today() -> None:
    """A path that crashed and fully recovered still reports the crash. Current drawdown would be
    zero here, and reporting only that is how a process's willingness to hand back a stack becomes
    invisible."""
    path = NavPath(nav=tuple(_ramp(100.0, 200.0, 15) + _ramp(200.0, 80.0, 15)[1:]
                             + _ramp(80.0, 220.0, 15)[1:]))
    mg = maximum_giveback(path.nav)
    assert mg is not None and mg == pytest.approx(0.6, abs=0.01)


def test_ruin_is_an_absorbing_state_not_a_large_negative_number() -> None:
    path = NavPath(nav=(1000.0, 1100.0, 0.0000001))
    # -100% within rounding: log growth must not come back as a merely bad float
    p2 = NavPath(nav=tuple([1000.0] * 40))
    assert realized_log_growth(p2) == pytest.approx(0.0)
    losses = NavPath(nav=(100.0, 0.0))
    assert realized_log_growth(losses) == float("-inf")
    del path


# ------------------------------------------------------------- flows are not returns

def test_a_deposit_is_not_a_return() -> None:
    """The easiest way to manufacture a good equity curve is to fund it. Growth must be flat."""
    nav = [1000.0]
    flows = [0.0]
    for _ in range(35):
        nav.append(nav[-1] + 100.0)
        flows.append(100.0)
    path = NavPath(nav=tuple(nav), flows=tuple(flows))
    g = realized_log_growth(path)
    assert g is not None and abs(g) < 1e-9, (
        f"a pure funding schedule reported {g} of growth -- deposits are being counted as returns")


def test_a_withdrawal_is_not_a_giveback() -> None:
    nav, flows = [1000.0], [0.0]
    for _ in range(35):
        nav.append(nav[-1] * 1.01)
        flows.append(0.0)
    # take half out
    nav.append(nav[-1] * 0.5)
    flows.append(-nav[-2] * 0.5)
    path = NavPath(nav=tuple(nav), flows=tuple(flows))
    rt = round_trip_ratio(path)
    assert rt is None or rt < 0.05, f"a withdrawal was scored as a round trip ({rt})"


# ------------------------------------------------------------------- marginal sizing

def test_an_unmeasured_edge_cannot_be_sized() -> None:
    """Absence must not resolve to a green light -- the specific defect class this desk names
    WS-005, pointed at the sizing decision."""
    p = RiskyProposal(name="mystery", edge=0.05, edge_sigma=0.0, variance=0.0)
    assert kelly_fraction(p) is None
    v, why = marginal_verdict(p, current_risky_fraction=0.0)
    assert v == "UNMEASURED"
    assert "absence is not a green light" in why


def test_uncertainty_shrinks_the_fraction_and_a_noisy_edge_gets_nothing() -> None:
    """Two proposals with the SAME point estimate and different posterior widths must not be sized
    the same. Textbook Kelly cannot tell them apart, which is why it produces round trips."""
    tight = RiskyProposal("tight", edge=0.02, edge_sigma=0.002, variance=0.04, effective_n=400)
    loose = RiskyProposal("loose", edge=0.02, edge_sigma=0.030, variance=0.04, effective_n=400)
    ft, fl = kelly_fraction(tight), kelly_fraction(loose)
    assert ft is not None and fl is not None
    assert ft > fl, "posterior width is not shrinking the allocation"
    assert fl == 0.0, "an edge smaller than its own uncertainty was still allocated capital"


def test_cash_can_beat_a_genuinely_profitable_strategy() -> None:
    """§5. A positive-edge strategy must be able to LOSE to retained capital. If it cannot, the
    allocator is structurally forced to be fully invested and the reserve exists on paper only."""
    p = RiskyProposal("small_edge", edge=0.001, edge_sigma=0.0002, variance=0.02, effective_n=500)
    rv = reserve_option_value(opportunity_arrival_rate=0.05,
                              expected_dislocation_edge=0.10, horizon_periods=30.0)
    assert rv > 0.0, "cash was priced at zero, which forces full investment"
    v, why = marginal_verdict(p, current_risky_fraction=0.10, reserve_value=rv)
    assert v == "HOLD", f"expected cash to win, got {v}: {why}"
    assert "option value" in why


def test_large_prior_gains_grant_no_risk_privilege_and_impose_no_penalty() -> None:
    """§4/§69. The marginal decision must be identical whether the desk is up 30x or flat -- past
    gains are simply not an input. A module that quietly de-risked after a win would be the
    arbitrary profit-locking rule the specification forbids, and one that levered up after a win
    would be the round trip itself."""
    p = RiskyProposal("engine", edge=0.02, edge_sigma=0.004, variance=0.05, effective_n=800)
    poor = marginal_verdict(p, current_risky_fraction=0.10, reserve_value=0.0)
    rich = marginal_verdict(p, current_risky_fraction=0.10, reserve_value=0.0)
    assert poor == rich
    flat = NavPath(nav=tuple([1000.0] * 40))
    won = NavPath(nav=tuple(_ramp(1000.0, 30_000.0, 40)))
    a = summarise(flat, proposals=(p,), current_risky_fraction=0.10)
    b = summarise(won, proposals=(p,), current_risky_fraction=0.10)
    assert a["marginal_verdicts"] == b["marginal_verdicts"], (
        "the marginal verdict changed because of past performance -- that is either a hidden "
        "profit-lock rule or a hidden martingale, and both are forbidden")


def test_overbetting_is_refused_past_the_shrunk_optimum() -> None:
    p = RiskyProposal("hot", edge=0.02, edge_sigma=0.004, variance=0.05, effective_n=800)
    f = kelly_fraction(p)
    assert f is not None
    v, why = marginal_verdict(p, current_risky_fraction=min(1.0, f + 0.10))
    assert v == "REDUCE"
    assert "unbounded" in why


def test_wealth_at_risk_is_absolute_not_a_percentage() -> None:
    """"18% at risk" reads the same at every wealth level and the whole argument is that it should
    not."""
    assert wealth_at_risk(1_000.0, 0.5, 0.4) == pytest.approx(200.0)
    assert wealth_at_risk(1_000_000.0, 0.5, 0.4) == pytest.approx(200_000.0)


# -------------------------------------------------------------------------- reporting

def test_a_short_path_reports_unmeasured_rather_than_a_small_sample_ratio() -> None:
    rep = summarise(NavPath(nav=tuple(_ramp(100.0, 300.0, 9))))
    assert rep["measured"] is False
    assert "UNMEASURED" in str(rep["headline"])
    assert "not 'no round-trip risk detected'" in str(rep["headline"])
    assert "GAIN_RETENTION_RATIO" not in rep, (
        "a 9-mark path produced a retention ratio -- that is the small-sample worship the "
        "specification forbids by name")


def test_the_report_carries_every_named_metric_once_measured() -> None:
    path = NavPath(nav=tuple(_ramp(1000.0, 5000.0, 30) + _ramp(5000.0, 2000.0, 20)[1:]))
    rep = summarise(path, current_risky_fraction=0.2)
    for k in ("GAIN_RETENTION_RATIO", "ROUND_TRIP_RATIO", "PEAK_WEALTH_AT_RISK",
              "REALIZED_LOG_GROWTH", "MAXIMUM_GIVEBACK"):
        assert k in rep, f"{k} missing from the report"
    assert "ROUND-TRIP" in str(rep["headline"])


def test_no_arbitrary_profit_lock_rule_exists_in_the_source() -> None:
    """A guard against the exact anti-pattern the spec names: "after +100%, cut risk in half".

    SCANS THE CODE, NOT THE PROSE, and the distinction is one this desk has already paid for once:
    an earlier version of a sibling test failed on the module's OWN disclaimer, which described
    the banned pattern in order to forbid it. A scanner that cannot tell a rule from a sentence
    about a rule will eventually be deleted for crying wolf, taking its real finding with it.
    """
    import ast
    import pathlib

    src = pathlib.Path("libs/portfolio/wealth_retention.py").read_text("utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        # Docstrings are the only string constants allowed to discuss the banned rule.
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            continue
        if isinstance(node, ast.Compare):
            # A comparison of an accumulated-gain name against a round multiple is the shape a
            # profit-lock rule takes when someone adds one.
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            consts = {c.value for c in ast.walk(node)
                      if isinstance(c, ast.Constant) and isinstance(c.value, int | float)}
            if names & {"gain", "peak_gain", "total_gain", "profit"} and consts & {1.0, 2.0, 100}:
                raise AssertionError(
                    f"a hard-coded profit-locking rule appeared: {ast.unparse(node)}")


def test_min_path_floor_is_not_silently_tiny() -> None:
    assert MIN_PATH_FOR_A_VERDICT >= 30
    assert math.isfinite(MIN_PATH_FOR_A_VERDICT)
