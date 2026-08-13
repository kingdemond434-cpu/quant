"""R0293: the funding-clamp table must degrade honestly -- live, then cache, then static tiers.

A CENSORED funding print read as a true extreme is a measurement error, and the label that fixes
it is only as good as the clamp it is checked against. These tests pin the three sources and the
order they are consulted in, WITHOUT any network: the live path is fed fakes, because from the
dev container every Binance host answers HTTP 451 (measured 2026-08-04) and a test that needs the
venue would be a test of the geo-block, not of the code.
"""

from __future__ import annotations

import json
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


class TestFundingIntervalCapture:
    """R0465: fundingIntervalHours rides in the SAME row as the clamp and was discarded.

    Measured against the live venue 2026-08-13: 443 symbols at 4h, 302 at 8h, 2 at 1h -- so the
    desk's hardcoded ``/ 8.0`` under-counts the majority of the universe by 2x, worst on exactly
    the high-funding alts carry selects. These pin the CAPTURE and the REFUSAL; the money-path
    switch that consumes them stays staged behind the L1.38 window.
    """

    def test_the_interval_is_kept_not_dropped(self) -> None:
        caps = fetch_live_caps(lambda url: _FUNDING_INFO)
        assert caps.interval_for("BLZUSDT") == pytest.approx(4.0)
        assert caps.interval_for("LOOMUSDT") == pytest.approx(8.0)

    def test_an_unstated_interval_refuses_rather_than_defaulting_to_8h(self) -> None:
        # The whole point: absence is UNKNOWN, not 8h. Defaulting here would re-create the 2x
        # under-count silently, which is the one failure mode this capture exists to prevent.
        caps = fetch_live_caps(lambda url: _FUNDING_INFO)
        assert caps.interval_for("BROKEN") is None
        assert caps.interval_for("NEVER-LISTED-USDT") is None

    def test_a_junk_interval_does_not_delete_that_rows_good_clamp(self) -> None:
        # Independent validity (L1.60): coupling the two fields in one try/except would let a
        # malformed interval silently drop a perfectly good cap, and vice versa.
        payload = [
            {"symbol": "AUSDT", "adjustedFundingRateCap": "0.02",
             "adjustedFundingRateFloor": "-0.02", "fundingIntervalHours": "junk"},
            {"symbol": "BUSDT", "adjustedFundingRateCap": "nope",
             "adjustedFundingRateFloor": "-0.02", "fundingIntervalHours": 4},
            {"symbol": "CUSDT", "adjustedFundingRateCap": "0.01",
             "adjustedFundingRateFloor": "-0.01", "fundingIntervalHours": 0},
        ]
        caps = fetch_live_caps(lambda url: payload)
        assert caps.caps["AUSDT"] == (0.02, -0.02)      # junk interval, clamp survives
        assert caps.interval_for("AUSDT") is None
        assert caps.interval_for("BUSDT") == pytest.approx(4.0)   # junk clamp, interval survives
        assert "BUSDT" not in caps.caps
        assert caps.interval_for("CUSDT") is None       # non-positive period is malformed

    def test_the_interval_survives_the_cache_round_trip(self, tmp_path) -> None:
        cache = tmp_path / "funding_caps.json"
        get_caps(refresh=True, cache_path=cache, get=lambda url: _FUNDING_INFO)
        again = load_cached_caps(cache)
        assert again is not None
        assert again.interval_for("BLZUSDT") == pytest.approx(4.0)

    def test_a_pre_r0465_cache_reads_as_unknown_never_as_8h(self, tmp_path) -> None:
        # A legacy cache file predates the field entirely; degrading it into a fabricated 8h
        # would be the L1.55 defect (a constant rendered as a measurement).
        cache = tmp_path / "funding_caps.json"
        cache.write_text(json.dumps({
            "fetched_at": "2026-08-01T00:00:00+00:00", "source": "live:legacy",
            "caps": {"BLZUSDT": [0.03, -0.03]},
        }), encoding="utf-8")
        legacy = load_cached_caps(cache)
        assert legacy is not None
        assert legacy.caps["BLZUSDT"] == (0.03, -0.03)
        assert legacy.interval_for("BLZUSDT") is None
