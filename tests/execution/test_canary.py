"""§5 canary. The test that matters most is the one asserting UNKNOWN reads as degraded: a
deleted state file, a fresh host, or a probe that has never run must never look healthy."""

from __future__ import annotations

from libs.execution.canary import (
    CANARY_INTERVAL_S,
    DEGRADED_S,
    MAX_LATENCY_MS,
    CanaryState,
)


class TestDueness:
    def test_a_never_run_canary_is_due(self, tmp_path) -> None:
        assert CanaryState.load(tmp_path / "c.json").is_due(now=0.0)

    def test_not_due_inside_the_window(self, tmp_path) -> None:
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=100.0, now=0.0)
        assert not s.is_due(now=CANARY_INTERVAL_S - 1)

    def test_due_after_the_window(self, tmp_path) -> None:
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=100.0, now=0.0)
        assert s.is_due(now=CANARY_INTERVAL_S + 1)


class TestUnknownIsDegraded:
    def test_no_history_at_all_is_degraded(self, tmp_path) -> None:
        m = CanaryState.load(tmp_path / "c.json").mode(now=0.0)
        assert m.degraded and m.limit_only and m.size_multiplier == 0.5

    def test_a_corrupt_state_file_is_degraded_not_healthy(self, tmp_path) -> None:
        p = tmp_path / "c.json"
        p.write_text("{ this is not json", "utf-8")
        assert CanaryState.load(p).mode(now=0.0).degraded

    def test_a_long_silent_probe_is_degraded(self, tmp_path) -> None:
        """Success six hours ago plus a runner that has since died must not read as healthy."""
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=10.0, now=0.0)
        assert not s.mode(now=CANARY_INTERVAL_S).degraded
        assert s.mode(now=CANARY_INTERVAL_S * 2 + 1).degraded


class TestFailureDegradesForSixHours:
    def test_a_failure_degrades(self, tmp_path) -> None:
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=10.0, now=0.0)
        m = s.record(ok=False, latency_ms=None, now=100.0)
        assert m.limit_only and m.size_multiplier == 0.5

    def test_degradation_expires_after_six_hours(self, tmp_path) -> None:
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=10.0, now=0.0)
        s.record(ok=False, latency_ms=None, now=100.0)
        s.record(ok=True, latency_ms=10.0, now=100.0 + DEGRADED_S + 1)
        assert not s.mode(now=100.0 + DEGRADED_S + 2).degraded

    def test_excess_latency_counts_as_failure(self, tmp_path) -> None:
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=10.0, now=0.0)
        m = s.record(ok=True, latency_ms=MAX_LATENCY_MS + 1, now=100.0)
        assert m.limit_only

    def test_a_fresh_failure_never_shortens_an_existing_window(self, tmp_path) -> None:
        """Two failures an hour apart must leave the LATER expiry standing -- taking the newer
        window unconditionally would let repeated failures shorten the penalty."""
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=True, latency_ms=10.0, now=0.0)
        s.record(ok=False, latency_ms=None, now=10_000.0)
        first_expiry = s.degraded_until
        s.degraded_until = first_expiry + 99_999.0        # a longer window from elsewhere
        s.record(ok=False, latency_ms=None, now=10_100.0)
        assert s.degraded_until == first_expiry + 99_999.0

    def test_consecutive_failures_accumulate_and_reset(self, tmp_path) -> None:
        s = CanaryState.load(tmp_path / "c.json")
        s.record(ok=False, latency_ms=None, now=0.0)
        s.record(ok=False, latency_ms=None, now=1.0)
        assert s.consecutive_failures == 2
        s.record(ok=True, latency_ms=10.0, now=2.0)
        assert s.consecutive_failures == 0


class TestPersistence:
    def test_state_round_trips(self, tmp_path) -> None:
        p = tmp_path / "c.json"
        s = CanaryState.load(p)
        s.record(ok=False, latency_ms=42.0, now=500.0)
        s.save()
        r = CanaryState.load(p)
        assert r.consecutive_failures == 1
        assert r.degraded_until == s.degraded_until
        assert r.mode(now=501.0).degraded
