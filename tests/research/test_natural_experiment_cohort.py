"""Cohort assembly for the MACRO-EVENT DiD -- where a causal study is actually won or lost.

The estimator can only be as honest as the control leg handed to it, so the assembly gets the
tests rather than the arithmetic. Each property here would, if it silently stopped applying,
convert a refusable study into one that confirms itself.

REPLACES the token-unlock cohort tests, deleted 2026-09-05 with the crypto desk. Those tested
`build_cohort` for vesting schedules and circulating supply; that function and its universe are
gone. The design that replaced it studies dated macro events against the MT5 universe, so the
properties worth pinning changed with it -- but the reason for pinning them did not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

rne = pytest.importorskip("scripts.run_natural_experiment")


class _Quote:
    __slots__ = ("price", "ts")

    def __init__(self, ts: datetime, price: float) -> None:
        self.ts, self.price = ts, price


class _Reader:
    """A tape where every symbol trends gently upward, so any DiD effect is orientation, not drift.

    Deliberately identical across symbols: if treated and control move the same way, a correct
    control leg differences the move to ~zero. A test tape with a built-in treated/control gap
    could not tell a working design from a broken one.
    """

    def __init__(self, start: datetime, n: int = 60) -> None:
        self._bars = {}
        self._start, self._n = start, n

    def bars(self, symbol: str, start=None, end=None):
        out = []
        px = 100.0
        for i in range(self._n):
            ts = self._start + timedelta(days=i)
            px *= 1.001
            if (start is None or ts >= start) and (end is None or ts <= end):
                out.append(_Quote(ts, px))
        return out


class _Rec:
    def __init__(self, category: str, when: datetime, instruments: tuple[str, ...]) -> None:
        self.category, self.instruments = category, instruments
        self.happened_at = when.isoformat()
        self.published_at = when.isoformat()


_T0 = datetime(2026, 3, 1, tzinfo=UTC)
_UNIVERSE = {f"SYM{i}": {"tradeable": True} for i in range(40)}


def _events(n: int, category: str = "cpi") -> list[_Rec]:
    return [_Rec(category, _T0 + timedelta(days=i), ("SYM0",)) for i in range(n)]


class TestOrientationIsAPriorNotADefault:
    def test_a_unit_with_no_stored_exposure_is_dropped(self) -> None:
        """THE PROPERTY THAT KEEPS THIS FALSIFIABLE. The estimator underneath is a ONE-SIDED
        POSITIVE test, so defaulting an unknown sign to +1 would confirm a coin flip half the
        time. The unit must leave the cohort instead."""
        reader = _Reader(_T0 - timedelta(days=30))
        cohorts, drops = rne.build_cohorts(_events(20), reader, {}, _UNIVERSE, min_cohort=1)
        assert not cohorts, "a cohort was built with no stored exposure to orient it"
        assert any("no stored exposure sign" in d for d in drops)

    @pytest.mark.parametrize("beta", [0.4, -0.4])
    def test_either_sign_yields_a_cohort_and_the_sign_is_carried(self, beta: float) -> None:
        """A negative exposure is a prediction too. Dropping it would silently restrict the study
        to instruments the desk expects to rise, which is a selected sample."""
        reader = _Reader(_T0 - timedelta(days=30))
        cohorts, _ = rne.build_cohorts(_events(20), reader, {"SYM0": {"cpi": beta}}, _UNIVERSE,
                                       min_cohort=1)
        units = cohorts.get("cpi") or []
        assert units, "a stored exposure of either sign must orient a unit"
        want = 1.0 if beta > 0 else -1.0
        raw_up = units[0].treated_pre[0] * want
        assert raw_up > 0, "the series was not oriented by the stored sign"

    def test_control_legs_are_oriented_with_the_treated_leg(self) -> None:
        """Orienting only the treated leg would put a sign on the EFFECT that came from the
        orientation rather than from the event -- a difference-in-differences between a flipped
        series and an unflipped one measures the flip."""
        reader = _Reader(_T0 - timedelta(days=30))
        cohorts, _ = rne.build_cohorts(_events(20), reader, {"SYM0": {"cpi": -0.4}}, _UNIVERSE,
                                       min_cohort=1)
        u = (cohorts.get("cpi") or [])[0]
        assert u.control_pre[0] < 0 and u.treated_pre[0] < 0, (
            "a rising tape oriented by a negative exposure must flip BOTH legs")

    def test_a_zero_exposure_is_no_prior_at_all(self) -> None:
        """Zero is not a direction. Reading it as +1 (or as -1) invents a hypothesis."""
        reader = _Reader(_T0 - timedelta(days=30))
        cohorts, drops = rne.build_cohorts(_events(20), reader, {"SYM0": {"cpi": 0.0}}, _UNIVERSE,
                                           min_cohort=1)
        assert not cohorts and any("no stored exposure sign" in d for d in drops)


class TestTheCohortFloorAndItsReasons:
    def test_a_cohort_under_the_floor_is_dropped_and_counted(self) -> None:
        """"n=6" with no story is unreadable, and a cohort that shrank from 200 events to 6 has
        one. The floor exists because a cross-sectional t on a handful of units reports noise
        with a label on it."""
        reader = _Reader(_T0 - timedelta(days=30))
        cohorts, drops = rne.build_cohorts(_events(3), reader, {"SYM0": {"cpi": 0.4}}, _UNIVERSE,
                                           min_cohort=8)
        assert not cohorts
        assert any("under the 8-unit floor" in d for d in drops)

    def test_an_event_naming_no_tradeable_instrument_is_dropped(self) -> None:
        reader = _Reader(_T0 - timedelta(days=30))
        recs = [_Rec("cpi", _T0 + timedelta(days=i), ("NOT_IN_UNIVERSE",)) for i in range(20)]
        cohorts, drops = rne.build_cohorts(recs, reader, {"SYM0": {"cpi": 0.4}}, _UNIVERSE,
                                           min_cohort=1)
        assert not cohorts
        assert any("named instrument" in d for d in drops)

    def test_a_tape_too_short_for_the_windows_drops_the_unit(self) -> None:
        """An absent bar is a gap, never a zero return. Padding here would put invented
        observations into the pre-period the parallel-trends test is computed on."""
        short = _Reader(_T0 - timedelta(days=2), n=3)
        cohorts, drops = rne.build_cohorts(_events(20), short, {"SYM0": {"cpi": 0.4}}, _UNIVERSE,
                                           min_cohort=1)
        assert not cohorts and drops


class TestTheWindowsHonourTheEstimatorsFloors:
    def test_the_declared_windows_sit_above_the_modules_minimums(self) -> None:
        """Pre-registered here, but they must also be legal: a PRE_BARS under MIN_PRE_OBS would
        make every study refuse, and 'we never got a result' is how a fence stops being read."""
        assert rne.PRE_BARS >= rne.MIN_PRE_OBS
        assert rne.POST_BARS >= rne.MIN_POST_OBS

    def test_units_carry_the_symbol_as_the_sutva_cohort_key(self) -> None:
        """SUTVA counts SYMBOLS, not events. A symbol with 30 dated events is ONE member of the
        cross-section; comparing an event count to a symbol count refuses well-powered studies."""
        reader = _Reader(_T0 - timedelta(days=30))
        cohorts, _ = rne.build_cohorts(_events(20), reader, {"SYM0": {"cpi": 0.4}}, _UNIVERSE,
                                       min_cohort=1)
        units = cohorts["cpi"]
        assert {u.cohort_key for u in units} == {"SYM0"}, "the key must be the symbol, not the id"
        assert len({u.unit_id for u in units}) == len(units), "unit ids must stay distinct"


class TestAnEmptyLedgerIsNotAResult:
    def test_run_reports_unmeasured_rather_than_no_effect(self, monkeypatch) -> None:
        """L1.28a. "No cohort" and "no effect" are opposite findings: one says the desk has not
        looked, the other that it looked and found nothing. Reporting the first as the second is
        how an unbuilt capability reads as a tested one."""
        rep = rne.run()
        assert rep["status"] == "UNMEASURED"
        assert rep["detail"], "an UNMEASURED verdict must say what was missing"
        assert not rep["cohorts"]
