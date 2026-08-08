"""THE FUTURES TESTNET CONNECTOR'S READ AND ORDER PATHS -- 49% covered on code that places orders.

WHY THIS FILE EXISTS. The coverage ratchet's own `next_ceiling` says it plainly: a bug in a
research script costs a cycle, a bug on the order path walks a short through zero. The money path
sat at 70.45% against 92.69% repo-wide, and 168 of the 221 uncovered statements were in the two
TESTNET connectors -- which is exactly backwards, because testnet is where the order path is
exercised BEFORE it is trusted with money. An untested rehearsal is not a rehearsal.

Every test here patches the transport (`_get` / `_signed`) rather than reaching a venue: these are
tests of PARSING, REFUSAL and ORDER CONSTRUCTION, which is where the defects this desk has actually
suffered live -- a maxQty cap ignored, a close leg missing reduce_only, an idempotency token that
tagged a flatten as an open.
"""

from __future__ import annotations

from typing import Any

import pytest

import libs.execution.binance_testnet as bt


@pytest.fixture(autouse=True)
def _armed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials present, so `_signed` reaches the patched transport rather than refusing."""
    monkeypatch.setenv("BINANCE_TESTNET_KEY", "k")
    monkeypatch.setenv("BINANCE_TESTNET_SECRET", "s")
    bt._MKT_MAX_CACHE.clear()


def _patch(monkeypatch: pytest.MonkeyPatch, *, get: Any = None, signed: Any = None) -> list[Any]:
    """Record every call so the ENDPOINT and PARAMS are assertable, not just the return value."""
    calls: list[Any] = []

    def _g(path: str, params: dict | None = None):
        calls.append(("GET", path, params))
        return get(path, params) if callable(get) else get

    def _s(path: str, params: dict, *, method: str = "GET"):
        calls.append((method, path, params))
        return signed(path, params, method) if callable(signed) else signed

    monkeypatch.setattr(bt, "_get", _g)
    monkeypatch.setattr(bt, "_signed", _s)
    return calls


# ----------------------------------------------------------------- credentials


def test_KEYS_LOAD_FROM_THE_KEYFILE_WHEN_ENV_IS_ABSENT(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("BINANCE_TESTNET_KEY", raising=False)
    monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)
    f = tmp_path / "k.json"
    f.write_text('{"key": "kk", "secret": "ss"}', "utf-8")
    monkeypatch.setattr(bt, "_KEYFILE", f)
    assert bt._creds() == ("kk", "ss") and bt.has_keys() is True


def test_A_CORRUPT_KEYFILE_IS_NO_KEYS_RATHER_THAN_A_CRASH(monkeypatch, tmp_path) -> None:
    """A truncated paste must disarm the connector, not raise from inside an order path. The
    failure mode to avoid is a JSONDecodeError surfacing at the moment someone is flattening."""
    monkeypatch.delenv("BINANCE_TESTNET_KEY", raising=False)
    monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)
    f = tmp_path / "k.json"
    f.write_text("{not json", "utf-8")
    monkeypatch.setattr(bt, "_KEYFILE", f)
    assert bt._creds() == (None, None) and bt.has_keys() is False


# ----------------------------------------------------------------- public reads


def test_EXCHANGE_FILTERS_PARSE_STEP_MIN_AND_PRECISION(monkeypatch) -> None:
    _patch(monkeypatch, get={"symbols": [{
        "symbol": "BTCUSDT", "quantityPrecision": 3, "pricePrecision": 1,
        "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.002"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.10"}]}]})
    f = bt.exchange_filters()["BTCUSDT"]
    assert f["step"] == 0.001 and f["min_qty"] == 0.002
    assert f["qty_prec"] == 3 and f["tick"] == 0.10 and f["price_prec"] == 1


def test_BOOK_TICKER_RETURNS_EMPTY_ON_A_NON_LIST_RATHER_THAN_RAISING(monkeypatch) -> None:
    """A venue error object where a list was expected must not propagate into maker pricing."""
    _patch(monkeypatch, get={"code": -1121, "msg": "Invalid symbol"})
    assert bt.book_ticker() == {}


def test_BOOK_TICKER_PARSES_BID_AND_ASK(monkeypatch) -> None:
    _patch(monkeypatch, get=[{"symbol": "BTCUSDT", "bidPrice": "100.5", "askPrice": "100.7"}])
    assert bt.book_ticker() == {"BTCUSDT": (100.5, 100.7)}


def test_QUOTE_DEPTH_SUMS_THE_SIDE_A_TRADE_WOULD_EAT(monkeypatch) -> None:
    """BUY eats asks, SELL eats bids. Getting this backwards would size against liquidity that
    is not there for the trade being placed."""
    book = {"asks": [["100", "1"], ["100.5", "2"], ["200", "9"]],
            "bids": [["99", "3"], ["98.5", "1"], ["50", "9"]]}
    _patch(monkeypatch, get=book)
    buy = bt.quote_depth("BTCUSDT", "BUY", pct=0.01)
    sell = bt.quote_depth("BTCUSDT", "SELL", pct=0.01)
    assert buy == pytest.approx(100 * 1 + 100.5 * 2)     # the 200 level is outside 1%
    assert sell == pytest.approx(99 * 3 + 98.5 * 1)      # the 50 level is outside 1%


def test_QUOTE_DEPTH_IS_ZERO_WHEN_UNKNOWN_SO_CALLERS_STAND_ASIDE(monkeypatch) -> None:
    """'Unknown' must read as 'thin'. Returning anything else would let a caller size into a book
    it could not measure."""
    _patch(monkeypatch, get={"asks": [], "bids": []})
    assert bt.quote_depth("BTCUSDT", "BUY") == 0.0

    def _boom(*a, **k):
        raise OSError("venue down")
    monkeypatch.setattr(bt, "_get", _boom)
    assert bt.quote_depth("BTCUSDT", "BUY") == 0.0


def test_MARK_PRICES_PARSE_AND_TOLERATE_A_NON_LIST(monkeypatch) -> None:
    _patch(monkeypatch, get=[{"symbol": "ETHUSDT", "price": "3000.5"}])
    assert bt.mark_prices() == {"ETHUSDT": 3000.5}
    _patch(monkeypatch, get={"code": -1})
    assert bt.mark_prices() == {}


# ----------------------------------------------------------------- signed reads


def test_AVG_FILL_IS_QUOTE_OVER_BASE_ON_OUR_SIDE_ONLY(monkeypatch) -> None:
    """Including the other side's fills would average a buy into a sell and report a price the
    desk never paid."""
    _patch(monkeypatch, signed=[
        {"side": "BUY", "qty": "2", "quoteQty": "200"},
        {"side": "BUY", "qty": "1", "quoteQty": "110"},
        {"side": "SELL", "qty": "5", "quoteQty": "9999"},
    ])
    assert bt.avg_fill("BTCUSDT", "BUY", 0) == pytest.approx(310 / 3)


def test_AVG_FILL_IS_NONE_RATHER_THAN_A_FABRICATED_PRICE(monkeypatch) -> None:
    """Callers fall back to the mark. A zero or a guess would enter accounting as a real fill."""
    _patch(monkeypatch, signed=[])
    assert bt.avg_fill("BTCUSDT", "BUY", 0) is None

    def _boom(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(bt, "_signed", _boom)
    assert bt.avg_fill("BTCUSDT", "BUY", 0) is None


def test_MY_TRADES_PASSES_THE_WINDOW_AND_DEGRADES_TO_EMPTY(monkeypatch) -> None:
    calls = _patch(monkeypatch, signed=[{"qty": "1"}])
    assert bt.my_trades("BTCUSDT", 100, end_ms=200, limit=50) == [{"qty": "1"}]
    _m, _p, params = calls[0]
    assert params["startTime"] == 100 and params["endTime"] == 200 and params["limit"] == 50

    def _boom(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(bt, "_signed", _boom)
    assert bt.my_trades("BTCUSDT", 0) == []


def test_ACCOUNT_BALANCE_PICKS_USDT_AND_DEFAULTS_TO_ZERO(monkeypatch) -> None:
    _patch(monkeypatch, signed=[{"asset": "BNB", "balance": "9"},
                                {"asset": "USDT", "balance": "1234.5"}])
    assert bt.account_balance() == 1234.5
    _patch(monkeypatch, signed=[{"asset": "BNB", "balance": "9"}])
    assert bt.account_balance() == 0.0


def test_ACCOUNT_SUMMARY_MAPS_EVERY_FIELD(monkeypatch) -> None:
    _patch(monkeypatch, signed={"totalWalletBalance": "100", "totalMarginBalance": "110",
                                "totalUnrealizedProfit": "10", "availableBalance": "80",
                                "totalInitialMargin": "30"})
    s = bt.account_summary()
    assert s == {"wallet": 100.0, "equity": 110.0, "unrealized_pnl": 10.0,
                 "available": 80.0, "margin_used": 30.0}


def test_POSITIONS_DROPS_FLAT_SYMBOLS(monkeypatch) -> None:
    """A zero row is not a position. Carrying it would make `flatten_all` send a reduce-only
    order against an already-flat symbol, which the venue rejects with -2022."""
    _patch(monkeypatch, signed=[{"symbol": "BTCUSDT", "positionAmt": "0.5"},
                                {"symbol": "ETHUSDT", "positionAmt": "0"},
                                {"symbol": "SOLUSDT", "positionAmt": "-2"}])
    assert bt.positions() == {"BTCUSDT": 0.5, "SOLUSDT": -2.0}


def test_FORCE_ORDERS_COUNTS_PER_SYMBOL_AND_IS_EMPTY_WITHOUT_KEYS(monkeypatch) -> None:
    """A short leg the VENUE closed must not be re-shorted into the squeeze that took it."""
    _patch(monkeypatch, signed=[{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"},
                                {"symbol": "ETHUSDT"}, {"symbol": ""}])
    assert bt.force_orders() == {"BTCUSDT": 2, "ETHUSDT": 1}

    monkeypatch.setattr(bt, "has_keys", lambda: False)
    assert bt.force_orders() == {}


def test_FORCE_ORDERS_IS_EMPTY_ON_ERROR_NOT_A_RAISE(monkeypatch) -> None:
    def _boom(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(bt, "_signed", _boom)
    assert bt.force_orders() == {}


def test_SET_LEVERAGE_SWALLOWS_A_NON_FATAL_VENUE_ERROR(monkeypatch) -> None:
    """Leverage already set is not a reason to abort a cycle."""
    def _boom(*a, **k):
        raise OSError("-4028")
    monkeypatch.setattr(bt, "_signed", _boom)
    assert bt.set_leverage("BTCUSDT", 3) is None


# --------------------------------------------------------------- the order path


def test_A_MARKET_ORDER_IS_SPLIT_TO_RESPECT_THE_VENUE_CAP(monkeypatch) -> None:
    """THE 2026-07-27 INCIDENT. COOKIEUSDT's maxQty is 150,000 and the desk sent 183,140; the
    venue rejected every market order with -4005, the caller fell back to a RESTING post-only
    limit, and accumulated fills walked a short through zero into a +916,772 LONG carrying -$482."""
    monkeypatch.setattr(bt, "_market_max_qty", lambda s: 100.0)
    calls = _patch(monkeypatch, signed={"orderId": 1})
    bt.place_market("COOKIEUSDT", "BUY", 250.0)
    qtys = [p["quantity"] for _m, _p, p in calls]
    assert qtys == [100.0, 100.0, 50.0], f"not split to the cap: {qtys}"


def test_A_CLOSE_LEG_IS_REDUCE_ONLY_AND_TAGGED_AS_A_CLOSE(monkeypatch) -> None:
    """GAP #90. Without reduce_only a close sized from a stale `positions()` read sells THROUGH
    zero into the opposite position -- incident #6's exact mechanism. And the client order ID must
    say `close`, or an emergency flatten collides with a genuine entry in the same 90s bucket."""
    monkeypatch.setattr(bt, "_market_max_qty", lambda s: float("inf"))
    calls = _patch(monkeypatch, signed={"orderId": 1})
    bt.place_market("BTCUSDT", "SELL", 1.0, reduce_only=True, cycle="c1")
    _m, _p, params = calls[0]
    assert params["reduceOnly"] == "true"
    close_id = params["newClientOrderId"]
    # The intent is HASHED into the id, not spelled in it, so the property that matters is
    # DISTINCTNESS: a flatten must not collide with a genuine entry inside the same idempotency
    # bucket. Asserting a substring would test the encoding; this tests the guarantee.
    calls2 = _patch(monkeypatch, signed={"orderId": 2})
    bt.place_market("BTCUSDT", "SELL", 1.0, reduce_only=False, cycle="c1")
    assert calls2[0][2]["newClientOrderId"] != close_id, (
        "a close and an open in the same cycle produced the SAME client order id -- the venue "
        "would reject one as a duplicate, and which one is not something the desk controls")


def test_AN_OPEN_IS_NOT_REDUCE_ONLY(monkeypatch) -> None:
    monkeypatch.setattr(bt, "_market_max_qty", lambda s: float("inf"))
    calls = _patch(monkeypatch, signed={"orderId": 1})
    bt.place_market("BTCUSDT", "BUY", 1.0)
    _m, _p, params = calls[0]
    assert "reduceOnly" not in params
    assert params["newClientOrderId"], "an open carries no idempotency token at all"


def test_POST_ONLY_IS_GTX_AND_CARRIES_AN_IDEMPOTENCY_TOKEN(monkeypatch) -> None:
    """Resting orders are MORE dangerous to duplicate, not less -- incident #6 was accumulated
    resting fills."""
    calls = _patch(monkeypatch, signed={"orderId": 7})
    bt.place_post_only("BTCUSDT", "BUY", 1.0, 100.0, cycle="c2")
    _m, path, params = calls[0]
    assert params["timeInForce"] == "GTX" and params["type"] == "LIMIT"
    assert path.endswith("/order")
    resting_id = params["newClientOrderId"]
    monkeypatch.setattr(bt, "_market_max_qty", lambda s: float("inf"))
    calls2 = _patch(monkeypatch, signed={"orderId": 8})
    bt.place_market("BTCUSDT", "BUY", 1.0, cycle="c2")
    assert calls2[0][2]["newClientOrderId"] != resting_id, (
        "a resting maker quote and a market order in the same cycle share an id")


def test_OPEN_ORDERS_AND_CANCEL_ALL_DEGRADE_TO_SAFE_SHAPES(monkeypatch) -> None:
    _patch(monkeypatch, signed=[{"orderId": 1}])
    assert bt.open_orders("BTCUSDT") == [{"orderId": 1}]
    _patch(monkeypatch, signed={"code": 200})
    assert bt.open_orders() == []                     # a dict where a list was expected
    calls = _patch(monkeypatch, signed={"code": 200})
    assert bt.cancel_all("BTCUSDT") == {"code": 200}
    assert calls[0][0] == "DELETE"


def test_FLATTEN_IS_REDUCE_ONLY_PER_SYMBOL_AND_ISOLATED(monkeypatch) -> None:
    """GAP #90 again, on the path that only runs because something already went wrong. One
    rejected leg -- routinely -2022 against an already-flat position -- must not abandon every
    position after it."""
    monkeypatch.setattr(bt, "positions", lambda: {"AAA": 1.0, "BBB": -2.0, "CCC": 3.0})
    monkeypatch.setattr(bt, "_market_max_qty", lambda s: float("inf"))
    seen: list[tuple[str, str, float, bool]] = []

    def _place(symbol, side, qty, reduce_only=False, cycle=None):
        seen.append((symbol, side, qty, reduce_only))
        if symbol == "BBB":
            raise OSError("-2022 ReduceOnly Order is rejected")
        return {"symbol": symbol}

    monkeypatch.setattr(bt, "place_market", _place)
    out = bt.flatten_all()
    assert [s[0] for s in seen] == ["AAA", "BBB", "CCC"], "a rejection abandoned the rest"
    assert all(s[3] is True for s in seen), "a close leg was not reduce-only"
    assert seen[0][1] == "SELL" and seen[1][1] == "BUY"      # long -> SELL, short -> BUY
    assert any("error" in r for r in out), "the failed leg was not reported as a failure"
    assert len(out) == 3
