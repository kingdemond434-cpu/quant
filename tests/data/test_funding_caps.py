"""R0293: the funding-clamp table must degrade honestly -- live, then cache, then static tiers.

A CENSORED funding print read as a true extreme is a measurement error, and the label that fixes
it is only as good as the clamp it is checked against. These tests pin the three sources and the
order they are consulted in, WITHOUT any network: the live path is fed fakes, because from the
dev container every Binance host answers HTTP 451 (measured 2026-08-04) and a test that needs the
venue would be a test of the geo-block, not of the code.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
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
    venue_intervals,
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


class TestFundingIntervalIsCaptured:
    """R0465. `fundingIntervalHours` rides in the payload this module already fetches daily and
    was discarded at parse time, so `held / 8.0` under-counted the 426 of 812 live perps that
    settle 4-hourly. The interval is now carried; absence of it stays UNKNOWN, never 8h.
    """

    def test_the_interval_survives_the_parse(self) -> None:
        caps = fetch_live_caps(lambda url: _FUNDING_INFO)
        assert caps.interval_for("BLZUSDT") == 4.0, "the 4h majority case must not read as 8h"
        assert caps.interval_for("LOOMUSDT") == 8.0

    def test_a_symbol_the_venue_did_not_describe_is_UNKNOWN_not_eight(self) -> None:
        # The whole defect in one assertion: 8.0 here would be a fabricated measurement, and
        # downstream it is indistinguishable from a real one (L1.55/L1.28a).
        caps = fetch_live_caps(lambda url: _FUNDING_INFO)
        assert caps.interval_for("BROKEN") is None
        assert caps.interval_for("NEVERLISTEDUSDT") is None
        assert FundingCaps(source="t", fetched_at=None).interval_for("BTCUSDT") is None

    def test_a_row_with_malformed_caps_still_yields_its_interval(self) -> None:
        # Collected independently: either field's absence must not silently delete the other.
        caps = fetch_live_caps(lambda url: [
            {"symbol": "ODDUSDT", "adjustedFundingRateCap": "not-a-number",
             "fundingIntervalHours": 4},
        ])
        assert "ODDUSDT" not in caps.caps
        assert caps.interval_for("ODDUSDT") == 4.0

    def test_a_zero_or_negative_interval_is_treated_as_unsaid(self) -> None:
        caps = fetch_live_caps(lambda url: [
            {"symbol": "ZUSDT", "adjustedFundingRateCap": "0.02",
             "adjustedFundingRateFloor": "-0.02", "fundingIntervalHours": 0},
        ])
        assert caps.caps["ZUSDT"] == (0.02, -0.02)
        assert caps.interval_for("ZUSDT") is None

    def test_the_interval_survives_the_cache_round_trip(self, tmp_path) -> None:
        cache = tmp_path / "funding_caps.json"
        get_caps(refresh=True, cache_path=cache, get=lambda url: _FUNDING_INFO)

        def refuse(url: str) -> object:
            raise RuntimeError("HTTP 451")

        again = get_caps(refresh=True, cache_path=cache, get=refuse)
        assert again.source.startswith("cache:")
        assert again.interval_for("BLZUSDT") == 4.0, "a blocked box must still know the cadence"

    def test_a_pre_R0465_cache_reads_as_unknown_not_as_eight(self, tmp_path) -> None:
        # The artifact on disk today has no `intervals` key. Caps must still load (no regression)
        # and every cadence must read UNKNOWN until the next live fetch repopulates it.
        cache = tmp_path / "funding_caps.json"
        cache.write_text('{"fetched_at": "2026-08-13T03:24:49Z", "source": "live:x",'
                         ' "caps": {"BLZUSDT": [0.03, -0.03]}}', encoding="utf-8")
        got = load_cached_caps(cache)
        assert got is not None
        assert got.caps["BLZUSDT"] == (0.03, -0.03)
        assert got.interval_for("BLZUSDT") is None

    def test_venue_intervals_feeds_the_clock_that_had_no_producer(self, tmp_path) -> None:
        # L1.49: funding_clock.interval_hours took a dict nothing in the repo ever built, so its
        # refusal branch was the only one that had ever run. This is the missing caller.
        from libs.research.funding_clock import interval_hours, settlements_in

        cache = tmp_path / "funding_caps.json"
        get_caps(refresh=True, cache_path=cache, get=lambda url: _FUNDING_INFO)
        mapping = venue_intervals(cache_path=cache)
        assert mapping == {"BLZUSDT": 4.0, "LOOMUSDT": 8.0}
        assert interval_hours("BLZUSDT", mapping) == 4.0
        assert interval_hours("NEVERLISTEDUSDT", mapping) is None

        # And the payoff the row is actually about: a 24h hold on a 4h symbol earns SIX
        # settlements, not the three the hardcoded /8.0 books.
        t0 = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
        assert settlements_in(t0, t1, interval_h=8.0) == 3
        assert settlements_in(t0, t1, interval_h=interval_hours("BLZUSDT", mapping)) == 6
