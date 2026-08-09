"""MUTATION-DRIVEN STRENGTH TESTS for the pre-trade risk gate (gap #53, the money path).

Measured 2026-07-29: `libs/risk/gate.py` killed **23.5%** of mutants (39 of 51 survived) against a
90% bar — **the worst score on the desk, on the module that decides whether capital moves.** Cause
is plain: 10 tests for 210 lines, and they covered the happy path plus a couple of rejections. Every
fail-closed branch, every governor hand-off, and every cap arithmetic term was unpinned.

The tests below are written as BOUNDARY PAIRS (the value that must pass and the neighbour that must
fail), because only a pair kills an off-by-one, and as REJECTION-REASON assertions, because a gate
that rejects for the wrong reason is a gate whose forensics lie.

DIRECTION NOTE: nothing here changes `gate.py`. A risk-path module is not edited to satisfy a
checker (register #52's standing warning); these tests pin the behaviour that exists.
"""
from __future__ import annotations

import pytest
from tests.risk.conftest import make_account, make_intent

from libs.risk.gate import risk_gate


def _approved() -> None:
    assert risk_gate(make_intent(), make_account()).approved


class TestFailClosedInputs:
    """Each guard's own boundary: the legal edge must pass, the illegal neighbour must reject."""

    @pytest.mark.parametrize("equity", [0.0, -1.0, -100_000.0])
    def test_non_positive_equity_rejects(self, equity: float) -> None:
        d = risk_gate(make_intent(), make_account(equity=equity))
        assert d.approved is False
        assert "invalid equity" in " ".join(d.reasons)

    def test_smallest_positive_equity_is_not_rejected_for_equity(self) -> None:
        # The boundary is `<= 0`, so a tiny POSITIVE equity must not trip the equity guard.
        d = risk_gate(make_intent(), make_account(equity=1.0, peak_equity=1.0))
        assert "invalid equity" not in " ".join(d.reasons)

    @pytest.mark.parametrize("peak", [0.0, -5.0])
    def test_non_positive_peak_equity_rejects(self, peak: float) -> None:
        d = risk_gate(make_intent(), make_account(peak_equity=peak))
        assert d.approved is False
        assert "invalid equity" in " ".join(d.reasons)

    @pytest.mark.parametrize("rpu", [0.0, -0.01, -10.0])
    def test_non_positive_risk_per_unit_rejects(self, rpu: float) -> None:
        d = risk_gate(make_intent(risk_per_unit=rpu), make_account())
        assert d.approved is False
        assert "invalid risk_per_unit" in " ".join(d.reasons)

    def test_smallest_positive_risk_per_unit_passes_that_guard(self) -> None:
        d = risk_gate(make_intent(risk_per_unit=1e-9), make_account())
        assert "invalid risk_per_unit" not in " ".join(d.reasons)

    def test_stale_data_rejects_and_records_the_check(self) -> None:
        d = risk_gate(make_intent(), make_account(data_stale=True))
        assert d.approved is False
        assert "stale data" in " ".join(d.reasons)
        # The check trail must show WHICH gate failed -- forensics depend on it.
        assert {"name": "data", "passed": False} in d.checks

    def test_fresh_data_records_a_passing_check(self) -> None:
        d = risk_gate(make_intent(), make_account())
        assert {"name": "data", "passed": True} in d.checks


class TestKillSwitch:
    def test_kill_switch_rejects_with_its_own_reason(self) -> None:
        d = risk_gate(make_intent(), make_account(kill_switch_tripped=True))
        assert d.approved is False
        assert "kill-switch" in " ".join(d.reasons)
        assert {"name": "kill_switch", "passed": False} in d.checks

    def test_kill_switch_outranks_a_perfectly_good_intent(self) -> None:
        # Ordering matters: the kill switch must not be reachable-past by good sizing.
        d = risk_gate(make_intent(kelly_fraction=0.01, risk_budget=0.01),
                      make_account(kill_switch_tripped=True))
        assert d.approved is False
        assert d.sized_units == 0.0

    def test_untripped_kill_switch_records_a_passing_check(self) -> None:
        assert {"name": "kill_switch", "passed": True} in risk_gate(
            make_intent(), make_account()).checks


class TestDrawdownGovernor:
    def test_deep_drawdown_halts_with_the_drawdown_reason(self) -> None:
        d = risk_gate(make_intent(), make_account(equity=50_000.0, peak_equity=100_000.0))
        assert d.approved is False
        assert "drawdown halt" in " ".join(d.reasons)

    def test_flat_equity_does_not_halt_on_drawdown(self) -> None:
        d = risk_gate(make_intent(), make_account())
        assert "drawdown halt" not in " ".join(d.reasons)

    def test_drawdown_check_carries_its_level(self) -> None:
        d = risk_gate(make_intent(), make_account(equity=95_000.0, peak_equity=100_000.0))
        dd = [c for c in d.checks if c.get("name") == "drawdown"]
        assert dd and "level" in dd[0]

    def test_monotone_in_drawdown_deeper_never_approves_more(self) -> None:
        """A deeper drawdown must never authorise MORE size than a shallower one -- the property
        the whole ladder exists to guarantee, and it was untested."""
        prev = None
        for eq in (100_000.0, 97_000.0, 94_000.0, 90_000.0, 85_000.0):
            d = risk_gate(make_intent(), make_account(equity=eq, peak_equity=100_000.0))
            units = d.sized_units if d.approved else 0.0
            if prev is not None:
                assert units <= prev + 1e-9, f"size rose as drawdown deepened at equity {eq}"
            prev = units


class TestScalarsAndCaps:
    def test_zero_confidence_collapses_the_scalar_and_rejects(self) -> None:
        d = risk_gate(make_intent(confidence=0.0), make_account())
        assert d.approved is False
        assert "global risk scalar is zero" in " ".join(d.reasons)

    def test_negative_confidence_is_clamped_not_trusted(self) -> None:
        # The gate clamps confidence into [0,1]; a negative must behave like 0, never flip a sign.
        d = risk_gate(make_intent(confidence=-5.0), make_account())
        assert d.approved is False
        assert d.sized_units == 0.0

    def test_confidence_above_one_is_clamped_and_cannot_inflate_size(self) -> None:
        base = risk_gate(make_intent(confidence=1.0), make_account())
        high = risk_gate(make_intent(confidence=99.0), make_account())
        assert high.approved == base.approved
        assert high.sized_units == pytest.approx(base.sized_units)

    def test_crisis_conditions_reduce_or_reject_never_increase(self) -> None:
        calm = risk_gate(make_intent(), make_account())
        crisis = risk_gate(make_intent(), make_account(vol_now=10.0, vol_baseline=1.0,
                                                      average_correlation=0.95))
        calm_units = calm.sized_units if calm.approved else 0.0
        crisis_units = crisis.sized_units if crisis.approved else 0.0
        assert crisis_units <= calm_units + 1e-9

    def test_exhausted_heat_budget_cannot_approve_more_size(self) -> None:
        d = risk_gate(make_intent(), make_account(current_heat_total=1e12))
        assert (d.approved is False) or d.sized_units == 0.0

    def test_existing_factor_exposure_cannot_increase_approved_size(self) -> None:
        clean = risk_gate(make_intent(), make_account())
        loaded = risk_gate(make_intent(), make_account(
            factor_exposures={"XAUUSD": 1e11}))
        clean_units = clean.sized_units if clean.approved else 0.0
        loaded_units = loaded.sized_units if loaded.approved else 0.0
        assert loaded_units <= clean_units + 1e-9

    def test_approved_decision_is_internally_consistent(self) -> None:
        d = risk_gate(make_intent(), make_account())
        assert d.approved is True
        assert d.sized_units > 0.0
        assert d.global_scalar > 0.0
        assert d.reasons == [] or all(isinstance(r, str) for r in d.reasons)

    def test_rejection_always_zeroes_size_and_scalar(self) -> None:
        """The rejection contract: no rejected decision may carry a non-zero size, or a caller
        that reads sized_units without checking `approved` trades on a refusal."""
        for acct in (make_account(kill_switch_tripped=True),
                     make_account(data_stale=True),
                     make_account(equity=1.0, peak_equity=100_000.0)):
            d = risk_gate(make_intent(), acct)
            if not d.approved:
                assert d.sized_units == 0.0
                assert d.global_scalar == 0.0
                assert d.risk_approval_id is None
                assert d.reasons, "a rejection must always carry a reason"

    def test_bool_of_decision_matches_approved(self) -> None:
        assert bool(risk_gate(make_intent(), make_account())) is True
        assert bool(risk_gate(make_intent(), make_account(data_stale=True))) is False


class TestModelContracts:
    """The remaining survivors were pydantic-level: frozen configs and field DEFAULTS. Both are
    real contracts -- a mutable intent could be edited between validation and execution, and a
    default that moves off the safe value silently re-prices every caller that omits the field."""

    def test_intent_and_account_are_frozen(self) -> None:
        intent, acct = make_intent(), make_account()
        with pytest.raises((ValueError, TypeError, AttributeError)):
            intent.risk_per_unit = 0.0   # type: ignore[misc]
        with pytest.raises((ValueError, TypeError, AttributeError)):
            acct.equity = 1.0            # type: ignore[misc]

    def test_decision_is_frozen(self) -> None:
        d = risk_gate(make_intent(), make_account())
        with pytest.raises((ValueError, TypeError, AttributeError)):
            d.approved = False           # type: ignore[misc]

    def test_intent_defaults_are_the_safe_values(self) -> None:
        from libs.risk.gate import OrderIntent
        i = OrderIntent(instrument="XAUUSD", side="buy", kelly_fraction=0.25,
                        risk_budget=0.5, risk_per_unit=10.0)
        assert i.confidence == 1.0        # full confidence only when nothing says otherwise
        assert i.cost is None and i.alpha_id is None
        assert i.id.startswith("intent")  # every intent is identifiable in the audit trail

    def test_account_defaults_are_the_neutral_values(self) -> None:
        from libs.risk.gate import AccountState
        a = AccountState(equity=100.0, peak_equity=100.0, forecast_vol=0.10)
        assert a.average_correlation == 0.0
        assert a.vol_now == 0.0 and a.vol_baseline == 0.0
        assert a.kill_switch_tripped is False and a.data_stale is False
        assert a.factor_exposures == {} and a.current_heat_total == 0.0

    def test_account_default_flags_do_not_block_a_benign_trade(self) -> None:
        # If a default flipped to the tripped/stale side, every default-constructed account would
        # reject -- the mutation is only observable if something asserts the default path APPROVES.
        from libs.risk.gate import AccountState
        d = risk_gate(make_intent(), AccountState(equity=100_000.0, peak_equity=100_000.0,
                                                 forecast_vol=0.10))
        assert d.approved is True

    def test_two_intents_get_distinct_ids(self) -> None:
        assert make_intent().id != make_intent().id

    def test_factor_exposures_default_is_not_shared_between_instances(self) -> None:
        from libs.risk.gate import AccountState
        a = AccountState(equity=1.0, peak_equity=1.0, forecast_vol=0.1)
        b = AccountState(equity=2.0, peak_equity=2.0, forecast_vol=0.1)
        assert a.factor_exposures == b.factor_exposures == {}
        assert a.factor_exposures is not b.factor_exposures   # no shared mutable default


# =================================================================================================
# ROUND 2 (2026-07-30). The first pass took gate.py from 23.5% -> 86.3%; these kill the seven
# mutants that survived it. Six are on the FACTOR-HEADROOM arithmetic and the two fail-closed
# return paths -- i.e. the code that decides how much capital may move and what happens when the
# gate itself errors, which is the last place a silent no-op should be possible.
# =================================================================================================


class TestRejectionPathsReturnADecisionNotNone:
    """`return _reject(...) -> return None` survived on two branches.

    A None return is the worst possible failure shape here: it carries no reasons, no checks and
    no `approved=False`, so any caller doing `if decision.approved` raises AttributeError while a
    caller doing `if not decision` silently treats a REJECTION as falsy and may proceed. Pinning
    the object identity -- not just the boolean -- is what kills the mutant.
    """

    def test_equity_floor_breach_returns_a_rejection_object(self) -> None:
        from libs.risk.config import PreservationConfig, RiskConfig
        cfg = RiskConfig(preservation=PreservationConfig(equity_floor=95_000.0))
        d = risk_gate(make_intent(), make_account(equity=94_000.0, peak_equity=100_000.0), cfg)
        assert d is not None, "the equity-floor branch must return a decision, never None"
        assert d.approved is False
        assert "equity floor breached" in " ".join(d.reasons)
        assert d.sized_units == 0.0
        assert any(c["name"] == "preservation" for c in d.checks)

    def test_internal_risk_error_fails_closed_with_a_decision(self) -> None:
        """The except-RiskError path. An unmapped instrument raises inside the gate; the gate must
        convert that into a REJECTION, not swallow it into None."""
        d = risk_gate(make_intent(instrument="NOT_A_REAL_SYMBOL"), make_account())
        assert d is not None
        assert d.approved is False
        assert "fail-closed" in " ".join(d.reasons)
        assert d.sized_units == 0.0


class TestFactorHeadroomArithmetic:
    """Three mutants lived in one expression pair:

        factor_used   = sum(abs(v) for s, v in exposures if get_factor(s) == factor)   # Eq->NotEq
        factor_cap    = cfg.exposure.factor_caps.get(factor, 1.0) * equity             # 1.0->2.0
        factor_headroom = factor_cap_amount - factor_used                              # Sub->Add

    Together they decide how much MORE of a factor the book may take on. Each mutant loosens it,
    and none of them is visible from a happy-path test, because the default account carries no
    exposure at all -- zero exposure makes all three arithmetically indistinguishable.
    """

    def test_same_factor_exposure_shrinks_the_size(self) -> None:
        """Kills `Sub -> Add`: headroom must FALL as same-factor exposure is consumed."""
        clean = risk_gate(make_intent(), make_account()).sized_units
        loaded = risk_gate(make_intent(),
                           make_account(factor_exposures={"XAUUSD": 39_000.0})).sized_units
        assert 0.0 < loaded < clean, (
            f"same-factor exposure must consume headroom (clean={clean}, loaded={loaded}); "
            "an ADD here would let existing exposure INCREASE the permitted size")

    def test_other_factor_exposure_does_not_touch_the_size(self) -> None:
        """Kills `Eq -> NotEq`: only the intent's OWN factor consumes its cap. EURUSD is FX,
        XAUUSD is precious metals -- a big FX book must not shrink a gold order, and under the
        mutant it is the only thing that would."""
        clean = risk_gate(make_intent(), make_account()).sized_units
        cross = risk_gate(make_intent(),
                          make_account(factor_exposures={"EURUSD": 39_000.0})).sized_units
        assert cross == clean, (
            f"unrelated-factor exposure changed the size ({clean} -> {cross}) -- the cap is "
            "per-factor, and summing the wrong side inverts the whole limit")

    def test_a_factor_with_no_configured_cap_defaults_to_one_times_equity(self) -> None:
        """Kills `1.0 -> 2.0`: the default cap for an UNCONFIGURED factor. This is the fail-closed
        direction for a factor nobody wrote a limit for -- at 1.0x equity a book already 1.5x
        deep in that factor has no headroom; at 2.0x it would be handed another 0.5x."""
        from libs.risk.config import ExposureLimits, RiskConfig
        from libs.risk.instruments import Factor
        cfg = RiskConfig(exposure=ExposureLimits(factor_caps={Factor.FX: 0.40}))
        d = risk_gate(make_intent(),                                    # XAUUSD: no cap configured
                      make_account(factor_exposures={"XAUUSD": 150_000.0}), cfg)
        assert d.approved is False, (
            "at a 1.0x-equity default cap, $150k of exposure on a $100k book leaves no headroom; "
            "a 2.0x default would approve and quietly double an unconfigured factor's limit")
        assert "factor_cap" in " ".join(d.reasons)


class TestCorrelationCheckBoundary:
    """`passed: s_corr >= 1.0` carried two mutants (`GtE -> Gt`, `1.0 -> 2.0`).

    It is a REPORTED field rather than control flow, which is exactly why it survived -- nothing
    asserted the reported value. It still matters: `checks` is the gate's forensic record, and a
    check that misreports at the boundary makes every post-trade review of a scaled-down day
    wrong in the same direction.
    """

    def test_uncorrelated_book_reports_the_scalar_as_passing_at_exactly_one(self) -> None:
        d = risk_gate(make_intent(), make_account(average_correlation=0.0))
        corr = next(c for c in d.checks if c["name"] == "correlation")
        assert corr["scalar"] == 1.0, "a zero-correlation book must not be scaled at all"
        assert corr["passed"] is True, (
            "at exactly 1.0 the check must read PASSED -- a strict '>' reports the neutral case "
            "as a failure, and a 2.0 threshold reports every possible case as one")

    def test_a_correlated_book_scales_down_and_reports_not_passed(self) -> None:
        d = risk_gate(make_intent(), make_account(average_correlation=0.95))
        corr = next(c for c in d.checks if c["name"] == "correlation")
        assert corr["scalar"] < 1.0
        assert corr["passed"] is False
