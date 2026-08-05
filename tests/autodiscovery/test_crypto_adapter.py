"""Crypto lake -> factory adapter: symbol discovery, provider skip, web payload shape."""

from __future__ import annotations

from pathlib import Path

from tests.autodiscovery.conftest import noise_provider

from libs.autodiscovery.crypto_adapter import (
    COST_PER_SIDE,
    DEFAULT_FAMILIES,
    crypto_symbols,
    lake_provider,
    web_payload,
)
from libs.autodiscovery.models import Family
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.timeframe import Timeframe
from libs.store.connection import Database


def test_crypto_symbols_lists_only_timeframe_dirs(tmp_path: Path) -> None:
    root = tmp_path / "lake" / "bronze" / "crypto"
    for sym in ("ETHUSDT", "BTCUSDT"):
        (root / sym / "D1").mkdir(parents=True)
    (root / "NODATAUSDT").mkdir(parents=True)  # no D1 subdir -> excluded
    syms = crypto_symbols(lake_root=str(tmp_path / "lake"))
    assert syms == ["BTCUSDT", "ETHUSDT"]  # sorted, only those with D1 bars


def test_crypto_symbols_empty_when_lake_absent(tmp_path: Path) -> None:
    assert crypto_symbols(lake_root=str(tmp_path / "missing")) == []


def test_provider_returns_none_for_unknown_symbol() -> None:
    provider = lake_provider([])  # no frames cached
    assert provider("ANYTHING") is None


def test_default_families_include_crypto_native_liquidity() -> None:
    # funding_stress_reversal lives in the LIQUIDITY family -- it MUST be in the default set.
    assert Family.LIQUIDITY in DEFAULT_FAMILIES
    assert 0.0 < COST_PER_SIDE < 0.01


def test_web_payload_shape_on_noise(db: Database) -> None:
    lab = AutoDiscoveryLab(db, noise_provider(), bar=Timeframe.D1,
                          cost_provider=lambda _s: COST_PER_SIDE)
    result = lab.cycle(["AAAUSDT", "BBBUSDT"])
    payload = web_payload(lab.store, result, timeframe="D1")
    assert payload["timeframe"] == "D1"
    assert payload["cumulative_tested"] == lab.store.total()
    assert payload["cumulative_survivors"] == 0  # pure noise -> gauntlet rejects everything
    assert payload["this_cycle"]["tested"] == result.tested
    assert isinstance(payload["by_family"], dict)
    assert isinstance(payload["rejection_by_gate"], dict)
    assert payload["survivors"] == []
