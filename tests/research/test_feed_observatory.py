"""The observatory on planted feeds: a stale feed lowers health, a lag the clocks cannot resolve
is refused, an edge that lives inside the timing noise is TIMING_FRAGILE, and every absence
comes back UNMEASURED rather than as a number."""
from __future__ import annotations

import numpy as np

from libs.research import feed_observatory as fo


def _clock(name: str, *, offset: float = 30_000.0, jitter: float = 20_000.0,
           stale: float = 0.0, in_session: bool = True, **kw: float) -> fo.FeedClock:
    base = {"inversion_rate": 0.0, "drop_prob": 0.01, "p_latency_ok": 0.95,
            "reference_ok": 1.0}
    base.update(kw)
    return fo.FeedClock(instrument=name, n=1000, offset_ms=offset, jitter_ms=jitter,
                        stale_prob=stale, in_session=in_session, **base)


def test_a_planted_stale_feed_lowers_health_and_is_named_worst() -> None:
    gaps = np.full(500, 1000.0)                      # a feed that ticks every second
    assert fo.staleness_probability(gaps, 500.0) == 0.0      # half a second old: not due yet
    assert fo.staleness_probability(gaps, 5_000.0) == 1.0    # five seconds old: overdue
    assert fo.staleness_probability(gaps[:5], 5_000.0) is None
    fresh = _clock("EURUSD", stale=fo.staleness_probability(gaps, 500.0) or 0.0)
    stale = _clock("GBPUSD", stale=fo.staleness_probability(gaps, 5_000.0) or 0.0)
    healthy = fo.feed_health(0.0, {"EURUSD": fresh})
    mixed = fo.feed_health(0.0, {"EURUSD": fresh, "GBPUSD": stale})
    assert healthy["status"] == "MEASURED"
    assert healthy["p_market_trustworthy"] is not None
    assert mixed["p_market_trustworthy"] < healthy["p_market_trustworthy"]
    assert mixed["worst_feed"]["instrument"] == "GBPUSD"
    assert mixed["feeds"]["GBPUSD"]["components"]["freshness"] == 0.0


def test_a_closed_feed_is_excluded_not_scored_zero_and_no_feed_is_unmeasured() -> None:
    closed = _clock("AUS200", in_session=False)
    doc = fo.feed_health(0.0, {"AUS200": closed, "EURUSD": _clock("EURUSD")})
    assert doc["feeds"]["AUS200"]["status"] == "CLOSED"
    assert doc["feeds"]["AUS200"]["p_trustworthy"] is None
    assert doc["n_closed"] == 1 and doc["n_in_session"] == 1
    assert doc["p_market_trustworthy"] == doc["feeds"]["EURUSD"]["p_trustworthy"]
    nothing = fo.feed_health(0.0, {"X": fo.FeedClock(instrument="X", n=0)})
    assert nothing["status"] == "UNMEASURED" and nothing["p_market_trustworthy"] is None
    assert nothing["feeds"]["X"]["unmeasured_components"] == [
        "completeness", "continuity", "freshness", "latency", "reference"]


def test_latency_distribution_keeps_negatives_and_reports_offset_and_jitter() -> None:
    venue = np.arange(0, 100_000, 100, dtype=float)
    local = venue + np.where(np.arange(venue.size) % 10 == 0, -50.0, 30_000.0)
    lat = fo.latency_distribution(venue, local)
    assert lat["status"] == "MEASURED" and lat["n"] == venue.size
    assert lat["n_negative"] == venue.size // 10
    assert lat["offset_ms"] == 30_000.0 and lat["jitter_ms"] == 0.0
    assert fo.latency_distribution([], [])["status"] == "UNMEASURED"


def test_sequence_continuity_counts_inversions_duplicates_and_dropped_numbers() -> None:
    seq = [1, 2, 3, 3, 5, 4, 9]
    got = fo.sequence_continuity(seq, integer_sequence=True)
    assert got["inversions"] == 1 and got["duplicates"] == 1
    assert got["dropped"] == 1 + 4                    # 3->5 lost one, 4->9 lost four
    stamps = fo.sequence_continuity([10.0, 20.0, 15.0])
    assert stamps["dropped"] is None and "UNMEASURED" in stamps["drop_basis"]
    assert fo.sequence_continuity([1.0])["status"] == "UNMEASURED"


def test_burst_rate_is_the_named_drop_proxy() -> None:
    gaps = np.r_[np.full(95, 100.0), np.full(5, 5_000.0)]
    got = fo.burst_rate(gaps)
    assert got["status"] == "MEASURED" and got["bursts"] == 5 and got["rate"] == 0.05
    assert "PROXY" in got["basis"]
    assert fo.burst_rate(gaps[:10])["status"] == "UNMEASURED"


def test_propagation_graph_refuses_a_lag_below_the_clocks_joint_resolution() -> None:
    a = _clock("XAUUSD", offset=30_000.0, jitter=25_000.0)
    b = _clock("XAGUSD", offset=0.0, jitter=500.0)
    assert fo.min_admissible_lag_ms(a, b) == 55_500.0
    ok, why = fo.admissible(a, b, 5_000.0)
    assert not ok and "REFUSED" in why
    ok, _ = fo.admissible(a, b, 60_000.0)
    assert ok
    graph = fo.propagation_graph({"XAUUSD": a, "XAGUSD": b}, lags_ms=(1_000.0, 60_000.0))
    assert graph["n_edges"] == 4 and graph["n_admissible"] == 2 and graph["n_refused"] == 2
    assert graph["n_resolution_admissible"] == 2
    refused = [e for e in graph["edges"] if not e["admissible"]]
    assert all(e["lag_ms"] == 1_000.0 for e in refused)
    # A pair no candidate lag can resolve is a FINDING, listed by name.
    slow = _clock("US30", offset=0.0, jitter=10_000_000.0)
    graph = fo.propagation_graph({"XAUUSD": a, "US30": slow}, lags_ms=(1_000.0,))
    assert graph["n_admissible"] == 0 and len(graph["unresolvable_pairs"]) == 2


def test_an_unmeasured_or_closed_clock_admits_no_ordering() -> None:
    a = _clock("XAUUSD")
    unknown = fo.FeedClock(instrument="BRENT", n=10)
    ok, why = fo.admissible(a, unknown, 900_000.0)
    assert not ok and "UNMEASURED" in why
    closed = _clock("AUS200", in_session=False)
    ok, why = fo.admissible(a, closed, 900_000.0)
    assert not ok and "out of session" in why
    assert fo.propagation_graph({"XAUUSD": a, "AUS200": closed}, lags_ms=(900_000.0,))[
        "n_resolution_admissible"] == 2          # the clocks could; the session cannot


def test_reference_consistency_finds_the_clock_offset_inside_the_span() -> None:
    t = np.arange(0, 3_600_000 * 48, 60_000, dtype=float)            # a minute series
    price = 100.0 + np.cumsum(np.sin(np.arange(t.size) / 7.0)) * 0.01
    # The same instrument viewed on a clock three hours AHEAD: stamped later, same prices.
    ahead_t = t[::60] + 3 * 3_600_000.0
    ahead_v = price[::60]
    got = fo.reference_consistency(ahead_t, ahead_v, t, price,
                                   lags_ms=[h * 3_600_000.0 for h in (-4, -3, -2, 0, 2, 3)])
    assert got["status"] == "MEASURED"
    assert got["best_lag_ms"] == -3 * 3_600_000.0
    assert got["median_abs_bps_at_best"] == 0.0
    # No pair may be matched beyond the reference's last observation (a stale match).
    for row in got["lags"]:
        if row["status"] == "MEASURED":
            assert row["n"] <= sum(1 for x in ahead_t if x + row["lag_ms"] <= t[-1])
    assert fo.reference_consistency([], [], t, price)["status"] == "UNMEASURED"


def test_implied_time_is_the_stalest_leg_and_stamp_coverage_names_absent_clocks() -> None:
    assert fo.implied_time([1.0, 5.0, 3.0]) == 5.0
    assert fo.implied_time([1.0, None]) is None
    cov = fo.stamp_coverage([fo.FeedStamp(exchange_ms=1.0, local_ms=2.0),
                             fo.FeedStamp(exchange_ms=3.0)])
    assert cov["exchange"]["n"] == 2 and cov["local_receipt"]["n"] == 1
    assert cov["source_event"]["status"] == "UNMEASURED"
    assert cov["vendor_receipt"]["status"] == "UNMEASURED"


def _returns(n: int, block: int, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float) * 1_000.0                             # one-second targets
    drift = np.repeat(rng.choice([-1.0, 1.0], size=n // block + 1), block)[:n]
    return t, drift * 0.001 + rng.normal(0.0, 0.0002, size=n)


def test_a_fast_edge_is_timing_fragile_and_a_slow_one_is_robust() -> None:
    t, r = _returns(3_000, block=1)                    # the edge lives inside one second
    fast = fo.timing_fragility(list(zip(t, np.sign(r), strict=True)),
                               list(zip(t, r, strict=True)),
                               fo.TimingNoise(jitter_ms=5_000.0), draws=16)
    assert fast["verdict"] == "TIMING_FRAGILE"
    assert fast["retained_at_measured_noise"] < fo.SURVIVAL_FRACTION
    assert fast["margin_multiplier"] == 0.0
    t, r = _returns(3_000, block=600)                  # a ten-minute drift regime
    slow = fo.timing_fragility(list(zip(t, np.sign(r), strict=True)),
                               list(zip(t, r, strict=True)),
                               fo.TimingNoise(jitter_ms=5_000.0), draws=16)
    assert slow["verdict"] == "TIMING_ROBUST"
    assert slow["retained_at_measured_noise"] >= fo.SURVIVAL_FRACTION
    assert slow["margin_multiplier"] >= 1.0
    assert [row["multiplier"] for row in slow["ladder"]] == [1.0, 10.0, 100.0]


def test_fragility_is_unmeasured_below_the_sample_floor_and_on_a_zero_edge() -> None:
    t, r = _returns(20, block=1)
    got = fo.timing_fragility(list(zip(t, np.sign(r), strict=True)),
                              list(zip(t, r, strict=True)), fo.TimingNoise())
    assert got["verdict"] == "UNMEASURED" and "fewer than" in got["why"]
    t, r = _returns(500, block=1)
    flat = fo.timing_fragility([(x, 1.0) for x in t], [(x, 0.0) for x in t], fo.TimingNoise())
    assert flat["verdict"] == "UNMEASURED"


def test_corrupt_timing_only_delays_drops_stales_and_swaps() -> None:
    rng = np.random.default_rng(1)
    t = np.arange(100, dtype=float) * 1_000.0
    v = np.arange(100, dtype=float)
    ct, cv = fo.corrupt_timing(t, v, fo.TimingNoise(jitter_ms=50.0), rng)
    assert ct.size == 100 and np.all(ct >= t)          # receipt is never early
    ct, cv = fo.corrupt_timing(t, v, fo.TimingNoise(drop_prob=0.5), rng)
    assert 0 < ct.size < 100
    ct, cv = fo.corrupt_timing(t, v, fo.TimingNoise(stale_prob=1.0), rng)
    assert cv[0] == 0.0 and np.all(cv[1:] == v[:-1])   # every value repeats its predecessor
    ct, cv = fo.corrupt_timing(t, v, fo.TimingNoise(inversion_prob=1.0), rng)
    assert not np.all(np.diff(ct) > 0)
    scaled = fo.TimingNoise(jitter_ms=1.0, drop_prob=0.2).scaled(10.0)
    assert scaled.jitter_ms == 10.0 and scaled.drop_prob == 0.95   # capped, never certain
