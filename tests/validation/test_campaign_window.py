"""The stratification planner must be results-blind, priced, and honest when it cannot help."""
from __future__ import annotations

import numpy as np

from libs.validation.campaign_window import (
    CAMPAIGN_ALPHA,
    MAX_STRATA,
    MIN_COHORT,
    MIN_OBS,
    _power_grid,
    detection_power,
    plan_strata,
    stratum_matrix,
)


def _realistic(n=420, seed=1):
    rng = np.random.default_rng(seed)
    lens = np.clip(rng.lognormal(np.log(1700), 0.55, n).astype(int), 310, 4000)
    lens[rng.choice(n, max(1, n // 17), replace=False)] = 310
    return lens


def test_power_grid_matches_the_scalar_form():
    """The grid duplicates expected_max_sharpe's expression inline for speed. Two copies of one
    formula drift; this is what stops the planner optimising against a stale model."""
    m = np.array([[12.0, 50.0, 200.0], [420.0, 30.0, 16.0]])
    t = np.array([[310.0, 620.0, 1250.0], [2500.0, 400.0, 3000.0]])
    grid = _power_grid(m, t, 2.0, 0.05)
    scalar = np.array([[detection_power(int(m[i, j]), int(t[i, j]), 2.0, 0.05)
                        for j in range(3)] for i in range(2)])
    assert np.max(np.abs(grid - scalar)) < 1e-12


def test_the_planner_never_sees_a_return():
    """THE SAFETY PROPERTY. plan_strata's only input is lengths, so a candidate's performance
    cannot influence which window it is judged in. A window picked after peeking at results would
    be a selection effect wearing a fix's clothes."""
    import inspect
    sig = inspect.signature(plan_strata)
    assert next(iter(sig.parameters)) == "lengths"
    src = inspect.getsource(plan_strata)
    for forbidden in ("sharpe_", "returns", "pvalue", "p_value"):
        assert forbidden not in src, f"plan_strata references {forbidden}"


def test_stratifying_beats_truncating_on_a_realistic_campaign():
    """The measurement the module exists for: min-length truncation spends the resource that buys
    power (observations) to keep the one that does not (cohort size)."""
    lens = _realistic()
    plan = plan_strata(lens)
    truncated = len(lens) * detection_power(len(lens), int(lens.min()))
    assert plan.expected_discoveries > 20 * max(truncated, 1e-9)
    assert plan.retained_fraction > 0.75          # vs 18% under truncation
    assert plan.n_tested > len(lens) // 2


def test_splitting_is_priced_so_fragmenting_cannot_buy_power_for_free():
    """Without the alpha/k penalty an earlier version fragmented to 34 minimum-size strata and
    reported a 279x gain that was mostly fictional -- 34 families at 5% each is ~82% chance of a
    false positive somewhere. Each stratum must be scored at CAMPAIGN_ALPHA/k."""
    lens = _realistic()
    plan = plan_strata(lens)
    k = len(plan.strata)
    assert k >= 1
    for s in plan.strata:
        expected = detection_power(len(s.keep), s.n_obs, alpha=CAMPAIGN_ALPHA / k)
        assert abs(s.power - expected) < 1e-12, "stratum scored at the wrong level"
    # and the level really does bite: the same shape at full alpha scores strictly higher
    s0 = plan.strata[0]
    assert detection_power(len(s0.keep), s0.n_obs, alpha=CAMPAIGN_ALPHA) > s0.power


def test_every_candidate_appears_at_most_once_and_indices_map_back():
    lens = _realistic(n=120, seed=4)
    plan = plan_strata(lens)
    seen: list[int] = []
    for s in plan.strata:
        seen.extend(s.keep)
        # a stratum's window must be supported by every one of its members
        assert all(lens[i] >= s.n_obs for i in s.keep)
        assert len(s.keep) >= MIN_COHORT and s.n_obs >= MIN_OBS
    assert len(seen) == len(set(seen)), "a candidate landed in two strata"
    assert set(seen) <= set(range(len(lens)))


def test_it_falls_back_loudly_when_nothing_clears_the_floors():
    """A builder that silently produces no campaign is worse than one that produces a weak
    campaign, because only the second is visible in the artifact."""
    plan = plan_strata([300] * 5)                  # too few candidates, too short
    assert plan.strata and plan.n_tested == 5
    assert "NO stratification met the floors" in plan.why
    assert "underpowered" in plan.why and "must not be read as evidence" in plan.why


def test_no_candidates_is_not_a_crash():
    plan = plan_strata([])
    assert plan.strata == () and plan.expected_discoveries == 0.0


def test_the_stratum_matrix_is_aligned_and_uses_the_most_recent_bars():
    series = [np.arange(float(n)) for n in (500, 400, 300)]
    from libs.validation.campaign_window import Stratum
    s = Stratum(n_obs=300, keep=(0, 1, 2), power=0.5, obs_retained=900)
    m = stratum_matrix(series, s)
    assert m.shape == (300, 3)
    # the LAST 300 observations of each, so the windows end together rather than start together
    assert m[-1, 0] == 499.0 and m[-1, 1] == 399.0 and m[-1, 2] == 299.0


def test_the_stratum_cap_sits_above_the_measured_optimum():
    """The cap was 8 on a guess and the measured optimum was 26 -- a cap below the optimum silently
    truncates the search. This asserts the chosen k is interior, so the cap is not binding."""
    lens = _realistic()
    plan = plan_strata(lens)
    assert len(plan.strata) < MAX_STRATA, (
        f"k={len(plan.strata)} is at the cap {MAX_STRATA} -- re-measure and raise it")


# --- R0263: the campaign's wall-clock is a measured field, not a docstring anecdote -----------

def test_a_costed_plan_reports_unmeasured_runtime_not_zero():
    """`plan_strata` COSTS a campaign; it never runs one, so its runtime is unknown.

    None and 0.0 must never be conflated here. Zero reads as "instant", which is the flattering
    direction and the one a reader acts on -- it is how a cost nobody has paid yet becomes a cost
    nobody believes is real.
    """
    plan = plan_strata(_realistic())
    assert plan.seconds is None
    assert plan.stratum_seconds == ()
    assert plan.parallel_speedup is None


def test_executing_a_campaign_fills_in_its_own_runtime():
    from libs.autodiscovery.validation import stratified_campaign_gates

    rng = np.random.default_rng(7)
    series = [rng.normal(0.0005, 0.01, n) for n in (900, 900, 900, 400, 400, 400)]
    _, plan = stratified_campaign_gates(series)

    assert plan.seconds is not None and plan.seconds > 0.0
    assert len(plan.stratum_seconds) == len(plan.strata)
    # The total is timed independently of the parts, so it can only ever be >= their sum.
    assert plan.seconds >= sum(plan.stratum_seconds) - 1e-6


def test_parallel_speedup_is_the_ceiling_a_per_stratum_pool_could_reach():
    """The remedy R0263 names. Strata are independent bootstraps, so a pool pays the SLOWEST
    stratum while the serial campaign pays their sum -- that ratio is the whole argument for
    parallelising instead of cutting n_boot, and it has to be measured to be made."""
    from libs.validation.campaign_window import StrataPlan

    plan = plan_strata([900] * 20)._replace(seconds=10.0, stratum_seconds=(6.0, 3.0, 1.0))
    assert plan.parallel_speedup == round(10.0 / 6.0, 2)
    # A degenerate single-stratum campaign has nothing to parallelise, and says 1.0 rather than
    # dividing by zero or claiming a speedup it cannot deliver.
    assert plan_strata([900] * 20)._replace(stratum_seconds=(4.0,)).parallel_speedup == 1.0
    assert isinstance(plan, StrataPlan)
