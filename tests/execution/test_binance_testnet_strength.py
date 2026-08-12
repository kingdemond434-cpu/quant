"""MUTATION-STRENGTH suite for the FUTURES TESTNET connector -- the perp leg the executor imports.

WHY THIS FILE EXISTS. `libs/execution/binance_testnet.py` carries 154 mutation sites and had
THREE dedicated tests (base URL pinned, no-keys refusal, has_keys-from-env). Everything that
decides what order is placed -- the MARKET_LOT_SIZE split, the reduce-only flag, the client order
id per chunk, the income pagination every P&L number is built from, the equity figure the ruin
rail reads -- was executed by no test at all. `run_cashcarry_executor` and
`run_stranded_recovery` import THIS module, not the live one, so the gap is not hypothetical:
it is the code that actually trades.

The assertions are about the REQUEST, not the reply, because on an order path the request is the
decision. `_signed` is replaced with a recorder throughout; the two tests that need to prove
`_signed` itself builds a valid request intercept `urlopen` instead. No network, no credentials.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.execution import binance_testnet as bt


@pytest.fixture()
def venue(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record every signed call; answer every one with a plausible order ack."""
    calls: list[dict[str, Any]] = []

    def fake(path: str, params: dict[str, Any], *, method: str = "GET") -> Any:
        calls.append({"path": path, "params": dict(params), "method": method})
        return {"orderId": 100 + len(calls)}

    monkeypatch.setattr(bt, "_signed", fake)
    monkeypatch.setattr(bt, "_market_max_qty", lambda _s: float("inf"))
    return calls


# ------------------------------------------------------------------ order placement

def test_place_market_sends_one_MARKET_order_with_the_asked_quantity(venue) -> None:  # type: ignore[no-untyped-def]
    bt.place_market("BTCUSDT", "BUY", 3.0)
    assert len(venue) == 1
    assert venue[0]["path"] == "/fapi/v1/order"
    assert venue[0]["method"] == "POST", "an order sent as a GET is not an order"
    assert venue[0]["params"]["type"] == "MARKET"
    assert venue[0]["params"]["quantity"] == 3.0
    assert venue[0]["params"]["side"] == "BUY"


def test_an_order_above_the_venue_cap_is_SPLIT_and_the_chunks_SUM(
        monkeypatch, venue) -> None:  # type: ignore[no-untyped-def]
    """THE 2026-07-27 INCIDENT, on the module that trades. COOKIEUSDT's MARKET_LOT_SIZE cap is
    150,000 and the desk sent 183,140; every order was rejected -4005, the caller fell back to a
    resting limit, and accumulated fills walked a short through zero into a +916,772 LONG.
    Splitting is the fix, and a split that loses or duplicates quantity is the same incident."""
    monkeypatch.setattr(bt, "_market_max_qty", lambda _s: 150_000.0)
    bt.place_market("COOKIEUSDT", "SELL", 183_140.0)
    chunks = [c["params"]["quantity"] for c in venue]
    assert chunks == [150_000.0, 33_140.0]
    assert sum(chunks) == pytest.approx(183_140.0), "a split must be conservative in quantity"


def test_every_chunk_carries_a_DISTINCT_client_order_id(monkeypatch, venue) -> None:  # type: ignore[no-untyped-def]
    """Chunks are separate orders. Sharing one id has the venue accept chunk 1 and reject the
    rest as duplicates -- a silently under-filled leg, which on a delta-neutral book is an
    unhedged directional position."""
    monkeypatch.setattr(bt, "_market_max_qty", lambda _s: 10.0)
    bt.place_market("BTCUSDT", "SELL", 25.0, cycle="c1")
    ids = [c["params"]["newClientOrderId"] for c in venue]
    assert len(ids) == 3
    assert len(set(ids)) == 3, "chunk index must be part of the id"


def test_the_same_logical_order_is_IDEMPOTENT_across_a_retry(venue) -> None:  # type: ignore[no-untyped-def]
    """An ambiguous timeout is indistinguishable from a failure. The retry must reproduce the
    SAME id so the venue -- not the desk -- deduplicates it."""
    bt.place_market("BTCUSDT", "BUY", 1.0, cycle="rebalance-7")
    bt.place_market("BTCUSDT", "BUY", 1.0, cycle="rebalance-7")
    assert venue[0]["params"]["newClientOrderId"] == venue[1]["params"]["newClientOrderId"]


def test_a_close_and_an_open_never_share_an_id(venue) -> None:  # type: ignore[no-untyped-def]
    """Same symbol, same side, same cycle -- but one covers and one opens. Colliding ids would
    have the venue silently drop the second, leaving the desk certain it had done both."""
    bt.place_market("BTCUSDT", "BUY", 1.0, reduce_only=True, cycle="c")
    bt.place_market("BTCUSDT", "BUY", 1.0, reduce_only=False, cycle="c")
    assert venue[0]["params"]["newClientOrderId"] != venue[1]["params"]["newClientOrderId"]


def test_reduce_only_is_TRANSMITTED_and_absent_when_not_asked(venue) -> None:  # type: ignore[no-untyped-def]
    """reduceOnly is what makes a cover arithmetically incapable of passing through zero into an
    opposite position. Dropping it turns an over-sized close into a fresh naked leg -- and
    sending it on an OPEN would have the venue reject the entry entirely."""
    bt.place_market("BTCUSDT", "SELL", 1.0, reduce_only=True)
    assert venue[0]["params"]["reduceOnly"] == "true"
    bt.place_market("BTCUSDT", "SELL", 1.0)
    assert "reduceOnly" not in venue[1]["params"]


def test_the_chunk_loop_cannot_spin_forever(monkeypatch, venue) -> None:  # type: ignore[no-untyped-def]
    """A tiny cap against a large order must stop at the 50-chunk bound rather than hammer the
    venue indefinitely. The order is then INCOMPLETE, which is a survivable outcome; an
    unbounded loop against a rate-limited venue is not."""
    monkeypatch.setattr(bt, "_market_max_qty", lambda _s: 1.0)
    bt.place_market("BTCUSDT", "BUY", 10_000.0)
    assert len(venue) == 50


def test_post_only_is_LIMIT_plus_GTX_which_is_what_makes_it_maker(venue) -> None:  # type: ignore[no-untyped-def]
    """GTX is rejected rather than crossing. Without it the same order crosses and pays taker
    fees on both legs -- and the fee difference IS the carry's edge."""
    bt.place_post_only("BTCUSDT", "SELL", 2.0, 70_000.0, cycle="c")
    p = venue[0]["params"]
    assert p["type"] == "LIMIT" and p["timeInForce"] == "GTX"
    assert p["quantity"] == 2.0 and p["price"] == 70_000.0
    assert "newClientOrderId" in p, "a RESTING order is the most dangerous kind to duplicate"


def test_cancel_all_deletes_ALL_open_orders_for_the_symbol(venue) -> None:  # type: ignore[no-untyped-def]
    bt.cancel_all("BTCUSDT")
    assert venue[0]["path"] == "/fapi/v1/allOpenOrders"
    assert venue[0]["method"] == "DELETE", "a cancel sent as a GET cancels nothing"
    assert venue[0]["params"] == {"symbol": "BTCUSDT"}


def test_open_orders_filters_by_symbol_only_when_asked(venue) -> None:  # type: ignore[no-untyped-def]
    bt.open_orders("BTCUSDT")
    assert venue[0]["params"] == {"symbol": "BTCUSDT"}
    bt.open_orders()
    assert venue[1]["params"] == {}


def test_set_leverage_posts_and_swallows_a_venue_refusal(monkeypatch, venue) -> None:  # type: ignore[no-untyped-def]
    bt.set_leverage("BTCUSDT", 3)
    assert venue[0]["path"] == "/fapi/v1/leverage" and venue[0]["method"] == "POST"
    assert venue[0]["params"] == {"symbol": "BTCUSDT", "leverage": 3}

    def boom(*_a: object, **_k: object) -> Any:
        raise RuntimeError("leverage already set")

    monkeypatch.setattr(bt, "_signed", boom)
    assert bt.set_leverage("BTCUSDT", 3) is None, "a non-fatal refusal must not abort the cycle"


# ------------------------------------------------------------- the MARKET_LOT_SIZE cap

def test_market_max_qty_reads_the_cap_and_caches_it(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[int] = []

    def fake_get(_path: str, _params: Any = None) -> Any:
        calls.append(1)
        return {"symbols": [{"symbol": "COOKIEUSDT", "filters": [
            {"filterType": "MARKET_LOT_SIZE", "maxQty": "150000"}]}]}

    monkeypatch.setattr(bt, "_get", fake_get)
    monkeypatch.setattr(bt, "_MKT_MAX_CACHE", {})
    assert bt._market_max_qty("COOKIEUSDT") == 150_000.0
    assert bt._market_max_qty("COOKIEUSDT") == 150_000.0
    assert len(calls) == 1, "the second call must be served from cache, not re-fetched"


def test_a_symbol_with_no_published_cap_is_INFINITY_not_a_guess(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Inventing a limit would split an order that never needed splitting, multiplying fees and
    market impact for no reason."""
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "BTCUSDT", "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001"}]}]})
    monkeypatch.setattr(bt, "_MKT_MAX_CACHE", {})
    assert bt._market_max_qty("BTCUSDT") == float("inf")


def test_a_TRANSIENT_lookup_failure_is_NOT_written_into_the_cache(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """THE DEFECT THIS PINS, stated in the source: caching `inf` after a network blip
    permanently disabled the cap for that symbol -- for the whole process lifetime, and the
    executor runs for days between restarts. Returning inf for THIS call is correct; remembering
    it is how the protection is silently lost with no trace."""
    state = {"fail": True}

    def flaky(_path: str, _params: Any = None) -> Any:
        if state["fail"]:
            raise TimeoutError("venue blip")
        return {"symbols": [{"symbol": "COOKIEUSDT", "filters": [
            {"filterType": "MARKET_LOT_SIZE", "maxQty": "150000"}]}]}

    monkeypatch.setattr(bt, "_get", flaky)
    monkeypatch.setattr(bt, "_MKT_MAX_CACHE", {})
    assert bt._market_max_qty("COOKIEUSDT") == float("inf")
    assert "COOKIEUSDT" not in bt._MKT_MAX_CACHE, "a failed lookup must leave the cache untouched"
    state["fail"] = False
    assert bt._market_max_qty("COOKIEUSDT") == 150_000.0, "the next call must retry"


# ------------------------------------------------------------------ positions / flatten

def test_positions_keeps_shorts_and_drops_flat_symbols(venue, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A short is a NEGATIVE quantity and dropping the sign turns the hedge leg into a second
    long. A flat symbol is not a position, and carrying it makes the book look wider than it is."""
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "positionAmt": "-0.5"},
        {"symbol": "ETHUSDT", "positionAmt": "2.0"},
        {"symbol": "SOLUSDT", "positionAmt": "0"},
    ])
    assert bt.positions() == {"BTCUSDT": -0.5, "ETHUSDT": 2.0}


def test_flatten_all_sends_the_OPPOSITE_side_at_absolute_size(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The emergency path. Closing a long with another BUY doubles the exposure it was called to
    remove, and a negative quantity is rejected outright -- leaving the position open in an
    emergency. reduce_only=True is asserted too: without it a position that shrank between the
    positions() read and the fill is sold THROUGH zero into the opposite side (the deliberate
    'Money path batch 17' change this test's old 3-arg mock silently swallowed -- flatten_all's
    per-symbol except turned the mock's TypeError into error dicts and sent stayed empty, so
    the suite read a signature mismatch as the emergency path being broken)."""
    monkeypatch.setattr(bt, "positions", lambda: {"BTCUSDT": 2.0, "ETHUSDT": -3.0})
    sent: list[tuple[str, str, float, bool]] = []
    monkeypatch.setattr(
        bt, "place_market",
        lambda s, side, q, reduce_only=False, cycle=None:
        sent.append((s, side, q, reduce_only)) or {"orderId": 1})
    bt.flatten_all()
    assert sent == [("BTCUSDT", "SELL", 2.0, True), ("ETHUSDT", "BUY", 3.0, True)]


# ------------------------------------------------------------------------- the equity

def test_equity_is_the_MAX_of_the_stable_sum_and_the_venue_total(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """R0053/R0054: under multiAssetsMargin=False `totalMarginBalance` is USDT-only, and it hid
    $5,000 of USDC -- sizing the book at 1/25th of true wealth and feeding the dead-man a
    high-water below its dust floor, which DISARMED the ruin rail at every equity. Max is what
    covers both venue modes; taking either term alone re-opens one of them."""
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: {
        "assets": [{"asset": "USDT", "marginBalance": "200.0"},
                   {"asset": "USDC", "marginBalance": "5000.0"},
                   {"asset": "BTC", "marginBalance": "999999.0"}],
        "totalMarginBalance": "200.0", "totalWalletBalance": "150.0",
        "totalUnrealizedProfit": "-7.5", "availableBalance": "120.0",
        "totalInitialMargin": "80.0"})
    s = bt.account_summary()
    assert s["equity"] == pytest.approx(5200.0), (
        "the stable sum must win when the venue undercounts")
    assert s["wallet"] == pytest.approx(150.0)
    assert s["unrealized_pnl"] == pytest.approx(-7.5)
    assert s["available"] == pytest.approx(120.0)
    assert s["margin_used"] == pytest.approx(80.0)


def test_the_venue_total_wins_when_it_is_the_larger_truth(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Under multiAssetsMargin=True the venue marks non-stables the stable sum cannot price."""
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: {
        "assets": [{"asset": "USDT", "marginBalance": "100.0"}],
        "totalMarginBalance": "9000.0"})
    assert bt.account_summary()["equity"] == pytest.approx(9000.0)


def test_account_balance_reads_USDT_and_answers_zero_when_absent(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [
        {"asset": "BNB", "balance": "3.0"}, {"asset": "USDT", "balance": "1234.5"}])
    assert bt.account_balance() == pytest.approx(1234.5)
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [{"asset": "BNB", "balance": "3.0"}])
    assert bt.account_balance() == 0.0


# ------------------------------------------------------------------ income pagination

def _page(n: int, start_id: int, t0: int) -> list[dict[str, Any]]:
    return [{"tranId": start_id + i, "incomeType": "COMMISSION", "symbol": "BTCUSDT",
             "time": t0 + i, "income": "-1.0"} for i in range(n)]


def test_income_pages_past_the_1000_row_cap(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """THE 2026-07-26 TRUNCATION INCIDENT: a direct limit=1000 call silently returned a page cap
    and understated commission by ~4.4x. Stopping at one page makes every aggregate -- funding,
    realized PnL, fees -- quietly too small, in the direction that flatters the book."""
    pages = [_page(1000, 0, 1_000), _page(1000, 1000, 2_000), _page(7, 2000, 3_000)]
    seen: list[dict[str, Any]] = []

    def fetch(params: dict[str, Any]) -> list[dict[str, Any]]:
        seen.append(dict(params))
        return pages[len(seen) - 1] if len(seen) <= len(pages) else []

    rows = bt._income_rows(1, fetch=fetch)
    assert len(rows) == 2007, "a short page ends the walk; a full one must not"
    assert len(seen) == 3
    assert seen[1]["startTime"] > seen[0]["startTime"], "the cursor must advance"


def test_rows_repeated_across_pages_are_counted_ONCE(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Pagination is by startTime, which is inclusive, so the boundary row comes back. Counting
    it twice inflates commission and realized PnL -- the same number, wrong the other way."""
    first = _page(1000, 0, 1_000)
    overlap = [first[-1], *_page(3, 5000, 2_000)]
    pages = [first, overlap]

    def fetch(_params: dict[str, Any]) -> list[dict[str, Any]]:
        return pages.pop(0) if pages else []

    assert len(bt._income_rows(1, fetch=fetch)) == 1003


def test_a_page_of_identical_timestamps_still_advances(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A full page whose rows all share one millisecond would leave the cursor where it was and
    loop forever on the same page. The walk must step past it."""
    same_ms = [{"tranId": i, "incomeType": "COMMISSION", "symbol": "B", "time": 500,
                "income": "-1.0"} for i in range(1000)]
    pages = [same_ms, []]

    def fetch(_params: dict[str, Any]) -> list[dict[str, Any]]:
        return pages.pop(0) if pages else []

    assert len(bt._income_rows(1, fetch=fetch)) == 1000


def test_no_anchor_means_ONE_page_and_no_walk(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: list[dict[str, Any]] = []

    def fetch(params: dict[str, Any]) -> list[dict[str, Any]]:
        seen.append(dict(params))
        return _page(1000, 0, 1)

    assert len(bt._income_rows(0, fetch=fetch)) == 1000
    assert len(seen) == 1
    assert "startTime" not in seen[0]


def test_income_type_and_symbol_narrow_the_venue_query(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Filtering client-side instead would page through 50,000 unrelated rows and hit the bound
    before reaching the ones asked for."""
    seen: list[dict[str, Any]] = []

    def fetch(params: dict[str, Any]) -> list[dict[str, Any]]:
        seen.append(dict(params))
        return []

    bt._income_rows(1, "COMMISSION", fetch=fetch, symbol="BTCUSDT")
    assert seen[0]["incomeType"] == "COMMISSION"
    assert seen[0]["symbol"] == "BTCUSDT"
    assert seen[0]["limit"] == 1000


def test_income_summary_splits_gross_by_SIGN_not_by_the_netted_total(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """gross_profit/gross_loss are every event split by sign. Deriving them from the NETTED
    realized_pnl hides winning trades inside a net-negative total, which is exactly the report
    that makes a bleeding execution path look like a bleeding strategy."""
    rows = [
        {"incomeType": "REALIZED_PNL", "income": "10.0"},
        {"incomeType": "REALIZED_PNL", "income": "-4.0"},
        {"incomeType": "REALIZED_PNL", "income": "0.0"},
        {"incomeType": "FUNDING_FEE", "income": "2.5"},
        {"incomeType": "COMMISSION", "income": "-1.5"},
    ]
    out = bt.income_summary(0, fetch=lambda _p: rows)
    assert out["realized_pnl"] == pytest.approx(6.0)
    assert out["funding"] == pytest.approx(2.5)
    assert out["commission"] == pytest.approx(-1.5)
    assert out["gross_profit"] == pytest.approx(12.5)
    assert out["gross_loss"] == pytest.approx(-5.5)
    assert out["n_wins"] == 1
    assert out["n_losses"] == 1, "a flat close is neither a win nor a loss"


def test_commission_events_report_POSITIVE_MEANS_PAID(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The venue signs commission negative; `_tca` signs cost positive. Passing the venue's sign
    through makes every fee a credit, and the desk's own log already read +$0.16 net while the
    venue billed $1,750.65."""
    monkeypatch.setattr(bt, "_income_rows", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "time": 5, "income": "-1.25"},
        {"symbol": None, "time": None, "income": None},
    ])
    out = bt.commission_events(1)
    assert out[0] == {"symbol": "BTCUSDT", "time": 5, "commission": pytest.approx(1.25)}
    assert out[1] == {"symbol": "", "time": 0, "commission": 0.0}


def test_realized_trades_returns_one_amount_per_close(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(bt, "_income_rows", lambda *_a, **_k: [
        {"income": "3.0"}, {"income": "-1.0"}])
    assert bt.realized_trades(0) == [3.0, -1.0]


# --------------------------------------------------------------------- force closures

def test_force_orders_counts_venue_closures_per_symbol(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A short perp leg that vanished via ADL must NOT be re-shorted into the squeeze that took
    it. Reporting {} when closures exist re-enters the position the venue just liquidated."""
    monkeypatch.setattr(bt, "has_keys", lambda: True)
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [
        {"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}, {"symbol": ""}])
    assert bt.force_orders() == {"BTCUSDT": 2, "ETHUSDT": 1}


def test_force_orders_is_EMPTY_without_keys_or_on_a_failed_read(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(bt, "has_keys", lambda: False)
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [{"symbol": "BTCUSDT"}])
    assert bt.force_orders() == {}, "no keys must not reach the venue at all"

    def boom(*_a: object, **_k: object) -> Any:
        raise RuntimeError("down")

    monkeypatch.setattr(bt, "has_keys", lambda: True)
    monkeypatch.setattr(bt, "_signed", boom)
    assert bt.force_orders() == {}


# ------------------------------------------------------------------- market data reads

def test_futures_min_notional_is_read_from_the_NOTIONAL_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """USD-M futures publishes the minimum order value under `notional`; spot uses
    `minNotional`. Reading the spot key here yields 0.0 for every symbol, which reads as
    'no minimum' -- the direction that sends orders the venue will reject."""
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "BTCUSDT", "quantityPrecision": 3, "pricePrecision": 2, "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
            {"filterType": "MIN_NOTIONAL", "notional": "5.0"}]},
        {"symbol": "BAREUSDT", "filters": []},
    ]})
    out = bt.exchange_filters()
    assert out["BTCUSDT"]["min_notional"] == pytest.approx(5.0)
    assert out["BTCUSDT"]["step"] == pytest.approx(0.001)
    assert out["BTCUSDT"]["qty_prec"] == 3
    assert out["BTCUSDT"]["tick"] == pytest.approx(0.10)
    assert out["BTCUSDT"]["price_prec"] == 2
    bare = out["BAREUSDT"]
    assert bare["step"] == pytest.approx(0.001) and bare["min_qty"] == 0.0
    assert bare["qty_prec"] == 3 and bare["price_prec"] == 2
    assert bare["tick"] == pytest.approx(0.01)
    assert bare["min_notional"] == 0.0


def test_mark_prices_and_book_ticker_read_an_error_object_as_NOTHING(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "price": "70000.0"}])
    assert bt.mark_prices() == {"BTCUSDT": 70000.0}
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: {"code": -1121})
    assert bt.mark_prices() == {}
    assert bt.book_ticker() == {}
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "bidPrice": "1.5", "askPrice": "1.6"}])
    assert bt.book_ticker() == {"BTCUSDT": (1.5, 1.6)}


def test_quote_depth_sums_the_side_the_trade_would_EAT_within_the_band(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A BUY consumes ASKS. Summing bids reports the liquidity available to the OPPOSITE trade --
    the number that makes an illiquid entry look safe. The touch itself is always affordable."""
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: {
        "bids": [["100", "2"], ["99.5", "4"], ["10", "1000"]],
        "asks": [["101", "3"], ["101.5", "1"], ["500", "1000"]]})
    assert bt.quote_depth("BTCUSDT", "BUY", pct=0.02) == pytest.approx(101 * 3 + 101.5)
    assert bt.quote_depth("BTCUSDT", "SELL", pct=0.02) == pytest.approx(100 * 2 + 99.5 * 4)
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: {"asks": [["100", "3"]], "bids": []})
    assert bt.quote_depth("BTCUSDT", "BUY", pct=0.0) == pytest.approx(300.0)


def test_an_empty_or_broken_book_is_zero_depth_not_an_exception(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Zero refuses the trade; raising takes down a sizing loop that is mid-way through building
    a hedged pair."""
    monkeypatch.setattr(bt, "_get", lambda *_a, **_k: {"bids": [], "asks": []})
    assert bt.quote_depth("BTCUSDT", "BUY") == 0.0

    def boom(*_a: object, **_k: object) -> Any:
        raise TimeoutError("venue down")

    monkeypatch.setattr(bt, "_get", boom)
    assert bt.quote_depth("BTCUSDT", "SELL") == 0.0


def test_avg_fill_is_quote_over_base_and_only_OUR_side(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """VWAP, not a mean of prices, and a BUY must not average in the sells on the same symbol --
    that is the venue's tape, not the desk's execution."""
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [
        {"side": "BUY", "qty": "1.0", "quoteQty": "100.0"},
        {"side": "BUY", "qty": "3.0", "quoteQty": "360.0"},
        {"side": "SELL", "qty": "5.0", "quoteQty": "9999.0"}])
    assert bt.avg_fill("BTCUSDT", "BUY", 0) == pytest.approx(115.0)


def test_avg_fill_is_None_rather_than_zero_when_nothing_filled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """None and zero are different facts and the caller divides by this. Zero propagates as an
    infinite slippage figure; None says 'not observed yet', which is what happened."""
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: [])
    assert bt.avg_fill("BTCUSDT", "BUY", 0) is None

    def boom(*_a: object, **_k: object) -> Any:
        raise RuntimeError("not armed")

    monkeypatch.setattr(bt, "_signed", boom)
    assert bt.avg_fill("BTCUSDT", "SELL", 0) is None


def test_my_trades_sends_endTime_only_when_a_window_end_was_given(venue) -> None:  # type: ignore[no-untyped-def]
    """Binance refuses startTime+endTime spans over 24h here. Sending an endTime the caller never
    asked for turns an open-ended forensic read into an empty one, and the reconciliation that
    consumes it then reports 'no fills' for a leg that filled."""
    bt.my_trades("BTCUSDT", 1000)
    assert venue[0]["params"] == {"symbol": "BTCUSDT", "startTime": 1000, "limit": 1000}
    bt.my_trades("BTCUSDT", 1000, 2000, limit=50)
    assert venue[1]["params"] == {"symbol": "BTCUSDT", "startTime": 1000, "endTime": 2000,
                                  "limit": 50}


def test_my_trades_is_EMPTY_not_an_exception_when_the_read_fails(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def boom(*_a: object, **_k: object) -> Any:
        raise RuntimeError("no keys")

    monkeypatch.setattr(bt, "_signed", boom)
    assert bt.my_trades("BTCUSDT", 0) == []
    monkeypatch.setattr(bt, "_signed", lambda *_a, **_k: {"code": -1})
    assert bt.my_trades("BTCUSDT", 0) == []


# ------------------------------------------------------- the signed request itself

class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    seen: list[Any] = []

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeResponse:
        req._seen_timeout = timeout
        seen.append(req)
        return _FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(bt.urllib.request, "urlopen", fake_urlopen)
    return seen


def test_every_venue_call_is_BOUNDED_by_a_socket_timeout(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """An unbounded read on the order path does not fail, it HANGS -- and a hung order is the one
    state the desk cannot reconcile, because it does not know whether the leg exists."""
    monkeypatch.setenv("BINANCE_TESTNET_KEY", "KKK")
    monkeypatch.setenv("BINANCE_TESTNET_SECRET", "SSS")
    seen = _capture(monkeypatch)
    assert bt._get("/fapi/v1/ping") == {"ok": True}, (
        "a reader that drops the venue's answer reports 'no data' for every healthy call")
    assert seen[0]._seen_timeout == 20
    assert bt._signed("/fapi/v2/account", {}) == {"ok": True}
    assert seen[1]._seen_timeout == 20


def test_a_signed_POST_carries_its_parameters_in_the_BODY(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A POST whose parameters went into the URL places nothing -- the signature travels with
    them, so the venue sees an unsigned empty order. `_signed` returned 200 either way, so the
    desk believes the leg is on."""
    monkeypatch.setenv("BINANCE_TESTNET_KEY", "KKK")
    monkeypatch.setenv("BINANCE_TESTNET_SECRET", "SSS")
    seen = _capture(monkeypatch)
    bt._signed("/fapi/v1/order", {"symbol": "BTCUSDT"}, method="POST")
    req = seen[0]
    assert req.get_method() == "POST"
    assert req.full_url == "https://testnet.binancefuture.com/fapi/v1/order"
    body = (req.data or b"").decode()
    assert "symbol=BTCUSDT" in body and "signature=" in body
    assert req.get_header("X-mbx-apikey") == "KKK"


def test_a_signed_GET_carries_its_parameters_in_the_QUERY_STRING(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BINANCE_TESTNET_KEY", "KKK")
    monkeypatch.setenv("BINANCE_TESTNET_SECRET", "SSS")
    seen = _capture(monkeypatch)
    bt._signed("/fapi/v2/account", {})
    req = seen[0]
    assert req.get_method() == "GET"
    assert req.data is None, "a GET must not carry a body"
    query = req.full_url.split("?", 1)[1]
    parsed = dict(part.split("=", 1) for part in query.split("&"))
    assert parsed["recvWindow"] == "5000"
    assert int(parsed["timestamp"]) > 1_600_000_000_000, (
        "timestamp must be in MILLISECONDS -- seconds are outside every recvWindow")


def test_HALF_a_credential_pair_refuses_rather_than_signing_with_None(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Key present, secret missing is what a partially-applied deploy leaves behind. It must
    raise the same refusal as no keys at all -- with `and` where the `or` belongs, a
    half-configured box signs and the caller gets an opaque crash from inside the order path."""
    monkeypatch.setattr(bt, "_KEYFILE", bt.Path("data/secrets/does-not-exist.json"))
    monkeypatch.setenv("BINANCE_TESTNET_KEY", "KKK")
    monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)
    assert bt.has_keys() is False
    with pytest.raises(RuntimeError, match="no testnet keys"):
        bt._signed("/fapi/v1/order", {"symbol": "BTCUSDT"}, method="POST")


def test_public_reads_append_their_params_and_need_no_keys(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """`_get` is the depth/price path, and `quote_depth` swallows its failures as 0.0 -- so a
    broken URL reads as 'this book is empty' and stands the desk aside on every symbol."""
    seen = _capture(monkeypatch)
    bt._get("/fapi/v1/depth", {"symbol": "BTCUSDT", "limit": 100})
    assert seen[0].full_url == f"{bt._BASE}/fapi/v1/depth?symbol=BTCUSDT&limit=100"
    assert seen[0].data is None
    bt._get("/fapi/v1/exchangeInfo")
    assert seen[1].full_url == f"{bt._BASE}/fapi/v1/exchangeInfo"
