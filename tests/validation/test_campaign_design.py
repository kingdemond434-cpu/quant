"""The preflight must reproduce the hand-run certification, and must never narrow the hunt."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.validation.admission_power import POWER_TARGET
from libs.validation.campaign_design import (
    INDETERMINATE,
    POWERED,
    UNDERPOWERED,
    dsr_hurdle_annual,
    preflight,
)

ROOT = Path(__file__).resolve().parents[2]

#: The desk's real campaign, the one that produced 420-tested / 0-survivors.
REAL_N, REAL_T = 420, 310


def test_reproduces_the_certification_hurdle() -> None:
    """Cross-check against certify_gauntlet, computed independently -- under the FIXED bar.

    Agreement with a separate script is still the evidence the arithmetic was re-homed faithfully.
    Since 2026-10-13 (principal: "make sure the bars never raise never ever penalty never inflation
    due to trials") both compute the hurdle at trial_count_guard.BAR_N, so the hurdle is identical
    whatever trial count is passed, and the count is still REPORTED on the Design. The recorded
    `reports/gauntlet_certification.json` is compared only once it carries `bar_n` (written by the
    pinned certifier); an artifact from before the pin priced a trial-scaled hurdle.
    """
    from scripts.certify_gauntlet import dsr_hurdle_annual as cert_hurdle
    for n in (1, 2, 4, 5, 30, 421, 10_000):
        for t in (310, 1250):
            assert dsr_hurdle_annual(n, t) == pytest.approx(cert_hurdle(n, t), rel=1e-12)
            if n >= 5:
                assert dsr_hurdle_annual(n, t) == dsr_hurdle_annual(421, t)
            else:                         # min(count, bar_n): never above the fixed bar
                assert dsr_hurdle_annual(n, t) <= dsr_hurdle_annual(421, t)
    assert preflight(421, 310).n_trials == 421          # the count is reported
    cert = ROOT / "reports/gauntlet_certification.json"
    design = json.loads(cert.read_text("utf-8")).get("design") if cert.exists() else None
    if not isinstance(design, dict) or "bar_n" not in design:
        return                                        # pre-pin artifact: nothing like-for-like
    assert dsr_hurdle_annual(design["n_trials"], design["n_obs"]) == pytest.approx(
        design["hurdle_annual_sharpe"], rel=1e-9)
    # Compare LIKE FOR LIKE: the design block's own n_trials (421) and n_obs.
    ours = preflight(design["n_trials"], design["n_obs"])
    for level, expected in design["power_by_true_annual_sharpe"].items():
        assert ours.power_curve[level] == pytest.approx(expected, rel=1e-9)


def test_the_real_campaign_is_underpowered_and_its_null_is_uninformative() -> None:
    """The real campaign's window (T=310) still cannot reach the power target against a
    world-class edge -- and the verdict is IDENTICAL whatever its trial count, because a wider
    campaign never raises the bar (fixed N, principal 2026-10-13). The count is reported."""
    d = preflight(REAL_N, REAL_T)
    assert d.verdict == UNDERPOWERED
    assert d.n_trials == REAL_N
    assert d.power_at_target < POWER_TARGET
    assert d.informative_null() is False
    for n in (5, 10_000):
        other = preflight(n, REAL_T)
        assert other.power_at_target == d.power_at_target
        assert other.verdict == d.verdict


def test_deep_history_is_powered() -> None:
    d = preflight(30, 2500)
    assert d.verdict == POWERED
    assert d.informative_null() is True
    assert d.cheapest_fix is None             # nothing to fix


def test_fix_preserves_breadth_when_history_can_rescue_it() -> None:
    """The regression that matters.

    The first draft scanned T ascending and took the first N that cleared, which recommended
    cutting the desk's 420 candidates to 10 -- the narrowing reflex the module exists to prevent.
    The measured frontier says T=2500 clears the target at the FULL N=420, so the fix must keep
    every candidate. A future edit that reintroduces the old ordering fails here.
    """
    fix = preflight(REAL_N, REAL_T).cheapest_fix
    assert fix is not None
    assert fix["narrows_the_hunt"] is False
    assert fix["n_trials"] == REAL_N          # not one candidate dropped
    assert fix["power"] >= POWER_TARGET


def test_narrowing_is_only_suggested_with_the_preregistration_condition() -> None:
    """If narrowing is ever proposed, it must carry the pre-registration condition in its text."""
    # A target so demanding that no reachable history rescues the full breadth.
    d = preflight(420, 310, target_true_sharpe=0.6)
    if d.cheapest_fix is not None and d.cheapest_fix["narrows_the_hunt"]:
        assert "PRE-REGISTERED" in d.cheapest_fix["legitimacy"]
        assert "post-hoc" in d.cheapest_fix["legitimacy"]


@pytest.mark.parametrize(("n", "t"), [(0, 310), (420, 1), (-5, 310), (1, 0)])
def test_degenerate_shapes_are_indeterminate_never_powered(n: int, t: int) -> None:
    """Unmeasurable must never read as healthy -- the `beats_baselines` failure class."""
    d = preflight(n, t)
    assert d.verdict == INDETERMINATE
    assert d.informative_null() is False


def test_bad_target_is_indeterminate() -> None:
    for bad in (0.0, -1.0, float("nan")):
        assert preflight(30, 2500, target_true_sharpe=bad).verdict == INDETERMINATE


def test_more_trials_never_lowers_the_hurdle() -> None:
    """Monotonicity: multiplicity can only ever cost you. Guards a sign error in the deflator."""
    hurdles = [dsr_hurdle_annual(n, 1250) for n in (5, 10, 30, 100, 420)]
    assert hurdles == sorted(hurdles)


def test_more_observations_never_raises_the_hurdle() -> None:
    hurdles = [dsr_hurdle_annual(100, t) for t in (310, 620, 1250, 2500)]
    assert hurdles == sorted(hurdles, reverse=True)


def test_module_cannot_write_a_threshold() -> None:
    """Structural, not conventional: nothing here may become a route to a looser bar.

    Mirrors `libs/execution/excitation.py`, which owns no vocabulary for position size. If a
    future edit adds a setter, this fails and the reviewer has to justify it explicitly.
    """
    import libs.validation.campaign_design as cd

    banned = [n for n in dir(cd)
              if n.startswith(("set_", "relax_", "lower_", "override_", "apply_"))]
    assert banned == []


def test_intraday_annualisation_is_not_silently_daily() -> None:
    """An intraday campaign must not inherit the daily 365.

    `run_moat_campaign.py` annualises by bars-per-year at its `--bar-ms` cadence. If `preflight`
    quietly assumed 365 there it would report a hurdle for an experiment nobody ran -- the same
    mixed-scope error as comparing futures-scope NAV against total-scope NAV.
    """
    daily = preflight(100, 2500)
    minute = preflight(100, 2500, ppy=365.0 * 24 * 60)
    assert minute.hurdle_annual_sharpe > daily.hurdle_annual_sharpe
    assert minute.periods_per_year != daily.periods_per_year


@pytest.mark.parametrize("bad_ppy", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_annualisation_is_refused_not_assumed(bad_ppy: float) -> None:
    d = preflight(100, 2500, ppy=bad_ppy)
    assert d.verdict == INDETERMINATE
    assert d.informative_null() is False


def test_verdict_is_a_label_not_a_veto() -> None:
    """preflight returns; it never raises. A campaign is never blocked by being underpowered."""
    assert preflight(10_000, 5).verdict in {UNDERPOWERED, INDETERMINATE}
    assert preflight(1, 3).verdict in {POWERED, UNDERPOWERED, INDETERMINATE}
