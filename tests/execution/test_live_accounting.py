"""VENUE ACCOUNTING ON THE LIVE CONNECTOR -- pagination, PnL attribution, and the read paths.

These functions decide what the desk BELIEVES about its own money: realized PnL, funding earned
and paid, commission, current positions, and whether the venue force-closed a leg. They were the
largest uncovered block in `binance_live.py`, which was itself the least-covered substantial file
in the repository at 29.9% while the repo sat at 88.1%.

Every one is exercised through its injected `fetch` seam or a replaced `_signed`, so nothing here
reaches a venue and no test needs credentials.

WHY PAGINATION GETS THE MOST ATTENTION. `_income_rows` walks past the venue's 1000-row page cap by
advancing a cursor. Three ways that goes wrong and each silently UNDERSTATES what the desk has
earned or lost: it stops at the first page and reports a fraction; it double-counts rows that
appear on both sides of a cursor boundary; or it never advances and loops on the same page until
the 50-iteration bound saves it. A PnL figure that is quietly a fraction of the truth is worse
than no figure -- it gets compared against a target.
"""

from __future__ import annotations

import pytest

from libs.execution import binance_live as L

# --------------------------------------------------------------- income pagination

def test_a_single_short_page_is_returned_whole() -> None:
    rows = [{"tranId": i, "incomeType": "FUNDING_FEE", "income": "1.0", "time": 1000 + i}
            for i in range(5)]
    got = L._income_rows(since_ms=1, fetch=lambda _p: rows)
    assert len(got) == 5


def test_pagination_walks_PAST_the_thousand_row_page_cap() -> None:
    """The venue caps a page at 1000 rows. Stopping there reports a FRACTION of realized PnL as if
    it were the total, and the number is then compared against a target."""
    page1 = [{"tranId": i, "incomeType": "REALIZED_PNL", "income": "1.0", "time": 1000 + i}
             for i in range(1000)]
    page2 = [{"tranId": 10_000 + i, "incomeType": "REALIZED_PNL", "income": "1.0",
              "time": 5000 + i} for i in range(7)]
    calls = {"n": 0}

    def fetch(_p):
        calls["n"] += 1
        return page1 if calls["n"] == 1 else (page2 if calls["n"] == 2 else [])

    got = L._income_rows(since_ms=1, fetch=fetch)
    assert len(got) == 1007, f"pagination stopped early: {len(got)}"
    assert calls["n"] >= 2


def test_a_row_seen_on_both_sides_of_a_cursor_is_counted_ONCE() -> None:
    """The cursor advances by timestamp, so a row on the boundary can legitimately appear in two
    pages. Counting it twice INFLATES realized PnL -- the flattering direction, which is exactly
    the one that gets believed."""
    shared = {"tranId": "X", "incomeType": "REALIZED_PNL", "income": "100.0", "time": 2000}
    page1 = [{"tranId": i, "incomeType": "REALIZED_PNL", "income": "1.0", "time": 1000 + i}
             for i in range(999)] + [shared]
    page2 = [shared, {"tranId": "Y", "incomeType": "REALIZED_PNL", "income": "5.0",
                      "time": 2001}]
    calls = {"n": 0}

    def fetch(_p):
        calls["n"] += 1
        return page1 if calls["n"] == 1 else (page2 if calls["n"] == 2 else [])

    got = L._income_rows(since_ms=1, fetch=fetch)
    assert sum(1 for r in got if r.get("tranId") == "X") == 1, "the boundary row double-counted"


def test_a_venue_that_never_advances_cannot_loop_forever() -> None:
    """Every page identical and full: without the iteration bound this walks until the process is
    killed, hammering a rate-limited endpoint -- the overrun that got this desk's IP cut for six
    hours."""
    page = [{"tranId": i, "incomeType": "COMMISSION", "income": "-0.1", "time": 1000}
            for i in range(1000)]
    calls = {"n": 0}

    def fetch(_p):
        calls["n"] += 1
        return page

    L._income_rows(since_ms=1, fetch=fetch)
    assert calls["n"] <= 50, f"unbounded pagination: {calls['n']} requests"


def test_a_non_list_response_is_survived_not_crashed() -> None:
    """A venue error body is a dict, not a list. Accounting must degrade to 'nothing seen' rather
    than raise inside whatever loop is reading the book."""
    assert L._income_rows(since_ms=0, fetch=lambda _p: {"code": -1021, "msg": "timestamp"}) == []
    assert L._income_rows(since_ms=1, fetch=lambda _p: {"code": -1021}) == []


# ------------------------------------------------------------------ PnL attribution

def _rows(*specs) -> list[dict]:
    return [{"tranId": i, "incomeType": t, "income": str(a), "time": 1000 + i}
            for i, (t, a) in enumerate(specs)]


def test_income_is_attributed_to_the_right_bucket() -> None:
    """Funding, commission and realized PnL are economically different and the desk's carry
    analysis reads them separately -- collapsing them makes a funding harvest look like alpha."""
    fetch = lambda _p: _rows(  # noqa: E731
        ("REALIZED_PNL", 100.0), ("REALIZED_PNL", -40.0),
        ("FUNDING_FEE", 7.5), ("FUNDING_FEE", -2.5), ("COMMISSION", -3.0))
    s = L.income_summary(since_ms=0, fetch=fetch)
    assert s["realized_pnl"] == pytest.approx(60.0)
    assert s["funding"] == pytest.approx(5.0)
    assert s["commission"] == pytest.approx(-3.0)


def test_wins_and_losses_are_counted_only_on_REALIZED_PNL() -> None:
    """A positive funding row is not a winning trade. Counting it as one inflates the win rate,
    which is an input to sizing."""
    fetch = lambda _p: _rows(  # noqa: E731
        ("REALIZED_PNL", 10.0), ("REALIZED_PNL", -5.0), ("FUNDING_FEE", 99.0))
    s = L.income_summary(since_ms=0, fetch=fetch)
    assert s["n_wins"] == 1 and s["n_losses"] == 1


def test_gross_profit_and_loss_span_EVERY_income_type() -> None:
    """Gross figures are the cash view -- they include funding and commission deliberately,
    because that is what actually moved in the account."""
    fetch = lambda _p: _rows(("REALIZED_PNL", 10.0), ("FUNDING_FEE", 2.0),  # noqa: E731
                             ("COMMISSION", -3.0))
    s = L.income_summary(since_ms=0, fetch=fetch)
    assert s["gross_profit"] == pytest.approx(12.0)
    assert s["gross_loss"] == pytest.approx(-3.0)


def test_a_zero_income_row_moves_nothing() -> None:
    """A zero row is neither a win nor a loss. Classifying it either way biases the win rate on a
    book whose rows are frequently exactly zero."""
    s = L.income_summary(since_ms=0, fetch=lambda _p: _rows(("REALIZED_PNL", 0.0)))
    assert s["n_wins"] == 0 and s["n_losses"] == 0
    assert s["gross_profit"] == 0.0 and s["gross_loss"] == 0.0


def test_no_income_at_all_is_zeros_not_an_exception() -> None:
    s = L.income_summary(since_ms=0, fetch=lambda _p: [])
    assert set(s) == {"realized_pnl", "funding", "commission", "gross_profit", "gross_loss",
                      "n_wins", "n_losses"}
    assert all(v == 0.0 for v in s.values())


# ------------------------------------------------------------------- position reads

def test_positions_are_signed_and_flat_symbols_are_dropped(monkeypatch) -> None:
    """A flat symbol reported as 0.0 would be indistinguishable from a held position of zero size
    downstream, and the hedge check counts keys."""
    monkeypatch.setattr(L, "_signed", lambda *_a, **_k: [
        {"symbol": "BTCUSDT", "positionAmt": "1.5"},
        {"symbol": "ETHUSDT", "positionAmt": "-2.0"},
        {"symbol": "SOLUSDT", "positionAmt": "0.0"},
    ])
    p = L.positions()
    assert p == {"BTCUSDT": 1.5, "ETHUSDT": -2.0}


def test_account_balance_picks_USDT_and_survives_a_missing_asset(monkeypatch) -> None:
    monkeypatch.setattr(L, "_signed", lambda *_a, **_k: [
        {"asset": "BNB", "balance": "9.0"}, {"asset": "USDT", "balance": "1234.5"}])
    assert L.account_balance() == pytest.approx(1234.5)
    monkeypatch.setattr(L, "_signed", lambda *_a, **_k: [{"asset": "BNB", "balance": "9.0"}])
    assert L.account_balance() == 0.0


def test_quote_depth_sums_the_side_a_trade_would_actually_EAT(monkeypatch) -> None:
    """side='BUY' consumes ASKS. Summing the wrong side reports the liquidity available to the
    opposite trade, which is the number that makes an illiquid entry look safe."""
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {
        "bids": [["100", "2"], ["99.5", "3"], ["50", "100"]],
        "asks": [["101", "1"], ["101.5", "2"], ["200", "100"]]})
    buy = L.quote_depth("BTCUSDT", "BUY", pct=0.02)
    sell = L.quote_depth("BTCUSDT", "SELL", pct=0.02)
    assert buy == pytest.approx(101 * 1 + 101.5 * 2), "BUY must sum the ASKS inside the band"
    assert sell == pytest.approx(100 * 2 + 99.5 * 3), "SELL must sum the BIDS inside the band"
    # the far levels are outside 2% of the touch and must not be counted as available
    assert buy < 101 * 1 + 101.5 * 2 + 200 * 100


def test_quote_depth_returns_zero_rather_than_raising_on_a_bad_book(monkeypatch) -> None:
    """A depth read that raises takes down whatever sizing loop called it. Zero depth is the safe
    reading: it refuses the trade rather than permitting an unmeasured one."""
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"bids": [], "asks": []})
    assert L.quote_depth("BTCUSDT", "BUY") == 0.0
    monkeypatch.setattr(L, "_get", lambda *_a, **_k: {"error": "nope"})
    assert L.quote_depth("BTCUSDT", "BUY") == 0.0
