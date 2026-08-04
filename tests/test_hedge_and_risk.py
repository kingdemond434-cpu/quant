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


# ---------------- funding-weighted sizing (capacity) ----------------
def test_alloc_weights_sum_to_capital_and_cap():
    from scripts.run_cashcarry_executor import _alloc
    cands = [("A", 0.010), ("B", 0.005), ("C", 0.001)]
    alloc = _alloc(cands, 3000.0, cap_frac=0.35)
    assert abs(sum(alloc.values()) - 3000.0) < 1e-6          # conserves total capital
    assert all(v <= 3000.0 * 0.35 + 1e-6 for v in alloc.values())  # concentration cap holds
    assert alloc["A"] >= alloc["B"] >= alloc["C"]            # higher funding -> more notional


def test_alloc_zero_funding_is_equal_weight():
    from scripts.run_cashcarry_executor import _alloc
    alloc = _alloc([("A", 0.0), ("B", 0.0)], 2000.0)
    assert abs(alloc["A"] - alloc["B"]) < 1e-6


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
class _StubConn:
    """Fake venue: place_market raises when the book is 'thin' (PERCENT_PRICE reject)."""
    def __init__(self, mkt_ok: bool) -> None:
        self.mkt_ok, self.calls = mkt_ok, []

    def place_market(self, s, side, q):
        self.calls.append(("mkt", s, side, q))
        if not self.mkt_ok:
            raise RuntimeError("HTTP 400 -4131 PERCENT_PRICE")
        return {"status": "FILLED"}

    def cancel_all(self, s):
        self.calls.append(("cancel", s))

    def book_ticker(self):
        return {"X": (0.035, 0.061)}

    def place_post_only(self, s, side, q, px):
        self.calls.append(("limit", s, side, q, px))
        return {"status": "NEW"}


def _cover():
    import sys
    sys.path.insert(0, "scripts")
    from run_cashcarry_executor import _mkt_or_limit
    return _mkt_or_limit


def test_reconcile_uses_market_on_healthy_book():
    c = _StubConn(True)
    assert _cover()(c, "X", "BUY", 100) == "mkt"
    assert c.calls == [("mkt", "X", "BUY", 100)]           # no needless limit churn


def test_reconcile_falls_back_to_limit_on_thin_book():
    # market rejected (thin book) -> the OLD guard would strand the orphan forever; now it limits
    c = _StubConn(False)
    assert _cover()(c, "X", "BUY", 100) == "limit"
    assert ("cancel", "X") in c.calls                      # no duplicate stacking across ticks
    assert ("limit", "X", "BUY", 100, 0.035) in c.calls    # BUY rests at the bid (near touch)


def test_reconcile_limit_side_correct_and_zero_guard():
    c = _StubConn(False)
    _cover()(c, "X", "SELL", 50)
    assert ("limit", "X", "SELL", 50, 0.061) in c.calls    # SELL rests at the ask
    z = _StubConn(True)
    assert _cover()(z, "X", "BUY", 0) == "" and z.calls == []   # nothing to do -> no order
