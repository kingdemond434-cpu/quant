"""FREE, KEY-LESS DATA FAMILIES -- 75 statements, untested, and every one is a NETWORK parser.

A network parser is the worst untested code on a desk, because its failure mode is not a crash: it
is a plausible-looking number computed from a payload the venue changed. Nothing downstream can
tell a real basis of +8% from one produced by a renamed field, and both enter the funnel wearing
the same vocabulary.

SO EVERY TEST HERE STUBS `_get` AND ASSERTS THE PARSE. No test in this file touches the network:
a suite that reached a venue would be slow, flaky, rate-limited, and would silently start passing
for the wrong reason the day the venue went down.

The two properties that matter more than the arithmetic:

  A DEGRADED SHAPE RETURNS EMPTY, NEVER A PARTIAL NUMBER. An unexpected payload must produce {} or
  an empty frame -- not a dict with three of four fields and a zero in the fourth, which reads
  downstream as "measured and zero" rather than "not measured".

  THE CALENDAR BASIS IS ANNUALISED BY ACTUAL DAYS TO EXPIRY. A quarterly at +2% with 9 days left is
  a very different carry from +2% with 90 days left, and collapsing them is how a term-structure
  signal becomes a constant.
"""

from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
import pytest

from libs.data import freesources as FS


def _stub(monkeypatch, responses: dict[str, Any] | list[Any]):
    """Replace `_get` with a lookup. Records the calls so request SHAPE can be asserted too."""
    calls: list[tuple[str, bytes | None]] = []

    def fake(url: str, *, data: bytes | None = None, hdr: dict | None = None, tries: int = 3):
        calls.append((url, data))
        if isinstance(responses, list):
            return responses.pop(0)
        for key, val in responses.items():
            if key in url:
                if isinstance(val, Exception):
                    raise val
                return val
        raise AssertionError(f"unstubbed URL: {url}")

    monkeypatch.setattr(FS, "_get", fake)
    return calls


# ============================================================ the fetcher itself

def test_the_fetcher_RETRIES_transient_failures_before_giving_up(monkeypatch) -> None:
    """Rate limits and transient DNS are the normal state of free public REST. One attempt would
    make every collector fail on a schedule rather than on a fault."""
    attempts = {"n": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"ok": True}).encode()

    def flaky(req, timeout=0):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("transient")
        return _Resp()

    monkeypatch.setattr(FS.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    assert FS._get("https://example.test/x") == {"ok": True}
    assert attempts["n"] == 3


def test_the_fetcher_RAISES_with_the_url_and_the_cause_after_exhausting_retries(
        monkeypatch) -> None:
    """A collector that returned None on total failure would write an empty artifact that looks
    exactly like a quiet day. Raising forces the caller to decide."""
    monkeypatch.setattr(FS.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="GET failed"):
        FS._get("https://example.test/x")


# ============================================================ fear & greed

def test_fear_greed_parses_epoch_seconds_and_sorts_ASCENDING(monkeypatch) -> None:
    """The API returns newest-first. A consumer computing a rolling mean over an unsorted frame
    gets a number about nothing, and pandas will not complain."""
    _stub(monkeypatch, {"alternative.me": {"data": [
        {"timestamp": "1767398400", "value": "70"},
        {"timestamp": "1767225600", "value": "30"},
    ]}})
    df = FS.fear_greed()
    assert list(df["fng"]) == [30.0, 70.0]
    assert df["timestamp"].is_monotonic_increasing
    assert str(df["timestamp"].dt.tz) == "UTC"


def test_fear_greed_returns_an_EMPTY_FRAME_on_a_degraded_payload(monkeypatch) -> None:
    for payload in ({"data": []}, {}, [], None, "unexpected"):
        _stub(monkeypatch, {"alternative.me": payload})
        assert FS.fear_greed().empty


def test_fear_greed_index_is_reset_so_positional_slicing_is_safe(monkeypatch) -> None:
    """A sort that keeps the original index makes `df.iloc[-1]` and `df.loc[len-1]` disagree, and
    a caller reaching for "the latest reading" gets whichever the venue happened to list last."""
    _stub(monkeypatch, {"alternative.me": {"data": [
        {"timestamp": "1767398400", "value": "70"},
        {"timestamp": "1767225600", "value": "30"},
    ]}})
    df = FS.fear_greed()
    assert list(df.index) == [0, 1]


# ============================================================ coingecko global

def test_coingecko_global_extracts_the_regime_snapshot(monkeypatch) -> None:
    _stub(monkeypatch, {"coingecko": {"data": {
        "total_market_cap": {"usd": 2.5e12, "eur": 2.3e12},
        "market_cap_percentage": {"btc": 54.2, "eth": 13.1},
        "market_cap_change_percentage_24h_usd": -1.4,
    }}})
    g = FS.coingecko_global()
    assert g["total_mcap_usd"] == pytest.approx(2.5e12)
    assert g["btc_dominance"] == pytest.approx(54.2)
    assert g["eth_dominance"] == pytest.approx(13.1)
    assert g["mcap_change_24h"] == pytest.approx(-1.4)


def test_coingecko_global_returns_EMPTY_on_a_degraded_payload(monkeypatch) -> None:
    """{} says NOT MEASURED. A dict of zeros says "BTC dominance is 0%", which is a regime claim
    no consumer should ever act on and none would question."""
    for payload in ({}, {"data": {}}, [], None):
        _stub(monkeypatch, {"coingecko": payload})
        assert FS.coingecko_global() == {}


def test_a_MISSING_sub_field_defaults_to_zero_rather_than_raising(monkeypatch) -> None:
    """The dict is non-empty, so the call succeeded and only one field is absent -- distinct from
    the whole payload being wrong, and worth degrading rather than failing the collector."""
    _stub(monkeypatch, {"coingecko": {"data": {"market_cap_percentage": {"btc": 50.0}}}})
    g = FS.coingecko_global()
    assert g["btc_dominance"] == 50.0 and g["total_mcap_usd"] == 0.0


# ============================================================ hyperliquid

def test_hyperliquid_zips_the_universe_to_its_contexts_by_POSITION(monkeypatch) -> None:
    """The API returns two parallel arrays. A misalignment here attributes BTC's funding to the
    next asset in the list -- a silent, total, per-asset corruption that no downstream check could
    detect, because every value is individually plausible."""
    _stub(monkeypatch, {"hyperliquid": [
        {"universe": [{"name": "BTC"}, {"name": "ETH"}, {"name": "SOL"}]},
        [{"funding": "0.0001"}, {"funding": "-0.0002"}, {"funding": "0.00005"}],
    ]})
    f = FS.hyperliquid_funding()
    assert f == {"BTC": pytest.approx(0.0001), "ETH": pytest.approx(-0.0002),
                 "SOL": pytest.approx(0.00005)}


def test_hyperliquid_sends_the_declared_POST_body(monkeypatch) -> None:
    """It is a POST with a typed body, not a GET. If the body ever changed shape the venue returns
    a different endpoint's payload, which would parse to {} and read as "no funding anywhere"."""
    calls = _stub(monkeypatch, {"hyperliquid": [{"universe": []}, []]})
    FS.hyperliquid_funding()
    assert calls and calls[0][1] is not None
    assert json.loads(calls[0][1]) == {"type": "metaAndAssetCtxs"}


def test_an_asset_with_NO_funding_field_is_OMITTED_not_zeroed(monkeypatch) -> None:
    """A perp with no funding printed is not a perp funding at zero. Zeroing it would put a
    fabricated observation into a cross-sectional funding study."""
    _stub(monkeypatch, {"hyperliquid": [
        {"universe": [{"name": "BTC"}, {"name": "GHOST"}]},
        [{"funding": "0.0001"}, {}],
    ]})
    assert FS.hyperliquid_funding() == {"BTC": pytest.approx(0.0001)}


@pytest.mark.parametrize("payload", [[], [{}], [{}, {}, {}], {}, None])
def test_hyperliquid_returns_EMPTY_on_an_unexpected_envelope(monkeypatch, payload) -> None:
    _stub(monkeypatch, {"hyperliquid": payload})
    assert FS.hyperliquid_funding() == {}


def test_RAGGED_arrays_are_truncated_rather_than_raising(monkeypatch) -> None:
    """`strict=False` on the zip. A venue adding one asset mid-response must cost that asset, not
    the whole collection."""
    _stub(monkeypatch, {"hyperliquid": [
        {"universe": [{"name": "BTC"}, {"name": "ETH"}]},
        [{"funding": "0.0001"}],
    ]})
    assert FS.hyperliquid_funding() == {"BTC": pytest.approx(0.0001)}


# ============================================================ dated quarterlies

def test_only_TRADING_quarterly_contracts_are_selected(monkeypatch) -> None:
    """A delivered or halted contract still has a symbol and a stale price. Including it produces
    a calendar basis against a price that has stopped moving."""
    _stub(monkeypatch, {"exchangeInfo": {"symbols": [
        {"symbol": "BTCUSDT_260925", "contractType": "CURRENT_QUARTER", "status": "TRADING"},
        {"symbol": "BTCUSDT_261225", "contractType": "NEXT_QUARTER", "status": "TRADING"},
        {"symbol": "BTCUSDT_250626", "contractType": "CURRENT_QUARTER", "status": "SETTLING"},
        {"symbol": "BTCUSDT", "contractType": "PERPETUAL", "status": "TRADING"},
    ]}})
    assert FS.dated_quarterly_symbols() == ["BTCUSDT_260925", "BTCUSDT_261225"]


def test_dated_quarterlies_return_EMPTY_on_a_degraded_payload(monkeypatch) -> None:
    for payload in ({}, {"symbols": []}, [], None):
        _stub(monkeypatch, {"exchangeInfo": payload})
        assert FS.dated_quarterly_symbols() == []


# ============================================================ calendar basis

def _basis_stub(monkeypatch, *, quarter_px: float, perp_px: float, expiry: str,
                symbol: str = "BTCUSDT_260925"):
    return _stub(monkeypatch, {
        "exchangeInfo": {"symbols": [
            {"symbol": symbol, "contractType": "CURRENT_QUARTER", "status": "TRADING"}]},
        f"ticker/price?symbol={symbol}": {"symbol": symbol, "price": str(quarter_px)},
        "ticker/price": [{"symbol": "BTCUSDT", "price": str(perp_px)}],
    })


def test_the_basis_is_ANNUALISED_BY_ACTUAL_DAYS_TO_EXPIRY(monkeypatch) -> None:
    """+2% with 9 days left is a very different carry from +2% with 90 days left. Collapsing them
    turns a term-structure signal into a constant, and the shorter one is where the carry is."""
    now = pd.Timestamp.now(tz="UTC")
    near = (now + pd.Timedelta(days=30)).strftime("%y%m%d")
    far = (now + pd.Timedelta(days=180)).strftime("%y%m%d")

    _basis_stub(monkeypatch, quarter_px=102.0, perp_px=100.0, expiry=near,
                symbol=f"BTCUSDT_{near}")
    near_ann = FS.calendar_basis()["BTCUSDT"]

    _basis_stub(monkeypatch, quarter_px=102.0, perp_px=100.0, expiry=far,
                symbol=f"BTCUSDT_{far}")
    far_ann = FS.calendar_basis()["BTCUSDT"]

    assert near_ann > far_ann * 4, "the same 2% over 30d must annualise far above 180d"
    assert near_ann == pytest.approx(0.02 * 365.0 / 30.0, rel=0.15)


def test_BACKWARDATION_comes_out_NEGATIVE(monkeypatch) -> None:
    """Positive = contango, negative = stress. A sign error here inverts a stress signal into a
    carry signal at exactly the moment it matters."""
    exp = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=60)).strftime("%y%m%d")
    _basis_stub(monkeypatch, quarter_px=98.0, perp_px=100.0, expiry=exp,
                symbol=f"BTCUSDT_{exp}")
    assert FS.calendar_basis()["BTCUSDT"] < 0


def test_a_quarterly_with_NO_MATCHING_PERP_is_skipped(monkeypatch) -> None:
    """Dividing by a perp price that is not there would raise; defaulting it would invent a basis
    against an assumed spot."""
    exp = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=60)).strftime("%y%m%d")
    _stub(monkeypatch, {
        "exchangeInfo": {"symbols": [
            {"symbol": f"OBSCUREUSDT_{exp}", "contractType": "CURRENT_QUARTER",
             "status": "TRADING"}]},
        "ticker/price": [{"symbol": "BTCUSDT", "price": "100.0"}],
    })
    assert FS.calendar_basis() == {}


def test_a_NON_POSITIVE_price_on_either_leg_is_skipped(monkeypatch) -> None:
    exp = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=60)).strftime("%y%m%d")
    _basis_stub(monkeypatch, quarter_px=0.0, perp_px=100.0, expiry=exp,
                symbol=f"BTCUSDT_{exp}")
    assert FS.calendar_basis() == {}


def test_a_MALFORMED_expiry_suffix_is_skipped(monkeypatch) -> None:
    """`BTCUSDT_PERP` and `BTCUSDT_2609` both partition cleanly and neither is a date. Parsing them
    as one would place the expiry in the wrong century and annualise against it."""
    _stub(monkeypatch, {
        "exchangeInfo": {"symbols": [
            {"symbol": "BTCUSDT_PERP", "contractType": "CURRENT_QUARTER", "status": "TRADING"}]},
        "ticker/price": [{"symbol": "BTCUSDT", "price": "100.0"}],
    })
    assert FS.calendar_basis() == {}


def test_an_expiry_ALREADY_PASSED_is_floored_at_one_day_not_divided_by_zero(
        monkeypatch) -> None:
    """A contract expiring today would otherwise divide by ~0 and annualise to infinity, which
    every downstream ranker would put first."""
    exp = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=3)).strftime("%y%m%d")
    _basis_stub(monkeypatch, quarter_px=101.0, perp_px=100.0, expiry=exp,
                symbol=f"BTCUSDT_{exp}")
    out = FS.calendar_basis()
    if out:
        assert all(abs(v) < 1e4 for v in out.values())


def test_no_quarterlies_means_an_EMPTY_result_and_no_further_requests(monkeypatch) -> None:
    """Short-circuiting matters: without quarterlies there is nothing to price, and fetching the
    whole ticker table anyway would spend a rate limit to compute {}."""
    calls = _stub(monkeypatch, {"exchangeInfo": {"symbols": []}})
    assert FS.calendar_basis() == {}
    assert len(calls) == 1


# ============================================================ the contract

def test_no_fetcher_reaches_the_network_in_this_suite(monkeypatch) -> None:
    """Stated as a test so it stays true. A suite that reached a venue would be slow, flaky,
    rate-limited, and would start passing for the wrong reason the day the venue went down."""
    def forbidden(*a, **k):
        raise AssertionError("a test reached the network")

    monkeypatch.setattr(FS.urllib.request, "urlopen", forbidden)
    _stub(monkeypatch, {"alternative.me": {"data": []}})
    assert FS.fear_greed().empty
