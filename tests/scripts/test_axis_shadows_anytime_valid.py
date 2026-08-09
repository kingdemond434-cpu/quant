"""R0187 (2026-08-05): Stage-B eligibility pays for the daily peeking it was taking for free.

`run_axis_shadows` runs on a cron and declares ELIGIBLE at the FIRST crossing of a Holm bar that
is calibrated for ONE look. That is optional stopping on a fixed-sample statistic, and it is the
desk's only path from research to capital. These tests pin the fix: eligibility now ALSO requires
the anytime-valid e-process (libs.research.anytime_valid) to cross 1/alpha at the SAME Holm alpha,
which by Ville's inequality is valid at every t simultaneously.

The load-bearing test here is `test_daily_peeking_inflates_alpha_and_the_e_process_fixes_it` --
it is the MEASUREMENT the change rests on, not an illustration of it, and it fails if either leg
of the conjunction is removed.
"""
from __future__ import annotations

import importlib

import numpy as np

from libs.research.anytime_valid import e_value
from libs.research.evidence_clock import MIN_OBS
from libs.validation.forward_stats import holm_alpha, holm_bar, nw_tstat

ras = importlib.import_module("scripts.run_axis_shadows")

_M = 12                              # the desk's forward cohort (slot_registry.MAX_FORWARD_SLOTS)
_BAR = holm_bar(_M, rank=1)          # 2.64
_ALPHA = holm_alpha(_M, rank=1)      # 0.05/12
_THR = 1.0 / _ALPHA                  # 240.0


def test_one_alpha_feeds_both_gates():
    """The fixed-sample t bar and the e-process threshold must be two readings of ONE alpha.

    If they were allowed to carry separate constants the family-wise rate would be whatever the
    looser one happened to be -- the exact class of drift that let m be counted three ways.
    """
    from statistics import NormalDist
    assert _ALPHA == 0.05 / _M
    assert round(NormalDist().inv_cdf(1.0 - _ALPHA), 2) == _BAR
    assert _THR == 1.0 / _ALPHA
    # and the rank-m candidate gets the uncorrected alpha, as Holm requires
    assert holm_alpha(_M, rank=_M) == 0.05


def test_daily_peeking_inflates_alpha_and_the_e_process_fixes_it():
    """THE MEASUREMENT. On true-null paths, evaluating the Holm bar every day and stopping at the
    first crossing realises many times the nominal alpha; requiring the e-process too does not.

    Deliberately a real simulation rather than a fixture: the claim in the docstring of
    `_stage_b_verdict` is a number about this gate, so the test that defends it has to recompute
    that number. Kept to 400 paths / 120 days so it runs in a few seconds; the committed
    1200-path/180-day figures are 0.0042 single-look, 0.0367 peeking, 0.0017 with the e-process.
    """
    rng = np.random.default_rng(2026)
    n_paths, horizon = 400, 120
    single = peek = peek_and_e = 0
    for _ in range(n_paths):
        path = rng.normal(0.0, 0.01, horizon)           # H0 is TRUE: zero mean
        if nw_tstat(path) >= _BAR:
            single += 1
        hit_peek = hit_both = False
        for n in range(MIN_OBS, horizon + 1):
            a = path[:n]
            if nw_tstat(a) >= _BAR:
                hit_peek = True
                if e_value(a) >= _THR:
                    hit_both = True
                    break
        peek += hit_peek
        peek_and_e += hit_both

    r_single, r_peek, r_both = single / n_paths, peek / n_paths, peek_and_e / n_paths
    # the one-look bar is honest at one look
    assert r_single <= 4 * _ALPHA, f"single look {r_single:.4f} should sit near alpha={_ALPHA:.5f}"
    # peeking is materially worse than a single look -- the defect being paid for
    assert r_peek > 2 * r_single, f"peeking {r_peek:.4f} vs single {r_single:.4f}"
    assert r_peek > 3 * _ALPHA, f"peeking {r_peek:.4f} should exceed nominal alpha {_ALPHA:.5f}"
    # and the conjunction brings it back under the design level
    assert r_both <= _ALPHA, f"peek+e {r_both:.4f} must not exceed nominal alpha {_ALPHA:.5f}"
    assert r_both < r_peek


def test_clearing_the_t_bar_alone_no_longer_grants_eligible():
    """The tightening BINDS: a series the old code would have promoted is held ACCRUING because
    the peek-safe process has not crossed."""
    rng = np.random.default_rng(19)
    arr = None
    for seed in range(200):                             # find a fixture in the gap between gates
        cand = np.random.default_rng(seed).normal(0.0032, 0.01, 90)
        if nw_tstat(cand) >= _BAR and e_value(cand) < _THR:
            arr = cand
            break
    assert arr is not None, "fixture: need a series clearing the t bar but not the e bar"
    assert rng is not None
    verdict, need, suff = ras._stage_b_verdict(arr, float(nw_tstat(arr)), _BAR, alpha=_ALPHA)
    assert suff.sufficient, "fixture: evidence_clock is satisfied, so only the e-process holds it"
    assert verdict == "ACCRUING", "a one-look crossing must not promote under daily peeking"
    assert need > arr.size, "the shortfall must be stated as MORE observations"


def test_clearing_both_gates_is_eligible():
    """Not a welded gate (L1.43): overwhelming forward evidence still reaches ELIGIBLE."""
    arr = np.random.default_rng(7).normal(0.02, 0.005, 40)
    t = float(nw_tstat(arr))
    assert t >= _BAR and e_value(arr) >= _THR, "fixture must clear both gates on its own merits"
    verdict, need, _ = ras._stage_b_verdict(arr, t, _BAR, alpha=_ALPHA)
    assert verdict == "ELIGIBLE"
    assert need == arr.size


def test_nothing_loosens_anywhere_in_the_input_space():
    """Structural guarantee: ELIGIBLE under the new rule implies ELIGIBLE under the old one.

    The new rule is an AND with the old conjunction, so this can only fail if someone later
    relaxes the t leg or the evidence_clock leg while adding the e leg -- which is precisely the
    'edit the guard to fit the violation it caught' failure this desk has paid for repeatedly.
    """
    rng = np.random.default_rng(4)
    saw_eligible = False
    for _ in range(300):
        n = int(rng.integers(5, 150))
        arr = rng.normal(rng.normal(0.0, 0.006), abs(rng.normal(0.01, 0.004)) + 1e-4, n)
        t = float(nw_tstat(arr))
        new, _, suff = ras._stage_b_verdict(arr, t, _BAR, alpha=_ALPHA)
        old_eligible = bool(suff.sufficient and t >= _BAR)     # the pre-R0187 condition
        if new == "ELIGIBLE":
            saw_eligible = True
            assert old_eligible, "new rule promoted something the old rule would have refused"
    assert saw_eligible, "fixture swept no eligible cases -- the assertion above proved nothing"


def test_the_e_process_does_not_touch_failing():
    """A negative effect is still called by evidence_clock at the trust floor. Asking a wealth
    process to certify FAILURE would be a category error: e sits near zero both for an edge that
    is absent and for one merely not yet proven, so it cannot distinguish them."""
    arr = np.random.default_rng(3).normal(-0.01, 0.008, MIN_OBS)
    t = float(nw_tstat(arr))
    assert t <= 0.0 and e_value(arr) < _THR
    verdict, need, _ = ras._stage_b_verdict(arr, t, _BAR, alpha=_ALPHA)
    assert verdict == "FAILING"
    assert need == MIN_OBS


def test_below_the_trust_floor_the_e_process_cannot_promote():
    """e_value returns 0.0 under its own 20-observation minimum, so a tiny lucky run cannot
    graduate on the peek-safe leg either. Belt and braces with evidence_clock's MIN_OBS."""
    arr = np.asarray([0.05] * 8)
    assert e_value(arr) == 0.0
    verdict, need, _ = ras._stage_b_verdict(arr, 99.0, _BAR, alpha=_ALPHA)
    assert verdict == "ACCRUING"
    assert need == MIN_OBS


def test_shortfall_is_reported_in_observations_and_names_the_binding_gate():
    """L1.48: shortfalls in OBSERVATIONS, never days -- and `need` must reflect whichever gate is
    actually further away, or a clock reads as nearly-eligible against a bar it is nowhere near."""
    arr = None
    for seed in range(200):
        cand = np.random.default_rng(seed).normal(0.0032, 0.01, 90)
        if nw_tstat(cand) >= _BAR and e_value(cand) < _THR:
            arr = cand
            break
    assert arr is not None
    e = e_value(arr)
    e_short = ras._e_shortfall(arr, e, _THR)
    _, need, suff = ras._stage_b_verdict(arr, float(nw_tstat(arr)), _BAR, alpha=_ALPHA)
    assert e_short > 0, "fixture: the e-process is the binding gate here"
    assert e_short >= suff.obs_short, "fixture: e is the FURTHER gate"
    assert need == arr.size + e_short, "need must track the binding constraint, not the loose one"


def test_e_shortfall_refuses_to_extrapolate_from_a_losing_bettor():
    """No honest observation count exists when the wealth process is not growing. -1 says so
    rather than emitting a large finite number that would read as a schedule."""
    arr = np.random.default_rng(3).normal(-0.01, 0.008, 40)
    assert ras._e_shortfall(arr, e_value(arr), _THR) == -1
    assert ras._e_shortfall(arr, 0.0, _THR) == -1
