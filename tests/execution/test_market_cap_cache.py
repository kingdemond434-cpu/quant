"""A TRANSIENT LOOKUP FAILURE MUST NOT PERMANENTLY DISABLE THE MARKET-ORDER CAP.

`_market_max_qty` exists because of a specific incident: COOKIEUSDT has a MARKET_LOT_SIZE maxQty
of 150,000, every 183,140-unit market order was rejected -4005, and the executor fell through to
its resting-limit fallback -- whose accumulated fills walked a short through zero into a +916,772
long. The cap is what stops that repeating.

It cached its own failure. On any exception the function fell through to
`_MKT_MAX_CACHE[symbol] = cap` with cap still inf, so ONE network blip during the lookup disabled
the cap for that symbol for the entire process lifetime -- and the executor runs for days between
restarts. The protection would be gone, silently, with no trace anywhere.

Returning inf for the failing call is correct (never invent a limit from a failed lookup). Caching
it is not.
"""

from __future__ import annotations

import pytest

from libs.execution import binance_live, binance_testnet


@pytest.mark.parametrize("mod", [binance_live, binance_testnet], ids=["live", "testnet"])
def test_a_failed_lookup_is_not_cached_and_the_next_call_retries(mod, monkeypatch) -> None:
    mod._MKT_MAX_CACHE.clear()
    calls = {"n": 0}

    def flaky(_path, **_kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("transient")
        return {"symbols": [{"symbol": "COOKIEUSDT",
                             "filters": [{"filterType": "MARKET_LOT_SIZE",
                                          "maxQty": "150000"}]}]}

    monkeypatch.setattr(mod, "_get", flaky)
    try:
        first = mod._market_max_qty("COOKIEUSDT")
        assert first == float("inf"), "a failed lookup must not invent a limit"
        assert "COOKIEUSDT" not in mod._MKT_MAX_CACHE, (
            "the failure was CACHED -- one blip and the cap is gone for the process lifetime")

        second = mod._market_max_qty("COOKIEUSDT")
        assert second == 150000.0, (
            "the retry did not happen, so the cap never comes back without a restart")
        assert calls["n"] == 2
    finally:
        mod._MKT_MAX_CACHE.clear()


@pytest.mark.parametrize("mod", [binance_live, binance_testnet], ids=["live", "testnet"])
def test_a_successful_lookup_IS_cached(mod, monkeypatch) -> None:
    """The other half: not caching successes would hit the venue on every single order, which is
    the rate-limit overrun that got this desk's IP cut off for six hours."""
    mod._MKT_MAX_CACHE.clear()
    calls = {"n": 0}

    def once(_path, **_kw):
        calls["n"] += 1
        return {"symbols": [{"symbol": "BTCUSDT",
                             "filters": [{"filterType": "MARKET_LOT_SIZE", "maxQty": "120"}]}]}

    monkeypatch.setattr(mod, "_get", once)
    try:
        assert mod._market_max_qty("BTCUSDT") == 120.0
        assert mod._market_max_qty("BTCUSDT") == 120.0
        assert calls["n"] == 1, "a cached cap must not re-query the venue"
    finally:
        mod._MKT_MAX_CACHE.clear()
