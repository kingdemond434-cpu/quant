"""Survival-critical invariants: growth-positive risk controls, sizing, leverage, book reconcile.

These guard the exact bug classes that can lose money silently -- hedge drift, over-exposure,
over-levering an unproven edge, fabricated metrics. Pure/offline (no network, no keys).
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.live_book import LivePortfolio
from libs.risk import risk_controls
from libs.risk.dynamic_leverage import optimize_sleeve


@pytest.fixture(autouse=True)
def _hermetic_fee_burn(tmp_path, monkeypatch):
    """Gap #98: evaluate() defaults to reading the executor's live income artifact. Redirect to
    empty per-test paths so these verdicts are about the code, not the box's live burn state."""
    monkeypatch.setattr(risk_controls, "INCOME_ARTIFACT", tmp_path / "cashcarry_live.json")
    monkeypatch.setattr(risk_controls, "BURN_WINDOW_FILE", tmp_path / "fee_burn_window.json")


# ---------------- growth-positive risk controls ----------------
def test_risk_ok_when_flat_book():
    d = risk_controls.evaluate(5000, 5000, 5000, 1000, ruin_cap_lev=8.0)
    assert d.action == "ok"                       # normal operation -> zero drag on compounding


def test_risk_pause_not_flatten_on_drawdown():
    # 20% down from peak but far from the ruin floor -> PAUSE opens, never realise a loss
    d = risk_controls.evaluate(4000, 5000, 5000, 1000, ruin_cap_lev=8.0)
    assert d.action == "pause_opens"
    assert d.action != "flatten"


def test_risk_flatten_only_at_ruin():
    # 40% loss from start (> 35% ruin threshold) -> flatten to preserve future compounding
    d = risk_controls.evaluate(3000, 5000, 5000, 1000, ruin_cap_lev=8.0)
    assert d.action == "flatten"
    assert "ruin" in " ".join(d.reasons).lower()


def test_risk_exposure_guard_backstops_sizing_bug():
    # gross well above the ruin-boundary notional -> no new opens (backstop), but not a flatten
    d = risk_controls.evaluate(5000, 5000, 5000, 100_000, ruin_cap_lev=1.0)
    assert d.action == "pause_opens"


def test_risk_small_gain_is_ok():
    d = risk_controls.evaluate(5100, 5000, 5100, 1000, ruin_cap_lev=8.0)
    assert d.action == "ok"                       # winners never trip a control


# ---------------- funding-weighted sizing: RETIRED WITH THE CRYPTO DESK ----------------
#
# Four tests stood here for `run_cashcarry_executor._alloc` and `._funding_notional`, and three
# more below for its `_mkt_or_limit` order-cover path. That executor was a cash-and-carry basket
# on a crypto exchange -- perp funding against spot -- and it was deleted under the MT5 universe
# mandate (2026-08-18): "no crypto-exchange universe may EVER be hunted again".
#
# THE TESTS OUTLIVED THE CODE BY WEEKS and failed on ModuleNotFoundError the entire time, which is
# how they were finally found: the repo-wide suite has been red at 139 failures, hidden behind a
# mypy plugin error and a 20-minute CI job timeout that killed the run before pytest could report.
# Deleted rather than skipped, because a skipped test for deleted code is a permanent piece of
# scar tissue that every future reader has to re-investigate.
#
# WHAT IS NOT DELETED, and the distinction matters: the funding-notional MARK-BASIS lesson (R0308)
# is about a real defect class -- booking a financing charge on entry cost when the venue charges
# it on the mark path -- and it applies to any carry sleeve on any venue. It lives on in
# `desks/mt5/mt5desk/family_carry.py`, which is the MT5 desk's own carry mechanism, and in the
# swap-terms reconstruction in `family_inputs`. The mechanism survived the venue.


# ---------------- dynamic leverage: never over-lever an unproven edge ----------------
def test_leverage_floors_on_no_data():
    d = optimize_sleeve("x", np.array([]), fwd_sharpe=0.0, fwd_days=0.0)
    assert d.confidence == 0.0
    assert d.recommended <= 0.5                    # sits at the operational floor, unproven


def test_leverage_never_exceeds_growth_optimal_or_ruin_cap():
    rng = np.random.default_rng(0)
    rets = rng.normal(0.0005, 0.01, 300)
    d = optimize_sleeve("x", rets, fwd_sharpe=1.2, fwd_days=95.0)
    assert d.recommended <= d.growth_optimal + 1e-9
    assert d.recommended <= d.ruin_cap + 1e-9      # survival cap always binds first


# ---------------- LivePortfolio: reconciliation + no fabrication ----------------
def _book(**kw):
    base = {"base_per_leg": 5000.0, "start": "2026-07-01T00:00:00+00:00", "fut_equity": 4990.0,
            "fut_start_equity": 5000.0, "fut_unrealized": -2.0, "spot_leg_pnl": 3.0,
            "spot_usdt": 4600.0, "funding": 1.0, "carries": [], "mcurve": [], "trades": []}
    base.update(kw)
    return LivePortfolio(**base)


def test_net_reconciles_to_legs():
    p = _book()
    assert abs(p.net_pnl - (p.fut_pnl + p.spot_leg_pnl)) < 1e-6


def test_net_includes_realized_spot_of_closed_carries():
    # the perp side of a closed carry stays in the futures-equity delta; the spot side's proceeds
    # sit in the spot wallet, invisible to open-position marks. Dropping it fabricated a loss that
    # grew with every close (the phantom -$400 of 2026-07-09). Net must bank it.
    p = _book(spot_realized=400.0)
    assert abs(p.net_pnl - (p.fut_pnl + p.spot_leg_pnl + 400.0)) < 1e-6


def test_unmeasured_funding_is_labelled_not_fabricated():
    # R0013: during a venue outage the executor emits funding_measured=false; the 0.0 the
    # dashboard then shows is an ABSENCE, not a harvest of zero. The flag must survive all the
    # way through to_public so no surface can present a fabricated number as a measurement.
    p = _book(funding=0.0, funding_measured=False)
    pub = p.to_public()
    assert pub["deployed"]["funding_measured"] is False
    assert _book().to_public()["deployed"]["funding_measured"] is True   # default: measured


# ---------------- income ledger: pagination past the venue's 1000-row cap ----------------
def _income_page(t0, n, tran0):
    return [{"incomeType": "FUNDING_FEE", "income": "1.0", "time": t0 + i,
             "tranId": tran0 + i, "symbol": "XUSDT"} for i in range(n)]


def test_income_summary_paginates_and_dedupes():
    from libs.execution.binance_testnet import income_summary
    # page 1: exactly 1000 rows (the cap -> more may exist); page 2 re-serves the boundary row
    p1 = _income_page(1000, 1000, 0)                       # times 1000..1999
    p2 = [p1[-1], *_income_page(2000, 500, 1000)]          # dup boundary + 500 new (<1000 -> stop)
    calls = []

    def fake(params):
        calls.append(dict(params))
        return p1 if params["startTime"] == 1000 else p2

    out = income_summary(1000, fetch=fake)
    assert out["funding"] == 1500.0                        # all rows counted, boundary dup dropped
    assert len(calls) == 2                                 # paged exactly once past the cap


def test_income_summary_single_short_page_stops():
    from libs.execution.binance_testnet import income_summary
    calls = []

    def fake(params):
        calls.append(dict(params))
        return _income_page(1000, 3, 0)

    assert income_summary(1000, fetch=fake)["funding"] == 3.0
    assert len(calls) == 1                                 # <1000 rows -> no extra round-trips


def test_winrate_none_without_closed_trades():
    assert _book(trades=[{"event": "open", "symbol": "A"}]).winrate is None


def test_winrate_from_closed_trades():
    trades = [{"event": "close", "net": 5.0}, {"event": "close", "net": -1.0},
              {"event": "close", "net": 2.0}]
    assert _book(trades=trades).winrate == round(100 * 2 / 3, 1)


def test_deployed_sharpe_none_before_min_days():
    # a curve with <5 days of history must NOT emit an annualised Sharpe (honesty)
    p = _book(start="2026-07-03T00:00:00+00:00")
    assert p.deployed_sharpe is None


# ---------------- reconcile: market-first, limit-fallback on thin books ----------------
