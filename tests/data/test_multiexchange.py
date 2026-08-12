"""Tests for the multi-exchange data family (pure logic; network fetchers are integration-only)."""

from __future__ import annotations

import typing

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


class TestResolveOkx:
    """R0294 parts 2+3: the blind strip declares a match without verifying the underlying.

    resolve_okx() must check the instrument EXISTS, try both name forms, and refuse a
    stripped-form match whose ctVal is too small to be a re-denomination -- that is the
    1000CATUSDT -> CAT-USDT-SWAP collision, where OKX's bare CAT is a different asset."""

    # Fixture mirrors real OKX shapes: micro-caps carry re-denomination-scale ctVal,
    # majors carry sub-unit ctVal, and CAT is the name-collision trap (ordinary ctVal).
    INSTRUMENTS: typing.ClassVar[dict[str, float]] = {
        "BTC-USDT-SWAP": 0.01, "ETH-USDT-SWAP": 0.1, "1INCH-USDT-SWAP": 1.0,
        "SHIB-USDT-SWAP": 1e6, "PEPE-USDT-SWAP": 1e7, "SATS-USDT-SWAP": 1e7,
        "CAT-USDT-SWAP": 10.0,
    }

    def test_verified_matches_resolve_with_full_accounting(self) -> None:
        from libs.data.multiexchange import resolve_okx
        res = resolve_okx(["BTCUSDT", "1000SHIBUSDT", "10000SATSUSDT", "1INCHUSDT"],
                          self.INSTRUMENTS)
        assert res.resolved == {"BTCUSDT": "BTC-USDT-SWAP", "1000SHIBUSDT": "SHIB-USDT-SWAP",
                                "10000SATSUSDT": "SATS-USDT-SWAP", "1INCHUSDT": "1INCH-USDT-SWAP"}
        assert res.dropped == {}
        assert res.attempted == 4

    def test_name_collision_is_refused_not_joined(self) -> None:
        """Bare CAT exists on OKX with ctVal=10: a blind strip would join a DIFFERENT asset.
        The ctVal guard (ctVal >= ticker multiplier) must DROP it with the reason named."""
        from libs.data.multiexchange import resolve_okx
        res = resolve_okx(["1000CATUSDT"], self.INSTRUMENTS)
        assert res.resolved == {}
        assert "1000CATUSDT" in res.dropped
        assert "ctVal" in res.dropped["1000CATUSDT"]

    def test_genuine_redenomination_clears_the_ctval_guard(self) -> None:
        from libs.data.multiexchange import resolve_okx
        res = resolve_okx(["1000CATUSDT"], {"CAT-USDT-SWAP": 1000.0})
        assert res.resolved == {"1000CATUSDT": "CAT-USDT-SWAP"}

    def test_missing_instrument_is_counted_never_silent(self) -> None:
        from libs.data.multiexchange import resolve_okx
        res = resolve_okx(["NOPEUSDT", "1000GONEUSDT", "BTCBUSD"], self.INSTRUMENTS)
        assert res.resolved == {}
        assert res.attempted == 3
        assert set(res.dropped) == {"NOPEUSDT", "1000GONEUSDT", "BTCBUSD"}

    def test_attempted_always_equals_resolved_plus_dropped(self) -> None:
        from libs.data.multiexchange import resolve_okx
        syms = ["BTCUSDT", "1000SHIBUSDT", "1000CATUSDT", "NOPEUSDT", "1INCHUSDT"]
        res = resolve_okx(syms, self.INSTRUMENTS)
        assert res.attempted == len(syms) == len(res.resolved) + len(res.dropped)

    def test_strip_multiplier_returns_the_multiplier(self) -> None:
        from libs.data.multiexchange import strip_multiplier
        assert strip_multiplier("1000SHIBUSDT") == ("SHIB", 1000.0)
        assert strip_multiplier("10000SATSUSDT") == ("SATS", 10000.0)
        assert strip_multiplier("1MBABYDOGEUSDT") == ("BABYDOGE", 1e6)
        assert strip_multiplier("1000000MOGUSDT") == ("MOG", 1e6)
        assert strip_multiplier("BTCUSDT") == ("BTC", 1.0)
        assert strip_multiplier("1INCHUSDT") == ("1INCH", 1.0)
