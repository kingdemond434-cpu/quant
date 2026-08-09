"""R0293: the funding-clamp table must degrade honestly -- live, then cache, then static tiers.

A CENSORED funding print read as a true extreme is a measurement error, and the label that fixes
it is only as good as the clamp it is checked against. These tests pin the three sources and the
order they are consulted in, WITHOUT any network: the live path is fed fakes, because from the
dev container every Binance host answers HTTP 451 (measured 2026-08-04) and a test that needs the
venue would be a test of the geo-block, not of the code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.data.funding_caps import (
    DEFAULT_CAP_MAJOR,
    DEFAULT_CAP_OTHER,
    FUNDING_INFO_MIRRORS,
    FundingCaps,
    fetch_live_caps,
    get_caps,
    load_cached_caps,
)

_FUNDING_INFO = [
    {"symbol": "BLZUSDT", "adjustedFundingRateCap": "0.03",
     "adjustedFundingRateFloor": "-0.03", "fundingIntervalHours": 4},
    {"symbol": "LOOMUSDT", "adjustedFundingRateCap": "0.02",
     "adjustedFundingRateFloor": "-0.01", "fundingIntervalHours": 8},
    {"symbol": "BROKEN", "adjustedFundingRateCap": "not-a-number"},   # skipped, not fatal
]


class TestStaticTiers:
    def test_no_cache_no_network_falls_to_the_documented_tier_table(self, tmp_path) -> None:
        caps = get_caps(refresh=False, cache_path=tmp_path / "absent.json")
        assert caps.source == "static-defaults"
        assert caps.clamp_for("BTCUSDT") == DEFAULT_CAP_MAJOR
        assert caps.clamp_for("ETHUSDT") == DEFAULT_CAP_MAJOR
        assert caps.clamp_for("DOGEUSDT") == DEFAULT_CAP_OTHER

    def test_the_tiers_are_the_documented_ones(self) -> None:
        # +/-0.75% majors, +/-1.0% common tier; the wider tier is only enumerable live, which is
        # the whole reason the refresh mechanism exists.
        assert (DEFAULT_CAP_MAJOR, DEFAULT_CAP_OTHER) == (0.0075, 0.01)


class TestLiveFetch:
    def test_the_first_answering_mirror_wins_and_parses(self) -> None:
        calls: list[str] = []

        def fake(url: str) -> object:
            calls.append(url)
            if url == FUNDING_INFO_MIRRORS[0]:
                raise RuntimeError("HTTP 451")
            return _FUNDING_INFO

        caps = fetch_live_caps(fake)
        assert calls == list(FUNDING_INFO_MIRRORS[:2])
        assert caps.source == f"live:{FUNDING_INFO_MIRRORS[1]}"
        assert caps.caps["BLZUSDT"] == (0.03, -0.03)
        assert "BROKEN" not in caps.caps

    def test_all_mirrors_refusing_names_every_verdict(self) -> None:
        def refuse(url: str) -> object:
            raise RuntimeError("HTTP 451 geo-block")

        with pytest.raises(RuntimeError) as err:
            fetch_live_caps(refuse)
        for url in FUNDING_INFO_MIRRORS:
            assert url in str(err.value), "a fallback without its reason is a wrong diagnosis"

    def test_sidedness_an_asymmetric_clamp_binds_by_the_prints_sign(self) -> None:
        caps = FundingCaps(source="test", fetched_at=None, caps={"LOOMUSDT": (0.02, -0.01)})
        assert caps.clamp_for("LOOMUSDT", +0.019) == pytest.approx(0.02)
        assert caps.clamp_for("LOOMUSDT", -0.009) == pytest.approx(0.01)


class TestCacheRoundTrip:
    def test_a_successful_refresh_writes_the_cache_a_blocked_box_reads_back(self, tmp_path) -> None:
        cache = tmp_path / "funding_caps.json"
        live = get_caps(refresh=True, cache_path=cache, get=lambda url: _FUNDING_INFO)
        assert live.source.startswith("live:") and cache.exists()

        # Same call on a box where every mirror refuses: the cached truth is used, and says so.
        def refuse(url: str) -> object:
            raise RuntimeError("HTTP 451")

        again = get_caps(refresh=True, cache_path=cache, get=refuse)
        assert again.source == f"cache:{cache.name}"
        assert again.caps["LOOMUSDT"] == (0.02, -0.01)
        assert again.fetched_at == live.fetched_at

    def test_a_corrupt_cache_degrades_to_static_not_a_crash(self, tmp_path) -> None:
        cache = tmp_path / "funding_caps.json"
        cache.write_text("{not json", encoding="utf-8")
        assert load_cached_caps(cache) is None
        caps = get_caps(refresh=False, cache_path=cache)
        assert caps.source == "static-defaults"
