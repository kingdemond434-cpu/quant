"""PROVE THE EXECUTION PATH WORKS BEFORE THE STRATEGY NEEDS IT -- 76 statements, untested.

The point of the canary is not the trade. It is discovering that keys have been revoked, the IP
whitelist has drifted, the venue changed a filter, or latency quietly tripled -- on a schedule the
desk chooses, rather than at the moment a real signal fires.

THE CRITICAL DESIGN POINT IS THE DIRECTION OF THE UNKNOWN, and it is the single thing most worth
pinning: `mode()` treats "no successful canary on record" as DEGRADED, not as healthy. A file that
has never been written, was deleted, or belongs to a fresh host must not read as a clean bill of
health. The failure mode of the opposite choice is a desk with a broken execution path believing it
is fine indefinitely -- and that belief is silent, so nothing else would ever surface it.

Three more properties, each of which is one sign flip away from inverting:

  A STALE PROBE IS ITSELF A FAULT. Overdue by 2x means the RUNNER is the suspect, not the venue.
  A canary that stopped running reads healthy under any check that only inspects its last result.

  DEGRADED WINDOWS EXTEND AND NEVER SHORTEN. A fresh failure inside an existing window must not
  hand back one that expires sooner than the one already running.

  SLOW IS FAILED. A round-trip that succeeds in 30 seconds proved the path is sick, and recording
  it as OK is how latency triples without anyone noticing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.execution import canary as C

_H = 3600.0


def _fresh(tmp_path: Path) -> C.CanaryState:
    return C.CanaryState(path=tmp_path / "canary.json")


# ------------------------------------------------------------------ the direction of the unknown

def test_NO_HISTORY_reads_DEGRADED_and_never_healthy(tmp_path: Path) -> None:
    """THE CRITICAL DESIGN POINT. A fresh host, a deleted file, a first boot -- none of them are
    evidence the execution path works, and the opposite default lets a broken desk believe it is
    fine indefinitely."""
    m = _fresh(tmp_path).mode(now=1_000.0)
    assert m.degraded is True
    assert m.limit_only is True and m.size_multiplier == C.DEGRADED_SIZE_MULT
    assert "unproven execution path" in m.reason


def test_a_MISSING_state_file_loads_to_that_same_unproven_state(tmp_path: Path) -> None:
    s = C.CanaryState.load(tmp_path / "absent.json")
    assert s.last_ok_ts is None
    assert s.mode(now=1_000.0).degraded is True


@pytest.mark.parametrize("junk", ["{not json", "[]", "null", '"text"', "7", ""])
def test_a_CORRUPT_state_file_loads_unproven_rather_than_crashing(tmp_path: Path,
                                                                  junk: str) -> None:
    """A guard that cannot start is a guard that is not running -- but it must fail toward
    DEGRADED, not toward healthy."""
    p = tmp_path / "canary.json"
    p.write_text(junk, "utf-8")
    s = C.CanaryState.load(p)
    assert s.last_ok_ts is None and s.mode(now=1_000.0).degraded is True


def test_a_non_numeric_persisted_timestamp_is_dropped_and_reads_unproven(
        tmp_path: Path) -> None:
    """A string where a float belongs must not become a truthy 'we had a success once'."""
    p = tmp_path / "canary.json"
    p.write_text(json.dumps({"last_ok_ts": "yesterday", "last_attempt_ts": "recently"}), "utf-8")
    s = C.CanaryState.load(p)
    assert s.last_ok_ts is None and s.last_attempt_ts is None
    assert s.mode(now=1_000.0).degraded is True


# ------------------------------------------------------------------ healthy

def test_a_successful_canary_restores_FULL_size_and_market_orders(tmp_path: Path) -> None:
    """The positive control: a mode that is always degraded is not a mode, and the desk would
    simply stop reading it."""
    s = _fresh(tmp_path)
    m = s.record(ok=True, latency_ms=120.0, now=1_000.0)
    assert m.degraded is False
    assert m.limit_only is False and m.size_multiplier == 1.0
    assert m.reason == "canary healthy"


def test_a_success_clears_the_consecutive_failure_count(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    s.record(ok=False, latency_ms=None, now=0.0)
    s.record(ok=False, latency_ms=None, now=100.0)
    assert s.consecutive_failures == 2
    s.record(ok=True, latency_ms=50.0, now=7 * _H)
    assert s.consecutive_failures == 0


# ------------------------------------------------------------------ slow is failed

def test_a_SLOW_round_trip_is_a_FAILURE_however_successful_it_was(tmp_path: Path) -> None:
    """It proved the path is sick. Recording it as OK is exactly how latency triples with nobody
    noticing -- the thing the canary exists to catch."""
    s = _fresh(tmp_path)
    m = s.record(ok=True, latency_ms=C.MAX_LATENCY_MS + 1, now=1_000.0)
    assert m.degraded is True
    assert s.consecutive_failures == 1
    assert s.last_ok_ts is None, "a slow round-trip must not count as a success on record"


def test_the_latency_budget_is_GENEROUS_by_design(tmp_path: Path) -> None:
    """This is a health probe, not a latency SLO. A bar tight enough to trip on ordinary venue
    jitter would degrade the desk for noise, and a rail that fires on noise gets switched off."""
    assert C.MAX_LATENCY_MS >= 1_000.0
    s = _fresh(tmp_path)
    assert s.record(ok=True, latency_ms=C.MAX_LATENCY_MS, now=1.0).degraded is False


def test_a_success_with_UNKNOWN_latency_is_not_treated_as_slow(tmp_path: Path) -> None:
    """None means the probe did not measure it, not that it was infinite. Treating it as a failure
    would degrade the desk for a missing metric on a working path."""
    s = _fresh(tmp_path)
    assert s.record(ok=True, latency_ms=None, now=1.0).degraded is False


# ------------------------------------------------------------------ the degraded window

def test_a_failure_degrades_for_the_full_window(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    s.record(ok=False, latency_ms=None, now=100.0, detail="key revoked")
    assert s.mode(100.0 + C.DEGRADED_S - 1).degraded is True
    assert s.mode(100.0 + C.DEGRADED_S + 1).degraded is False


def test_degraded_mode_is_LIMIT_ONLY_because_a_sick_path_should_not_pay_the_spread(
        tmp_path: Path) -> None:
    """If the path is sick, do not pay the spread to find out again."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    m = s.record(ok=False, latency_ms=None, now=100.0)
    assert m.limit_only is True and m.size_multiplier == C.DEGRADED_SIZE_MULT


def test_a_fresh_failure_EXTENDS_the_window_and_can_never_shorten_it(tmp_path: Path) -> None:
    """`max`, not assignment. A second failure five minutes into a six-hour window must not hand
    back a window expiring five minutes sooner than the one already running."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    s.record(ok=False, latency_ms=None, now=1_000.0)
    first_end = s.degraded_until
    s.record(ok=False, latency_ms=None, now=1_100.0)
    assert s.degraded_until >= first_end


def test_the_window_counts_from_the_LATEST_failure(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    s.record(ok=False, latency_ms=None, now=1_000.0)
    s.record(ok=False, latency_ms=None, now=1_000.0 + 5 * _H)
    assert s.degraded_until == pytest.approx(1_000.0 + 5 * _H + C.DEGRADED_S)


def test_the_reason_names_how_many_failures_and_how_long_is_left(tmp_path: Path) -> None:
    """A degraded desk with no stated cause or end time is one an operator will override."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    s.record(ok=False, latency_ms=None, now=100.0)
    s.record(ok=False, latency_ms=None, now=200.0)
    reason = s.mode(300.0).reason
    assert "2 consecutive" in reason and "more" in reason


# ------------------------------------------------------------------ staleness

def test_a_canary_that_STOPPED_RUNNING_degrades_the_desk(tmp_path: Path) -> None:
    """Overdue by 2x means the RUNNER is the suspect, not the venue. A check that only inspects
    the last RESULT reads a dead probe as perfectly healthy -- forever."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    assert s.mode(C.CANARY_INTERVAL_S * 1.5).degraded is False, "merely due is not yet stale"
    m = s.mode(C.CANARY_INTERVAL_S * C.STALE_MULTIPLE + 1)
    assert m.degraded is True
    assert "probe itself unproven" in m.reason


def test_due_and_stale_are_different_questions(tmp_path: Path) -> None:
    """Due says 'run it now'. Stale says 'the thing that runs it is broken'. Collapsing them
    either degrades the desk every six hours or never degrades it at all."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    at = C.CANARY_INTERVAL_S + 1
    assert s.is_due(at) is True and s.is_stale(at) is False
    assert s.is_stale(C.CANARY_INTERVAL_S * C.STALE_MULTIPLE + 1) is True


def test_a_never_run_canary_is_both_due_and_stale(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    assert s.is_due(0.0) is True and s.is_stale(0.0) is True


def test_an_ACTIVE_degraded_window_outranks_staleness_in_the_reason(tmp_path: Path) -> None:
    """Both are true at once after a long outage. The failure is the more actionable cause, and
    reporting the staleness instead would send an operator to check the scheduler."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    s.record(ok=False, latency_ms=None, now=100.0)
    assert "consecutive" in s.mode(200.0).reason


# ------------------------------------------------------------------ persistence

def test_the_degraded_window_SURVIVES_A_RESTART(tmp_path: Path) -> None:
    """Otherwise a crash-loop clears the degradation on every respawn, and a desk with a broken
    execution path returns to full size the moment its own guard restarts."""
    p = tmp_path / "canary.json"
    s = C.CanaryState(path=p)
    s.record(ok=True, latency_ms=10.0, now=0.0)
    s.record(ok=False, latency_ms=None, now=1_000.0)
    s.save()

    reborn = C.CanaryState.load(p)
    assert reborn.degraded_until == s.degraded_until
    assert reborn.consecutive_failures == 1
    assert reborn.mode(1_100.0).degraded is True


def test_the_state_is_written_ATOMICALLY(tmp_path: Path) -> None:
    p = tmp_path / "canary.json"
    s = C.CanaryState(path=p, last_ok_ts=5.0)
    s.save()
    assert json.loads(p.read_text("utf-8"))["last_ok_ts"] == 5.0
    assert not p.with_suffix(".json.tmp").exists()


def test_the_history_is_BOUNDED(tmp_path: Path) -> None:
    """Written every six hours forever. Unbounded, it eventually fills the disk -- and a full disk
    takes down the very execution path this probe exists to certify."""
    p = tmp_path / "canary.json"
    s = C.CanaryState(path=p)
    s.history = [{"ts": float(i), "ok": True} for i in range(500)]
    s.save()
    assert len(json.loads(p.read_text("utf-8"))["history"]) == 200


def test_every_attempt_is_recorded_with_its_detail_truncated(tmp_path: Path) -> None:
    """The detail is a venue error message. Unbounded, one verbose HTML error page per failure
    grows the state file without limit -- which is the same disk failure by another route."""
    s = _fresh(tmp_path)
    s.record(ok=False, latency_ms=None, now=1.0, detail="X" * 5_000)
    assert len(s.history) == 1
    assert len(s.history[0]["detail"]) <= 200


def test_the_recorded_ok_flag_reflects_SLOW_AS_FAILED(tmp_path: Path) -> None:
    """The history is what an audit reads later. A slow round-trip logged as ok=True would make
    the outage invisible in hindsight as well as at the time."""
    s = _fresh(tmp_path)
    s.record(ok=True, latency_ms=C.MAX_LATENCY_MS * 10, now=1.0)
    assert s.history[0]["ok"] is False
    assert s.history[0]["latency_ms"] == C.MAX_LATENCY_MS * 10


# ------------------------------------------------------------------ boundary

def test_this_module_places_no_orders() -> None:
    """It decides the MODE. The round-trip itself lives in the runner, so a logic bug here cannot
    become an order."""
    src = Path(C.__file__).read_text("utf-8")
    for banned in ("urllib", "requests", "hmac", "place_order", "new_order"):
        assert banned not in src, f"{banned} in a pure-logic canary"
