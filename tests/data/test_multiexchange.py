"""Tests for the multi-exchange data family (pure logic; network fetchers are integration-only)."""

from __future__ import annotations

from libs.data.multiexchange import okx_inst


def test_okx_inst_mapping() -> None:
    assert okx_inst("BTCUSDT") == "BTC-USDT-SWAP"
    assert okx_inst("ETHUSDT") == "ETH-USDT-SWAP"
    assert okx_inst("1000PEPEUSDT") == "1000PEPE-USDT-SWAP"
