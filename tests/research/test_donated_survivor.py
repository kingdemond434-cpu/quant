"""Donated survivors, pinned on the one number that decides whether the scheme helps or harms.

A SURVIVOR IS A MAXIMUM. If a donor screened forty candidates and sends the best, that statistic
is the best of forty draws. Judged against a one-trial bar it is not mildly optimistic -- it is the
entire multiple-comparisons problem, imported with the evidence stripped off, and every number on
the receiving side still looks right. These tests exist because that failure is invisible: there is
no file to grep, no error, and no verdict that reads as wrong.
"""

from __future__ import annotations

import pytest

from libs.research.donated_survivor import admit, review
from libs.validation.forward_stats import holm_bar


def _row(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "donor_funding_skew", "source": "opencode-factory",
        "trials_screened": 40, "t_stat": 3.0, "mechanism": "funding dispersion",
    }
    base.update(kw)
    return base


def test_THE_BAR_IS_BUILT_ON_THE_UNION_NOT_THE_LOCAL_COHORT() -> None:
    """THE WHOLE POINT. Both searches contributed to the chance the best candidate looks good by
    accident, so both must be priced. The local-only bar is the number that turns a maximum into
    an edge."""
    v = admit(_row(trials_screened=40), local_m=12)
    assert v.union_m == 52
    assert v.bar == pytest.approx(holm_bar(52, rank=1))
    assert v.bar > holm_bar(12, rank=1), "the union bar must be STRICTER than the local one"


def test_A_DONATION_WITHOUT_A_TRIAL_COUNT_IS_REFUSED() -> None:
    """Refused, not down-weighted and not admitted with a warning. An undeclared trial count is
    indistinguishable from a trial count of one -- the exact reading that spends money."""
    v = admit({"name": "x", "source": "s", "t_stat": 9.0}, local_m=12)
    assert v.refused and "trials_screened" in v.why


def test_ZERO_TRIALS_IS_NOT_A_SEARCH() -> None:
    v = admit(_row(trials_screened=0), local_m=12)
    assert v.refused and "did not" in v.why


def test_A_HARDER_HUNTING_DONOR_FACES_A_HIGHER_BAR() -> None:
    """INCENTIVE SAFETY, and it is the property that makes donation robust to a careless or
    adversarial donor: a factory cannot buy admission by generating more."""
    lo = admit(_row(trials_screened=10, t_stat=3.2), local_m=12)
    hi = admit(_row(trials_screened=500, t_stat=3.2), local_m=12)
    assert lo.bar is not None and hi.bar is not None and hi.bar > lo.bar
    assert lo.admit and hi.refused, (
        "the same t-stat admitted from a small search and refused from a huge one -- which is the "
        "arithmetic working, not an inconsistency")


def test_DONOR_CLOCKS_ADD_TO_DONOR_SCREENS_RATHER_THAN_REPLACING_THEM() -> None:
    """Taking the max would let a donor hide 500 screens behind a 3-clock cohort."""
    v = admit(_row(trials_screened=40, donor_cohort_m=8), local_m=12)
    assert v.union_m == 60


def test_A_STRONG_ENOUGH_SURVIVOR_IS_ADMITTED() -> None:
    v = admit(_row(trials_screened=40, t_stat=4.5), local_m=12)
    assert v.admit and "FORWARD CLOCK, NOT TO CAPITAL" in v.why


def test_ADMISSION_IS_TO_A_CLOCK_AND_NEVER_TO_CAPITAL() -> None:
    """The donor's backtest carries the same authority as this desk's backtest, which under the
    two-stage law is none. What crosses the wire is a hypothesis worth a clock."""
    v = admit(_row(t_stat=6.0), local_m=12)
    assert v.admit
    assert "two-stage law" in v.why and "hypothesis worth" in v.why


def test_A_BATCH_IS_NOT_RANKED_AGAINST_ITSELF() -> None:
    """Ranking donated survivors would add a THIRD selection step on top of the donor's and this
    desk's, and nothing downstream would know it happened. Each row faces the same bar."""
    rows = [_row(name=f"c{i}", t_stat=t) for i, t in enumerate((4.5, 4.4, 4.6))]
    rep = review(rows, local_m=12)
    bars = {a["bar"] for a in rep["admitted"]}
    assert len(bars) == 1, "every row judged against the same union bar, not against each other"
    assert rep["n_admitted"] == 3


def test_REFUSALS_ARE_REPORTED_WITH_THEIR_ARITHMETIC() -> None:
    """A donation path whose refusals are silent is indistinguishable from one that is not running.
    """
    rep = review([_row(t_stat=0.4), _row(name="ok", t_stat=5.0)], local_m=12)
    assert rep["n_refused"] == 1 and rep["n_admitted"] == 1
    assert "union bar" in rep["refused"][0]["why"]


def test_AN_EMPTY_BATCH_IS_A_REAL_ANSWER() -> None:
    rep = review([], local_m=12)
    assert rep["n_offered"] == 0 and rep["n_admitted"] == 0
