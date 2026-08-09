"""Tests for self-healing spot-realized accounting (the 2026-07-10 phantom-loss fix)."""

from __future__ import annotations

from libs.execution.carry_accounting import (
    carry_bleed_report,
    dedup_basis,
    derive_spot_realized,
    read_income,
    reconcile_futures_leg,
)

# The live book as published 2026-08-05T20:50Z, from web/cashcarry_live.json and
# data/cashcarry_positions.json. Kept as one named fixture because the defect was an INTERACTION
# between these numbers, and a test built from rounder ones could not have expressed it.
_LIVE = {
    "equity_delta": 16.66,        # fut_eq - effective_start_equity(5757.08)
    "venue_realized": -3153.27,   # income_summary realized_pnl, exact
    "funding": 113.06,
    "commission": 1750.88,
    "rebase_usd": 4790.70,        # state 10547.78 -> ledgered RESTART inception 5757.08
    "spot_realized": 2921.35,
}


def _closes() -> list[dict]:
    return [
        {"event": "open", "symbol": "AAA", "opened": "t0"},
        {"event": "close", "symbol": "AAA", "opened": "t0", "price_pnl": 2.0},
        {"event": "close", "symbol": "BBB", "opened": "t1", "price_pnl": -1.0},
    ]


def test_dedup_basis_sums_closes() -> None:
    assert dedup_basis(_closes()) == 1.0


def test_dedup_basis_collapses_duplicate_close_logs() -> None:
    # a flatten logs the same (symbol, opened) close several times -> count once
    trades = [
        *_closes(),
        {"event": "close", "symbol": "AAA", "opened": "t0", "price_pnl": 2.0},
        {"event": "close", "symbol": "AAA", "opened": "t0", "price_pnl": 2.0},
    ]
    assert dedup_basis(trades) == 1.0


def test_derive_spot_realized_offsets_venue_realized() -> None:
    # delta-neutral: shorts realized -650 (market rose) -> spot legs realized ~+650 + basis
    trades = [{"event": "close", "symbol": "X", "opened": "t", "price_pnl": 61.17}]
    assert derive_spot_realized(-650.68, trades) == 711.85


def test_derive_is_robust_to_bad_rows() -> None:
    trades = [
        {"event": "close", "symbol": "X", "opened": "t", "price_pnl": "oops"},
        {"event": "close", "symbol": "Y", "opened": "u", "price_pnl": 5.0},
    ]
    assert derive_spot_realized(0.0, trades) == 5.0
    assert derive_spot_realized(None, trades) == 5.0  # type: ignore[arg-type]


def test_carry_bleed_clean_when_legs_cancel() -> None:
    r = carry_bleed_report(funding=100.0, spot_pnl=60.0, fut_pnl=42.0)  # non-funding +2
    assert not r.alert
    assert bool(r) is True
    assert r.non_funding_pnl == 2.0
    assert "clean" in r.verdict


def test_carry_bleed_ok_when_small_drain() -> None:
    r = carry_bleed_report(funding=100.0, spot_pnl=10.0, fut_pnl=70.0)  # non-funding -20 (20%)
    assert not r.alert
    assert r.non_funding_pnl == -20.0
    assert r.harvest_eaten_frac == 0.2


def test_carry_bleed_alarms_when_hedge_loses_more_than_it_earns() -> None:
    # the live shape: +90 funding, real legs -252 -> non-funding -342 = ~382% of harvest
    r = carry_bleed_report(funding=89.65, spot_pnl=-200.0, fut_pnl=-52.84)
    assert r.alert
    assert bool(r) is False
    assert r.non_funding_pnl == -342.49
    assert r.harvest_eaten_frac > 3.0
    assert "BLEED" in r.verdict


def test_carry_bleed_alarms_on_any_drain_with_no_harvest() -> None:
    r = carry_bleed_report(funding=-5.0, spot_pnl=-10.0, fut_pnl=0.0)
    assert r.alert
    assert r.harvest_eaten_frac == float("inf")


def test_carry_bleed_alarms_on_a_large_POSITIVE_non_funding_pnl() -> None:
    # delta-neutral target is ~0 in BOTH signs: a windfall this size is a naked/untracked leg
    # (the 2026-07-26 stranded-spot class), never edge. A one-sided alarm called this "clean".
    r = carry_bleed_report(funding=100.0, spot_pnl=500.0, fut_pnl=-100.0)  # non-funding +300
    assert r.alert
    assert bool(r) is False
    assert r.non_funding_pnl == 300.0
    assert "BLEED(inverted)" in r.verdict
    assert "NAKED" in r.verdict


def test_carry_bleed_small_positive_non_funding_is_still_clean() -> None:
    # only a windfall >= alert_frac of the harvest is a broken hedge; noise must not page
    r = carry_bleed_report(funding=100.0, spot_pnl=60.0, fut_pnl=42.0)  # non-funding +2
    assert not r.alert
    assert "clean" in r.verdict


# --- UNMEASURED funding: unknown is not zero (2026-07-26 incident) -------------------------


def test_bleed_report_unmeasured_does_not_fabricate_a_verdict() -> None:
    """A failed venue read must NOT be judged as a zero harvest.

    Regression for 2026-07-26: `_safe()` swallowed an HTTP 502 on /fapi/v1/income, funding stayed
    at its initialised 0.0, and the alarm divided by it to publish an `inf%` total-bleed verdict
    against a book that had really harvested $101.96.
    """
    r = carry_bleed_report(funding=None, spot_pnl=-32.7, fut_pnl=-876.93)
    assert r.measured is False
    assert r.alert is False                      # an outage is not an economic bleed verdict
    assert r.funding is None
    assert r.non_funding_pnl is None             # undecidable, not zero
    assert r.harvest_eaten_frac is None          # never inf from a fabricated denominator
    assert "UNMEASURED" in r.verdict
    assert not r                                 # unmeasured must not read as healthy


def test_bleed_report_zero_funding_still_alarms() -> None:
    """A genuine zero harvest is a real state and must keep alarming -- the fix must not mute it."""
    r = carry_bleed_report(funding=0.0, spot_pnl=-10.0, fut_pnl=-5.0)
    assert r.measured is True
    assert r.alert is True
    assert r.non_funding_pnl == -15.0


def test_read_income_returns_none_after_retries_not_zero() -> None:
    calls: list[int] = []

    def boom() -> dict:
        calls.append(1)
        raise OSError("HTTP Error 502: Bad Gateway")

    assert read_income(boom, attempts=3, sleeper=lambda _: None) is None
    assert len(calls) == 3                       # transient 5xx is retried before giving up


def test_read_income_retries_then_succeeds() -> None:
    seq: list[object] = [OSError("502"), OSError("502"), {"funding": 101.96}]

    def flaky() -> dict:
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[return-value]

    assert read_income(flaky, attempts=3, sleeper=lambda _: None) == {"funding": 101.96}


def test_read_income_rejects_non_dict_payload() -> None:
    """A venue error page parsed as a list is not a measurement."""
    assert read_income(lambda: ["unexpected"], attempts=1, sleeper=lambda _: None) is None


# =================================================================================================
# FUTURES-LEG RECONCILIATION (2026-08-05). The primary carry book published net_pnl +2938.01 while
# the venue income ledger said the futures leg was -4791.09 -- a $4,807.75 overstatement on the
# desk's ONLY deployed sleeve, whose own note says it "builds the forward track record the gate
# sizes on". Cause: `fut_pnl = fut_eq - start_eq` where start_eq is the RUIN RAIL's inception,
# which a principal-signed re-base legitimately moved 10,547.78 -> 5,757.08 on 2026-08-01.
# =================================================================================================


def test_reconcile_reproduces_the_live_overstatement_exactly() -> None:
    """The regression that motivates the whole feature, in the numbers it actually happened in."""
    r = reconcile_futures_leg(**{k: v for k, v in _LIVE.items() if k != "spot_realized"})
    assert r.measured
    assert r.income_ledger == -4791.09          # realized + funding - commission, venue-native
    assert r.gap == 4807.75                     # exactly the residual the old code called unknown
    assert r.explained                          # and the ledgered re-base accounts for it
    assert "REBASE-LEAK" in r.verdict
    # The published headline was +2938.01; the honest one is -1869.74. A $4.8k sign flip.
    published = round(_LIVE["spot_realized"] + _LIVE["equity_delta"], 2)
    reported = round(_LIVE["spot_realized"] + (r.reporting_pnl or 0.0), 2)
    assert published == 2938.01
    assert reported == -1869.74


def test_reporting_pnl_is_immune_to_the_rebase_that_broke_it() -> None:
    """The point of the fix: moving the rail's inception may not move the performance number."""
    base = {k: v for k, v in _LIVE.items() if k != "spot_realized"}
    before = reconcile_futures_leg(**{**base, "equity_delta": -4791.09, "rebase_usd": 0.0})
    after = reconcile_futures_leg(**base)       # same book, inception re-based by +4790.70
    assert before.reporting_pnl == after.reporting_pnl == -4791.09
    assert before.gap == 0.0 and before.verdict.startswith("AGREE")


def test_a_gap_the_rebase_does_not_explain_is_a_phantom_not_a_rebase_leak() -> None:
    """EXPLAINED and FINE are different claims -- the distinction the old `residual` field lost."""
    base = {k: v for k, v in _LIVE.items() if k != "spot_realized"}
    r = reconcile_futures_leg(**{**base, "rebase_usd": 0.0})
    assert r.measured and not r.explained
    assert "PHANTOM" in r.verdict
    assert r.gap == 4807.75                     # same gap, different and louder verdict


def test_unmeasured_income_is_never_reported_as_agreement() -> None:
    """A venue read that failed is not two measurements agreeing (the 2026-07-26 inf% class)."""
    base = {k: v for k, v in _LIVE.items() if k != "spot_realized"}
    for missing in ("venue_realized", "funding", "commission"):
        r = reconcile_futures_leg(**{**base, missing: None})
        assert not r.measured and not r.explained
        assert r.gap is None and r.reporting_pnl is None   # no fabricated substitute
        assert missing in r.verdict and "UNDECIDABLE" in r.verdict


def test_tolerance_does_not_scale_with_the_gap_it_must_catch() -> None:
    base = {k: v for k, v in _LIVE.items() if k != "spot_realized"}
    near = reconcile_futures_leg(**{**base, "equity_delta": -4780.0, "rebase_usd": 0.0})
    assert near.gap == 11.09 and near.verdict.startswith("AGREE")


def test_bleed_alarm_cannot_order_a_hedge_reconcile_on_a_book_with_no_legs() -> None:
    """The alarm fired for four days demanding an action that was impossible to perform."""
    flat = carry_bleed_report(funding=113.06, spot_pnl=2921.35, fut_pnl=16.66, open_legs=0)
    assert flat.alert                                        # still alarms -- this is not a mute
    assert "NAKED" not in flat.verdict
    assert "ZERO open carries" in flat.verdict
    # It narrows to two candidates rather than clearing the hedge: `open_legs` counts TRACKED
    # carries, and untracked exposure is exactly what the naked-leg hypothesis is about.
    assert "ACCOUNTING artifact" in flat.verdict and "UNTRACKED exposure" in flat.verdict


def test_bleed_alarm_still_names_a_naked_leg_when_legs_actually_exist() -> None:
    """The old verdict is correct when the book HAS legs; the fix narrows it, never deletes it."""
    held = carry_bleed_report(funding=113.06, spot_pnl=2921.35, fut_pnl=16.66, open_legs=4)
    assert held.alert and "NAKED/UNTRACKED leg" in held.verdict and "4 open leg(s)" in held.verdict


def test_bleed_alarm_prefers_the_measured_cause_over_the_guessed_one() -> None:
    base = {k: v for k, v in _LIVE.items() if k != "spot_realized"}
    recon = reconcile_futures_leg(**base)
    b = carry_bleed_report(funding=113.06, spot_pnl=2921.35, fut_pnl=16.66,
                           open_legs=0, recon=recon)
    assert b.alert and "ACCOUNTING, NOT EDGE" in b.verdict and "REBASE-LEAK" in b.verdict
