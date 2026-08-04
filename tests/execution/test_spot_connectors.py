"""THE SPOT LEGS -- the other half of a delta-neutral book, and the least-covered code in it.

`binance_spot_testnet.py` sat at 22.1% and `binance_spot_live.py` at 40.9% when coverage was first
measured on 2026-08-04. A cash-and-carry position is a perp leg AND a spot leg; a defect here
leaves the book directional in exactly the way the strategy exists to avoid, and it does it
quietly because the perp side still looks correct.

Both modules expose the same surface, so every test runs against BOTH -- which is also the point.
They were written by copying one from the other, so a bug in one is very likely a bug in the
other: the market-cap-cache defect fixed earlier today was present in both, identically.

No network, no credentials: `_get` and `_signed` are replaced.
"""

from __future__ import annotations

import pytest

from libs.execution import binance_spot_live, binance_spot_testnet

MODS = [binance_spot_live, binance_spot_testnet]
IDS = ["spot_live", "spot_testnet"]


# ------------------------------------------------------------------------- depth

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_quote_depth_sums_the_side_the_trade_would_EAT(mod, monkeypatch) -> None:
    """A BUY consumes ASKS. Summing bids instead reports the liquidity available to the OPPOSITE
    trade -- the number that makes an illiquid entry look safe, on the leg that is supposed to be
    the easy one."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {
        "bids": [["100", "2"], ["99.5", "4"], ["10", "1000"]],
        "asks": [["101", "3"], ["101.5", "1"], ["500", "1000"]]})
    buy = mod.quote_depth("BTCUSDT", "BUY", pct=0.02)
    sell = mod.quote_depth("BTCUSDT", "SELL", pct=0.02)
    assert buy == pytest.approx(101 * 3 + 101.5 * 1)
    assert sell == pytest.approx(100 * 2 + 99.5 * 4)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_levels_outside_the_band_are_excluded(mod, monkeypatch) -> None:
    """The far level is real liquidity at a ruinous price. Counting it says the book can absorb a
    size it can only absorb by paying 5x."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {
        "asks": [["100", "1"], ["500", "1000"]], "bids": []})
    assert mod.quote_depth("BTCUSDT", "BUY", pct=0.01) == pytest.approx(100.0)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_an_empty_or_broken_book_is_zero_depth_not_an_exception(mod, monkeypatch) -> None:
    """Zero refuses the trade. Raising takes down the sizing loop that asked, which is worse:
    the caller is mid-way through building a hedged pair."""
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"bids": [], "asks": []})
    assert mod.quote_depth("BTCUSDT", "BUY") == 0.0
    monkeypatch.setattr(mod, "_get", lambda *_a, **_k: {"code": -1121, "msg": "bad symbol"})
    assert mod.quote_depth("BTCUSDT", "SELL") == 0.0

    def boom(*_a, **_k):
        raise TimeoutError("venue down")

    monkeypatch.setattr(mod, "_get", boom)
    assert mod.quote_depth("BTCUSDT", "BUY") == 0.0


# -------------------------------------------------------------------- fill truth

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_avg_fill_is_quote_over_base_and_filters_to_OUR_side(mod, monkeypatch) -> None:
    """VWAP, not a mean of prices: a mean over-weights small fills. And a BUY must not average in
    the sell trades on the same symbol -- that is the venue's tape, not the desk's execution."""
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: [
        {"isBuyer": True, "qty": "1.0", "quoteQty": "100.0"},
        {"isBuyer": True, "qty": "3.0", "quoteQty": "360.0"},
        {"isBuyer": False, "qty": "5.0", "quoteQty": "9999.0"},
    ])
    assert mod.avg_fill("BTCUSDT", "BUY", 0) == pytest.approx(460.0 / 4.0)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_avg_fill_is_None_rather_than_zero_when_nothing_filled(mod, monkeypatch) -> None:
    """NONE AND ZERO ARE DIFFERENT FACTS and the caller divides by this. A zero average fill
    propagates as an infinite or nonsensical slippage figure into the cost model; None says 'not
    observed yet', which is what actually happened."""
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: [])
    assert mod.avg_fill("BTCUSDT", "BUY", 0) is None
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: [
        {"isBuyer": True, "qty": "0", "quoteQty": "0"}])
    assert mod.avg_fill("BTCUSDT", "BUY", 0) is None


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_an_unarmed_or_failing_read_is_None_not_a_crash(mod, monkeypatch) -> None:
    """The connector refuses signed calls when unarmed. That must read as 'no fill data', because
    avg_fill is called from reconciliation loops that run whether or not keys are present."""
    def boom(*_a, **_k):
        raise RuntimeError("not armed")

    monkeypatch.setattr(mod, "_signed", boom)
    assert mod.avg_fill("BTCUSDT", "SELL", 0) is None


# --------------------------------------------------------------------- balances

@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_balances_drop_zero_assets(mod, monkeypatch) -> None:
    """A dust-free zero balance is not a holding. Carrying it makes the account look diversified
    across assets it does not hold, and account_value iterates these keys."""
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: {"balances": [
        {"asset": "USDT", "free": "500.0"},
        {"asset": "BTC", "free": "0.25"},
        {"asset": "DOGE", "free": "0.0"},
    ]})
    b = mod.balances()
    assert b == {"USDT": 500.0, "BTC": 0.25}
    assert mod.usdt_balance() == pytest.approx(500.0)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_usdt_balance_is_zero_when_the_account_holds_none(mod, monkeypatch) -> None:
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: {"balances": [
        {"asset": "BTC", "free": "1.0"}]})
    assert mod.usdt_balance() == 0.0


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_account_value_marks_every_holding_at_spot(mod, monkeypatch) -> None:
    """USDT counts at par; everything else needs a mark. A holding with no price must not be
    silently valued at zero OR at one -- both are wrong, and one of them is wrong upward."""
    monkeypatch.setattr(mod, "_signed", lambda *_a, **_k: {"balances": [
        {"asset": "USDT", "free": "100.0"},
        {"asset": "BTC", "free": "2.0"},
    ]})
    monkeypatch.setattr(mod, "prices", lambda: {"BTCUSDT": 50_000.0})
    assert mod.account_value_usdt() == pytest.approx(100.0 + 2.0 * 50_000.0)


@pytest.mark.parametrize("mod", MODS, ids=IDS)
def test_the_two_spot_connectors_expose_the_SAME_surface(mod) -> None:
    """They were written by copying one from the other, so a divergence is a bug waiting to be
    found in production on whichever one is not being read. The market-cap-cache defect fixed
    earlier today was present in both, identically."""
    required = {"quote_depth", "avg_fill", "balances", "usdt_balance", "account_value_usdt",
                "prices", "exchange_filters", "book_ticker", "has_keys"}
    missing = required - set(dir(mod))
    assert not missing, f"{mod.__name__} is missing {sorted(missing)}"


def test_ONLY_the_live_connector_demands_an_arming_ceremony() -> None:
    """THE ONE DIVERGENCE THAT IS CORRECT, AND WHY, WRITTEN DOWN.

    The parity test above initially demanded `is_armed` on both and failed on the testnet module.
    Investigating it: `binance_spot_live._signed` refuses every signed call unless `is_armed()`
    passes, because those calls move REAL money and possessing a key is not the same as intending
    to trade. `binance_spot_testnet._signed` asks only for keys -- an arming ceremony on fake money
    is friction with no safety value, and friction on the safe path pushes people to test on the
    unsafe one.

    So the asymmetry is deliberate, and pinning it here means the next parity sweep does not
    "fix" it by adding an arming gate to testnet -- or, far worse, by removing one from live.
    """
    import inspect
    live = inspect.getsource(binance_spot_live._signed)
    testnet = inspect.getsource(binance_spot_testnet._signed)
    assert "is_armed()" in live, "the LIVE connector lost its arming gate -- keys are not consent"
    assert "not armed" in live
    assert "is_armed" not in testnet, (
        "testnet grew an arming gate: friction on the safe path pushes testing onto the live one")
    assert "no spot-testnet keys" in testnet, "testnet must still require its own keys"
