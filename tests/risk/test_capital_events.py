"""A ruin stop must have a way back, and that way must not be "move the rail".

The 2026-07-30 absorbing state: the carry book flattened on 113 consecutive rebalances, 100% of
them, because `dd_start` was measured against an inception frozen at $5,000 since 2026-07-02 and
never re-based. Flatten -> no opens -> no funding -> equity constant -> flatten. Provably closed.

The rail was right; the book really was down 37.2%. What was missing was a re-entry condition --
the same gap L1.16a names for the research graveyard, in risk form. These tests pin that the way
back is a CAPITAL EVENT and that the cheap way out is refused.
"""

from __future__ import annotations

import pytest

from libs.risk import capital_events as CE
from libs.risk import risk_controls


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(CE, "LEDGER", tmp_path / "capital_events.jsonl")


def _breached():
    """The desk's real position at audit time: $5,000 inception, $3,139.86 equity, -37.2%."""
    return 5000.0 - 1860.14, 5000.0


class TestTheAbsorbingStateIsReal:
    def test_the_rail_flattens_and_the_state_cannot_clear_itself(self):
        eq, start = _breached()
        d = risk_controls.evaluate(eq, start, 5061.379, 0.0, ruin_cap_lev=8.0)
        assert d.action == "flatten"
        assert "ruin-floor breach" in " ".join(d.reasons)
        # The closed loop: flat book => equity constant => same verdict forever. Re-evaluating
        # with identical inputs is exactly what the executor did 113 times.
        again = risk_controls.evaluate(eq, start, 5061.379, 0.0, ruin_cap_lev=8.0)
        assert again.action == "flatten"

    def test_a_deposit_is_what_clears_it(self):
        eq, start = _breached()
        ev = CE.rebase(equity_now=eq, start_equity=start, deposit_usd=2000.0,
                       authorised_by="principal", reason="Gate 0 launch funding deposit")
        d = risk_controls.evaluate(eq + 2000.0, ev.start_equity_after, 5061.379, 0.0,
                                   ruin_cap_lev=8.0)
        assert d.action != "flatten", "new capital re-bases the inception and clears the stop"


class TestTheCheapWayOutIsRefused:
    """THE property that makes this safe to build at all."""

    def test_a_zero_dollar_deposit_is_refused_as_meaningless(self):
        """Found by running the CLI on an empty state: it recorded a $0 DEPOSIT and reported
        success. That row moves the inception, links into the cumulative-loss chain, and says
        nothing -- a ledger of meaningless rows hides the real events."""
        eq, start = _breached()
        with pytest.raises(CE.CapitalEventRefused, match="records nothing"):
            CE.rebase(equity_now=eq, start_equity=start, deposit_usd=0.0,
                      authorised_by="the executor", reason="clear the stop so we can trade")

    def test_restarting_during_a_live_breach_without_capital_is_refused(self):
        """The real eat-the-safety-margin move: relabel it a RESTART and clear the breach with no
        new money. RESTART legitimately skips the zero-deposit guard, so this is the path that
        matters, and it must still be stopped without an explicit override."""
        eq, start = _breached()
        with pytest.raises(CE.CapitalEventRefused, match="NO capital"):
            CE.rebase(equity_now=eq, start_equity=start, deposit_usd=0.0, kind="RESTART",
                      authorised_by="the executor", reason="clear the stop so we can trade")

    def test_the_refusal_names_the_law_it_is_protecting(self):
        eq, start = _breached()
        with pytest.raises(CE.CapitalEventRefused) as exc:
            CE.rebase(equity_now=eq, start_equity=start, deposit_usd=0.0, kind="RESTART",
                      authorised_by="cron", reason="routine maintenance rebase")
        assert "L1.23" in str(exc.value) and "immutable core" in str(exc.value)

    def test_an_explicit_principal_override_is_allowed_and_recorded(self):
        """A human may still restart a book with no deposit -- but it is signed, and it is in the
        ledger under their name rather than happening quietly inside a rebalance."""
        eq, start = _breached()
        ev = CE.rebase(equity_now=eq, start_equity=start, deposit_usd=0.0,
                       authorised_by="PRINCIPAL-OVERRIDE zaid", kind="RESTART",
                       reason="formal restart of the carry book at reduced size after review")
        assert ev.start_equity_after == pytest.approx(eq)
        assert CE.history()[-1]["authorised_by"] == "PRINCIPAL-OVERRIDE zaid"

    def test_unsigned_events_are_refused(self):
        eq, start = _breached()
        with pytest.raises(CE.CapitalEventRefused, match="unsigned"):
            CE.rebase(equity_now=eq, start_equity=start, deposit_usd=5000.0,
                      authorised_by="   ", reason="a perfectly good reason here")

    def test_a_reason_that_is_not_a_record_is_refused(self):
        eq, start = _breached()
        with pytest.raises(CE.CapitalEventRefused, match="not a record"):
            CE.rebase(equity_now=eq, start_equity=start, deposit_usd=5000.0,
                      authorised_by="principal", reason="fix")


class TestMemoryIsNeverErased:
    def test_cumulative_loss_is_measured_from_the_FIRST_inception(self):
        """A re-base moves the rail's reference point. It must never move the desk's memory of
        what has been lost, or a book could be restarted to a clean sheet indefinitely."""
        eq, start = _breached()
        CE.rebase(equity_now=eq, start_equity=start, deposit_usd=2000.0,
                  authorised_by="principal", reason="first funding deposit after the stop")
        # Second stop, later, from the new inception.
        ev2 = CE.rebase(equity_now=3000.0, start_equity=5139.86, deposit_usd=2000.0,
                        authorised_by="principal", reason="second funding deposit after review")
        assert ev2.cumulative_loss_since_first_inception_usd == pytest.approx(3000.0 - 5000.0)

    def test_every_event_records_the_inception_it_replaced(self):
        eq, start = _breached()
        CE.rebase(equity_now=eq, start_equity=start, deposit_usd=1000.0,
                  authorised_by="principal", reason="deposit one for the launch")
        row = CE.history()[-1]
        assert row["start_equity_before"] == pytest.approx(5000.0)
        assert row["start_equity_after"] == pytest.approx(eq + 1000.0)


class TestItCannotLoosenAnythingByExisting:
    def test_no_ledger_means_the_rail_is_completely_unchanged(self):
        """The module must be inert on any box that has never had a capital event."""
        assert CE.effective_start_equity(5000.0) == 5000.0
        eq, start = _breached()
        assert risk_controls.evaluate(eq, CE.effective_start_equity(start), 5061.379, 0.0,
                                      ruin_cap_lev=8.0).action == "flatten"

    def test_the_ruin_threshold_itself_is_untouched(self):
        """L2.8a immutable core: a bar may be raised, never lowered. Nothing in this feature
        changes drawdown_ruin, and this fails the day something does."""
        import inspect
        sig = inspect.signature(risk_controls.evaluate)
        assert sig.parameters["drawdown_ruin"].default == 0.35
        src = inspect.getsource(risk_controls.evaluate)
        assert "dd_start <= -abs(drawdown_ruin)" in src
