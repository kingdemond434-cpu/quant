"""The venue-truth fee join (2026-07-28 finding).

Every per-trade economic verdict this desk produced was fee-blind: `_tca` records slippage-vs-mid
and no commission term, so `net` = price_pnl + est_funding never charged the trade. The venue
billed $1,750.65 while the trade log's aggregate net read +$0.16, and the >24h hold class read
-42 bps against a true -635 bps. These tests pin the join that closes that gap.
"""
from __future__ import annotations

import scripts.run_trade_forensics as tf


def _close(sym: str, opened: str, closed: str, notional: float, net: float, held: float):
    return {"event": "close", "symbol": sym, "opened": opened, "closed": closed,
            "notional": notional, "net": net, "held_hours": held}


def _ms(stamp: str) -> int:
    return tf._ms(stamp)


def _patch_events(monkeypatch, events):
    """Stand in for the venue's COMMISSION feed."""
    import libs.execution.binance_testnet as bt
    monkeypatch.setattr(bt, "commission_events", lambda since_ms, symbol="": events)


def test_commission_lands_on_the_trade_that_was_open(monkeypatch):
    """A fee inside [opened, closed] for that symbol is charged to that round-trip."""
    a = _close("BTCUSDT", "2026-07-01T00:00:00+00:00", "2026-07-01T10:00:00+00:00", 1000.0, 5.0, 10)
    _patch_events(monkeypatch, [
        {"symbol": "BTCUSDT", "time": _ms("2026-07-01T00:00:01+00:00"), "commission": 0.5},
        {"symbol": "BTCUSDT", "time": _ms("2026-07-01T09:59:00+00:00"), "commission": 0.5},
    ])
    r = tf._fee_attribution([a], 0)
    assert r["_fees"][id(a)] == 1.0
    assert r["attributed"] == 1.0
    assert r["unattributed"] == 0.0


def test_fee_outside_any_window_is_unattributed_not_smeared(monkeypatch):
    """Commission billed against no round-trip stays visible instead of being spread nearby.

    This residual is what a phantom-fill bug looks like from the outside; hiding it inside the
    trades that happen to be adjacent is how a fee fire reads as ordinary execution cost.
    """
    a = _close("BTCUSDT", "2026-07-01T00:00:00+00:00", "2026-07-01T10:00:00+00:00", 1000.0, 5.0, 10)
    _patch_events(monkeypatch, [
        {"symbol": "BTCUSDT", "time": _ms("2026-07-02T00:00:00+00:00"), "commission": 7.0},
    ])
    r = tf._fee_attribution([a], 0)
    assert r["_fees"].get(id(a), 0.0) == 0.0
    assert r["unattributed"] == 7.0
    assert r["unattributed_share"] == 1.0


def test_symbol_must_match(monkeypatch):
    """A fee on ETH is never charged to a BTC carry that happened to be open."""
    a = _close("BTCUSDT", "2026-07-01T00:00:00+00:00", "2026-07-01T10:00:00+00:00", 1000.0, 5.0, 10)
    _patch_events(monkeypatch, [
        {"symbol": "ETHUSDT", "time": _ms("2026-07-01T05:00:00+00:00"), "commission": 3.0},
    ])
    r = tf._fee_attribution([a], 0)
    assert r["_fees"].get(id(a), 0.0) == 0.0
    assert r["unattributed"] == 3.0


def test_each_event_claimed_once_across_adjacent_windows(monkeypatch):
    """Sequential carries on one symbol must not double-count a boundary fill.

    The book holds at most one carry per symbol, so windows are adjacent rather than overlapping;
    double-charging the boundary would inflate the bill and manufacture a leak that is not there.
    """
    a = _close("BTCUSDT", "2026-07-01T00:00:00+00:00", "2026-07-01T10:00:00+00:00", 1000.0, 5.0, 10)
    b = _close("BTCUSDT", "2026-07-01T10:00:00+00:00", "2026-07-01T20:00:00+00:00", 1000.0, 5.0, 10)
    _patch_events(monkeypatch, [
        {"symbol": "BTCUSDT", "time": _ms("2026-07-01T10:00:00+00:00"), "commission": 4.0},
    ])
    r = tf._fee_attribution([a, b], 0)
    assert r["attributed"] == 4.0
    assert r["_fees"].get(id(a), 0.0) + r["_fees"].get(id(b), 0.0) == 4.0
    assert r["unattributed"] == 0.0


def test_unreadable_venue_yields_no_verdict_not_a_zero(monkeypatch):
    """An unmeasured cost reported as zero is the phantom the organ exists to prevent."""
    import libs.execution.binance_testnet as bt

    def boom(*_a, **_k):
        raise RuntimeError("venue down")
    monkeypatch.setattr(bt, "commission_events", boom)
    r = tf._fee_attribution([], 0)
    assert "error" in r
    assert "_fees" not in r          # -> main() publishes no fee-adjusted bucket at all


def test_buckets_charge_the_fee(monkeypatch):
    """The whole point: the same trades read differently once the bill is applied."""
    a = _close("BTCUSDT", "2026-07-01T00:00:00+00:00", "2026-07-02T12:00:00+00:00",
               1000.0, 5.0, 36.0)
    blind = tf._buckets([a])
    charged = tf._buckets([a], {id(a): 20.0})
    assert blind[">24h"]["bps"] == 50.0                  # +5 on 1000 notional
    assert charged[">24h"]["fee"] == 20.0
    assert charged[">24h"]["bps"] == -150.0              # (5 - 20) / 1000
    assert "fee" not in blind[">24h"]                    # fee-blind row stays unchanged
