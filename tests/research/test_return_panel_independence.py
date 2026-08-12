"""The panel's headline independence number (R0338).

THE DEFECT THIS LOCKS. build_return_panel computed pairwise correlation TWO ways, printed both,
stored both, and then fed the headline `effective_bets` from the ZERO-FILLED one -- the more
forgiving of the two numbers it had just computed itself. Measured on the live tape 2026-08-12:
rho +0.198 zero-filled vs +0.421 jointly-active across 8 columns, publishing 3.36 effective bets
where the jointly-active reading gives 2.03.

WHY IT MATTERED MORE THAN A COSMETIC NUMBER. The same artifact's admission audit rejected all
seven non-seed columns for "correlation to the book is not yet measurable, so a duplicate cannot
be ruled out". So the file asserted 3.36 independent bets in one key and, four keys later, that
it could not measure independence at all. Over-estimating independence is also the dangerous
direction: a Kelly bettor sized on 3.4 bets it does not hold over-levers, and Kelly's penalty is
asymmetric.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("brp", _ROOT / "scripts/build_return_panel.py")
assert _spec and _spec.loader
brp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brp)


def _pw(zf: float, ja: float, *, median: int = 60, n_ja: int = 25) -> dict[str, Any]:
    return {"mean_pairwise_zero_filled": zf, "mean_pairwise_jointly_active": ja,
            "n_pairs_zero_filled": 28, "n_pairs_jointly_active": n_ja,
            "max_joint_overlap_days": median, "median_joint_overlap_days": median}


class TestTheFlatteringNumberIsNeverPublished:
    def test_the_published_number_is_below_the_zero_filled_one(self) -> None:
        n_eff, n_zf, n_ja, _ = brp._independence(8, _pw(0.198, 0.421))
        assert n_zf > n_ja, "the live disagreement: zero-fill reads as more diversified"
        assert n_eff <= n_ja, "published must not exceed the conservative reading"

    def test_the_live_2026_08_12_panel_no_longer_publishes_3_36(self) -> None:
        """The measured instance, at the live rho and its real median overlap of 4 days."""
        n_eff, n_zf, _, _ = brp._independence(
            8, _pw(0.1977270729507395, 0.42084295939940297, median=4))
        assert round(n_zf, 2) == 3.36, "the old headline, kept for comparison"
        assert n_eff < 1.5, "at 4 overlapping days independence is not measurable"

    def test_both_readings_are_still_published_for_audit(self) -> None:
        _, n_zf, n_ja, basis = brp._independence(8, _pw(0.198, 0.421))
        assert n_zf > 0 and n_ja > 0
        assert "zero-filled would have published" in basis


class TestUnmeasurableReadsAsOneBet:
    def test_no_jointly_active_pair_floors_at_one(self) -> None:
        """L1.28a: 'we cannot tell whether these are the same bet' must not render as health."""
        n_eff, _, _, basis = brp._independence(8, _pw(0.05, float("nan"), n_ja=0))
        assert n_eff == 1.0
        assert "UNMEASURED" in basis

    def test_a_tiny_overlap_cannot_buy_independence(self) -> None:
        """Three overlapping days is not evidence of anything -- the bound saturates at rho=1."""
        n_eff, _, _, _ = brp._independence(8, _pw(0.0, 0.0, median=3))
        assert n_eff == pytest.approx(1.0, abs=0.05)

    def test_more_overlap_earns_more_measured_independence(self) -> None:
        """The bound must relax as evidence accumulates, or the panel could never grow a book."""
        few, _, _, _ = brp._independence(8, _pw(0.198, 0.421, median=10))
        many, _, _, _ = brp._independence(8, _pw(0.198, 0.421, median=400))
        assert many > few


class TestTheMedianNotTheMaxCarriesTheBound:
    def test_pairwise_reports_a_median_overlap(self) -> None:
        import numpy as np
        mat = np.array([[1.0, 1.0, 0.0], [2.0, -1.0, 0.0], [3.0, 0.5, 1.0],
                        [-1.0, 2.0, 2.0], [0.5, -2.0, -1.0]])
        pw = brp._pairwise(mat, ["A", "B", "C"])
        assert pw["median_joint_overlap_days"] <= pw["max_joint_overlap_days"]

    def test_the_bound_is_taken_at_the_median_not_the_best_observed_pair(self) -> None:
        """Using the max would price every pair as if it were the most-observed one."""
        at_median, _, _, _ = brp._independence(8, _pw(0.198, 0.421, median=4))
        at_max, _, _, _ = brp._independence(8, _pw(0.198, 0.421, median=7))
        assert at_median < at_max
