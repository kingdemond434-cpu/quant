"""THE LIVE CONNECTOR'S READ, ACCOUNTING AND FLATTEN LAYER -- the rest of the money path.

`tests/execution/test_place_market_live.py` covers order SPLITTING and `test_binance_live.py`
covers ARMING. Between them they left the majority of `binance_live.py` unexercised: every read
that feeds a sizing decision, the whole income-pagination accounting layer, and `flatten_all` --
the emergency close, which had never been called by any test at all.

WHY THIS FILE EXISTS AND NOT MORE RESEARCH TESTS. `docs/research/COVERAGE_RATCHET.json` names its
own next ceiling: "money-path coverage at parity with the repo. It sits at 41.6% against 88.1%
everywhere else, which is backwards: a bug in a research script costs a cycle, a bug on the order
path walks a short through zero." The money-path floor is 59.59% against a repo floor of 89.06%.
Closing that gap is worth more than another percentage point of aggregate.

THE READS ARE NOT INNOCUOUS JUST BECAUSE THEY ARE READS. `positions()` sizes the flatten.
`quote_depth()` decides whether an order is placed at all. `_market_max_qty()` decides whether it
is split, and getting that wrong is what caused incident #6. A read that returns a plausible wrong
number is worse than one that raises, because the executor acts on it.

Writing these found a real defect: `flatten_all` closed positions WITHOUT `reduce_only`, so the
emergency close could sell through zero into the opposite position -- incident #6's mechanism, on
the path that only runs because something already went wrong. Fixed, and pinned below.

No network anywhere: `_signed` and `_get` are replaced in every test.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.execution import binance_live as L
from libs.execution import binance_testnet as T


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Recording stand-in for the signed endpoint; returns the calls it was asked to make."""
    calls: list[dict[str, Any]] = []

    def _signed(path: str, params: dict[str, Any], method: str = "GET") -> Any:
        calls.append({"path": path, "method": method, **params})
        return {"orderId": len(calls), "status": "FILLED"}

    monkeypatch.setattr(L, "_signed", _signed)
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"symbols": []})
    L._MKT_MAX_CACHE.clear()
    yield calls
    L._MKT_MAX_CACHE.clear()


def _raiser(msg: str) -> Any:
    """A stand-in that fails the way a venue fails: at call time, not at setup."""
    def _f(*_a: object, **_k: object) -> dict[str, Any]:
        raise RuntimeError(msg)
    return _f


def _reply(monkeypatch: pytest.MonkeyPatch, mod: Any, payload: Any) -> None:
    """Make every signed call return `payload` (or raise it, if it is an exception)."""
    def _signed(_path: str, _params: dict[str, Any], method: str = "GET") -> Any:
        if isinstance(payload, BaseException):
            raise payload
        return payload
    monkeypatch.setattr(mod, "_signed", _signed)


# ===================================================================== flatten_all: the close leg

def test_FLATTEN_IS_REDUCE_ONLY_on_every_leg(monkeypatch: pytest.MonkeyPatch,
                                             sent: list[dict[str, Any]]) -> None:
    """THE DEFECT THIS FILE FOUND. `flatten_all` sizes each close from a `positions()` read, and
    the position can shrink between that read and the fill -- a resting maker quote fills, a
    venue-side STOP_MARKET triggers, an earlier chunk of this same flatten lands. SELL(100)
    against a position that is now +40 does not close it, it sells THROUGH ZERO into a 60-lot
    SHORT. That is incident #6 (+916,772 long) reproduced on the emergency path, at the one moment
    the book is most likely to be moving underneath the read. `reduceOnly` makes it
    arithmetically impossible.
    """
    monkeypatch.setattr(L, "positions", lambda: {"BTCUSDT": 100.0, "ETHUSDT": -50.0})
    L.flatten_all()
    assert sent, "flatten placed no orders at all"
    assert all(c.get("reduceOnly") == "true" for c in sent), (
        f"a flatten leg could pass through zero and OPEN the opposite position: {sent}")


def test_FLATTEN_TAGS_THE_ORDER_ID_AS_A_CLOSE_not_an_open(monkeypatch: pytest.MonkeyPatch,
                                                          sent: list[dict[str, Any]]) -> None:
    """The same defect seen from the idempotency side, which is why one fix closes both.
    `place_market` derives `intent = "close" if reduce_only else "open"`, and idempotency.py exists
    so that "a cover and an entry on the same symbol/side never share an ID inside one bucket".
    While the flatten was tagged `open`, a genuine entry on the same symbol and side inside the
    same 90s bucket produced the SAME client order ID -- and the venue would have rejected THE
    FLATTEN as the duplicate. Fail-safe is losing an entry; this lost the emergency close."""
    monkeypatch.setattr(L, "positions", lambda: {"BTCUSDT": 100.0})
    L.flatten_all()
    close_id = sent[0]["newClientOrderId"]

    sent.clear()
    L.place_market("BTCUSDT", "SELL", 100.0)          # a genuine entry, same symbol, same side
    assert sent[0]["newClientOrderId"] != close_id, (
        "an emergency close and an entry collided on one client order ID -- the venue rejects the "
        "second, and there is no rule saying the flatten arrives first")


def test_ONE_FAILING_SYMBOL_DOES_NOT_ABANDON_THE_REST(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loop had no isolation and the only caller wraps the whole call in ONE try/except, so a
    single symbol erroring left every position after it open while the report read "flatten
    FAILED". This matters MORE after the reduce-only fix, not less: reduce-only orders are
    rejected -2022 against an already-flat position, which here is a routine race rather than an
    error -- and without isolation that benign rejection would strand the whole rest of the book.
    """
    monkeypatch.setattr(L, "positions",
                        lambda: {"AAAUSDT": 1.0, "BBBUSDT": 2.0, "CCCUSDT": 3.0})

    def _boom(symbol: str, side: str, qty: float, reduce_only: bool = False,
              cycle: str | None = None) -> dict[str, Any]:
        if symbol == "BBBUSDT":
            raise RuntimeError("-2022 ReduceOnly Order is rejected")
        return {"symbol": symbol, "status": "FILLED"}

    monkeypatch.setattr(L, "place_market", _boom)
    res = L.flatten_all()

    assert len(res) == 3, "a raising leg swallowed the symbols after it"
    assert [r for r in res if r.get("symbol") == "CCCUSDT" and not r.get("error")], (
        "the position AFTER the failure was never closed")


def test_A_FAILED_LEG_IS_REPORTED_NOT_SWALLOWED(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolation without reporting is worse than no isolation: the guard would print
    "FLATTENED 3 position(s)" over a book that still has one open. The failure row carries the
    symbol and the error so `run_live_guard` can say which ones are STILL OPEN."""
    monkeypatch.setattr(L, "positions", lambda: {"AAAUSDT": 1.0})
    monkeypatch.setattr(L, "place_market", _raiser("venue down"))
    (row,) = L.flatten_all()
    assert row["error"] and "venue down" in row["error"]
    assert row["symbol"] == "AAAUSDT" and row["qty"] == 1.0, "cannot act on an unattributed failure"


def test_flatten_SIDES_INVERT_the_position_and_size_is_ABSOLUTE(
    monkeypatch: pytest.MonkeyPatch, sent: list[dict[str, Any]]
) -> None:
    """A short is closed by BUYing. Passing the signed quantity straight through would send a
    negative qty, which the venue rejects -- leaving the short open in an emergency."""
    monkeypatch.setattr(L, "positions", lambda: {"BTCUSDT": 4.0, "ETHUSDT": -7.0})
    L.flatten_all()
    by_symbol = {c["symbol"]: c for c in sent}
    assert by_symbol["BTCUSDT"]["side"] == "SELL"
    assert by_symbol["ETHUSDT"]["side"] == "BUY"
    assert by_symbol["ETHUSDT"]["quantity"] == 7.0, "a negative quantity would be rejected"


def test_TESTNET_FLATTEN_MATCHES_LIVE(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two connectors are documented drop-in replacements, and testnet is where the flatten is
    rehearsed before it is trusted with money. A testnet that closes by a mechanism live no longer
    uses is a rehearsal of the wrong thing."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(T, "positions", lambda: {"BTCUSDT": 3.0})
    monkeypatch.setattr(T, "_signed",
                        lambda p, params, method="GET": calls.append({**params}) or {"ok": 1})
    T.flatten_all()
    assert all(c.get("reduceOnly") == "true" for c in calls), (
        "testnet flatten can walk through zero -- so the rehearsal proves nothing about live")


# ============================================================ income pagination: the ledger reader

def test_income_UNPAGINATED_when_no_start_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """`since_ms=0` means "recent" -- one call, and crucially NO startTime param. Sending
    startTime=0 would ask the venue for all history from 1970 on every poll."""
    seen: list[dict[str, Any]] = []

    def fetch(p: dict[str, Any]) -> list[dict[str, Any]]:
        seen.append(dict(p))
        return [{"incomeType": "REALIZED_PNL", "income": "1.0"}]

    rows = L._income_rows(0, fetch=fetch)
    assert len(rows) == 1
    assert len(seen) == 1, "an unpaginated read looped"
    assert "startTime" not in seen[0]


def test_income_PAGINATES_PAST_THE_1000_ROW_CAP(monkeypatch: pytest.MonkeyPatch) -> None:
    """The venue caps a page at 1000. A single call silently returns a TRUNCATED ledger, and a
    truncated ledger understates losses as readily as gains -- it is the number the desk reports
    its own P&L from."""
    pages = [
        [{"tranId": i, "incomeType": "REALIZED_PNL", "symbol": "BTCUSDT",
          "income": "1.0", "time": 1000 + i} for i in range(1000)],
        [{"tranId": 9001, "incomeType": "REALIZED_PNL", "symbol": "BTCUSDT",
          "income": "5.0", "time": 99_000}],
    ]
    calls: list[dict[str, Any]] = []

    def fetch(p: dict[str, Any]) -> list[dict[str, Any]]:
        calls.append(dict(p))
        return pages[len(calls) - 1] if len(calls) <= len(pages) else []

    rows = L._income_rows(1, fetch=fetch)
    assert len(rows) == 1001, "the second page was never fetched -- the ledger is truncated"
    assert calls[1]["startTime"] > calls[0]["startTime"], "the cursor did not advance"


def test_income_DEDUPES_the_overlapping_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cursor advances to the last row's timestamp, NOT past it, precisely because several
    rows can share one millisecond -- advancing past would drop them. The cost is that the last row
    of page N is the first row of page N+1, so without the dedupe every page boundary
    DOUBLE-COUNTS one realized-PnL row into the reported total."""
    row = {"tranId": 7, "incomeType": "REALIZED_PNL", "symbol": "BTCUSDT",
           "income": "3.0", "time": 5000}
    pages = [
        # filler ids start at 1000 so none of them collides with the boundary row's id -- the
        # dedupe key is (tranId, incomeType, symbol, time), so a filler reusing id 7 at a
        # DIFFERENT timestamp is a legitimately distinct row and would look like a dedupe failure
        [{**row, "tranId": 1000 + i, "time": 4000 + i} for i in range(999)] + [row],
        [row, {"tranId": 8, "incomeType": "REALIZED_PNL", "symbol": "BTCUSDT",
               "income": "2.0", "time": 6000}],
    ]
    calls: list[int] = []

    def fetch(p: dict[str, Any]) -> list[dict[str, Any]]:
        calls.append(1)
        return pages[len(calls) - 1] if len(calls) <= len(pages) else []

    rows = L._income_rows(1, fetch=fetch)
    ids = [r["tranId"] for r in rows]
    assert ids.count(7) == 1, "the page-boundary row was counted twice"
    assert 8 in ids, "the genuinely new row on page 2 was lost"


def test_income_CANNOT_LOOP_FOREVER_on_a_stuck_cursor() -> None:
    """A venue that keeps returning a full page whose last timestamp never advances would spin
    this loop forever inside a scheduled organ -- no error, no output, just a process that never
    finishes and a report that never lands. Two guards: the cursor is forced forward when the last
    timestamp does not exceed it, and the page count is hard-capped."""
    page = [{"tranId": i, "incomeType": "REALIZED_PNL", "symbol": "BTCUSDT",
             "income": "1.0", "time": 1} for i in range(1000)]
    n = 0

    def fetch(_p: dict[str, Any]) -> list[dict[str, Any]]:
        nonlocal n
        n += 1
        return page

    L._income_rows(1, fetch=fetch)
    assert n <= 50, f"unbounded pagination: {n} pages and still going"


def test_income_NON_LIST_REPLY_IS_NOT_AN_EMPTY_LEDGER() -> None:
    """Binance returns an error DICT on a bad request. Iterating it yields its KEYS, so a failed
    read would become a ledger of string rows -- or, worse, silently zero income. Reported as
    empty is at least a number an operator can question."""
    assert L._income_rows(0, fetch=lambda _p: {"code": -1121, "msg": "Invalid symbol"}) == []
    assert L._income_rows(1, fetch=lambda _p: {"code": -1121}) == []


def test_income_summary_SPLITS_BY_TYPE_AND_BY_SIGN() -> None:
    """gross_profit/gross_loss are EVERY income event split by sign, not a sign-split of the netted
    realized PnL -- so commission and funding land in them too. That makes
    gross_profit/|gross_loss| a NET-OF-COSTS ratio, which is the intended meaning and is pinned
    here because it looks like an inconsistency and 'fixing' it would silently redefine the
    number the desk reports."""
    rows = [
        {"incomeType": "REALIZED_PNL", "income": "10.0"},
        {"incomeType": "REALIZED_PNL", "income": "-4.0"},
        {"incomeType": "FUNDING_FEE", "income": "-1.0"},
        {"incomeType": "COMMISSION", "income": "-0.5"},
    ]
    s = L.income_summary(0, fetch=lambda _p: rows)
    assert s["realized_pnl"] == pytest.approx(6.0)
    assert s["funding"] == pytest.approx(-1.0)
    assert s["commission"] == pytest.approx(-0.5)
    assert s["n_wins"] == 1 and s["n_losses"] == 1, "the trade win rate is built from these"
    assert s["gross_profit"] == pytest.approx(10.0)
    assert s["gross_loss"] == pytest.approx(-5.5), "costs belong in the gross split, by design"


def test_income_summary_A_ZERO_PNL_CLOSE_IS_NEITHER_A_WIN_NOR_A_LOSS() -> None:
    """A scratch close counted as a win would inflate the win rate that gates promotion."""
    s = L.income_summary(0, fetch=lambda _p: [{"incomeType": "REALIZED_PNL", "income": "0.0"}])
    assert s["n_wins"] == 0 and s["n_losses"] == 0


def test_realized_trades_returns_ONLY_the_pnl_amounts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(L, "_income_rows",
                        lambda *_a, **_k: [{"income": "2.5"}, {"income": "-1.5"}])
    assert L.realized_trades(0) == [2.5, -1.5]


# ================================================================ reads that size or block orders

def test_quote_depth_SUMS_ONLY_WITHIN_THE_BAND(monkeypatch: pytest.MonkeyPatch) -> None:
    """Depth far from the touch is not liquidity you can take. Summing the whole book would report
    a thin market as deep, which is exactly backwards from the direction this guard must fail."""
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {
        "asks": [["100", "1"], ["100.5", "2"], ["200", "99"]],   # 200 is far outside 1%
        "bids": [["99", "3"], ["50", "99"]],
    })
    assert L.quote_depth("BTCUSDT", "BUY", 0.01) == pytest.approx(100.0 + 201.0)
    assert L.quote_depth("BTCUSDT", "SELL", 0.01) == pytest.approx(297.0)


def test_quote_depth_UNKNOWN_READS_AS_THIN_NOT_DEEP(monkeypatch: pytest.MonkeyPatch) -> None:
    """The docstring's contract: callers treat unknown as thin and stand aside. If a failed depth
    read returned anything nonzero -- or raised into a caller that catches broadly -- a network
    blip would authorise an order into a book nobody measured."""
    monkeypatch.setattr(L, "_get", _raiser("timeout"))
    assert L.quote_depth("BTCUSDT", "BUY") == 0.0
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"asks": [], "bids": []})
    assert L.quote_depth("BTCUSDT", "BUY") == 0.0
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {})
    assert L.quote_depth("BTCUSDT", "SELL") == 0.0


def test_avg_fill_IS_SIZE_WEIGHTED_not_a_mean_of_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Averaging the price column gives the wrong answer whenever fills differ in size, and every
    real market order fills in unequal pieces. This number is the desk's venue-truth entry price;
    a wrong one mis-states slippage and every P&L attribution built on it."""
    _reply(monkeypatch, L, [
        {"side": "BUY", "qty": "1", "quoteQty": "100"},
        {"side": "BUY", "qty": "9", "quoteQty": "1800"},        # 9x the size at 200
        {"side": "SELL", "qty": "5", "quoteQty": "5000"},       # the other side: must not count
    ])
    assert L.avg_fill("BTCUSDT", "BUY", 0) == pytest.approx(1900.0 / 10.0)


def test_avg_fill_NONE_RATHER_THAN_A_FABRICATED_PRICE(monkeypatch: pytest.MonkeyPatch) -> None:
    """No fills visible yet is the NORMAL state immediately after placing. Returning 0.0 there
    would read as a fill at zero and make every downstream slippage number nonsense; None routes
    the caller to the mark, which is what the docstring promises."""
    _reply(monkeypatch, L, [{"side": "SELL", "qty": "5", "quoteQty": "5000"}])
    assert L.avg_fill("BTCUSDT", "BUY", 0) is None
    _reply(monkeypatch, L, RuntimeError("not armed"))
    assert L.avg_fill("BTCUSDT", "BUY", 0) is None
    _reply(monkeypatch, L, [{"side": "BUY", "qty": "0", "quoteQty": "0"}])
    assert L.avg_fill("BTCUSDT", "BUY", 0) is None, "a zero-size fill must not divide by zero"


def test_positions_DROPS_FLAT_SYMBOLS_AND_KEEPS_SIGN(monkeypatch: pytest.MonkeyPatch) -> None:
    """positionRisk returns every symbol ever traded, almost all at 0. Keeping them would have
    `flatten_all` place a zero-quantity order per symbol, and the reconciler count naked legs that
    do not exist. The SIGN is what tells a long from a short."""
    _reply(monkeypatch, L, [
        {"symbol": "BTCUSDT", "positionAmt": "1.5"},
        {"symbol": "ETHUSDT", "positionAmt": "-2.0"},
        {"symbol": "XRPUSDT", "positionAmt": "0.0"},
    ])
    assert L.positions() == {"BTCUSDT": 1.5, "ETHUSDT": -2.0}


def test_account_balance_PICKS_USDT_and_is_zero_when_absent(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Returning the first asset's balance would size the book off BNB dust."""
    _reply(monkeypatch, L, [{"asset": "BNB", "balance": "9999"},
                            {"asset": "USDT", "balance": "250.5"}])
    assert L.account_balance() == pytest.approx(250.5)
    _reply(monkeypatch, L, [{"asset": "BNB", "balance": "9999"}])
    assert L.account_balance() == 0.0, "no USDT must read as no capital, never as another asset"


def test_account_summary_MISSING_FIELDS_READ_AS_ZERO(monkeypatch: pytest.MonkeyPatch) -> None:
    """A partial venue reply must not KeyError inside the guard's reporting pass -- the guard is
    what runs when things are already going wrong."""
    _reply(monkeypatch, L, {"totalWalletBalance": "100"})
    s = L.account_summary()
    assert s["wallet"] == pytest.approx(100.0)
    assert s["equity"] == 0.0 and s["margin_used"] == 0.0


def test_force_orders_UNARMED_IS_EMPTY_NOT_AN_ERROR(monkeypatch: pytest.MonkeyPatch) -> None:
    """This gates re-entry after a venue-side liquidation. Unarmed it cannot know, and it must not
    raise into the caller's decision path -- but see the next test for what {} costs."""
    monkeypatch.setattr(L, "is_armed", lambda: (False, "keys_present=False"))
    assert L.force_orders() == {}


def test_force_orders_COUNTS_PER_SYMBOL(monkeypatch: pytest.MonkeyPatch) -> None:
    """A short force-closed by ADL must not be re-shorted into the squeeze that took it. The COUNT
    matters: repeated force events on one symbol is a different signal from one."""
    monkeypatch.setattr(L, "is_armed", lambda: (True, ""))
    _reply(monkeypatch, L, [{"symbol": "BTCUSDT"}, {"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"},
                            {"symbol": ""}])
    assert L.force_orders() == {"BTCUSDT": 2, "ETHUSDT": 1}, "a blank symbol became a key"


def test_force_orders_A_FAILED_READ_IS_INDISTINGUISHABLE_FROM_NO_LIQUIDATIONS(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """PINNED AS A KNOWN ASYMMETRY, not endorsed. Both "the venue liquidated nothing" and "the
    read failed" return {}, so a timeout here reads as PERMISSION TO RE-ENTER a symbol that may
    have just been force-closed. It is the fail-open shape this desk's own doctrine lists first.
    The safe fix is a third state the caller must handle, which is a caller change, not a
    connector change -- recorded here so it is a decision rather than an oversight."""
    monkeypatch.setattr(L, "is_armed", lambda: (True, ""))
    _reply(monkeypatch, L, RuntimeError("timeout"))
    assert L.force_orders() == {}


def test_set_leverage_NEVER_RAISES(monkeypatch: pytest.MonkeyPatch) -> None:
    """Already-set leverage returns an error the desk does not care about. Raising would abort the
    cycle before the order, over a no-op."""
    _reply(monkeypatch, L, RuntimeError("-4046 No need to change leverage"))
    assert L.set_leverage("BTCUSDT", 3) is None


# ============================================== the MARKET_LOT_SIZE cache: incident #6's proximate

def test_market_max_qty_CACHES_THE_WHOLE_SWEEP(monkeypatch: pytest.MonkeyPatch) -> None:
    """exchangeInfo is one large call. Caching only the requested symbol would re-fetch it per
    symbol per cycle and get the connector rate-limited mid-rebalance."""
    L._MKT_MAX_CACHE.clear()
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "AAAUSDT", "filters": [{"filterType": "MARKET_LOT_SIZE", "maxQty": "150000"}]},
        {"symbol": "BBBUSDT", "filters": [{"filterType": "MARKET_LOT_SIZE", "maxQty": "9"}]},
    ]})
    assert L._market_max_qty("AAAUSDT") == 150_000.0
    monkeypatch.setattr(L, "_get", _raiser("must not be called again"))
    assert L._market_max_qty("BBBUSDT") == 9.0
    L._MKT_MAX_CACHE.clear()


def test_market_max_qty_A_TRANSIENT_FAILURE_IS_NOT_CACHED(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE 2026-08-04 DEFECT. Caching inf on failure meant ONE network blip permanently disabled
    the cap for that symbol -- for the whole process lifetime, and the executor runs for days
    between restarts. The protection lost is the one that stops a -4005 rejection pushing the
    executor onto the resting-limit fallback that walked a short through zero. Silent, permanent,
    and it left no trace."""
    L._MKT_MAX_CACHE.clear()
    monkeypatch.setattr(L, "_get", _raiser("timeout"))
    assert L._market_max_qty("AAAUSDT") == float("inf"), "never invent a limit from a failed read"
    assert "AAAUSDT" not in L._MKT_MAX_CACHE, "a blip was cached -- the cap is gone until restart"

    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "AAAUSDT", "filters": [{"filterType": "MARKET_LOT_SIZE", "maxQty": "150000"}]}]})
    assert L._market_max_qty("AAAUSDT") == 150_000.0, "the retry never happened"
    L._MKT_MAX_CACHE.clear()


def test_market_max_qty_A_SYMBOL_WITH_NO_CAP_IS_UNLIMITED(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not every symbol carries MARKET_LOT_SIZE. Defaulting to some finite guess would split
    orders that need no splitting, multiplying fees and client order IDs for nothing."""
    L._MKT_MAX_CACHE.clear()
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"symbols": [
        {"symbol": "AAAUSDT", "filters": [{"filterType": "LOT_SIZE", "maxQty": "5"}]}]})
    assert L._market_max_qty("AAAUSDT") == float("inf")
    L._MKT_MAX_CACHE.clear()


# ========================================================== market-data parsers and reply coercion

def test_exchange_filters_DEFAULTS_ARE_CONSERVATIVE(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing LOT_SIZE must not produce step=0: the sizing code rounds to a multiple of step,
    and a zero step is a division by zero on the order path."""
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"symbols": [{"symbol": "AAAUSDT",
                                                                   "filters": []}]})
    f = L.exchange_filters()["AAAUSDT"]
    assert f["step"] > 0.0 and f["tick"] > 0.0
    assert f["min_qty"] == 0.0 and f["qty_prec"] == 3


def test_book_ticker_and_mark_prices_COERCE_A_NON_LIST_TO_EMPTY(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Binance returns an error DICT on failure. Iterating it yields KEYS, so `d["bidPrice"]` would
    TypeError deep inside the maker pricing pass rather than at the read."""
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"code": -1003, "msg": "Too much request"})
    assert L.book_ticker() == {}
    assert L.mark_prices() == {}

    monkeypatch.setattr(L, "_get", lambda *_a, **_k: [{"symbol": "AAAUSDT", "bidPrice": "1.5",
                                                       "askPrice": "1.6"}])
    assert L.book_ticker() == {"AAAUSDT": (1.5, 1.6)}


def test_open_orders_and_cancel_all_COERCE_THEIR_REPLY_SHAPE(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """`open_orders` feeds the naked-position reconciler; a non-list reply becoming a truthy object
    would have the reconciler believe orders are resting that are not."""
    _reply(monkeypatch, L, {"code": -1121})
    assert L.open_orders() == []
    _reply(monkeypatch, L, [{"orderId": 1}])
    assert L.open_orders("BTCUSDT") == [{"orderId": 1}]
    _reply(monkeypatch, L, ["unexpected"])
    assert L.cancel_all("BTCUSDT") == {"raw": ["unexpected"]}


def test_post_only_is_GTX_and_stop_is_REDUCE_ONLY(sent: list[dict[str, Any]]) -> None:
    """GTX is what makes post-only actually post-only: without it the order crosses and pays taker.
    And a protective stop that is not reduce-only can OPEN a position at the stop price -- the
    stop's entire purpose inverted."""
    L.place_post_only("BTCUSDT", "BUY", 1.0, 100.0)
    assert sent[-1]["timeInForce"] == "GTX"

    L.place_stop_market("BTCUSDT", "SELL", 1.0, 90.0)
    assert sent[-1]["reduceOnly"] == "true"
    assert sent[-1]["type"] == "STOP_MARKET"
