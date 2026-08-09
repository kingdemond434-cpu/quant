"""Tests for the multi-exchange data family (pure logic; network fetchers are integration-only)."""

from __future__ import annotations

from libs.data.multiexchange import okx_inst


def test_okx_inst_mapping() -> None:
    assert okx_inst("BTCUSDT") == "BTC-USDT-SWAP"
    assert okx_inst("ETHUSDT") == "ETH-USDT-SWAP"
    # CORRECTED 2026-08-04 (R0294/L0061): this line used to assert 1000PEPE-USDT-SWAP, an
    # instrument that does not exist on OKX -- the test was pinning the coverage defect. OKX
    # carries the bare name and puts the 1000x in ctVal; funding is a rate, so no rescaling.
    assert okx_inst("1000PEPEUSDT") == "PEPE-USDT-SWAP"


class TestOkxInstRedenomination:
    """L0061, graduated: the 1000-prefix lives in Binance's TICKER and OKX's CONTRACT SIZE.

    A literal join MISSES the asset (coverage loss), it does not mismatch it (corruption) --
    funding is a rate, so stripping the prefix needs no value rescaling. R0294: the literal
    mapping resolved 260/653 and dropped SHIB/PEPE/FLOKI/BONK/SATS."""

    def test_redenominated_tickers_resolve_to_the_bare_okx_name(self) -> None:
        from libs.data.multiexchange import okx_inst
        assert okx_inst("1000SHIBUSDT") == "SHIB-USDT-SWAP"
        assert okx_inst("1000PEPEUSDT") == "PEPE-USDT-SWAP"
        assert okx_inst("10000SATSUSDT") == "SATS-USDT-SWAP"
        assert okx_inst("1000000MOGUSDT") == "MOG-USDT-SWAP"
        assert okx_inst("1MBABYDOGEUSDT") == "BABYDOGE-USDT-SWAP"

    def test_plain_tickers_are_untouched(self) -> None:
        from libs.data.multiexchange import okx_inst
        assert okx_inst("BTCUSDT") == "BTC-USDT-SWAP"
        assert okx_inst("ETHUSDT") == "ETH-USDT-SWAP"

    def test_a_numeric_base_is_not_mistaken_for_a_prefix(self) -> None:
        """1INCH starts with a digit; stripping '1' would invent a nonexistent INCH ticker.
        The guard is that the character AFTER the prefix must not be a digit -- so 1000...
        prefixes strip only when they are prefixes, never when they are the name."""
        from libs.data.multiexchange import okx_inst
        assert okx_inst("1INCHUSDT") == "1INCH-USDT-SWAP"
