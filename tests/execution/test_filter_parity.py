"""Four near-duplicate exchangeInfo parsers, and nothing pinned them together until now.

THE DEFECT THIS EXISTS TO PREVENT (found 2026-07-31). ``min_notional`` was added to
``binance_spot_live.exchange_filters`` alone. Every money-path caller
(run_cashcarry_executor, run_stranded_recovery, run_deadman_stranded_sweep) imports the
**testnet** modules, so the new field reached ZERO consumers and ``run_stranded_recovery``
went on using its hardcoded ``10.0`` fallback. A green unit test on the module that was
edited would have proved the parse worked and said nothing about whether anything read it.

So these tests pin the two things that actually fail silently:
  1. KEY PARITY -- the spot live/testnet parsers must expose the SAME field set, so a field
     added to one is a test failure until it is added to the other.
  2. KEY NAME -- spot publishes the minimum under ``minNotional``; USD-M futures publishes
     the same filter under ``notional``. Copying the spot line into the futures parsers
     yields 0.0 for every symbol, which reads as "no minimum" -- the dangerous direction.

No network: ``_get`` is monkeypatched with a synthetic exchangeInfo payload, so this runs
offline in CI exactly as the real parse would.
"""

from __future__ import annotations

import libs.execution.binance_live as bl
import libs.execution.binance_spot_live as bsl
import libs.execution.binance_spot_testnet as bst
import libs.execution.binance_testnet as bt

_SPOT_MODULES = (bsl, bst)


def _spot_payload() -> dict:
    """Three symbols covering the current filter name, the legacy one, and neither."""
    return {"symbols": [
        {"symbol": "AAAUSDT", "baseAssetPrecision": 8, "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.00100000", "minQty": "0.00100000"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
            {"filterType": "NOTIONAL", "minNotional": "5.00000000"}]},
        {"symbol": "BBBUSDT", "baseAssetPrecision": 6, "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.10000000", "minQty": "0.10000000"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.00010000"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "10.00000000"}]},   # legacy name
        {"symbol": "CCCUSDT", "baseAssetPrecision": 4, "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "1.00000000", "minQty": "1.00000000"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.00001000"}]},       # no minimum
    ]}


def _parsed(mod, monkeypatch) -> dict:
    monkeypatch.setattr(mod, "_get", lambda *a, **k: _spot_payload())
    return mod.exchange_filters()


def test_spot_parsers_expose_identical_field_sets(monkeypatch):
    """A field added to one spot parser and not the other is INERT -- fail, don't ship it."""
    keysets = []
    for mod in _SPOT_MODULES:
        out = _parsed(mod, monkeypatch)
        assert set(out) == {"AAAUSDT", "BBBUSDT", "CCCUSDT"}, mod.__name__
        keysets.append({sym: frozenset(f) for sym, f in out.items()})
    assert keysets[0] == keysets[1], (
        f"spot filter parsers diverged: {bsl.__name__} vs {bst.__name__}. A field present in "
        "only one reaches only that module's callers -- the money path imports the TESTNET one.")


def test_spot_parsers_agree_value_for_value(monkeypatch):
    parsed = [_parsed(mod, monkeypatch) for mod in _SPOT_MODULES]
    assert parsed[0] == parsed[1]


def test_min_notional_parsed_from_both_filter_names(monkeypatch):
    """NOTIONAL is current, MIN_NOTIONAL is legacy; Binance serves both across symbols."""
    for mod in _SPOT_MODULES:
        out = _parsed(mod, monkeypatch)
        assert out["AAAUSDT"]["min_notional"] == 5.0, f"{mod.__name__}: NOTIONAL not parsed"
        assert out["BBBUSDT"]["min_notional"] == 10.0, f"{mod.__name__}: MIN_NOTIONAL not parsed"


def test_absent_minimum_is_zero_not_a_silent_default(monkeypatch):
    """0.0 means "venue publishes no minimum" and callers must recognise it AS that.

    Parsing an absent filter into a plausible-looking number (e.g. 10.0) would make a guess
    indistinguishable from venue truth at every call site downstream.
    """
    for mod in _SPOT_MODULES:
        assert _parsed(mod, monkeypatch)["CCCUSDT"]["min_notional"] == 0.0, mod.__name__


def test_futures_parsers_must_not_copy_the_spot_key(monkeypatch):
    """USD-M futures publishes the minimum as ``notional``, not ``minNotional``.

    Futures does not parse the field today. This test does not demand that it does -- it demands
    that IF it starts to, it uses the futures key. A copy-paste of the spot line would read
    ``minNotional`` off a futures payload, get 0.0 for every symbol, and be indistinguishable
    from "this venue has no minimums".
    """
    fut_payload = {"symbols": [
        {"symbol": "AAAUSDT", "quantityPrecision": 3, "pricePrecision": 2, "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"}]}]}
    for mod in (bl, bt):
        monkeypatch.setattr(mod, "_get", lambda *a, **k: fut_payload)
        got = mod.exchange_filters()["AAAUSDT"]
        assert got.get("min_notional", 0.0) != 0.0 or "min_notional" not in got, (
            f"{mod.__name__} exposes min_notional as 0.0 on a payload that publishes 5 under "
            "'notional' -- it is reading the SPOT key 'minNotional' on a FUTURES payload.")
