"""R0320 -- a capital event may move the money. It may never move the drawdown rail's ruler.

The gap these pin, journal-verified 2026-08-01: the pause rail read `peak = max(stored_peak,
equity)` on RAW wallet equity, so a deposit lifted equity to a fresh high-water and a LIVE -15%
pause cleared in a single tick while not one position had improved. The denominator moved under
the rail -- the same move `capital_events.rebase` already refuses in its own domain, arriving
through arithmetic instead of through a ledger row.

The ruling (module docstring, libs/risk/capital_events.py): the drawdown rail measures equity NET
of post-inception external flows, against a flow-adjusted high-water that carries ACROSS events.
Deposits raise it ADDITIVELY by exactly the cash deposited; withdrawals lower it by at most the
cash removed and never below the flow-adjusted equity; no event ever resets it downward.

Every test here is written so that a future "simplification" back to raw equity goes RED.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.risk import capital_events as CE
from libs.risk import risk_controls
from libs.risk.risk_controls import DD_PAUSE, DRAWDOWN_RUIN, evaluate

_WHY = "R0320 test: a ledgered capital event with a reason a reader can act on"


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CE, "LEDGER", tmp_path / "capital_events.jsonl")


def _deposit(equity_now: float, start: float, usd: float) -> None:
    CE.rebase(equity_now=equity_now, start_equity=start, deposit_usd=usd,
              authorised_by="principal", reason=_WHY)


def _withdraw(equity_now: float, start: float, usd: float) -> None:
    CE.rebase(equity_now=equity_now, start_equity=start, deposit_usd=-abs(usd),
              authorised_by="principal", reason=_WHY, kind="WITHDRAWAL")


# ------------------------------------------------------------------------------------------
# The defect itself
# ------------------------------------------------------------------------------------------

class TestADepositCannotBuyBackDrawdown:
    def test_deposit_does_not_reduce_measured_drawdown(self) -> None:
        """$5,000 book down to $4,000 (-20%). $5,000 arrives. It is STILL down 20%."""
        before = CE.flow_adjusted_rail(4_000.0, None, 5_000.0)
        assert before.dd_from_peak == pytest.approx(-0.20)

        _deposit(4_000.0, 5_000.0, 5_000.0)
        after = CE.flow_adjusted_rail(9_000.0, before.peak, before.peak_raw)

        assert after.net_flows_usd == 5_000.0
        assert after.equity == pytest.approx(4_000.0), "equity net of flows is unchanged"
        assert after.peak == pytest.approx(5_000.0), "the high-water did not move down or up"
        assert after.dd_from_peak == pytest.approx(before.dd_from_peak)
        assert after.dd_from_peak <= before.dd_from_peak + 1e-12, "a deposit may never LOOSEN it"

    def test_deposit_does_not_untrip_an_already_tripped_dd_pause(self) -> None:
        """The whole point. Tripped at -20%, stays tripped through the deposit."""
        rail = CE.flow_adjusted_rail(4_000.0, None, 5_000.0)
        tripped = evaluate(4_000.0, 5_000.0, rail.peak, 0.0, ruin_cap_lev=8.0,
                           flow_adjusted_equity=rail.equity)
        assert tripped.action == "pause_opens"

        _deposit(4_000.0, 5_000.0, 5_000.0)
        after = CE.flow_adjusted_rail(9_000.0, rail.peak, rail.peak_raw)
        # The ruin rail's inception moves with the ledger (that is its authorised re-entry);
        # the pause rail's does not, and that is the only thing holding the stop here.
        start = CE.effective_start_equity(5_000.0)
        assert start == 9_000.0
        still = evaluate(9_000.0, start, after.peak, 0.0, ruin_cap_lev=8.0,
                         flow_adjusted_equity=after.equity)

        assert still.action == "pause_opens", "money arriving is not a position improving"
        assert still.dd_from_peak == pytest.approx(-0.20)
        assert any("pausing new opens" in r for r in still.reasons)

    def test_the_raw_arithmetic_this_replaced_would_have_cleared_the_pause(self) -> None:
        """Pins the DEFECT, so deleting the fix cannot pass this suite quietly."""
        raw_peak = max(5_000.0, 9_000.0)                  # the old `max(stored_peak, eq_c)` line
        loosened = evaluate(9_000.0, 9_000.0, raw_peak, 0.0, ruin_cap_lev=8.0)
        assert loosened.action == "ok", "this is what the pre-R0320 executor did with a deposit"

    def test_the_highwater_rises_additively_by_exactly_the_deposit(self) -> None:
        """ADDITIVE, never proportional: +$5,000 of cash moves the raw high-water +$5,000."""
        before = CE.flow_adjusted_rail(4_000.0, None, 5_000.0)
        _deposit(4_000.0, 5_000.0, 5_000.0)
        after = CE.flow_adjusted_rail(9_000.0, before.peak, before.peak_raw)
        assert after.peak_raw == pytest.approx(before.peak_raw + 5_000.0)

    def test_a_deposit_cannot_rescue_a_ruin_breach_through_the_pause_channel(self) -> None:
        """The ruin rail's re-entry is the ledgered inception, NOT the drawdown channel."""
        eq, start = 3_139.86, 5_000.0                      # the 2026-07-30 book, -37.2%
        rail = CE.flow_adjusted_rail(eq, None, 5_061.379)
        assert evaluate(eq, start, rail.peak, 0.0, ruin_cap_lev=8.0,
                        flow_adjusted_equity=rail.equity).action == "flatten"


# ------------------------------------------------------------------------------------------
# The other direction: taking money out must not invent a loss
# ------------------------------------------------------------------------------------------

class TestAWithdrawalManufacturesNoPhantomDrawdown:
    def test_withdrawal_at_the_high_water_leaves_zero_drawdown(self) -> None:
        at_peak = CE.flow_adjusted_rail(6_000.0, None, 6_000.0)
        assert at_peak.dd_from_peak == pytest.approx(0.0)

        _withdraw(6_000.0, 5_000.0, 1_000.0)
        after = CE.flow_adjusted_rail(5_000.0, at_peak.peak, at_peak.peak_raw)

        assert after.net_flows_usd == -1_000.0
        assert after.equity == pytest.approx(6_000.0)
        assert after.dd_from_peak == pytest.approx(0.0), "no phantom drawdown from a cash-out"
        d = evaluate(5_000.0, CE.effective_start_equity(5_000.0), after.peak, 0.0,
                     ruin_cap_lev=8.0, flow_adjusted_equity=after.equity)
        assert d.action == "ok"

    def test_withdrawal_lowers_the_raw_highwater_by_at_most_the_amount_removed(self) -> None:
        at_peak = CE.flow_adjusted_rail(6_000.0, None, 6_000.0)
        _withdraw(6_000.0, 5_000.0, 1_000.0)
        after = CE.flow_adjusted_rail(5_000.0, at_peak.peak, at_peak.peak_raw)
        drop = at_peak.peak_raw - after.peak_raw
        assert drop == pytest.approx(1_000.0)
        assert drop <= 1_000.0 + 1e-9, "never more than the cash that actually left"
        assert after.peak >= after.equity, "and never below the flow-adjusted equity"

    def test_withdrawal_does_not_erase_a_real_drawdown(self) -> None:
        """The tighten rule cuts both ways: a cash-out is not a recovery either."""
        down = CE.flow_adjusted_rail(4_800.0, None, 6_000.0)          # -20%
        assert down.dd_from_peak == pytest.approx(-0.20)
        _withdraw(4_800.0, 6_000.0, 1_000.0)
        after = CE.flow_adjusted_rail(3_800.0, down.peak, down.peak_raw)
        assert after.dd_from_peak == pytest.approx(-0.20)
        assert evaluate(3_800.0, CE.effective_start_equity(6_000.0), after.peak, 0.0,
                        ruin_cap_lev=8.0,
                        flow_adjusted_equity=after.equity).action == "pause_opens"


# ------------------------------------------------------------------------------------------
# Properties of the rail itself
# ------------------------------------------------------------------------------------------

class TestTheHighWaterCarriesAcrossEvents:
    def test_peak_is_monotone_non_decreasing_through_a_deposit_sequence(self) -> None:
        rail = CE.flow_adjusted_rail(5_000.0, None, 5_000.0)
        peaks = [rail.peak]
        for eq, dep in ((5_500.0, 0.0), (4_500.0, 2_000.0), (6_800.0, 0.0), (5_000.0, 1_000.0)):
            if dep:
                _deposit(eq, 5_000.0, dep)
                eq += dep
            rail = CE.flow_adjusted_rail(eq, rail.peak, rail.peak_raw)
            peaks.append(rail.peak)
        assert peaks == sorted(peaks), f"an event reset the high-water downward: {peaks}"
        assert peaks[-1] == pytest.approx(5_500.0)         # best flow-free equity ever reached

    def test_peak_never_sits_below_the_equity_it_measures(self) -> None:
        for eq in (0.0, 1.0, 4_000.0, 50_000.0):
            r = CE.flow_adjusted_rail(eq, None, 5_000.0)
            assert r.peak >= r.equity and r.peak_raw >= min(eq, r.peak_raw)

    def test_migration_from_a_raw_peak_strips_a_deposit_already_baked_into_it(self) -> None:
        """First tick after R0320 lands on a box where a deposit already inflated the peak."""
        _deposit(4_000.0, 5_000.0, 5_000.0)
        r = CE.flow_adjusted_rail(9_000.0, None, 10_000.0)   # stored raw peak carries the deposit
        assert r.peak == pytest.approx(5_000.0), "the inflation does not survive the migration"
        assert r.dd_from_peak == pytest.approx(-0.20)


class TestNoLedgerMeansNoBehaviourChange:
    def test_rail_is_the_identity_with_no_capital_events(self) -> None:
        r = CE.flow_adjusted_rail(4_000.0, None, 5_000.0)
        assert (r.net_flows_usd, r.n_events) == (0.0, 0)
        assert r.equity == 4_000.0 and r.peak == 5_000.0 and r.peak_raw == 5_000.0
        assert CE.flow_adjusted_rail(7_000.0, None, 5_000.0).peak == 7_000.0   # max(stored, eq)

    def test_evaluate_is_byte_identical_when_the_flow_channel_is_unused(self) -> None:
        for eq, start, peak in ((4_000.0, 5_000.0, 5_000.0), (9_000.0, 5_000.0, 6_000.0),
                                (2_000.0, 5_000.0, 5_000.0)):
            legacy = evaluate(eq, start, peak, 0.0, ruin_cap_lev=8.0)
            explicit = evaluate(eq, start, max(start, peak, eq), 0.0, ruin_cap_lev=8.0,
                                flow_adjusted_equity=eq)
            assert legacy.to_dict() == explicit.to_dict()

    def test_the_thresholds_themselves_are_untouched(self) -> None:
        """TIGHTEN-ONLY: R0320 changes the RULER, never the bar."""
        assert (DD_PAUSE, DRAWDOWN_RUIN) == (0.15, 0.35)
        assert risk_controls.BURN_FLOOR_EQUITY_FRAC == DD_PAUSE


class TestFlowSignsResolveTowardTighter:
    def test_withdrawal_kind_is_negative_whichever_sign_was_typed(self) -> None:
        assert CE.event_flow_usd({"kind": "WITHDRAWAL", "deposit_usd": 500.0}) == -500.0
        assert CE.event_flow_usd({"kind": "WITHDRAWAL", "deposit_usd": -500.0}) == -500.0

    def test_a_negative_deposit_credits_nothing(self) -> None:
        """A mis-keyed withdrawal that never said WITHDRAWAL must not reduce measured drawdown."""
        assert CE.event_flow_usd({"kind": "DEPOSIT", "deposit_usd": -500.0}) == 0.0
        assert CE.event_flow_usd({"kind": "RESTART", "deposit_usd": 0.0}) == 0.0

    def test_an_unparseable_row_contributes_nothing(self, tmp_path: Path) -> None:
        assert CE.event_flow_usd({"kind": "DEPOSIT", "deposit_usd": "lots"}) == 0.0
        (tmp_path / "capital_events.jsonl").write_text(
            json.dumps({"kind": "DEPOSIT", "deposit_usd": None}) + "\nnot json\n", "utf-8")
        assert CE.net_external_flows() == 0.0

    def test_net_flows_sum_the_ledger_in_order(self) -> None:
        _deposit(5_000.0, 5_000.0, 1_000.0)
        _withdraw(6_000.0, 6_000.0, 250.0)
        assert CE.net_external_flows() == pytest.approx(750.0)
        assert CE.flow_adjusted_rail(6_000.0, None, None).n_events == 2
