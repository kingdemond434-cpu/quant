"""GAP #98 / ledger R0025 -- the cost-rate brake between an alarm and the ruin rail.

The 2026-07-28 churn engine burned $1,456 of fees in 48h against $113 of LIFETIME funding
harvest. §40 (`check_fee_carry_ratio`) fired ~27h before diagnosis with no authority to stop
anything; the only brake that ended the fire was the equity ruin rail at -35%, after the money
was gone. These tests pin the two new pause-opens triggers in BOTH directions:

  * they FIRE (windowed fees past the documented fraction of harvest; windowed net burn past the
    DD-pause fraction of equity) -- and only ever as `pause_opens`, NEVER a flatten or any touch
    on closes (closes are never excited, L1.45);
  * they STAY QUIET on healthy economics, on a flat-book denominator, and -- recorded, not
    silent -- on UNMEASURED input (L1.41: an unreadable venue read must never become a phantom
    pause, and must never disappear from the record either).

The thresholds are pinned to their DOCUMENTED sources so a drive-by edit cannot silently mint a
new number: `alert_frac` from `carry_bleed_report` (the desk's standing bleed-alarm bar), §40's
7-day window and flat-book guard, and the ruin rail's own DD-pause level for the burn floor.
"""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.execution.carry_accounting import carry_bleed_report
from libs.risk import risk_controls
from libs.risk.risk_controls import (
    BURN_FLOOR_EQUITY_FRAC,
    DD_PAUSE,
    DRAWDOWN_RUIN,
    FEE_HARVEST_PAUSE_FRAC,
    FEE_MIN_FUNDING,
    FEE_WINDOW_H,
    FeeBurnWindow,
    evaluate,
    fee_burn_triggers,
    load_fee_burn_window,
)

BASE = {"equity": 10_000.0, "start_equity": 10_000.0, "peak_equity": 10_000.0,
        "gross_notional": 5_000.0, "ruin_cap_lev": 3.0}
T0 = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def _win(funding: float, fees: float, span_h: float = 168.0) -> FeeBurnWindow:
    return FeeBurnWindow(funding=funding, fees=fees, span_h=span_h)


UNMEASURED = FeeBurnWindow(funding=None, fees=None, span_h=0.0, note="test: no artifact")


# ---------------- the fractions are REUSED desk constants, not invented numbers ----------------
def test_fee_fraction_is_the_desks_documented_bleed_alarm_bar() -> None:
    """0.5 is `carry_bleed_report(alert_frac=...)` -- the standing dashboard bar for 'the leak is
    eating the harvest'. Pinned equal so the brake and the alarm can never drift apart silently."""
    documented = inspect.signature(carry_bleed_report).parameters["alert_frac"].default
    assert FEE_HARVEST_PAUSE_FRAC == documented == 0.5
    # ... and strictly inside §40's absolute ratio>1.0 bar ("fees EXCEED the funding earned").
    assert FEE_HARVEST_PAUSE_FRAC < 1.0


def test_burn_floor_derives_from_the_ruin_rails_own_levels() -> None:
    """The income channel gets the same pause bar the mark-to-market channel already has, leaving
    the identical 20-point headroom to the ruin rail that the DD breaker leaves."""
    assert BURN_FLOOR_EQUITY_FRAC == DD_PAUSE == 0.15
    assert DRAWDOWN_RUIN == 0.35
    assert DRAWDOWN_RUIN - BURN_FLOOR_EQUITY_FRAC > 0, "the brake must sit BEFORE the ruin rail"


def test_window_and_flat_book_guard_match_section_40() -> None:
    """§40 (`check_fee_carry_ratio`) measures 7d and returns below $5 of harvest -- same here."""
    assert FEE_WINDOW_H == 7 * 24.0
    assert FEE_MIN_FUNDING == 5.0


# ---------------- trigger (a): windowed fee-vs-harvest ----------------
def test_fees_past_the_fraction_pause_opens() -> None:
    d = evaluate(**BASE, fee_burn=_win(funding=20.0, fees=10.1))
    assert d.action == "pause_opens"
    assert any("fee-vs-harvest" in r for r in d.reasons)


def test_fees_below_the_fraction_do_not_pause() -> None:
    d = evaluate(**BASE, fee_burn=_win(funding=20.0, fees=9.9))
    assert d.action == "ok"


def test_flat_book_guard_keeps_the_ratio_quiet_like_section_40() -> None:
    """Below §40's $5 harvest bar the ratio is noise -- a 50x 'ratio' on $0.10 of funding must not
    pause a book that only paid a cup of coffee in fees. (The burn floor still guards the real
    fee-fire case: see test_burn_floor_fires_even_with_zero_harvest.)"""
    d = evaluate(**BASE, fee_burn=_win(funding=0.10, fees=5.0))
    assert d.action == "ok"


def test_fee_trigger_never_escalates_past_pause_opens() -> None:
    """Closes are never excited (L1.45): however obscene the fee bill, this brake must not
    realise a loss to fix a cost problem."""
    d = evaluate(**BASE, fee_burn=_win(funding=100.0, fees=100_000.0))
    assert d.action == "pause_opens"
    assert d.action != "flatten"


# ---------------- trigger (b): absolute-burn floor ----------------
def test_burn_floor_fires_even_with_zero_harvest() -> None:
    """The churn-engine class: near-zero funding, a fee fire eating equity. §40's ratio was
    guarded off exactly here -- the floor is the trigger that needs no denominator."""
    d = evaluate(**BASE, fee_burn=_win(funding=0.0, fees=1_500.0))   # 15% of $10k equity
    assert d.action == "pause_opens"
    assert any("burn floor" in r for r in d.reasons)


def test_burn_below_the_floor_does_not_pause() -> None:
    d = evaluate(**BASE, fee_burn=_win(funding=0.0, fees=1_499.0))
    assert d.action == "ok"


def test_paying_funding_counts_as_burn() -> None:
    """Negative windowed funding is money OUT the same as fees -- the floor sees the sum."""
    reasons, pause = fee_burn_triggers(10_000.0, _win(funding=-1_000.0, fees=500.0))
    assert pause and any("burn floor" in r for r in reasons)


def test_burn_floor_never_flattens() -> None:
    d = evaluate(**BASE, fee_burn=_win(funding=-5_000.0, fees=5_000.0))
    assert d.action == "pause_opens"


# ---------------- unmeasured input: quiet, but RECORDED (L1.41) ----------------
def test_unmeasured_never_pauses_and_never_skips_silently() -> None:
    d = evaluate(**BASE, fee_burn=UNMEASURED)
    assert d.action == "ok", "a venue outage must never be rendered as a burn verdict"
    assert any("UNMEASURED" in r for r in d.reasons), "a silent skip hides a blind brake"


def test_missing_artifact_on_the_default_path_is_recorded_unmeasured() -> None:
    """The executor's exact call shape (no fee_burn kwarg) on a box with no artifact."""
    d = evaluate(**BASE)   # conftest redirects the artifact paths to an empty tmp dir
    assert d.action == "ok"
    assert any("UNMEASURED" in r for r in d.reasons)


def test_unmeasured_cannot_downgrade_a_real_pause() -> None:
    d = evaluate(equity=8_000.0, start_equity=10_000.0, peak_equity=10_000.0,
                 gross_notional=1_000.0, ruin_cap_lev=3.0, fee_burn=UNMEASURED)
    assert d.action == "pause_opens"                      # the DD breaker still owns its verdict
    assert any("drawdown" in r for r in d.reasons)


def test_ruin_flatten_still_wins_over_everything() -> None:
    """Survival ordering unchanged: the ruin rail short-circuits before any fee logic runs."""
    d = evaluate(equity=6_000.0, start_equity=10_000.0, peak_equity=10_000.0,
                 gross_notional=1_000.0, ruin_cap_lev=3.0,
                 fee_burn=_win(funding=100.0, fees=100_000.0))
    assert d.action == "flatten"


# ---------------- the defensive artifact/window reader ----------------
def _write_artifact(p: Path, *, updated: datetime, funding: object, commission: object) -> None:
    p.write_text(json.dumps({"updated": updated.isoformat(), "funding_harvested": funding,
                             "fut_commission": commission, "funding_measured": True}), "utf-8")


def test_reader_absent_artifact_is_unmeasured(tmp_path: Path) -> None:
    w = load_fee_burn_window(tmp_path / "missing.json", tmp_path / "h.json", now=T0)
    assert not w.measured and "unreadable" in w.note


def test_reader_corrupt_artifact_is_unmeasured(tmp_path: Path) -> None:
    art = tmp_path / "live.json"
    art.write_text("{not json", "utf-8")
    w = load_fee_burn_window(art, tmp_path / "h.json", now=T0)
    assert not w.measured and not (tmp_path / "h.json").exists()


def test_reader_null_income_fields_are_unmeasured_not_zero(tmp_path: Path) -> None:
    """`read_income` publishes None when the venue read fails -- that must stay None here, never
    decay into a measured $0 window (the 2026-07-26 fabricated-zero class)."""
    art = tmp_path / "live.json"
    _write_artifact(art, updated=T0, funding=None, commission=None)
    w = load_fee_burn_window(art, tmp_path / "h.json", now=T0)
    assert not w.measured and "not measured" in w.note


def test_reader_single_tick_does_not_fabricate_a_window(tmp_path: Path) -> None:
    art, hist = tmp_path / "live.json", tmp_path / "h.json"
    _write_artifact(art, updated=T0, funding=10.0, commission=3.0)
    w = load_fee_burn_window(art, hist, now=T0)
    assert not w.measured and "not yet spanning" in w.note


def test_reader_differences_cumulatives_across_ticks(tmp_path: Path) -> None:
    art, hist = tmp_path / "live.json", tmp_path / "h.json"
    _write_artifact(art, updated=T0, funding=10.0, commission=3.0)
    load_fee_burn_window(art, hist, now=T0)
    _write_artifact(art, updated=T0 + timedelta(hours=6), funding=14.0, commission=5.5)
    w = load_fee_burn_window(art, hist, now=T0 + timedelta(hours=6))
    assert w.measured
    assert w.funding == 4.0 and w.fees == 2.5 and w.span_h == 6.0


def test_reader_prunes_samples_older_than_the_window(tmp_path: Path) -> None:
    art, hist = tmp_path / "live.json", tmp_path / "h.json"
    _write_artifact(art, updated=T0, funding=1.0, commission=1.0)
    load_fee_burn_window(art, hist, now=T0)
    later = T0 + timedelta(hours=FEE_WINDOW_H + 1)          # first sample now outside the window
    _write_artifact(art, updated=later, funding=50.0, commission=20.0)
    w = load_fee_burn_window(art, hist, now=later)
    assert not w.measured, "a lone in-window sample must not difference against ancient history"


def test_reader_restarts_on_inception_rebase(tmp_path: Path) -> None:
    """Cumulative commission can only grow; a fall means the book re-based -- differencing across
    two inceptions would fabricate a negative fee bill."""
    art, hist = tmp_path / "live.json", tmp_path / "h.json"
    _write_artifact(art, updated=T0, funding=100.0, commission=400.0)
    load_fee_burn_window(art, hist, now=T0)
    _write_artifact(art, updated=T0 + timedelta(hours=1), funding=0.0, commission=0.0)
    w = load_fee_burn_window(art, hist, now=T0 + timedelta(hours=1))
    assert not w.measured and "not yet spanning" in w.note


def test_reader_ignores_a_repeated_tick(tmp_path: Path) -> None:
    """Several organs read the same artifact write; the window must not double-record it."""
    art, hist = tmp_path / "live.json", tmp_path / "h.json"
    _write_artifact(art, updated=T0, funding=10.0, commission=3.0)
    load_fee_burn_window(art, hist, now=T0)
    load_fee_burn_window(art, hist, now=T0)
    assert len(json.loads(hist.read_text("utf-8"))) == 1


# ---------------- end-to-end: the executor's call shape, burning book ----------------
def test_executor_call_shape_pauses_on_a_live_burning_artifact(
    tmp_path: Path, monkeypatch,
) -> None:
    """evaluate() with NO fee_burn kwarg -- exactly run_cashcarry_executor.py's call -- must read
    the artifact, difference the window and pause opens on churn-engine economics."""
    art, hist = tmp_path / "cashcarry_live.json", tmp_path / "fee_burn_window.json"
    monkeypatch.setattr(risk_controls, "INCOME_ARTIFACT", art)
    monkeypatch.setattr(risk_controls, "BURN_WINDOW_FILE", hist)
    hist.write_text(json.dumps(
        [{"t": (datetime.now(tz=UTC) - timedelta(hours=48)).isoformat(),
          "funding": 100.0, "commission": 10.0}]), "utf-8")
    _write_artifact(art, updated=datetime.now(tz=UTC), funding=113.0, commission=1_466.0)
    d = evaluate(**BASE)                     # fees 1456 vs funding 13 in-window on $10k equity
    assert d.action == "pause_opens"
    assert any("fee-vs-harvest" in r or "burn floor" in r for r in d.reasons)
    assert d.action != "flatten", "the brake adds a pause, never a liquidation"
