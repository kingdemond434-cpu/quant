"""WHY THE MOAT COULD NOT PRODUCE A SURVIVOR, pinned as arithmetic.

THE DEFECT. `run_moat_campaign` built its panel with `T = min(len(r) for r in series)` -- every
candidate truncated to the SHORTEST one. Measured 2026-08-05 the campaign ran at T=1,065
one-minute bars, under eighteen hours, against a tape the desk holds in gigabytes, because one
late-added symbol capped the panel and every other column was cropped to match it.

What that costs, priced by the desk's own `campaign_design.preflight` at the real shape (eleven
long columns, one short):

    OLD  k=12  T=1,065    hurdle annualised Sharpe 73.54   power 0.06%
    NEW  k=11  T=500,000  hurdle annualised Sharpe  3.35   power 9.40%

469x the sample length and 148x the expected discoveries, by dropping ONE column. Keeping it cost
every other hypothesis its entire history AND raised N for all of them -- both of the two things
that destroy power -- to save a single candidate that could not carry a test anyway.

THE OBJECTIVE MATTERS AS MUCH AS THE FIX. Maximising POWER alone drives k to its minimum, because
each added hypothesis tightens the multiplicity bar for all of them; on this shape that picks k=2
and discards ten live hypotheses. This desk's whole philosophy is many weak uncorrelated edges, so
the objective is EXPECTED DISCOVERIES, k*power(k), which keeps everything that brings history and
drops only what collapses the panel.

Nothing here is a results filter. A column is dropped for how little HISTORY it brings, decided
before the compute is spent -- never for what it scored.
"""
from __future__ import annotations

import pytest

from libs.validation.campaign_design import preflight

#: One-minute bars, the campaign's default cadence.
_PPY = 365.0 * 24.0 * 3600_000.0 / 60_000.0

#: The real 2026-08-05 shape: eleven columns with history, one late-added symbol with almost none.
_REAL_LENGTHS = [500_000] * 11 + [1_065]


def _ladder(lengths: list[int]) -> list[dict[str, float]]:
    """The prefix ladder the campaign prices, longest history first."""
    order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
    out = []
    for k in range(2, len(order) + 1):
        t_k = min(lengths[i] for i in order[:k])
        d = preflight(k, t_k, ppy=_PPY)
        out.append({"k": k, "T": t_k, "power": float(d.power_at_target),
                    "expected": k * float(d.power_at_target),
                    "hurdle": float(d.hurdle_annual_sharpe)})
    return out


def _chosen(lengths: list[int]) -> dict[str, float]:
    return max(_ladder(lengths), key=lambda r: r["expected"])


class TestTheShortestColumnNoLongerCapsThePanel:
    def test_the_old_rule_could_not_have_seen_any_edge(self) -> None:
        """Not a weak design -- a design with essentially zero chance of detecting a real edge,
        which is why its zero-survivor result was never evidence about the market."""
        d = preflight(len(_REAL_LENGTHS), min(_REAL_LENGTHS), ppy=_PPY)
        assert d.power_at_target < 0.01
        assert d.hurdle_annual_sharpe > 50.0, (
            "a hurdle this high is not a bar anything real clears; it is an arithmetic artifact "
            "of annualising a 1,065-bar sample")
        assert not d.informative_null(), (
            "a zero-survivor result from this shape must never read as evidence about the market")

    def test_dropping_one_short_column_recovers_the_sample(self) -> None:
        best = _chosen(_REAL_LENGTHS)
        assert best["T"] == 500_000, "the long columns must keep their full history"
        assert best["T"] / min(_REAL_LENGTHS) > 400

    def test_the_chosen_panel_keeps_almost_every_hypothesis(self) -> None:
        """THE MEDALLION LINE. Many weak uncorrelated edges is the strategy, so a rule that
        maximised power alone -- and it would pick k=2 here -- optimises the wrong thing."""
        best = _chosen(_REAL_LENGTHS)
        assert best["k"] == len(_REAL_LENGTHS) - 1 == 11
        power_only = max(_ladder(_REAL_LENGTHS), key=lambda r: r["power"])
        assert power_only["k"] == 2, "the shape that makes this trade-off real has moved"
        assert best["k"] > power_only["k"], (
            "expected-discoveries must keep more hypotheses than power-alone, or the objective "
            "has quietly reverted to a narrow search")

    def test_expected_discoveries_beats_the_old_rule_by_two_orders_of_magnitude(self) -> None:
        best = _chosen(_REAL_LENGTHS)
        old = preflight(len(_REAL_LENGTHS), min(_REAL_LENGTHS), ppy=_PPY)
        old_expected = len(_REAL_LENGTHS) * float(old.power_at_target)
        assert best["expected"] / max(old_expected, 1e-9) > 100

    def test_a_balanced_panel_is_left_alone(self) -> None:
        """No column is dropped when none is short -- the rule must not shrink a healthy panel."""
        best = _chosen([400_000] * 8)
        assert best["k"] == 8

    def test_selection_is_on_history_never_on_score(self) -> None:
        """A results filter would be survivorship by another name. The ladder is a function of
        LENGTHS alone -- this test passes no returns at all, and could not if score leaked in."""
        a = _chosen([300_000, 300_000, 300_000, 900])
        b = _chosen([300_000, 300_000, 300_000, 900])
        assert a == b
        assert set(a) == {"k", "T", "power", "expected", "hurdle"}

    def test_a_uniformly_short_tape_is_not_rescued_by_dropping_columns(self) -> None:
        """The honest limit. When EVERY column is short there is no panel to recover, and the rule
        must not pretend otherwise by shrinking to two columns and calling it powered."""
        best = _chosen([1_200] * 10)
        assert best["power"] < 0.5
        d = preflight(int(best["k"]), int(best["T"]), ppy=_PPY)
        assert not d.informative_null(), (
            "a short tape stays uninformative however the panel is cut -- the fix is MORE TAPE")


class TestTheDeskWideDiagnosis:
    """The same arithmetic, on the desk's own recorded shapes. These numbers are the answer to
    'why are there no survivors' and they must not drift silently."""

    @pytest.mark.parametrize(("n", "t", "ppy", "max_power"), [
        (420, 310, 252.0, 0.02),      # the historic price-family campaign
        (126, 619, 365.0, 0.10),      # today's Stage-A axis screens
        (66, 48, 365.0, 0.01),        # vol-risk-premium
    ])
    def test_the_recorded_campaigns_could_not_have_seen_a_sharpe_3_edge(
            self, n: int, t: int, ppy: float, max_power: float) -> None:
        d = preflight(n, t, ppy=ppy)
        assert d.power_at_target < max_power
        assert not d.informative_null()

    def test_the_one_campaign_that_can_honestly_report_a_zero(self) -> None:
        """exchange-netflow: N=12 over 5,553 observations. The ONLY desk shape whose null is
        informative -- and the difference is sample length, not a friendlier threshold."""
        d = preflight(12, 5553, ppy=365.0)
        assert d.power_at_target > 0.9
        assert d.informative_null()

    def test_multiplicity_alone_is_worth_an_order_of_magnitude(self) -> None:
        """Same data, only the hypothesis count changes. N is an ACCIDENT OF GENERATION VOLUME on
        this desk, not a design decision, and it costs more than any threshold argument."""
        wide = preflight(420, 619, ppy=365.0).power_at_target
        narrow = preflight(4, 619, ppy=365.0).power_at_target
        assert narrow / max(wide, 1e-9) > 10
