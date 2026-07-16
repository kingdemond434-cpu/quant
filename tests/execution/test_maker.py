"""Tests for maker-first batch execution (post-only quote, wait, taker fallback)."""

from __future__ import annotations

import libs.execution.maker as mk


def _filters() -> dict[str, dict[str, float]]:
    return {s: {"tick": 0.1, "price_prec": 2, "step": 0.001, "min_qty": 0.0, "qty_prec": 3}
            for s in ("AAA", "BBB", "CCC")}


def test_maker_fills_rest_become_maker_and_unfilled_fall_back(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    placed: dict[str, str] = {}
    market_calls: list[str] = []

    def fake_post_only(sym, side, qty, price):  # type: ignore[no-untyped-def]
        placed[sym] = "rested"
        return {"orderId": sym + "1"}

    def fake_market(sym, side, qty):  # type: ignore[no-untyped-def]
        market_calls.append(sym)
        return {"status": "FILLED"}

    # AAA fills (no longer open), BBB stays resting -> taker fallback
    def fake_open_orders(sym=None):  # type: ignore[no-untyped-def]
        return [] if sym == "AAA" else [{"orderId": sym + "1"}]

    monkeypatch.setattr(mk.bt, "place_post_only", fake_post_only)
    monkeypatch.setattr(mk.bt, "place_market", fake_market)
    monkeypatch.setattr(mk.bt, "open_orders", fake_open_orders)
    monkeypatch.setattr(mk.bt, "cancel_all", lambda sym: {"code": 200})
    monkeypatch.setattr(mk.time, "sleep", lambda *_: None)

    book = {"AAA": (100.0, 100.5), "BBB": (50.0, 50.4)}
    modes = mk.maker_execute_batch([("AAA", "BUY", 1.0), ("BBB", "SELL", 2.0)],
                                   filters=_filters(), book=book, wait_s=0.0)
    assert modes["AAA"] == "maker"             # filled while resting -> maker
    assert modes["BBB"] == "taker_fallback"    # still resting -> cancelled + market
    assert "BBB" in market_calls and "AAA" not in market_calls
    assert abs(mk.maker_share(modes) - 0.5) < 1e-9


def test_maker_no_book_routes_taker(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    market_calls: list[str] = []
    monkeypatch.setattr(mk.bt, "place_market",
                        lambda s, side, q: market_calls.append(s) or {"status": "FILLED"})
    modes = mk.maker_execute_batch([("CCC", "BUY", 1.0)], filters=_filters(),
                                   book={}, wait_s=0.0)        # no book quote
    assert modes["CCC"] == "taker"
    assert market_calls == ["CCC"]
