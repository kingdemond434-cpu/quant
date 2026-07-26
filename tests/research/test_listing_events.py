"""The listing log must actually become event-study evidence (§33 acquired -> convertible).

The properties that decide whether this consumer is trustworthy rather than decorative: the
hypothesis stays pre-registered, incomplete windows are dropped instead of zero-filled, the
benchmark is always subtracted, and the short-side sign flip is the hypothesis rather than an
afterthought."""

from __future__ import annotations

import json

from libs.research.listing_events import (
    FUNDING_THRESHOLD,
    HOLD_HOURS,
    VARIANTS_TRIED,
    build_events,
    listing_rows,
    qualifying,
    study_listings,
)

_T0 = 1_700_000_000.0


def _row(sym: str, funding: float, ts: float = _T0) -> dict[str, object]:
    from datetime import UTC, datetime
    return {"ts": datetime.fromtimestamp(ts, tz=UTC).isoformat(), "event": "listed",
            "symbol": sym, "funding_at_detect": funding}


class TestParsing:
    def test_missing_log_is_empty_not_an_error(self, tmp_path) -> None:
        assert listing_rows(tmp_path / "nope.jsonl") == []

    def test_delistings_are_not_listings(self, tmp_path) -> None:
        p = tmp_path / "l.jsonl"
        p.write_text(json.dumps(_row("AUSDT", 0.002)) + "\n"
                     + json.dumps({"event": "delisted", "symbol": "BUSDT"}) + "\n", "utf-8")
        assert [r["symbol"] for r in listing_rows(p)] == ["AUSDT"]

    def test_a_torn_append_does_not_kill_the_study(self, tmp_path) -> None:
        # a half-written final line is normal for an appending collector killed mid-write
        p = tmp_path / "l.jsonl"
        p.write_text(json.dumps(_row("AUSDT", 0.002)) + "\n" + '{"event": "list', "utf-8")
        assert len(listing_rows(p)) == 1


class TestQualifying:
    def test_only_the_extreme_funding_regime_counts(self) -> None:
        rows = [_row("HI", FUNDING_THRESHOLD * 2), _row("LO", FUNDING_THRESHOLD / 10)]
        assert [r["symbol"] for r in qualifying(rows)] == ["HI"]

    def test_negative_funding_is_a_different_hypothesis(self) -> None:
        assert qualifying([_row("NEG", -0.005)]) == []


class TestBuildEvents:
    def test_the_short_side_is_the_hypothesis(self) -> None:
        # extreme-positive funding is a crowded long, so a FALLING price is the winning trade
        evs = build_events([_row("X", 0.002)], lambda s, t: -0.10, lambda t: 0.0)
        assert len(evs) == 1 and evs[0].ret > 0

    def test_benchmark_is_subtracted(self) -> None:
        # asset -10%, market -10% -> zero edge, not a +10% "win"
        evs = build_events([_row("X", 0.002)], lambda s, t: -0.10, lambda t: -0.10)
        assert abs(evs[0].ret) < 1e-12

    def test_incomplete_window_is_dropped_not_zero_filled(self) -> None:
        # a zero is an observation; a missing bar is not, and zero-filling would dilute the mean
        assert build_events([_row("X", 0.002)], lambda s, t: None, lambda t: 0.0) == []

    def test_missing_benchmark_drops_the_event(self) -> None:
        # without a benchmark the number is beta, so refuse rather than report it
        assert build_events([_row("X", 0.002)], lambda s, t: 0.05, lambda t: None) == []

    def test_window_length_matches_the_pre_registration(self) -> None:
        evs = build_events([_row("X", 0.002)], lambda s, t: 0.01, lambda t: 0.0)
        assert evs[0].duration_s == HOLD_HOURS * 3600.0

    def test_unparseable_timestamp_is_skipped(self) -> None:
        bad = {"ts": "not-a-time", "event": "listed", "symbol": "X", "funding_at_detect": 0.002}
        assert build_events([bad], lambda s, t: 0.01, lambda t: 0.0) == []


class TestPreRegistration:
    def test_a_thin_panel_is_refused(self) -> None:
        rows = [_row(f"S{i}", 0.002, _T0 + i * 86_400) for i in range(5)]
        evs = build_events(rows, lambda s, t: -0.05, lambda t: 0.0)
        assert study_listings(evs).passed is False

    def test_the_trial_count_is_declared_not_assumed(self) -> None:
        # the Holm bar can only be honest if every window/direction variant is counted
        assert VARIANTS_TRIED >= 1
