"""The stratified campaign must buy power with OBSERVATIONS, never with a loosened level.

These pin the three properties that make `stratified_campaign_gates` a power fix rather than a
multiplicity loophole. Every one of them is a way the change could silently become the opposite
of what it claims:

  1. the per-stratum level is CAMPAIGN_ALPHA/k, so family-wise error stays at 5% however the
     campaign is cut -- without this, splitting into k pieces IS the loophole;
  2. a candidate no stratum supports comes back None, so the caller must record it as untested
     rather than let it fall through as a pass;
  3. the column a candidate is handed indexes ITS OWN returns in its stratum's matrix -- a
     mis-mapping would attribute one candidate's significance to another, which is the worst
     failure available here because it promotes the wrong thing rather than nothing.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.autodiscovery.validation import stratified_campaign_gates
from libs.validation.campaign_window import CAMPAIGN_ALPHA, plan_strata, stratum_matrix


def _series(lengths: list[int], seed: int = 0) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [rng.normal(0.0, 0.01, size=n) for n in lengths]


def _mixed_lengths() -> list[int]:
    """A campaign that genuinely stratifies: a long cohort and a short one.

    Kept as small as the planner's floors allow (MIN_COHORT=12, MIN_OBS=250). The cost here is
    Romano-Wolf's bootstrap, which is linear in retained observations x n_boot -- the real
    420-candidate campaign retains 698,655 of them, so a full-size fixture would make this file
    take minutes. These pin CONTRACTS, not throughput.
    """
    return [1000] * 14 + [300] * 14


@pytest.fixture(scope="module")
def mixed_campaign() -> tuple[list[np.ndarray], object, object]:
    """Computed once: three tests read the same plan and the bootstrap is the expensive part."""
    series = _series(_mixed_lengths())
    per_candidate, plan = stratified_campaign_gates(series)
    return series, per_candidate, plan


def test_every_stratum_is_tested_at_campaign_alpha_over_k(mixed_campaign):
    """THE HONESTY PROPERTY. k families at 5% each would be ~1-(1-0.05)^k overall, not 5%."""
    _, per_candidate, plan = mixed_campaign
    k = len(plan.strata)
    assert k >= 1
    tested = [g for g in per_candidate if g is not None]
    assert tested, "the campaign produced no tested candidate at all"
    for gates, _col in tested:
        assert gates.stepdown.alpha == pytest.approx(CAMPAIGN_ALPHA / k), (
            f"stratum tested at {gates.stepdown.alpha} but k={k} demands "
            f"{CAMPAIGN_ALPHA / k} -- splitting the campaign has become a way to evade the "
            "multiplicity correction rather than pay it"
        )


def test_a_candidate_no_stratum_supports_comes_back_untested_not_passed():
    """None is the caller's signal to record 'untested'. Silence here would be a silent pass."""
    # One candidate far shorter than the rest and below MIN_OBS: it cannot join any stratum.
    series = _series([600] * 14 + [30])
    per_candidate, _plan = stratified_campaign_gates(series)
    assert per_candidate[-1] is None, "the unsupported candidate was handed campaign statistics"
    assert any(g is not None for g in per_candidate[:-1]), "the supported cohort went untested"


def test_the_column_indexes_the_candidates_own_returns(mixed_campaign):
    """THE MIS-ATTRIBUTION GUARD. column must select this candidate's column, not a neighbour's."""
    series, per_candidate, plan = mixed_campaign
    by_window = {s.n_obs: s for s in plan.strata}
    for cand, entry in enumerate(per_candidate):
        if entry is None:
            continue
        _gates, col = entry
        stratum = next(s for s in plan.strata if cand in s.keep)
        matrix = stratum_matrix(series, stratum)
        np.testing.assert_array_equal(
            matrix[:, col], series[cand][-stratum.n_obs:],
            err_msg=(f"candidate {cand} was handed column {col}, which holds a different "
                     "candidate's returns -- significance would be attributed to the wrong one"),
        )
    assert by_window, "no strata formed on a campaign built to stratify"


def test_stratifying_retains_more_observations_than_min_length_truncation():
    """The whole point: buy power with the data already on disk."""
    lengths = _mixed_lengths()
    plan = plan_strata(lengths)
    min_len_retained = min(lengths) * len(lengths)
    assert plan.obs_retained > min_len_retained, (
        f"stratification retained {plan.obs_retained:,} observations against min-length's "
        f"{min_len_retained:,} -- it is not buying anything"
    )


def test_a_uniform_campaign_still_forms_one_family_at_the_full_level():
    """No stratification to do => k=1 => alpha is CAMPAIGN_ALPHA, i.e. the old behaviour exactly."""
    series = _series([600] * 14)
    per_candidate, plan = stratified_campaign_gates(series)
    assert len(plan.strata) == 1, "a uniform-length campaign was split for no reason"
    gates, _col = next(g for g in per_candidate if g is not None)
    assert gates.stepdown.alpha == pytest.approx(CAMPAIGN_ALPHA)
