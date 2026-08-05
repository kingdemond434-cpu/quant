"""Regression tests for the Stage-A screening harness -- the shared instrument every axis screen is
mandated to use. Three independent screening passes on 2026-07-26 found the same defects in it, so
these pin the corrected behaviour: horizon-correct annualisation, honest power reporting, and a
lookahead rail that a whole-period shift cannot walk under."""
from __future__ import annotations

import numpy as np

from libs.research.axis_screen import stage_a_screen


def _noise(n=800, seed=0):
    rng = np.random.default_rng(seed)
    return rng.normal(size=n), rng.normal(0, 0.10, size=n)


def test_default_is_one_day_unchanged():
    """horizon_days defaults to 1 -> sqrt(365), identical to the pre-fix behaviour."""
    sig, ret = _noise()
    r = stage_a_screen(sig, ret, name="d")
    assert r["horizon_days"] == 1.0
    assert r["panel_width"] == 1


def test_noise_at_20d_no_longer_clears_the_sharpe_floor():
    """THE BUG: sqrt(365) on 20-day returns inflated Sharpe 4.47x, so pure noise scored 0.55
    against a 0.5 floor. With the horizon declared, noise must read as noise."""
    sig, ret20 = _noise()
    wrong = stage_a_screen(sig, ret20, name="n20-undeclared")
    right = stage_a_screen(sig, ret20, name="n20", horizon_days=20)
    assert abs(wrong["sharpe_momentum"]) > 0.5          # the old, inflated reading
    assert abs(right["sharpe_momentum"]) < 0.2          # honest
    # the harness rounds Sharpe to 2dp, so allow slack on the ratio of two rounded values
    assert np.isclose(abs(wrong["sharpe_momentum"]) / abs(right["sharpe_momentum"]),
                      np.sqrt(20), rtol=0.05)


def test_underpowered_is_not_reported_as_refuted():
    """A weak result on too few effective observations is 'could not tell', not 'dead'. The
    graveyard is permanent -- recording the two as one destroys hypothesis classes on no
    evidence."""
    sig, ret = _noise(n=200)
    r = stage_a_screen(sig, ret, name="thin", horizon_days=20)
    assert r["n_eff"] < 20
    assert r["verdict"] == "SCREEN-UNDERPOWERED"
    assert r["powered"] is False


def test_powered_null_is_still_screen_weak():
    """n must be big enough that an effect at ic_min (0.03) would have shown up: 1.96/sqrt(n)<=0.03
    needs n>~4270, so 4000 is genuinely (and correctly) still underpowered."""
    sig, ret = _noise(n=8000)
    r = stage_a_screen(sig, ret, name="thick")
    assert r["powered"] is True
    assert r["verdict"] == "SCREEN-WEAK"


def test_panel_width_deflates_effective_n():
    """A 139-symbol panel flattened into one array has n = symbol-days; treating those as
    independent inflates t by sqrt(139) ~ 11.8x."""
    sig, ret = _noise(n=1390)
    flat = stage_a_screen(sig, ret, name="flat")
    panel = stage_a_screen(sig, ret, name="panel", panel_width=139)
    assert np.isclose(flat["n_eff"] / panel["n_eff"], 139, rtol=0.01)
    assert panel["min_detectable_ic"] > flat["min_detectable_ic"]
    assert flat["ic"] == panel["ic"]  # power only -- never touches the estimate


def test_whole_period_shift_is_caught_as_lookahead():
    """The macro failure mode: shifting the signal a full period gives strong forward IC AND
    near-zero same-period corr, so the angle-20 gate sees nothing and a global ic_ceiling of 0.35
    sits above honest contemporaneous correlation. Forward IC must not exceed what the signal knows
    about its own period."""
    rng = np.random.default_rng(7)
    ret = rng.normal(0, 0.02, size=1500)
    leaked = np.roll(ret, -1)                      # signal[t] IS next period's return
    r = stage_a_screen(leaked, ret, name="leak")
    assert r["verdict"] == "SUSPECT-LOOKAHEAD"
    assert r["ic_exceeds_contemporaneous"] is True


def test_honest_contemporaneous_signal_is_not_flagged_as_leak():
    """Guard the other way: a signal that co-moves with its own period and barely leads is a
    TIMING-ARTIFACT (the coinbase/turkey class), never a lookahead accusation."""
    rng = np.random.default_rng(11)
    ret = rng.normal(0, 0.02, size=1500)
    sig = ret + rng.normal(0, 0.02, size=1500)     # knows the CURRENT period, not the next
    r = stage_a_screen(sig, ret, name="contemporaneous")
    assert r["ic_exceeds_contemporaneous"] is False
    assert r["verdict"] != "SUSPECT-LOOKAHEAD"


def test_real_lead_still_screens_interesting():
    """The harness must not have become unable to pass a genuinely good signal -- a gate that
    rejects everything carries zero information."""
    rng = np.random.default_rng(3)
    n = 6000  # >4270, so an effect at ic_min would have been detectable -> genuinely powered
    sig = rng.normal(size=n)
    ret = np.zeros(n)
    ret[1:] = 0.10 * sig[:-1] + rng.normal(0, 0.9, size=n - 1)  # modest genuine lead
    r = stage_a_screen(sig, ret, name="real-lead")
    assert r["verdict"] == "SCREEN-INTERESTING"
    assert r["powered"] is True


# --- sub-daily horizons (2026-08-05): the harness's first intraday callers ---------------------

def test_n_eff_can_never_exceed_the_rows_observed():
    """THE BUG. The horizon divisor is an OVERLAP deflator; below a day it inverts and MULTIPLIES.
    Measured on the first intraday caller: 4,314 five-minute bars reported n_eff=1,236,384, which
    drives min_detectable_ic to ~0.002 and pins `powered` True whatever the sample really was."""
    sig, ret = _noise(n=600)
    r = stage_a_screen(sig, ret, name="5m", horizon_days=5 / 1440.0)
    assert r["n_eff"] <= r["n"], f"n_eff {r['n_eff']} exceeds the {r['n']} rows it came from"
    assert r["min_detectable_ic"] > 0.05          # a 600-row sample cannot resolve a 0.002 IC


def test_the_bound_is_inactive_at_daily_and_slower():
    """Pure tightening: at horizon_days>=1 the deflator already shrinks n, so nothing changes."""
    sig, ret = _noise(n=800)
    for hd in (1.0, 5.0, 20.0):
        r = stage_a_screen(sig, ret, name=f"h{hd}", horizon_days=hd)
        # `n` is the PAIRED count the harness actually screens (input minus zwin minus the
        # forward shift), not the input length -- the deflator divides that, and the new bound
        # caps at that same number, so at hd>=1 the two agree exactly.
        assert r["n_eff"] == round(max(r["n"] / hd, 1.0), 1)


def test_intraday_noise_is_not_branded_a_lookahead_leak():
    """POSITIVE CONTROL, run because a rail that has only ever been observed REJECTING has not been
    validated. sqrt(365/horizon) is ~725 at 60s, so pure noise annualises past a ceiling meant for
    daily data and six honest hypotheses came back SUSPECT-LOOKAHEAD. Rescaling by the same factor
    the annualisation applies keeps the rail at constant per-period strictness."""
    sig, ret = _noise(n=1500, seed=7)
    r = stage_a_screen(sig, ret, name="60s", horizon_days=60 / 86400.0)
    assert r["verdict"] != "SUSPECT-LOOKAHEAD"
    assert r["sharpe_ceiling_applied"] > 6.0              # rescaled, and reported
    assert r["implausible_leak"] is False


def test_the_ic_ceiling_is_never_rescaled():
    """A correlation does not annualise, so 0.35 means the same thing at 60s as at a day. Only the
    Sharpe bar moves with the sampling rate -- a leak this large must still be caught intraday."""
    rng = np.random.default_rng(3)
    ret = rng.normal(0, 0.01, size=1200)
    sig = ret.copy()                                      # signal IS the next return: a real leak
    sig[:-1] = ret[1:]
    r = stage_a_screen(sig, ret, name="leak60s", horizon_days=60 / 86400.0)
    assert abs(r["ic"]) > 0.35 and r["implausible_leak"] is True
    assert r["verdict"] == "SUSPECT-LOOKAHEAD"
