"""COLLAPSING THE DIAGNOSTIC BANDS INTO "FAILED" DESTROYS THE DIAGNOSIS.

A cell that is economically positive and statistically weak needs more TAPE. One that is
statistically strong and economically negative needs cheaper EXECUTION. Both read as "did not
survive", and the actions are spent in different budgets in different weeks. This desk has already
made that error in production: F5 SAMPLE FLOOR cells were read as an absence of edge when they were
an absence of observations.
"""

from __future__ import annotations

from libs.research.failure_bands import BANDS, FailureRecord, band_of, mine, summarise


def _r(**kw) -> FailureRecord:
    base = {"key": "c1", "hurdle": 5.236}
    return FailureRecord(**{**base, **kw})


def test_AN_UNMEASURED_CELL_GETS_NO_BAND() -> None:
    """A band is a claim about DISTANCE from the bar. Calling a cell with no t 'FAR' converts
    missing data into a negative result, which is WS-005."""
    band, why = band_of(_r(t_stat=None, net_bps=None))
    assert band == ""
    assert "UNMEASURED" in why and "WS-005" in why


def test_A_MISSING_HURDLE_ALSO_BLOCKS_BANDING() -> None:
    assert band_of(_r(t_stat=4.0, net_bps=1.0, hurdle=None))[0] == ""


def test_ECONOMICALLY_POSITIVE_AND_THIN_IS_A_SPAN_PROBLEM() -> None:
    """The economics work and the sample cannot prove it. No amount of harness tuning creates
    observations."""
    band, why = band_of(_r(t_stat=1.2, net_bps=0.8, n_observations=90))
    assert band == "ECON_POSITIVE_STAT_WEAK"
    assert "cannot prove it" in why
    action = mine([_r(t_stat=1.2, net_bps=0.8, n_observations=90)])[0]["action"]
    assert "GET MORE TAPE" in str(action)
    assert "no amount of harness tuning creates observations" in str(action)


def test_STATISTICALLY_STRONG_AND_UNPROFITABLE_IS_A_COST_PROBLEM() -> None:
    band, why = band_of(_r(t_stat=6.0, net_bps=-0.4, cost_bps=1.1))
    assert band == "STAT_STRONG_ECON_NEGATIVE"
    assert "the round trip eats it" in why
    action = mine([_r(t_stat=6.0, net_bps=-0.4)])[0]["action"]
    assert "ATTACK COST, NOT SIGNAL" in str(action)


def test_THE_TWO_DIAGNOSTIC_BANDS_OUTRANK_NEAR() -> None:
    """They name a CAUSE, and a named cause is cheaper to act on than proximity."""
    assert BANDS.index("ECON_POSITIVE_STAT_WEAK") < BANDS.index("NEAR")
    assert BANDS.index("STAT_STRONG_ECON_NEGATIVE") < BANDS.index("NEAR")


def test_NEAR_CARRIES_THE_MANUFACTURING_WARNING() -> None:
    """Near is the cheapest experiment the desk owns AND the easiest place to manufacture a
    survivor by trying variants until one passes."""
    band, _ = band_of(_r(t_stat=4.5, net_bps=-0.1))
    assert band == "NEAR"
    action = str(mine([_r(t_stat=4.5, net_bps=-0.1)])[0]["action"])
    assert "ancestry-deflated hurdle" in action and "manufacture a survivor" in action


def test_A_CLEARED_CELL_IS_NOT_FAILURE_MININGS_BUSINESS() -> None:
    assert band_of(_r(t_stat=6.0, net_bps=1.2))[0] == "CLEARED"


def test_FAR_IS_EVIDENCE_ABOUT_THE_WHOLE_FAMILY() -> None:
    band, why = band_of(_r(t_stat=-0.4, net_bps=-2.0))
    assert band == "FAR" and "whole family" in why
    action = str(mine([_r(t_stat=-0.4, net_bps=-2.0)])[0]["action"])
    assert "RETIRE THE FAMILY, not the cell" in action


def test_WEAK_LICENSES_ONLY_CHEAP_EXPANSION() -> None:
    band, _ = band_of(_r(t_stat=1.0, net_bps=-0.2))
    assert band == "WEAK"
    assert "CHEAP AXIS EXPANSION ONLY" in str(mine([_r(t_stat=1.0, net_bps=-0.2)])[0]["action"])


def test_NEAR_FRACTION_IS_A_PARAMETER_BECAUSE_THE_HURDLE_MOVES() -> None:
    """A fixed t-threshold would silently redefine 'near' every time the declared universe grew."""
    r = _r(t_stat=3.0, net_bps=-0.1)
    assert band_of(r, near_fraction=0.5)[0] == "NEAR"
    assert band_of(r, near_fraction=0.9)[0] == "WEAK"


def test_THE_HEADLINE_NAMES_TWO_PROJECTS_NOT_A_FAILURE_COUNT() -> None:
    """'1,200 cells failed' is a number nobody can act on."""
    recs = ([_r(key=f"s{i}", t_stat=1.1, net_bps=0.5, n_observations=80) for i in range(4)]
            + [_r(key=f"c{i}", t_stat=6.0, net_bps=-0.3) for i in range(3)])
    head = str(summarise(recs)["headline"])
    assert "4 cell(s) blocked by SPAN and 3 by COST" in head
    assert "neither of them is 'search harder'" in head


def test_AN_EMPTY_GRAVEYARD_IS_NOT_A_CLEAN_SWEEP() -> None:
    assert "UNMEASURED" in str(summarise([])["headline"])


def test_UNMEASURED_CELLS_ARE_HANDED_TO_NOBODY() -> None:
    """A descendant inherits the ancestry's whole trial count; searching the neighbourhood of a
    number nobody measured is searching noise with extra steps."""
    rows = mine([_r(t_stat=None, net_bps=None)])
    assert rows[0]["band"] == "UNMEASURED"
    assert "re-band" in str(rows[0]["action"])
    assert "unmeasured cells are handed to nobody" in str(summarise([_r()])["note"])
