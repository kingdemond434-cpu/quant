"""GAP #54 -- per-venue exposure cap. The one fatal risk nothing capped.

Per-name was capped at 35% and per-factor was capped, while the fraction of net worth sitting
inside a single exchange was capped by nothing: `grep -rn 'per_venue|venue_cap|venue_exposure'`
returned zero hits across the entire repo. SYSTEM_REVIEW ranks it fatal in its own words -- *"an
FTX-class failure is fatal to deployed capital regardless of strategy correctness"* -- and every
other control in risk_controls silently assumes the exchange gives the money back.

Two design decisions are pinned here because both are easy to "fix" into something worse:

  BREACH PAUSES OPENS, IT DOES NOT FLATTEN. Yanking capital off an exchange in a panic realises
  losses and is the move that converts a concentration problem into a solvency one. The cap
  governs where NEW money goes; moving existing balance is a treasury decision.

  DEFAULT 1.0 IS THE HONEST ONE-VENUE CAP, not a disabled control. It binds exactly where the
  desk already runs, so the enforcement path is live and proven before it ever has to bite.
"""

from __future__ import annotations

import pytest

from libs.risk.risk_controls import VENUE_CAP, evaluate

BASE = {"equity": 100_000.0, "start_equity": 100_000.0, "peak_equity": 100_000.0,
        "gross_notional": 50_000.0, "ruin_cap_lev": 3.0}


def test_single_venue_desk_is_unaffected_today() -> None:
    """Installing this now must change nothing -- that is what makes it free to install now."""
    d = evaluate(**BASE, venue_equity={"bybit": 100_000.0})
    assert d.action == "ok" and d.venue_breaches == []
    assert VENUE_CAP == 1.0


def test_breach_pauses_opens_and_names_the_venue() -> None:
    d = evaluate(**BASE, venue_equity={"bybit": 70_000.0, "binance": 30_000.0}, venue_cap=0.5)
    assert d.action == "pause_opens"
    assert d.venue_breaches == ["bybit"]
    assert "FTX-class" in " ".join(d.reasons)


def test_breach_never_escalates_to_flatten() -> None:
    """Flattening on concentration would realise losses to solve a counterparty problem."""
    d = evaluate(**BASE, venue_equity={"bybit": 100_000.0}, venue_cap=0.10)
    assert d.action == "pause_opens", "concentration must never trigger a forced liquidation"


def test_at_the_cap_exactly_is_not_a_breach() -> None:
    """Float noise must not manufacture a breach at the boundary."""
    d = evaluate(**BASE, venue_equity={"a": 50_000.0, "b": 50_000.0}, venue_cap=0.5)
    assert d.action == "ok" and d.venue_breaches == []


def test_every_breaching_venue_is_reported_not_just_the_worst() -> None:
    d = evaluate(**BASE, venue_equity={"a": 40_000.0, "b": 40_000.0, "c": 20_000.0},
                 venue_cap=0.3)
    assert d.venue_breaches == ["a", "b"]


def test_absent_venue_data_does_not_fabricate_a_breach() -> None:
    """No venue map means unmeasured, and unmeasured is not a violation to invent."""
    assert evaluate(**BASE).venue_breaches == []
    assert evaluate(**BASE, venue_equity={}).venue_breaches == []


def test_ruin_flatten_still_wins_over_a_venue_breach() -> None:
    """Survival ordering is unchanged: a ruin-floor breach short-circuits everything."""
    d = evaluate(equity=50_000.0, start_equity=100_000.0, peak_equity=100_000.0,
                 gross_notional=10_000.0, ruin_cap_lev=3.0,
                 venue_equity={"bybit": 50_000.0}, venue_cap=0.1)
    assert d.action == "flatten"


def test_drawdown_pause_and_venue_breach_coexist() -> None:
    d = evaluate(equity=80_000.0, start_equity=100_000.0, peak_equity=100_000.0,
                 gross_notional=10_000.0, ruin_cap_lev=3.0,
                 venue_equity={"bybit": 80_000.0}, venue_cap=0.5)
    assert d.action == "pause_opens"
    assert d.venue_breaches == ["bybit"]
    assert any("drawdown" in r for r in d.reasons), "the DD reason must not be lost"


@pytest.mark.parametrize("cap", [-1.0, 0.0, 1.0, 2.0])
def test_nonsense_caps_are_clamped_not_crashed(cap: float) -> None:
    d = evaluate(**BASE, venue_equity={"a": 100_000.0}, venue_cap=cap)
    assert d.action in ("ok", "pause_opens")


def test_zero_equity_does_not_divide_by_zero() -> None:
    d = evaluate(equity=0.0, start_equity=100_000.0, peak_equity=100_000.0,
                 gross_notional=0.0, ruin_cap_lev=3.0, venue_equity={"a": 1.0})
    assert d.action == "flatten"


def test_breaches_are_serialised_for_the_alerting_path() -> None:
    """A control nothing can page on is a control that fires into the void."""
    d = evaluate(**BASE, venue_equity={"a": 90_000.0, "b": 10_000.0}, venue_cap=0.5)
    assert d.to_dict()["venue_breaches"] == ["a"]
