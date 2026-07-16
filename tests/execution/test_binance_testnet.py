"""Binance testnet connector -- safety invariants (no live-trading risk, no keys in code)."""

from __future__ import annotations

import libs.execution.binance_testnet as bt


def test_base_url_is_pinned_to_testnet() -> None:
    assert "testnet" in bt._BASE                          # cannot point at a live account
    assert bt._BASE.startswith("https://")


def test_no_keys_means_no_signed_calls(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("BINANCE_TESTNET_KEY", raising=False)
    monkeypatch.delenv("BINANCE_TESTNET_SECRET", raising=False)
    monkeypatch.setattr(bt, "_KEYFILE", tmp_path / "nope.json")   # no env, no file
    assert bt.has_keys() is False
    # signed calls must refuse without keys (so a misconfigured run cannot trade)
    try:
        bt.account_balance()
    except RuntimeError as e:
        assert "keys" in str(e)
    else:  # pragma: no cover
        raise AssertionError("signed call should have raised without keys")


def test_has_keys_true_with_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BINANCE_TESTNET_KEY", "x")
    monkeypatch.setenv("BINANCE_TESTNET_SECRET", "y")
    assert bt.has_keys() is True
