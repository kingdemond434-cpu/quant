"""Supported-instrument registry for Stage 3 ingestion.

Asset class drives the trading calendar (crypto trades 24/7; FX/metals/indices close on
weekends), which in turn drives missing-bar and weekend-gap detection.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from libs.data.errors import DataError


class AssetClass(StrEnum):
    FX = "fx"
    METAL = "metal"
    INDEX = "index"
    CRYPTO = "crypto"
    ENERGY = "energy"
    EQUITY = "equity"
    SOFT = "soft"
    BOND = "bond"


# Maps an MT5 symbol-group path prefix (the first path segment) to an asset class. Used by the
# bulk history ingester to register the live broker universe without a hand-maintained catalog.
# Covers FusionMarkets and IC Markets EU group taxonomies (the two terminals seen in this env).
GROUP_TO_ASSET_CLASS: dict[str, AssetClass] = {
    "Forex": AssetClass.FX,
    "Forex Exotics": AssetClass.FX,
    "Commodities": AssetClass.METAL,
    "Energy": AssetClass.ENERGY,
    "Crypto": AssetClass.CRYPTO,
    "Indices": AssetClass.INDEX,
    "Equities": AssetClass.EQUITY,
    "Stock CFD's": AssetClass.EQUITY,
    "Soft Commodity": AssetClass.SOFT,
    "Bonds CFDs": AssetClass.BOND,
}


def asset_class_for_group(group_path: str) -> AssetClass:
    """Derive an :class:`AssetClass` from an MT5 group path; defaults to FX if unrecognized."""
    head = group_path.split("\\", 1)[0].split("/", 1)[0]
    return GROUP_TO_ASSET_CLASS.get(head, AssetClass.FX)


class InstrumentSpec(BaseModel):
    """Static metadata for a supported instrument."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    asset_class: AssetClass
    description: str

    @property
    def trades_weekends(self) -> bool:
        """Crypto trades 24/7; everything else is closed Saturday and Sunday."""
        return self.asset_class is AssetClass.CRYPTO


_SUPPORTED: dict[str, InstrumentSpec] = {
    spec.symbol: spec
    for spec in (
        InstrumentSpec(symbol="XAUUSD", asset_class=AssetClass.METAL, description="Gold"),
        InstrumentSpec(symbol="XAGUSD", asset_class=AssetClass.METAL, description="Silver"),
        InstrumentSpec(symbol="EURUSD", asset_class=AssetClass.FX, description="Euro / US Dollar"),
        InstrumentSpec(symbol="GBPUSD", asset_class=AssetClass.FX, description="Sterling / USD"),
        InstrumentSpec(symbol="USDJPY", asset_class=AssetClass.FX, description="USD / Yen"),
        InstrumentSpec(symbol="US500", asset_class=AssetClass.INDEX, description="S&P 500 CFD"),
        InstrumentSpec(symbol="NAS100", asset_class=AssetClass.INDEX, description="Nasdaq 100 CFD"),
        InstrumentSpec(symbol="BTCUSD", asset_class=AssetClass.CRYPTO, description="Bitcoin / USD"),
    )
}

SUPPORTED_SYMBOLS: tuple[str, ...] = tuple(_SUPPORTED)


def register_instrument(spec: InstrumentSpec) -> InstrumentSpec:
    """Register (or overwrite) an instrument spec at runtime and return it.

    Used by the bulk ingester to admit the live broker universe (hundreds of symbols) without a
    hand-maintained catalog. The eight built-in specs remain the deterministic default for tests.
    """
    _SUPPORTED[spec.symbol] = spec
    return spec


def get_spec(symbol: str) -> InstrumentSpec:
    """Return the spec for ``symbol`` or raise :class:`DataError`."""
    try:
        return _SUPPORTED[symbol]
    except KeyError as exc:
        raise DataError(
            f"unsupported instrument {symbol!r}; supported: {', '.join(SUPPORTED_SYMBOLS)}"
        ) from exc


def is_supported(symbol: str) -> bool:
    return symbol in _SUPPORTED
