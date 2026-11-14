"""The independent reviewer's local call limit scales with the prompt (#604/#618: a ~70k money
part timed out five times at a flat 30 min, 2 h 42 min of runner per attempt, no verdict).

Pins: the limit grows with the prompt and never drops under CALL_TIMEOUT_S; it never runs past
the job's own allowance; ask_local passes it to the HTTP call; a scaled local timeout is not
re-asked inside the same vote and ends UNAVAILABLE (never FAIL, never a vote); a remote timeout
is still retried; a size limit never changes what is read (num_ctx and the money rule stand)."""

from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "independent_review_t", ROOT / "ops/release/independent_review.py"
)
assert _spec is not None and _spec.loader is not None
ir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ir)

_PASS = (
    '{"verdict": "PASS", "risk_increasing": false, "touches_control": false, '
    '"findings": [], "summary": "ok"}'
)


def test_the_limit_grows_with_the_prompt_and_has_a_floor() -> None:
    t0 = ir._STARTED
    small = ir.local_call_timeout(3_000, now=t0)
    part = ir.local_call_timeout(ir.PART_CHARS, now=t0)
    money = ir.local_call_timeout(70_000, now=t0)
    assert small == ir.CALL_TIMEOUT_S  # never shorter than before
    assert part > ir.CALL_TIMEOUT_S
    assert money > 3 * ir.CALL_TIMEOUT_S  # #604's part gets the time it was measured to need
    need = ir.LOCAL_START_S + 60 * 70_000 / ir.LOCAL_CHARS_PER_MIN
    assert money == pytest.approx(1.5 * need)


def test_the_limit_never_runs_past_the_job() -> None:
    late = ir._STARTED + ir.JOB_S - 600
    assert ir.local_call_timeout(70_000, now=late) == pytest.approx(600)
    assert ir.local_call_timeout(70_000, now=ir._STARTED + ir.JOB_S + 5) == 60.0
    # the step's own timeout in release-gates.yml stays above JOB_S
    wf = (ROOT / ".github/workflows/release-gates.yml").read_text(encoding="utf-8")
    assert "timeout-minutes: 200" in wf and ir.JOB_S <= 200 * 60 - 5 * 60


def test_ask_local_hands_the_scaled_limit_to_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []

    def http(url: str, body: Any, h: Any) -> Any:
        seen.append(ir._CALL_TIMEOUT.get())
        return {"message": {"content": _PASS}, "prompt_eval_count": 9_000}

    monkeypatch.setattr(ir, "_http", http)
    assert ir.ask_local("http://x", "q:7b", 32768, "r" * 2_000, "u" * 60_000) == _PASS
    assert seen and seen[0] == pytest.approx(ir.local_call_timeout(62_000), rel=0.01)
    assert ir._CALL_TIMEOUT.get() == ir.CALL_TIMEOUT_S  # restored for every other caller


def test_a_local_timeout_is_exhausted_not_a_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def http(url: str, body: Any, h: Any) -> Any:
        raise ir.TimedOut("TimeoutError")

    monkeypatch.setattr(ir, "_http", http)
    with pytest.raises(ir.Exhausted):
        ir.ask_local("http://x", "q:7b", 32768, "r", "u" * 9_000)
    assert issubclass(ir.Exhausted, ir.Unavailable)


def test_an_exhausted_model_is_not_asked_again_and_the_vote_is_unavailable() -> None:
    calls: list[int] = []

    def ask(rubric: str, user: str) -> str:
        calls.append(1)
        raise ir.Exhausted("TimeoutError after 95 min, scaled to the prompt")

    slept: list[float] = []
    v, log = ir.vote(
        "DIFF-BODY",
        ["a.py"],
        [("qwen", "q:7b", ask)],
        budget_s=9 * 3600,
        sleep=slept.append,
        clock=iter(range(0, 10**6, 10)).__next__,
    )
    assert v == "UNAVAILABLE"  # queued for the controller's re-run, never quarantined
    assert len(calls) == 1 and not slept  # the old loop asked five times, ~2.5 h
    assert any("not asked again" in x for x in log)


def test_a_remote_timeout_is_still_asked_again() -> None:
    asked: list[int] = []

    def ask(rubric: str, user: str) -> str:
        asked.append(1)
        if len(asked) == 1:
            raise ir.TimedOut("TimeoutError")
        return _PASS

    v, _ = ir.vote(
        "DIFF-BODY",
        ["a.py"],
        [("qwen", "qwen/x:free", ask)],
        budget_s=10_000,
        sleep=lambda s: None,
        clock=iter(range(0, 10**6, 10)).__next__,
    )
    assert len(asked) >= 2  # a remote host's timeout is transient: asked again after a pause
    assert v in ("PASS", "UNAVAILABLE")


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("t"), urllib.error.URLError(TimeoutError("t"))],
)
def test_both_timeout_shapes_are_timed_out(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def boom(req: Any, timeout: float) -> Any:
        raise exc

    monkeypatch.setattr(ir.urllib.request, "urlopen", boom)
    with pytest.raises(ir.TimedOut):
        ir._http("http://x", {}, {})


def test_a_refused_connection_stays_plain_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(req: Any, timeout: float) -> Any:
        raise urllib.error.URLError(ConnectionRefusedError("no"))

    monkeypatch.setattr(ir.urllib.request, "urlopen", boom)
    with pytest.raises(ir.Unavailable) as got:
        ir._http("http://x", {}, {})
    assert not isinstance(got.value, ir.TimedOut)


def test_the_size_limit_changes_no_reading_rule() -> None:
    src = (ROOT / "ops/release/independent_review.py").read_text(encoding="utf-8")
    assert "PART_CHARS = 24_000" in src and '"num_ctx"' in src
    assert "every money-path file is in ONE part" in src
