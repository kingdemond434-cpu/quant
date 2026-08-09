"""R0243 T7 -- the free Bybit L2 archive's retention, measured instead of inferred.

The 2026-08-01 sweep INFERRED rolling retention and that inference set the row's entire urgency
("every day of delay destroys a day of free history permanently"). The probe exists to decide it,
so the tests that matter are about the two ways a decision organ lies: claiming an alarm it cannot
support, and losing the baseline the alarm is measured against.
"""
from __future__ import annotations

from datetime import date, timedelta

from scripts.probe_bybit_archive import build_report, earliest_available

TODAY = date(2026, 8, 5)


def _fake(boundary: date | None, *, dead: bool = False, dead_before: date | None = None):
    """A probe that says a file exists iff its date >= boundary. ``dead`` fails every request."""
    def probe(symbol: str, d: date) -> bool | None:
        if dead or (dead_before is not None and d < dead_before):
            return None
        return boundary is not None and d >= boundary
    return probe


class TestTheBisection:
    def test_it_finds_the_exact_first_available_day(self) -> None:
        want = date(2025, 8, 21)
        got, n = earliest_available("BTCUSDT", today=TODAY, probe=_fake(want))
        assert got == want
        assert n < 20, f"{n} requests to bisect ~2 years is not a bisection"

    def test_a_publication_lag_does_not_break_the_upper_bound(self) -> None:
        """The archive publishes T+1, and some days it may be later still. Assuming a fixed lag
        would make the bisection start from a 404 and return nonsense."""
        want = date(2025, 8, 21)

        def laggy(symbol: str, d: date) -> bool:
            return want <= d <= TODAY - timedelta(days=4)     # 3-day publication lag
        got, _ = earliest_available("BTCUSDT", today=TODAY, probe=laggy)
        assert got == want

    def test_retention_wider_than_the_lookback_is_refused_not_guessed(self) -> None:
        got, _ = earliest_available("BTCUSDT", today=TODAY, probe=_fake(date(2019, 1, 1)))
        assert got is None, "an unbounded window must not be reported as a boundary"


class TestAnUnreachableHostIsNeverAnAlarm:
    """The failure this organ must not have. A verdict about the HOST is not a verdict about the
    ARCHIVE, and folding a network drop into "file absent" moves the measured boundary FORWARD --
    which is precisely the shape of the ROLLING alarm."""

    def test_a_dead_network_reports_unreachable_not_rolling(self, tmp_path) -> None:
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY, probe=_fake(None, dead=True))
        assert rep["status"] == "UNREACHABLE"
        assert rep["symbols"]["BTCUSDT"]["status"] == "UNREACHABLE"

    def test_a_dead_network_does_not_destroy_the_stored_baseline(self, tmp_path) -> None:
        """Overwriting the prior with a null on an unreadable run silently disarms the alarm for
        every future run -- the detector-that-cannot-fire class, one indirection away."""
        import json
        (tmp_path / "data").mkdir()
        (tmp_path / "data/bybit_archive_retention.json").write_text(json.dumps(
            {"symbols": {"BTCUSDT": {"earliest": "2025-08-21", "first_seen": "2026-08-01"}}}),
            "utf-8")
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY, probe=_fake(None, dead=True))
        assert rep["symbols"]["BTCUSDT"]["earliest"] == "2025-08-21"
        assert rep["symbols"]["BTCUSDT"]["first_seen"] == "2026-08-01"

    def test_a_partial_outage_mid_bisection_is_still_unreachable(self, tmp_path) -> None:
        """The nastiest shape: recent dates answer, old ones time out. A probe that treated the
        timeout as 404 would converge on a boundary far too recent and shout ROLLING."""
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY,
                           probe=_fake(date(2025, 8, 21), dead_before=date(2026, 1, 1)))
        assert rep["status"] == "UNREACHABLE"


class TestTheVerdicts:
    def test_the_first_run_refuses_to_call_rolling_or_fixed(self, tmp_path) -> None:
        """One observation cannot distinguish a moving floor from a still one, and saying so is
        the whole difference between this and the prose inference it replaces."""
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY, probe=_fake(date(2025, 8, 21)))
        assert rep["status"] == "BASELINE"
        assert "UNDECIDABLE" in rep["detail"].upper()

    def test_an_advanced_boundary_is_ROLLING(self, tmp_path) -> None:
        import json
        (tmp_path / "data").mkdir()
        (tmp_path / "data/bybit_archive_retention.json").write_text(json.dumps(
            {"symbols": {"BTCUSDT": {"earliest": "2025-08-21"}}}), "utf-8")
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY, probe=_fake(date(2025, 8, 28)))
        assert rep["status"] == "ROLLING"
        assert "2025-08-21->2025-08-28" in rep["detail"]

    def test_an_unmoved_boundary_is_FIXED_and_says_the_span_grew(self, tmp_path) -> None:
        import json
        (tmp_path / "data").mkdir()
        (tmp_path / "data/bybit_archive_retention.json").write_text(json.dumps(
            {"symbols": {"BTCUSDT": {"earliest": "2025-08-21"}}}), "utf-8")
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY, probe=_fake(date(2025, 8, 21)))
        assert rep["status"] == "FIXED"
        assert rep["symbols"]["BTCUSDT"]["span_days"] == 349

    def test_a_boundary_that_moved_BACKWARDS_is_not_an_alarm(self, tmp_path) -> None:
        """The archive extending its history is good news and must not page anyone."""
        import json
        (tmp_path / "data").mkdir()
        (tmp_path / "data/bybit_archive_retention.json").write_text(json.dumps(
            {"symbols": {"BTCUSDT": {"earliest": "2025-08-21"}}}), "utf-8")
        rep = build_report(tmp_path, ["BTCUSDT"], today=TODAY, probe=_fake(date(2025, 1, 1)))
        assert rep["status"] != "ROLLING"
