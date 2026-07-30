"""SCREEN-STAGE SELECTION calibration (gap #71).

A selection rule is only trustworthy if it is calibrated on KNOWN TRUTH, so these tests do what
test_stepwise.py does for the FWER path: an all-null campaign must not manufacture a shortlist, and
a campaign containing real winners must make them reachable. The whole point of the change is that
the incumbent FWER screen fails the SECOND property on the desk's real campaign (0 of 420 at any
window), so proving reachability here is the load-bearing test.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.validation.screen_select import screen_report, screen_select
from libs.validation.stepwise import romano_wolf_stepdown

_PPY = 365.0
_SD = 0.40 / np.sqrt(_PPY)


def _stream(true_ann_sharpe: float, n_obs: int, rng: np.random.Generator) -> np.ndarray:
    """Fat-tailed (Student-t df=6) daily net returns with a KNOWN true annual Sharpe -- the same
    generator tests/validation/test_stepwise.py uses, so the two calibration suites are comparable
    (the first version of this file rolled its own mu and got it wrong)."""
    z = rng.standard_t(6, size=n_obs)
    z /= np.sqrt(6.0 / 4.0)                       # unit variance
    return true_ann_sharpe * _SD / np.sqrt(_PPY) + _SD * z


def _campaign(n_null: int, goods: list[float], n_obs: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    cols = [_stream(0.0, n_obs, rng) for _ in range(n_null)]
    cols += [_stream(s, n_obs, rng) for s in goods]
    return np.column_stack(cols)


def _campaign_fixed_winner(n_null: int, good: float, n_obs: int, *, winner_seed: int,
                           null_seed: int) -> np.ndarray:
    """Winner drawn from its OWN generator so its data is IDENTICAL across batch sizes.

    The first version of the anti-escalation test drew nulls first from a shared generator, so
    adding nulls changed the winner's random stream -- it was comparing different realisations and
    calling the difference an escalation effect. Holding the winner fixed is what makes the test
    actually about batch size."""
    wr = np.random.default_rng(winner_seed)
    winner = _stream(good, n_obs, wr)
    nr = np.random.default_rng(null_seed)
    nulls = [_stream(0.0, n_obs, nr) for _ in range(n_null)]
    return np.column_stack([*nulls, winner])


class TestNullCalibration:
    """The phantom-edge property: a 100%-null campaign must not produce a shortlist."""

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_all_null_campaign_shortlists_almost_nobody(self, seed: int) -> None:
        m = _campaign(n_null=40, goods=[], n_obs=400, seed=seed)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=300, seed=seed)
        sel = screen_select(sd, q=0.05, method="by")
        # FDR controls the expected PROPORTION of false discoveries; on a pure-null campaign the
        # expected count of selections is bounded well below the batch size.
        assert sel.n_selected <= 2, f"{sel.n_selected} nulls shortlisted (seed {seed})"

    def test_by_is_never_looser_than_bh(self) -> None:
        m = _campaign(n_null=30, goods=[1.0], n_obs=400, seed=7)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=300, seed=7)
        by = screen_select(sd, q=0.05, method="by")
        bh = screen_select(sd, q=0.05, method="bh")
        # Benjamini-Yekutieli pays a log(m) penalty for arbitrary dependence, so it can never
        # select MORE than Benjamini-Hochberg. If it ever did, the implementation is wrong.
        assert by.n_selected <= bh.n_selected
        assert by.threshold <= bh.threshold + 1e-12


class TestReachability:
    """The property the incumbent FWER screen FAILS on the real campaign: a winner is reachable."""

    def test_a_strong_winner_is_shortlisted_in_a_large_batch(self) -> None:
        m = _campaign(n_null=60, goods=[3.0], n_obs=500, seed=11)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=400, seed=11)
        sel = screen_select(sd, q=0.05, method="bh")
        assert sel.selected[-1] is True, "a Sharpe-3 candidate must survive a SCREEN"
        assert sel.n_selected >= 1

    def test_winners_survive_as_the_batch_grows(self) -> None:
        """THE ANTI-ESCALATION PROPERTY, and it is the whole argument. A screen bar must not rise
        with generation volume (TWO_STAGE_DISCOVERY_LAW). Adding pure nulls around the SAME winner
        must not evict it -- which is exactly what a family-wise bar does.

        n_boot is sized from the resolution requirement rather than picked: selecting the top of m
        candidates at q needs p <= q/m, and a B-draw bootstrap cannot represent a p below 1/B. The
        first version of this test used a flat n_boot=300 and the winner was evicted at m=61 by
        ARITHMETIC, not by evidence -- which is what `resolvable` now reports."""
        keep = []
        for n_null in (20, 60, 120):
            m = _campaign_fixed_winner(n_null, 4.0, 600, winner_seed=101, null_seed=202)
            need_boot = int(4 * (n_null + 1) / 0.05)      # boundary on an atom, 4x headroom
            sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=need_boot, seed=13)
            sel = screen_select(sd, q=0.05, method="bh")
            assert sel.resolvable, f"bootstrap too coarse at m={n_null + 1}"
            keep.append(sel.selected[-1])
        assert all(keep), f"winner evicted as the batch grew: {keep}"

    def test_coarse_bootstrap_is_reported_as_a_measurement_limit(self) -> None:
        """A coarse bootstrap does NOT make selection impossible (p=0 is attainable) -- it costs
        DISCRIMINATION among candidates tied at the floor. The report must say which."""
        m = _campaign_fixed_winner(200, 5.0, 500, winner_seed=17, null_seed=18)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=200, seed=17)
        sel = screen_select(sd, q=0.05, method="bh")
        assert sel.resolvable is False
        assert "COARSE BOOTSTRAP" in sel.error_statement
        assert "measurement limit, NOT evidence" in sel.error_statement
        assert sel.ties_at_floor >= 1
        assert sel.required_n_boot >= 4000        # 0.05/201 -> boundary needs ~4020 draws

    def test_required_n_boot_is_arithmetically_right(self) -> None:
        m = _campaign(n_null=99, goods=[2.0], n_obs=400, seed=19)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=500, seed=19)
        sel = screen_select(sd, q=0.05, method="bh")
        assert sel.required_n_boot == 2000       # ceil(1 / (0.05/100))


class TestContract:
    """A shortlist must never be mistakable for a promotion."""

    def test_error_statement_names_the_control_and_denies_promotion(self) -> None:
        m = _campaign(n_null=20, goods=[2.0], n_obs=400, seed=5)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=200, seed=5)
        sel = screen_select(sd, q=0.05)
        assert "EXPECTED PROPORTION" in sel.error_statement
        assert "zero promotion authority" in sel.error_statement
        assert "forward evidence" in sel.error_statement

    def test_fwer_answer_is_always_carried_alongside(self) -> None:
        m = _campaign(n_null=20, goods=[2.0], n_obs=400, seed=5)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=200, seed=5)
        sel = screen_select(sd, q=0.05)
        assert sel.fwer_n_selected == sum(bool(x) for x in sd.rejected)

    def test_empty_campaign_is_handled(self) -> None:
        m = _campaign(n_null=3, goods=[], n_obs=300, seed=2)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=100, seed=2)
        sel = screen_select(sd, q=0.05)
        assert sel.n_candidates == 3
        assert len(sel.selected) == 3

    def test_report_shows_both_dependence_assumptions(self) -> None:
        m = _campaign(n_null=25, goods=[2.5], n_obs=450, seed=9)
        sd = romano_wolf_stepdown(m, alpha=0.05, n_boot=300, seed=9)
        rep = screen_report(sd, q=0.05)
        assert {"fwer_selected", "by_selected", "bh_selected", "min_p"} <= set(rep)
        assert rep["by_selected"] <= rep["bh_selected"]

    def test_q_is_the_same_five_percent_as_the_fwer_bar(self) -> None:
        # The tolerance did not move; only the error rate being controlled did.
        from libs.validation.screen_select import _DEFAULT_Q
        assert _DEFAULT_Q == 0.05
