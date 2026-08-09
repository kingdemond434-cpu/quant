"""Live connector BEHAVIOUR -- what the order and read functions actually do.

The existing suite covers arming interlocks and the capability whitelist: everything the module
must REFUSE. Measured 2026-07-27, that left 25% line coverage and a 0% mutation score, with every
order-placing and position-reading function unexecuted -- including `place_stop_market`, which the
entire §3 host-death rail depends on.

NO NETWORK. Every test monkeypatches `_signed`/`_get`, so nothing here can reach fapi.binance.com
even if arming were somehow satisfied. What is being checked is the REQUEST the module builds and
the parsing of the response, which is exactly where a silent live-money bug would live.
"""

from __future__ import annotations

from typing import Any

import pytest

import libs.execution.binance_live as bl


@pytest.fixture
def calls(monkeypatch) -> list[dict[str, Any]]:
    """Capture every signed request instead of sending it. Returns the call log."""
    log: list[dict[str, Any]] = []

    def fake_signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
        log.append({"path": path, "params": dict(params), "method": method})
        return log[-1].get("_response", {})

    monkeypatch.setattr(bl, "_signed", fake_signed)
    return log


def _respond(monkeypatch, payload: Any, log: list | None = None) -> None:
    def fake_signed(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
        if log is not None:
            log.append({"path": path, "params": dict(params), "method": method})
        return payload
    monkeypatch.setattr(bl, "_signed", fake_signed)


class TestProtectiveStopIsTheRailItClaimsToBe:
    """`place_stop_market` is the venue-side stop the §3 invariant is built on. If it silently
    stopped sending reduceOnly, every naked-position check would still pass -- the order exists --
    while the stop could OPEN a position on the far side instead of closing one."""

    def test_it_sends_reduce_only(self, calls) -> None:
        bl.place_stop_market("BTCUSDT", "SELL", 1.0, 50_000.0)
        assert calls[0]["params"]["reduceOnly"] == "true"

    def test_it_is_a_stop_market_not_a_stop_limit(self, calls) -> None:
        """A STOP_LIMIT can go unfilled through the very gap the stop exists for."""
        bl.place_stop_market("BTCUSDT", "SELL", 1.0, 50_000.0)
        assert calls[0]["params"]["type"] == "STOP_MARKET"

    def test_it_carries_symbol_side_qty_and_trigger(self, calls) -> None:
        bl.place_stop_market("ETHUSDT", "BUY", 2.5, 1234.5)
        p = calls[0]["params"]
        assert (p["symbol"], p["side"], p["quantity"], p["stopPrice"]) == \
            ("ETHUSDT", "BUY", 2.5, 1234.5)

    def test_it_posts(self, calls) -> None:
        bl.place_stop_market("BTCUSDT", "SELL", 1.0, 1.0)
        assert calls[0]["method"] == "POST" and calls[0]["path"] == "/fapi/v1/order"


class TestOrderPlacement:
    def test_market_order_shape(self, calls) -> None:
        bl.place_market("BTCUSDT", "BUY", 0.5)
        p = calls[0]["params"]
        assert p["type"] == "MARKET" and p["side"] == "BUY" and p["quantity"] == 0.5
        assert "reduceOnly" not in p          # an opening order must not be reduce-only

    def test_post_only_uses_GTX_so_it_can_never_take(self, calls) -> None:
        """timeInForce=GTX is what makes it guaranteed-maker. Losing it turns every passive
        quote into a taker fill and silently inverts the sleeve's cost model."""
        bl.place_post_only("BTCUSDT", "SELL", 1.0, 60_000.0)
        p = calls[0]["params"]
        assert p["timeInForce"] == "GTX" and p["type"] == "LIMIT" and p["price"] == 60_000.0

    def test_a_non_dict_venue_response_is_wrapped_not_crashed(self, monkeypatch) -> None:
        _respond(monkeypatch, ["unexpected"])
        assert bl.place_market("BTCUSDT", "BUY", 1.0) == {"raw": ["unexpected"]}

    def test_cancel_all_is_a_DELETE_scoped_to_one_symbol(self, calls) -> None:
        bl.cancel_all("BTCUSDT")
        assert calls[0]["method"] == "DELETE"
        assert calls[0]["params"] == {"symbol": "BTCUSDT"}

    def test_set_leverage_swallows_venue_errors(self, monkeypatch) -> None:
        """Leverage already-set is a normal venue reject and must not abort a trading pass."""
        def boom(*a: Any, **k: Any) -> Any:
            raise RuntimeError("leverage not modified")
        monkeypatch.setattr(bl, "_signed", boom)
        assert bl.set_leverage("BTCUSDT", 3) is None


class TestPositionReading:
    def test_zero_positions_are_excluded(self, monkeypatch) -> None:
        """A flat symbol is not a position. Including it would make the naked-position reconcile
        demand a stop for something that does not exist and freeze the book forever."""
        _respond(monkeypatch, [{"symbol": "BTCUSDT", "positionAmt": "0"},
                               {"symbol": "ETHUSDT", "positionAmt": "-2.5"}])
        assert bl.positions() == {"ETHUSDT": -2.5}

    def test_shorts_keep_their_sign(self, monkeypatch) -> None:
        _respond(monkeypatch, [{"symbol": "ETHUSDT", "positionAmt": "-2.5"}])
        assert bl.positions()["ETHUSDT"] < 0

    def test_flatten_all_closes_on_the_OPPOSITE_side(self, monkeypatch) -> None:
        """The one function whose sign error would double every position instead of closing it."""
        log: list[dict[str, Any]] = []
        seq = [[{"symbol": "BTCUSDT", "positionAmt": "1.5"},
                {"symbol": "ETHUSDT", "positionAmt": "-2.0"}]]

        def fake(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
            if path == "/fapi/v2/positionRisk":
                return seq[0]
            log.append({"path": path, "params": dict(params), "method": method})
            return {}
        monkeypatch.setattr(bl, "_signed", fake)

        bl.flatten_all()
        sent = {c["params"]["symbol"]: c["params"] for c in log}
        assert sent["BTCUSDT"]["side"] == "SELL" and sent["BTCUSDT"]["quantity"] == 1.5
        assert sent["ETHUSDT"]["side"] == "BUY" and sent["ETHUSDT"]["quantity"] == 2.0

    def test_open_orders_returns_a_list_even_on_a_junk_response(self, monkeypatch) -> None:
        _respond(monkeypatch, {"unexpected": "dict"})
        assert bl.open_orders() == []

    def test_open_orders_can_be_scoped_to_a_symbol(self, calls) -> None:
        bl.open_orders("BTCUSDT")
        assert calls[0]["params"] == {"symbol": "BTCUSDT"}
        bl.open_orders()
        assert calls[1]["params"] == {}


class TestIncomePagination:
    """`_income_rows` walks past the venue's 1000-row page cap. Three ways this goes wrong and
    all three are silent: an infinite loop, double-counted rows, or a truncated ledger."""

    def test_a_single_short_page_terminates(self) -> None:
        rows = [{"tranId": i, "incomeType": "FUNDING_FEE", "income": "1", "time": i}
                for i in range(10)]
        assert len(bl._income_rows(1, fetch=lambda p: rows)) == 10

    def test_it_pages_until_a_short_page(self) -> None:
        pages = [
            [{"tranId": i, "incomeType": "REALIZED_PNL", "income": "1", "time": i}
             for i in range(1000)],
            [{"tranId": 1000 + i, "incomeType": "REALIZED_PNL", "income": "1", "time": 1000 + i}
             for i in range(5)],
        ]
        state = {"n": 0}

        def fetch(_p: dict[str, Any]) -> Any:
            state["n"] += 1
            return pages[min(state["n"] - 1, len(pages) - 1)]
        assert len(bl._income_rows(1, fetch=fetch)) == 1005

    def test_duplicate_rows_across_pages_are_deduped(self) -> None:
        same = [{"tranId": 7, "incomeType": "FUNDING_FEE", "income": "1", "time": 5}]
        assert len(bl._income_rows(1, fetch=lambda p: same)) == 1

    def test_a_stalled_cursor_cannot_loop_forever(self) -> None:
        """Every page identical with the same timestamp -- the guard is the 50-page cap plus the
        dedupe. Without both this pins the process at 100% CPU against the venue."""
        page = [{"tranId": i, "incomeType": "FUNDING_FEE", "income": "1", "time": 500}
                for i in range(1000)]
        assert len(bl._income_rows(1, fetch=lambda p: page)) == 1000

    def test_an_empty_first_page_is_not_an_error(self) -> None:
        assert bl._income_rows(1, fetch=lambda p: []) == []


class TestIncomeSummary:
    def test_it_splits_pnl_funding_and_commission(self) -> None:
        rows = [
            {"tranId": 1, "incomeType": "REALIZED_PNL", "income": "10.0", "time": 1},
            {"tranId": 2, "incomeType": "REALIZED_PNL", "income": "-4.0", "time": 2},
            {"tranId": 3, "incomeType": "FUNDING_FEE", "income": "2.5", "time": 3},
            {"tranId": 4, "incomeType": "COMMISSION", "income": "-0.5", "time": 4},
        ]
        s = bl.income_summary(0, fetch=lambda p: rows)
        assert s["realized_pnl"] == 6.0
        assert s["funding"] == 2.5
        assert s["commission"] == -0.5

    def test_win_and_loss_counts_ignore_flat_closes(self) -> None:
        rows = [{"tranId": i, "incomeType": "REALIZED_PNL", "income": v, "time": i}
                for i, v in enumerate(["5", "-3", "0"])]
        s = bl.income_summary(0, fetch=lambda p: rows)
        assert s["n_wins"] == 1 and s["n_losses"] == 1

    def test_gross_profit_and_loss_span_every_income_type(self) -> None:
        rows = [{"tranId": 1, "incomeType": "FUNDING_FEE", "income": "3", "time": 1},
                {"tranId": 2, "incomeType": "COMMISSION", "income": "-1", "time": 2}]
        s = bl.income_summary(0, fetch=lambda p: rows)
        assert s["gross_profit"] == 3.0 and s["gross_loss"] == -1.0


class TestReadsFailSafe:
    def test_quote_depth_returns_zero_on_failure(self, monkeypatch) -> None:
        """Callers must read 'unknown' as 'thin' and stand aside. Returning anything non-zero
        here would size a trade into a book nobody could see."""
        def boom(*a: Any, **k: Any) -> Any:
            raise OSError("timeout")
        monkeypatch.setattr(bl, "_get", boom)
        assert bl.quote_depth("BTCUSDT", "BUY") == 0.0

    def test_quote_depth_sums_only_levels_within_the_band(self, monkeypatch) -> None:
        book = {"asks": [["100", "1"], ["100.5", "2"], ["200", "9"]]}
        monkeypatch.setattr(bl, "_get", lambda *a, **k: book)
        # 1% band off a 100 touch keeps 100 and 100.5, drops 200
        assert bl.quote_depth("BTCUSDT", "BUY", pct=0.01) == pytest.approx(100 * 1 + 100.5 * 2)

    def test_quote_depth_reads_the_opposite_side_for_a_sell(self, monkeypatch) -> None:
        book = {"asks": [["100", "1"]], "bids": [["99", "3"]]}
        monkeypatch.setattr(bl, "_get", lambda *a, **k: book)
        assert bl.quote_depth("BTCUSDT", "SELL") == pytest.approx(99 * 3)

    def test_an_empty_book_is_zero_depth(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "_get", lambda *a, **k: {"asks": [], "bids": []})
        assert bl.quote_depth("BTCUSDT", "BUY") == 0.0

    def test_avg_fill_returns_None_rather_than_fabricating_a_price(self, monkeypatch) -> None:
        def boom(*a: Any, **k: Any) -> Any:
            raise OSError("down")
        monkeypatch.setattr(bl, "_signed", boom)
        assert bl.avg_fill("BTCUSDT", "BUY", 0) is None

    def test_avg_fill_is_quote_weighted_over_our_side_only(self, monkeypatch) -> None:
        trades = [{"side": "BUY", "qty": "1", "quoteQty": "100"},
                  {"side": "BUY", "qty": "3", "quoteQty": "360"},
                  {"side": "SELL", "qty": "5", "quoteQty": "9999"}]
        _respond(monkeypatch, trades)
        assert bl.avg_fill("BTCUSDT", "BUY", 0) == pytest.approx(460 / 4)

    def test_avg_fill_with_no_matching_fills_is_None(self, monkeypatch) -> None:
        _respond(monkeypatch, [{"side": "SELL", "qty": "1", "quoteQty": "1"}])
        assert bl.avg_fill("BTCUSDT", "BUY", 0) is None

    def test_force_orders_is_empty_when_not_armed(self, monkeypatch) -> None:
        """Unarmed must mean 'we cannot see liquidations', and the caller treats {} as none --
        so this is checked explicitly rather than assumed."""
        monkeypatch.setattr(bl, "is_armed", lambda: (False, "no keys"))
        assert bl.force_orders() == {}

    def test_force_orders_counts_events_per_symbol(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "is_armed", lambda: (True, ""))
        _respond(monkeypatch, [{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"},
                               {"symbol": "ETHUSDT"}])
        assert bl.force_orders() == {"BTCUSDT": 2, "ETHUSDT": 1}

    def test_force_orders_swallows_a_venue_error(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "is_armed", lambda: (True, ""))

        def boom(*a: Any, **k: Any) -> Any:
            raise OSError("429")
        monkeypatch.setattr(bl, "_signed", boom)
        assert bl.force_orders() == {}


class TestAccountParsing:
    def test_balance_picks_the_usdt_row(self, monkeypatch) -> None:
        _respond(monkeypatch, [{"asset": "BNB", "balance": "9"},
                               {"asset": "USDT", "balance": "1234.5"}])
        assert bl.account_balance() == 1234.5

    def test_balance_is_zero_when_usdt_is_absent(self, monkeypatch) -> None:
        _respond(monkeypatch, [{"asset": "BNB", "balance": "9"}])
        assert bl.account_balance() == 0.0

    def test_summary_maps_every_field(self, monkeypatch) -> None:
        _respond(monkeypatch, {"totalWalletBalance": "100", "totalMarginBalance": "110",
                               "totalUnrealizedProfit": "10", "availableBalance": "80",
                               "totalInitialMargin": "30"})
        s = bl.account_summary()
        assert s == {"wallet": 100.0, "equity": 110.0, "unrealized_pnl": 10.0,
                     "available": 80.0, "margin_used": 30.0}

    def test_summary_defaults_missing_fields_to_zero(self, monkeypatch) -> None:
        _respond(monkeypatch, {})
        assert bl.account_summary()["equity"] == 0.0


class TestPublicMarketData:
    def test_mark_prices_parses_a_list(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "_get", lambda *a, **k: [{"symbol": "BTCUSDT", "price": "50000"}])
        assert bl.mark_prices() == {"BTCUSDT": 50000.0}

    def test_mark_prices_on_a_junk_response_is_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "_get", lambda *a, **k: {"code": -1})
        assert bl.mark_prices() == {}

    def test_book_ticker_pairs_bid_and_ask(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "_get", lambda *a, **k: [
            {"symbol": "BTCUSDT", "bidPrice": "99", "askPrice": "101"}])
        assert bl.book_ticker() == {"BTCUSDT": (99.0, 101.0)}

    def test_exchange_filters_extract_step_and_tick(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "_get", lambda *a, **k: {"symbols": [{
            "symbol": "BTCUSDT", "quantityPrecision": 3, "pricePrecision": 2,
            "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.10"}]}]})
        f = bl.exchange_filters()["BTCUSDT"]
        assert f["step"] == 0.001 and f["tick"] == 0.10 and f["qty_prec"] == 3

    def test_exchange_filters_fall_back_when_a_filter_is_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(bl, "_get", lambda *a, **k: {"symbols": [
            {"symbol": "XUSDT", "filters": []}]})
        f = bl.exchange_filters()["XUSDT"]
        assert f["step"] > 0 and f["tick"] > 0


class TestSigningAndTransport:
    """The signing path decides whether an order authenticates at all. Still no network: the
    urlopen call is replaced, so what is verified is the REQUEST that would have gone out."""

    @pytest.fixture
    def armed(self, monkeypatch, tmp_path):
        keyfile = tmp_path / "binance_live.json"
        keyfile.write_text('{"key": "TESTKEY", "secret": "TESTSECRET"}', "utf-8")
        monkeypatch.setattr(bl, "_KEYFILE", keyfile)
        monkeypatch.setattr(bl, "_ENABLE_FLAG", tmp_path / "LIVE_ENABLE")
        monkeypatch.setattr(bl, "_VPS_MARKER", tmp_path / "LIVE_VPS_VERIFIED")
        (tmp_path / "LIVE_ENABLE").touch()
        (tmp_path / "LIVE_VPS_VERIFIED").touch()
        return tmp_path

    @pytest.fixture
    def sent(self, monkeypatch):
        """Capture the urllib Request instead of sending it."""
        box: dict[str, Any] = {}

        class _Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"ok": true}'

        def fake_urlopen(req, timeout=None):
            box["req"] = req
            return _Resp()
        monkeypatch.setattr(bl.urllib.request, "urlopen", fake_urlopen)
        return box

    def test_an_unarmed_signed_call_raises_before_any_request(self, monkeypatch, sent) -> None:
        monkeypatch.setattr(bl, "is_armed", lambda: (False, "keys_present=False"))
        with pytest.raises(RuntimeError, match="not armed"):
            bl._signed("/fapi/v2/account", {})
        assert "req" not in sent, "an unarmed call reached the transport"

    def test_the_api_key_header_is_attached(self, armed, sent) -> None:
        bl._signed("/fapi/v2/account", {})
        assert sent["req"].get_header("X-mbx-apikey") == "TESTKEY"

    def test_the_signature_is_hmac_sha256_over_the_query(self, armed, sent) -> None:
        import hashlib
        import hmac
        import urllib.parse
        bl._signed("/fapi/v2/account", {})
        url = sent["req"].full_url
        query = url.split("?", 1)[1]
        body, sig = query.rsplit("&signature=", 1)
        expect = hmac.new(b"TESTSECRET", body.encode(), hashlib.sha256).hexdigest()
        assert sig == expect
        # and the venue's replay guards are present
        parsed = dict(urllib.parse.parse_qsl(body))
        assert "timestamp" in parsed and parsed["recvWindow"] == "5000"

    def test_a_post_sends_the_body_not_a_query_string(self, armed, sent) -> None:
        bl._signed("/fapi/v1/order", {"symbol": "BTCUSDT"}, method="POST")
        req = sent["req"]
        assert req.get_method() == "POST"
        assert req.data and b"symbol=BTCUSDT" in req.data
        assert "?" not in req.full_url

    def test_public_reads_carry_no_key(self, monkeypatch, sent) -> None:
        bl._get("/fapi/v1/ticker/price")
        assert sent["req"].get_header("X-mbx-apikey") is None

    def test_a_corrupt_keyfile_reads_as_no_keys(self, monkeypatch, tmp_path) -> None:
        bad = tmp_path / "k.json"
        bad.write_text("{ not json", "utf-8")
        monkeypatch.setattr(bl, "_KEYFILE", bad)
        assert bl.has_keys() is False
        assert bl.is_armed()[0] is False

    def test_realized_trades_returns_per_close_amounts(self, monkeypatch) -> None:
        rows = [{"tranId": 1, "incomeType": "REALIZED_PNL", "income": "5.5", "time": 1},
                {"tranId": 2, "incomeType": "REALIZED_PNL", "income": "-2.25", "time": 2}]
        monkeypatch.setattr(bl, "_income_rows", lambda *a, **k: rows)
        assert bl.realized_trades(0) == [5.5, -2.25]
