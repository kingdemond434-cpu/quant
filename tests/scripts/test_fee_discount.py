"""THE BNB FEE DISCOUNT SURVEY -- that a toggle with no BNB behind it is not reported as a saving.

The whole reason this script exists is that the discount is invisible from inside the repo. A
survey that reports the toggle and stops would be worse than none: it would let every cost forecast
on the desk keep its 25% optimism while a green line said the discount was on.
"""

from __future__ import annotations

from typing import Any

import pytest
import scripts.run_fee_discount as fd


class _Spot:
    def __init__(self, *, armed: bool = True, burn: bool = True, interest: bool = True,
                 bnb: float = 1.0, status_raises: bool = False,
                 balance_raises: bool = False) -> None:
        self._armed, self._burn, self._interest = armed, burn, interest
        self._bnb, self._status_raises = bnb, status_raises
        self._balance_raises = balance_raises
        self.set_calls: list[tuple[bool, bool]] = []

    def is_armed(self) -> tuple[bool, str]:
        return self._armed, "armed" if self._armed else "no keyfile"

    def bnb_burn_status(self) -> dict[str, bool]:
        if self._status_raises:
            raise RuntimeError("venue down")
        return {"spotBNBBurn": self._burn, "interestBNBBurn": self._interest}

    def set_bnb_burn(self, *, spot: bool = True, interest: bool = True) -> dict[str, bool]:
        self.set_calls.append((spot, interest))
        self._burn, self._interest = spot, interest
        return {"spotBNBBurn": spot, "interestBNBBurn": interest}

    def balances(self) -> dict[str, float]:
        if self._balance_raises:
            raise RuntimeError("venue down")
        return {"BNB": self._bnb, "USDC": 100.0}


@pytest.fixture
def _patch(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _install(spot: _Spot) -> _Spot:
        import libs.execution.binance_spot_live as real

        for name in ("is_armed", "bnb_burn_status", "set_bnb_burn", "balances"):
            monkeypatch.setattr(real, name, getattr(spot, name), raising=False)
        return spot

    return _install


class TestTheToggleAloneIsNotASaving:
    def test_burn_on_with_no_bnb_is_TOGGLED_UNFUNDED_not_ARMED(self, _patch: Any) -> None:
        # The venue charges the FULL rate when there is no BNB to burn. A switch that reports on
        # and saves nothing is armed and idle, on a cost term -- III.16 wearing a green light.
        _patch(_Spot(burn=True, bnb=0.0))
        rep = fd.survey()
        assert rep["state"] == "TOGGLED-UNFUNDED"
        assert rep["effective_commission_per_side"] == fd.VIP0_SPOT_COMMISSION

    def test_burn_on_with_bnb_is_ARMED_and_prices_the_discount(self, _patch: Any) -> None:
        _patch(_Spot(burn=True, bnb=0.5))
        rep = fd.survey()
        assert rep["state"] == "ARMED"
        assert rep["effective_commission_per_side"] == pytest.approx(
            fd.VIP0_SPOT_COMMISSION * (1 - fd.BNB_DISCOUNT))

    def test_dust_below_the_floor_does_not_count_as_funded(self, _patch: Any) -> None:
        _patch(_Spot(burn=True, bnb=fd.MIN_BNB_BALANCE / 2))
        assert fd.survey()["state"] == "TOGGLED-UNFUNDED"


class TestUnmeasuredIsNeverOff:
    def test_an_unarmed_clone_reports_UNMEASURED_not_OFF(self, _patch: Any) -> None:
        # "We could not ask" and "it is off" lead to different actions and only one is free.
        _patch(_Spot(armed=False))
        rep = fd.survey()
        assert rep["state"] == "UNMEASURED"
        assert rep["spot_burn"] is None

    def test_an_unreadable_venue_reports_UNMEASURED(self, _patch: Any) -> None:
        _patch(_Spot(status_raises=True))
        rep = fd.survey()
        assert rep["state"] == "UNMEASURED"
        assert rep["effective_commission_per_side"] is None

    def test_burn_on_with_an_unreadable_balance_is_UNMEASURED_not_ARMED(self, _patch: Any) -> None:
        _patch(_Spot(burn=True, balance_raises=True))
        assert fd.survey()["state"] == "UNMEASURED"


class TestWritingIsExplicit:
    def test_the_default_survey_never_changes_the_account(self, _patch: Any) -> None:
        spot = _patch(_Spot(burn=False, bnb=1.0))
        rep = fd.survey()
        assert spot.set_calls == [], "a read-only survey switched an account setting"
        assert rep["state"] == "OFF"
        assert rep["changed"] is False

    def test_enable_switches_both_the_commission_and_the_interest_burn(self, _patch: Any) -> None:
        spot = _patch(_Spot(burn=False, interest=False, bnb=1.0))
        rep = fd.survey(enable=True)
        assert spot.set_calls == [(True, True)], "only half the discount was switched on"
        assert rep["changed"] is True
        assert rep["state"] == "ARMED"
