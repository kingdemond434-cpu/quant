"""The allocator interrupt is a REQUEST to solve sooner, and it must almost always refuse.

The fast leg is now 60s, so the baseline staleness an interrupt has to beat fell by a factor of
five and most of the case for interrupting went with it. An interrupt that fires often is just an
expensive clock. These pin every gate, and two of them are drift detectors: this module carries
copies of the supervisor's fast cadence and the allocator's turnover cost, and a copy that rots
into disagreement would size the interrupt's economics against a clock that no longer exists --
silently.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.interrupt import (  # noqa: E402
    FAST_CLOCK_S,
    MAX_PER_WINDOW,
    MIN_SPACING_S,
    MIN_UNPRICED,
    REQUEST_TTL_S,
    SUPERVISOR_HOOK,
    TURNOVER_COST_R,
    pending,
    request,
    should_fire,
)
from macro.schema import Status  # noqa: E402

NOW = 1_800_000_000.0

#: A case that passes every gate: authorised, measured, plenty unpriced, decaying inside the
#: clock, and worth far more than the turnover it would cause.
GOOD: dict[str, object] = {
    "importance": 0.7, "importance_status": Status.MEASURED, "unpriced_fraction": 0.8,
    "decay_half_life_s": 10.0, "capital_authority": True,
    "expected_gain_per_day": 5.0, "expected_turnover": 0.001,
}


def test_the_good_case_fires() -> None:
    d = should_fire(**GOOD, history=(), now=NOW)
    assert d.fire is True
    assert "exceeds the turnover cost" in d.reason


def test_no_capital_authority_never_fires() -> None:
    d = should_fire(**{**GOOD, "capital_authority": False}, history=(), now=NOW)
    assert d.fire is False and "no capital authority" in d.reason


def test_an_unmeasured_importance_never_fires() -> None:
    d = should_fire(**{**GOOD, "importance_status": Status.UNMEASURED}, history=(), now=NOW)
    assert d.fire is False and "only a MEASURED importance" in d.reason


def test_a_fully_priced_event_never_fires() -> None:
    """The whole point of the priced estimator, enforced at the last gate too."""
    d = should_fire(**{**GOOD, "unpriced_fraction": 0.0}, history=(), now=NOW)
    assert d.fire is False and "MIN_UNPRICED" in d.reason
    assert should_fire(**{**GOOD, "unpriced_fraction": None}, history=(), now=NOW).fire is False


def test_an_unmeasured_decay_rate_never_fires() -> None:
    """The justification for preempting a clock IS the decay rate. Without a measured one there
    is no case, and guessing would make the interrupt fire on vibes."""
    d = should_fire(**{**GOOD, "decay_half_life_s": None}, history=(), now=NOW)
    assert d.fire is False and "decay half-life UNMEASURED" in d.reason


def test_an_event_that_survives_the_wait_does_not_preempt_it() -> None:
    """A policy shift, a trade measure, a harvest report: a sixty-second wait is free."""
    d = should_fire(**{**GOOD, "decay_half_life_s": 3600.0}, history=(), now=NOW)
    assert d.fire is False and "HOLD" in d.reason


def test_a_move_worth_less_than_its_turnover_is_a_loss_with_extra_steps() -> None:
    d = should_fire(**{**GOOD, "expected_gain_per_day": 1e-6, "expected_turnover": 0.5},
                    history=(), now=NOW)
    assert d.fire is False
    assert "loss with extra steps" in d.reason


def test_an_unpriced_move_the_allocator_cannot_price_holds() -> None:
    d = should_fire(**{**GOOD, "expected_gain_per_day": None}, history=(), now=NOW)
    assert d.fire is False and "cannot show the move beats its own cost" in d.reason


def test_the_rate_limiter_binds() -> None:
    spaced = [NOW - 500, NOW - 400, NOW - 300]
    d = should_fire(**GOOD, history=spaced, now=NOW)
    assert d.fire is False and "rate limited" in d.reason
    assert f"max {MAX_PER_WINDOW}" in d.reason


def test_minimum_spacing_binds() -> None:
    d = should_fire(**GOOD, history=[NOW - 5], now=NOW)
    assert d.fire is False and "MIN_SPACING_S" in d.reason


def test_an_old_interrupt_falls_out_of_the_window() -> None:
    d = should_fire(**GOOD, history=[NOW - 5000, NOW - 4000, NOW - 3000], now=NOW)
    assert d.fire is True


def test_the_request_artifact_carries_evidence_and_no_direction(tmp_path: Path) -> None:
    """It says 'consider solving now'. It must not say what the answer is."""
    d = should_fire(**GOOD, history=(), now=NOW)
    payload = request(event_ids=["abc"], decision=d, importance=0.7, unpriced_fraction=0.8,
                      path=tmp_path / "req.json", log_path=tmp_path / "log.jsonl", now=NOW)
    assert payload["mode"] == "fast"
    assert payload["authority"] == "REQUEST_ONLY"
    assert payload["event_ids"] == ["abc"]
    assert payload["evidence"]["gain_at_risk"] > payload["evidence"]["turnover_cost"]
    for forbidden in ("weights", "book", "direction", "target_weight", "side", "size"):
        assert forbidden not in payload
    on_disk = json.loads((tmp_path / "req.json").read_text("utf-8"))
    assert on_disk == payload
    assert (tmp_path / "log.jsonl").read_text("utf-8").strip()


def test_a_request_is_live_then_expires(tmp_path: Path) -> None:
    d = should_fire(**GOOD, history=(), now=NOW)
    request(event_ids=["abc"], decision=d, importance=0.7, unpriced_fraction=0.8,
            path=tmp_path / "req.json", log_path=tmp_path / "log.jsonl", now=NOW)
    assert pending(tmp_path / "req.json", now=NOW + 1) is not None
    assert pending(tmp_path / "req.json", now=NOW + REQUEST_TTL_S + 1) is None


def test_a_consumed_request_is_not_served_twice(tmp_path: Path) -> None:
    d = should_fire(**GOOD, history=(), now=NOW)
    request(event_ids=["abc"], decision=d, importance=0.7, unpriced_fraction=0.8,
            path=tmp_path / "req.json", log_path=tmp_path / "log.jsonl", now=NOW)
    assert pending(tmp_path / "req.json", now=NOW + 1, consumed_at=0.0) is not None
    assert pending(tmp_path / "req.json", now=NOW + 1, consumed_at=NOW) is None


def test_a_missing_or_corrupt_request_is_None_not_an_exception(tmp_path: Path) -> None:
    """The supervisor is the desk's watchdog. It must survive anything this file does."""
    assert pending(tmp_path / "absent.json") is None
    (tmp_path / "bad.json").write_text("{half a fi", encoding="utf-8")
    assert pending(tmp_path / "bad.json") is None


# ------------------------------------------------------------------- drift detectors ----

def test_the_fast_clock_copy_matches_the_supervisor() -> None:
    """DRIFT DETECTOR. This module sizes the interrupt's economics against the supervisor's fast
    cadence. A stale copy would price the decision against a clock that no longer exists."""
    src = (_DESK / "research" / "research_supervisor.py").read_text("utf-8")
    m = re.search(r'"cadence_s":\s*\{"fast":\s*(\d+)', src)
    assert m, "could not find the allocator's fast cadence in research_supervisor.py"
    assert int(m.group(1)) == FAST_CLOCK_S, (
        f"supervisor fast leg is {m.group(1)}s but macro.interrupt.FAST_CLOCK_S is "
        f"{FAST_CLOCK_S}s -- the interrupt's economics are sized against the wrong clock")


def test_the_turnover_cost_copy_matches_the_allocator() -> None:
    """DRIFT DETECTOR. Duplicated rather than imported (importing pf_allocator pulls numpy,
    pandas and a module-level solve into a capture path that must stay light), so the
    duplication is pinned instead."""
    src = (_DESK / "research" / "pf_allocator.py").read_text("utf-8")
    m = re.search(r"^TURNOVER_COST_R\s*=\s*([0-9.]+)", src, re.M)
    assert m, "could not find TURNOVER_COST_R in pf_allocator.py"
    assert float(m.group(1)) == TURNOVER_COST_R


def test_the_supervisor_hook_is_specified_and_additive() -> None:
    """The hook is described, not applied -- the supervisor is another agent's territory. What is
    pinned is that the description keeps the properties that make it safe."""
    assert "tick_periodic" in SUPERVISOR_HOOK
    assert "_allocator_mode" in SUPERVISOR_HOOK
    assert "macro_interrupt_consumed_at" in SUPERVISOR_HOOK
    assert 'mode = "fast"' in SUPERVISOR_HOOK
    assert "additive" in SUPERVISOR_HOOK
    assert "no-trade" in SUPERVISOR_HOOK
    # It must never touch the expensive legs.
    assert '"heavy"' not in SUPERVISOR_HOOK and '"normal"' not in SUPERVISOR_HOOK


def test_the_thresholds_are_where_the_docstring_says() -> None:
    assert FAST_CLOCK_S == 60
    assert MIN_UNPRICED == 0.25
    assert MIN_SPACING_S >= FAST_CLOCK_S, (
        "spacing below the fast clock would let the interrupt fire more often than the clock it "
        "is meant to preempt")
    assert REQUEST_TTL_S <= 4 * FAST_CLOCK_S
