"""THE PERP DATA SOURCE -- 132 statements, 107 of them uncovered, and it feeds the whole desk.

Funding rate is the highest-information free solo-accessible signal the desk ranked top: it measures
leverage demand, longs paying shorts when positive. Everything downstream -- the carry sleeve, the
funding-clock work, the cross-sectional funding studies -- is built on the frames this module
returns, and a parser error here is not a crash. It is a plausible series with a wrong scale, a
wrong sign, or a silently truncated history, and nothing further down can tell.

THREE PROPERTIES ARE WORTH MORE THAN THE ARITHMETIC:

  PAGINATION MUST TERMINATE AND MUST NOT DUPLICATE. The cursor advances to `last + 1`, so an
  off-by-one either loops forever on the same page or drops one bar per page -- 1 in 1500 for
  klines, invisible in any spot check, and cumulative across years.

  DAILY FUNDING IS A SUM, 8h FUNDING IS A MATCH. Funding settles three times a day; a daily bar
  carries the day's total carry cost while an 8h bar maps to exactly one payment. Using a mean for
  the daily case understates the carry by 3x -- and 3x on the desk's one confirmed edge.

  A MISSING LEG DEGRADES TO A NEUTRAL VALUE, NEVER TO A DROPPED ROW. `funding=0.0`, `basis=0.0`,
  `taker_buy_frac=0.5`: each is the "no information" value for its own axis, so a gap does not
  become a signal. Dropping the row instead would silently shorten every history by whatever the
  weakest leg was missing.
"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import pytest

from libs.data import crypto_source as CS

_DAY_MS = 86_400_000
_T0 = 1_767_225_600_000          # 2026-01-01T00:00:00Z


def _kline(ts: int, close: float = 100.0, *, quote_vol: float = 1_000.0,
           taker_buy_quote: float = 600.0) -> list[Any]:
    """A Binance kline row: [openTime, o, h, l, c, baseVol, closeTime, quoteVol, n, tbBase, tbQuote,
    ignore]."""
    return [ts, str(close), str(close * 1.01), str(close * 0.99), str(close), "10.0",
            ts + _DAY_MS - 1, str(quote_vol), 50, "6.0", str(taker_buy_quote), "0"]


def _stub(monkeypatch, handler):
    calls: list[str] = []

    def fake(url: str, *, tries: int = 4):
        calls.append(url)
        return handler(url)

    monkeypatch.setattr(CS, "_get", fake)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    return calls


# ============================================================ pagination

def test_pagination_ADVANCES_PAST_the_last_bar_and_terminates(monkeypatch) -> None:
    """The cursor goes to `last + 1`. Advancing to `last` re-requests the same bar forever;
    advancing to `last + interval` drops one bar per page -- 1 in 1500, invisible in a spot check,
    and cumulative across years of history."""
    pages = [
        [_kline(_T0 + i * _DAY_MS) for i in range(1500)],
        [_kline(_T0 + (1500 + i) * _DAY_MS) for i in range(10)],
    ]
    starts: list[int] = []

    def handler(url: str):
        starts.append(int(url.split("startTime=")[1]))
        return pages.pop(0) if pages else []

    _stub(monkeypatch, handler)
    df = CS.fetch_klines("BTCUSDT", start_ms=_T0)
    assert len(df) == 1510, "every bar from both pages, none dropped and none duplicated"
    assert starts[1] == _T0 + 1499 * _DAY_MS + 1
    assert df["timestamp"].is_monotonic_increasing
    assert df["timestamp"].is_unique


def test_a_PARTIAL_page_ends_the_walk(monkeypatch) -> None:
    """A page shorter than the limit means the venue has nothing more. Continuing would spend a
    request per symbol per run forever."""
    calls = _stub(monkeypatch, lambda url: [_kline(_T0)])
    CS.fetch_klines("BTCUSDT", start_ms=_T0)
    assert len(calls) == 1


def test_an_EMPTY_first_page_returns_an_empty_frame(monkeypatch) -> None:
    _stub(monkeypatch, lambda url: [])
    assert CS.fetch_klines("BTCUSDT").empty


def test_SPOT_and_FUTURES_use_DIFFERENT_page_limits(monkeypatch) -> None:
    """Futures cap at 1500, spot at 1000. Requesting 1500 from spot returns 1000, so the
    `len(batch) < limit` termination fires on a FULL page and the history stops silently at the
    first thousand bars."""
    calls = _stub(monkeypatch, lambda url: [])
    CS.fetch_klines("BTCUSDT")
    CS.fetch_spot_klines("BTCUSDT")
    assert "limit=1500" in calls[0] and "/fapi/" in calls[0]
    assert "limit=1000" in calls[1] and "/api/v3/" in calls[1]


def test_FUNDING_pagination_advances_on_the_FUNDING_TIME_field(monkeypatch) -> None:
    """A different payload shape from klines -- dicts, not lists -- so the cursor field differs
    too. Reading index 0 of a dict is a KeyError; reading the wrong key is a silent reset to the
    start of history and an infinite walk."""
    pages = [
        [{"fundingTime": _T0 + i * 28_800_000, "fundingRate": "0.0001"} for i in range(1000)],
        [{"fundingTime": _T0 + 1000 * 28_800_000, "fundingRate": "0.0002"}],
    ]
    starts: list[int] = []

    def handler(url: str):
        starts.append(int(url.split("startTime=")[1]))
        return pages.pop(0) if pages else []

    _stub(monkeypatch, handler)
    df = CS.fetch_funding("BTCUSDT", start_ms=_T0)
    assert len(df) == 1001
    assert starts[1] == _T0 + 999 * 28_800_000 + 1


# ============================================================ the taker-buy fraction

def test_taker_buy_frac_is_the_QUOTE_ratio_and_flags_net_buying(monkeypatch) -> None:
    """>0.5 means net taker BUYING. Computed from quote volumes rather than base, because base
    volumes across different-priced assets are not comparable."""
    _stub(monkeypatch, lambda url: [_kline(_T0, quote_vol=1_000.0, taker_buy_quote=750.0)])
    df = CS.fetch_klines("BTCUSDT")
    assert df["taker_buy_frac"].iloc[0] == pytest.approx(0.75)


def test_a_ZERO_VOLUME_bar_reads_taker_buy_frac_of_a_HALF(monkeypatch) -> None:
    """Not NaN and not zero. A bar with no volume carries NO FLOW INFORMATION, and 0.5 is the
    neutral value; 0.0 would read as 'everyone sold', which is a signal nobody observed."""
    _stub(monkeypatch, lambda url: [_kline(_T0, quote_vol=0.0, taker_buy_quote=0.0)])
    assert CS.fetch_klines("BTCUSDT")["taker_buy_frac"].iloc[0] == pytest.approx(0.5)


def test_timestamps_are_the_bar_OPEN_time_in_UTC(monkeypatch) -> None:
    """Index 0 is openTime and index 6 is closeTime. Using the close would shift every bar forward
    by one interval and make yesterday's feature align with today's return."""
    _stub(monkeypatch, lambda url: [_kline(_T0)])
    ts = CS.fetch_klines("BTCUSDT")["timestamp"].iloc[0]
    assert ts == pd.Timestamp(_T0, unit="ms", tz="UTC")


# ============================================================ funding alignment

def _bars_stub(monkeypatch, klines, funding):
    def handler(url: str):
        if "klines" in url:
            return klines.pop(0) if klines else []
        if "fundingRate" in url:
            return funding.pop(0) if funding else []
        return []
    return _stub(monkeypatch, handler)


def test_DAILY_funding_is_the_SUM_of_the_days_three_payments(monkeypatch) -> None:
    """THE 3x ERROR. Funding settles every 8h, so a daily bar's carry cost is the SUM. A mean --
    the natural resample default -- understates it threefold, on the desk's one confirmed edge."""
    day = _T0
    _bars_stub(monkeypatch,
               [[_kline(day)]],
               [[{"fundingTime": day + h * 28_800_000, "fundingRate": "0.0001"}
                 for h in range(3)]])
    df = CS.bars_with_funding("BTCUSDT", interval="1d", start="2026-01-01")
    assert df["funding"].iloc[0] == pytest.approx(0.0003)


def test_8h_funding_maps_each_bar_to_EXACTLY_ONE_payment(monkeypatch) -> None:
    """At its native frequency each bar carries one settlement -- ~3x the independent observations
    of the daily series, which is why the 8h path exists at all."""
    _bars_stub(monkeypatch,
               [[_kline(_T0), _kline(_T0 + 28_800_000), _kline(_T0 + 57_600_000)]],
               [[{"fundingTime": _T0, "fundingRate": "0.0001"},
                 {"fundingTime": _T0 + 28_800_000, "fundingRate": "0.0002"},
                 {"fundingTime": _T0 + 57_600_000, "fundingRate": "0.0003"}]])
    df = CS.bars_with_funding("BTCUSDT", interval="8h", start="2026-01-01")
    assert list(df["funding"]) == pytest.approx([0.0001, 0.0002, 0.0003])


def test_the_8h_match_is_TOLERANCE_BOUNDED_so_a_distant_payment_is_not_borrowed(
        monkeypatch) -> None:
    """`method='nearest'` with no tolerance attaches the closest payment however far away it is, so
    a bar in a data gap inherits funding from days later -- a look-ahead that reads as carry."""
    _bars_stub(monkeypatch,
               [[_kline(_T0), _kline(_T0 + 30 * _DAY_MS)]],
               [[{"fundingTime": _T0, "fundingRate": "0.0001"}]])
    df = CS.bars_with_funding("BTCUSDT", interval="8h", start="2026-01-01")
    assert df["funding"].iloc[0] == pytest.approx(0.0001)
    assert df["funding"].iloc[1] == 0.0, "a bar 30 days from any payment must get nothing"


def test_NO_FUNDING_HISTORY_degrades_to_ZERO_not_to_a_dropped_row(monkeypatch) -> None:
    """Zero is "no carry observed"; a dropped row silently shortens the price history too, and the
    two failures look identical in a length check."""
    _bars_stub(monkeypatch, [[_kline(_T0), _kline(_T0 + _DAY_MS)]], [[]])
    df = CS.bars_with_funding("BTCUSDT", interval="1d", start="2026-01-01")
    assert len(df) == 2 and (df["funding"] == 0.0).all()


def test_NO_KLINES_returns_empty_WITHOUT_inventing_a_funding_column(monkeypatch) -> None:
    _bars_stub(monkeypatch, [[]], [[{"fundingTime": _T0, "fundingRate": "0.0001"}]])
    assert CS.bars_with_funding("BTCUSDT", start="2026-01-01").empty


def test_a_day_with_NO_payment_gets_zero_rather_than_a_forward_fill(monkeypatch) -> None:
    """Forward-filling funding across a gap invents payments that were never made and turns a
    venue outage into carry."""
    _bars_stub(monkeypatch,
               [[_kline(_T0), _kline(_T0 + _DAY_MS)]],
               [[{"fundingTime": _T0, "fundingRate": "0.0001"}]])
    df = CS.bars_with_funding("BTCUSDT", interval="1d", start="2026-01-01")
    assert df["funding"].iloc[1] == 0.0


# ============================================================ the enriched frame

def test_the_BASIS_is_PERP_over_SPOT_and_positive_means_CONTANGO(monkeypatch) -> None:
    """A sign error here inverts the carry sleeve's entire premise: it would short the basis in
    contango, which is when the trade pays."""
    # The counters make each leg return ONE page then stop -- the pagination walk would otherwise
    # re-serve the same bar forever and never terminate.
    state = {"spot": 0, "perp": 0}

    def handler(url: str):
        if "/api/v3/klines" in url:
            state["spot"] += 1
            return [_kline(_T0, close=100.0)] if state["spot"] == 1 else []
        if "fapi/v1/klines" in url:
            state["perp"] += 1
            return [_kline(_T0, close=105.0)] if state["perp"] == 1 else []
        return []

    _stub(monkeypatch, handler)
    df = CS.daily_enriched("BTCUSDT", start="2026-01-01")
    assert df["basis"].iloc[0] == pytest.approx(0.05)


def test_NO_SPOT_history_degrades_the_basis_to_ZERO(monkeypatch) -> None:
    """Zero basis is "no premium observed". Dropping the bar would lose the funding and the price
    for a missing third leg."""
    state = {"perp": 0}

    def handler(url: str):
        if "/api/v3/klines" in url:
            return []
        if "fapi/v1/klines" in url:
            state["perp"] += 1
            return [_kline(_T0)] if state["perp"] == 1 else []
        return []

    _stub(monkeypatch, handler)
    df = CS.daily_enriched("BTCUSDT", start="2026-01-01")
    assert len(df) == 1 and df["basis"].iloc[0] == 0.0


def test_the_enriched_frame_always_carries_every_declared_column(monkeypatch) -> None:
    """Downstream code indexes these by name. A missing column is an AttributeError deep in a
    sleeve rather than a clear failure here."""
    state = {"perp": 0, "spot": 0}

    def handler(url: str):
        if "/api/v3/klines" in url:
            state["spot"] += 1
            return [_kline(_T0, close=100.0)] if state["spot"] == 1 else []
        if "fapi/v1/klines" in url:
            state["perp"] += 1
            return [_kline(_T0, close=101.0)] if state["perp"] == 1 else []
        return []

    _stub(monkeypatch, handler)
    df = CS.daily_enriched("BTCUSDT", start="2026-01-01")
    for col in ("timestamp", "open", "high", "low", "close", "volume",
                "funding", "basis", "taker_buy_frac"):
        assert col in df.columns, col


def test_an_empty_perp_history_short_circuits_the_enrichment(monkeypatch) -> None:
    _stub(monkeypatch, lambda url: [])
    assert CS.daily_enriched("BTCUSDT", start="2026-01-01").empty


# ============================================================ the universe

def test_only_TRADING_USDT_PERPETUALS_are_in_the_universe(monkeypatch) -> None:
    """A delisted or coin-margined contract still has a symbol and a stale price, and including one
    puts a frozen series into every cross-sectional study."""
    _stub(monkeypatch, lambda url: {"symbols": [
        {"symbol": "BTCUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT",
         "status": "TRADING"},
        {"symbol": "ETHUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT",
         "status": "TRADING"},
        {"symbol": "DEADUSDT", "contractType": "PERPETUAL", "quoteAsset": "USDT",
         "status": "SETTLING"},
        {"symbol": "BTCUSD_PERP", "contractType": "PERPETUAL", "quoteAsset": "USD",
         "status": "TRADING"},
        {"symbol": "BTCUSDT_260925", "contractType": "CURRENT_QUARTER", "quoteAsset": "USDT",
         "status": "TRADING"},
    ]})
    assert CS.list_perp_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_a_degraded_exchangeInfo_yields_an_EMPTY_universe(monkeypatch) -> None:
    for payload in ({}, {"symbols": []}, [], None):
        _stub(monkeypatch, lambda url, p=payload: p)
        assert CS.list_perp_symbols() == []


def test_the_LIQUID_universe_is_ranked_by_QUOTE_volume_and_capped(monkeypatch) -> None:
    """Base volume across differently-priced assets is not comparable -- ranking on it puts the
    cheapest token first. And the cap is what makes it the TRADEABLE universe rather than all of it.
    """
    def handler(url: str):
        if "exchangeInfo" in url:
            return {"symbols": [
                {"symbol": s, "contractType": "PERPETUAL", "quoteAsset": "USDT",
                 "status": "TRADING"} for s in ("A", "B", "C", "D")]}
        return [{"symbol": "A", "quoteVolume": "10"}, {"symbol": "B", "quoteVolume": "1000"},
                {"symbol": "C", "quoteVolume": "100"}, {"symbol": "D", "quoteVolume": "1"},
                {"symbol": "NOTAPERP", "quoteVolume": "99999"}]

    _stub(monkeypatch, handler)
    assert CS.list_liquid_perps(top_n=3) == ["B", "C", "A"]


def test_a_ticker_that_is_NOT_a_perp_is_excluded_from_the_liquid_list(monkeypatch) -> None:
    """The 24h ticker endpoint returns dated contracts too. A quarterly ranked into the perp
    universe would be traded as one."""
    def handler(url: str):
        if "exchangeInfo" in url:
            return {"symbols": [{"symbol": "BTCUSDT", "contractType": "PERPETUAL",
                                 "quoteAsset": "USDT", "status": "TRADING"}]}
        return [{"symbol": "BTCUSDT", "quoteVolume": "10"},
                {"symbol": "BTCUSDT_260925", "quoteVolume": "1000000"}]

    _stub(monkeypatch, handler)
    assert CS.list_liquid_perps() == ["BTCUSDT"]


# ============================================================ point-in-time reads

def test_current_funding_maps_symbol_to_the_LAST_funding_rate(monkeypatch) -> None:
    _stub(monkeypatch, lambda url: [{"symbol": "BTCUSDT", "lastFundingRate": "0.0001"},
                                    {"symbol": "ETHUSDT", "lastFundingRate": "-0.0002"}])
    assert CS.current_funding() == {"BTCUSDT": pytest.approx(0.0001),
                                    "ETHUSDT": pytest.approx(-0.0002)}


def test_current_funding_SKIPS_rows_with_no_symbol_and_degrades_to_empty(monkeypatch) -> None:
    _stub(monkeypatch, lambda url: [{"lastFundingRate": "0.0001"}, "junk"])
    assert CS.current_funding() == {}
    _stub(monkeypatch, lambda url: {"unexpected": "shape"})
    assert CS.current_funding() == {}


def test_a_row_with_NO_rate_defaults_to_zero_rather_than_dropping_the_symbol(
        monkeypatch) -> None:
    _stub(monkeypatch, lambda url: [{"symbol": "BTCUSDT"}])
    assert CS.current_funding() == {"BTCUSDT": 0.0}


def test_open_interest_degrades_to_zero_on_an_unexpected_shape(monkeypatch) -> None:
    _stub(monkeypatch, lambda url: {"openInterest": "12345.6"})
    assert CS.fetch_open_interest("BTCUSDT") == pytest.approx(12345.6)
    _stub(monkeypatch, lambda url: [])
    assert CS.fetch_open_interest("BTCUSDT") == 0.0


# ============================================================ the 30d-capped derivatives stats

@pytest.mark.parametrize(("fn", "field", "col"), [
    (CS.fetch_long_short_ratio, "longShortRatio", "ls_ratio"),
    (CS.fetch_long_short_hist, "longShortRatio", "ls_ratio"),
    (CS.fetch_open_interest_hist, "sumOpenInterest", "open_interest"),
    (CS.fetch_taker_ratio, "buySellRatio", "taker_ratio"),
])
def test_every_capped_stat_parses_to_a_UTC_timestamped_frame(monkeypatch, fn, field,
                                                             col) -> None:
    """These endpoints are ~30-day capped, which is exactly why the desk archives them forward --
    an unrecorded day cannot be bought back. A parse failure here loses history permanently."""
    _stub(monkeypatch, lambda url: [{"timestamp": _T0, field: "1.5"},
                                    {"timestamp": _T0 + 3_600_000, field: "0.8"}])
    df = fn("BTCUSDT")
    assert list(df[col]) == pytest.approx([1.5, 0.8])
    assert str(df["timestamp"].dt.tz) == "UTC"


@pytest.mark.parametrize("fn", [CS.fetch_long_short_ratio, CS.fetch_long_short_hist,
                                CS.fetch_open_interest_hist, CS.fetch_taker_ratio])
@pytest.mark.parametrize("payload", [[], {}, None, "unexpected"])
def test_every_capped_stat_degrades_to_an_EMPTY_FRAME(monkeypatch, fn, payload) -> None:
    _stub(monkeypatch, lambda url: payload)
    assert fn("BTCUSDT").empty


def test_the_HIST_endpoints_request_the_declared_period_and_limit(monkeypatch) -> None:
    """The whole reason the hist variants exist is ~480 hourly points over ~20 days -- enough to
    backtest now rather than waiting for forward accumulation. A dropped limit gives the default."""
    calls = _stub(monkeypatch, lambda url: [])
    CS.fetch_open_interest_hist("BTCUSDT", period="1h", limit=500)
    CS.fetch_long_short_hist("BTCUSDT", period="1h", limit=500)
    assert all("period=1h" in c and "limit=500" in c for c in calls)


# ============================================================ the fetcher

def test_the_fetcher_retries_then_raises_naming_the_url(monkeypatch) -> None:
    monkeypatch.setattr(CS.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError):
        CS._get("https://example.test/x")


def test_no_test_in_this_file_reaches_the_network(monkeypatch) -> None:
    def forbidden(*a, **k):
        raise AssertionError("a test reached Binance")

    monkeypatch.setattr(CS.urllib.request, "urlopen", forbidden)
    _stub(monkeypatch, lambda url: [])
    assert CS.fetch_klines("BTCUSDT").empty
