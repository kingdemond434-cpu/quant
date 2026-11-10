"""The independent review waits long enough for a big money part, and a queued review is re-run
on its own clock (Combiner blocker, 2026-11-10). Neither changes who votes, how, or on what."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ir = _load("independent_review_t", "ops/release/independent_review.py")
rq = _load("review_requeue_t", ".github/scripts/review_requeue.py")
_PASS = json.dumps({"verdict": "PASS", "risk_increasing": False, "touches_control": False,
                    "findings": [], "summary": "ok"})  # fmt: skip


def test_a_local_call_is_sized_for_its_prompt_and_never_shorter_than_before() -> None:
    assert ir.local_timeout(3_000) == ir.CALL_TIMEOUT_S  # small: as before
    assert ir.local_timeout(90_000) == 90 * ir.LOCAL_S_PER_KCHAR  # #713's money part: 135 min
    assert ir.local_timeout(90_000) > 2 * 30 * 60  # twice the measured ~1 min per 1k characters
    # never past the budget, never zero
    assert ir.local_timeout(90_000, left=600.0) == 600.0
    assert ir.local_timeout(90_000, left=-5.0) == 1.0


def test_ask_local_uses_the_sized_timeout_and_restores_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[float] = []

    def http(url: str, body: Any, h: Any) -> Any:
        seen.append(ir._call_timeout)
        return {"message": {"content": _PASS}, "prompt_eval_count": 20_000}

    monkeypatch.setattr(ir, "_http", http)
    monkeypatch.setattr(ir, "_DEADLINE", None)
    assert ir.ask_local("http://x", "q:7b", 32768, "r" * 2_000, "u" * 78_000) == _PASS
    assert seen == [80 * ir.LOCAL_S_PER_KCHAR]
    assert ir._call_timeout == ir.CALL_TIMEOUT_S  # other calls (free API rungs) keep 30 min


def test_ask_local_never_runs_past_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ir, "_http", lambda *a: pytest.fail("asked after the budget was spent"))
    monkeypatch.setattr(ir, "_DEADLINE", ir.time.monotonic() - 1)
    with pytest.raises(ir.Unavailable):
        ir.ask_local("http://x", "q:7b", 32768, "r", "u" * 1000)
    seen: list[float] = []

    def http(url: str, body: Any, h: Any) -> Any:
        seen.append(ir._call_timeout)
        return {"message": {"content": _PASS}, "prompt_eval_count": 20_000}

    monkeypatch.setattr(ir, "_http", http)
    monkeypatch.setattr(ir, "_DEADLINE", ir.time.monotonic() + 300)
    ir.ask_local("http://x", "q:7b", 32768, "r", "u" * 80_000)
    assert 290 <= seen[0] <= 300


@pytest.mark.parametrize(
    ("raw", "minutes"),
    [("", 170), ("310", 310), ("5", 170), ("9999", 340), ("nan", 170), ("x", 170)],
)
def test_the_budget_comes_from_the_workflow_within_its_bounds(raw: str, minutes: int) -> None:
    assert ir.budget_s({"REVIEW_BUDGET_MIN": raw}) == minutes * 60


def test_the_review_job_outlives_its_budget() -> None:
    """The review ends with a verdict or REVIEW_UNAVAILABLE before GitHub kills the job: a killed
    job carries no annotation, so it would read as a FAIL instead of queued."""
    yml = (ROOT / ".github/workflows/release-gates.yml").read_text(encoding="utf-8")
    job = yml.split("\n  independent-review:\n", 1)[1]
    m_limit = re.search(r"\n    timeout-minutes: (\d+)", job)
    m_budget = re.search(r'REVIEW_BUDGET_MIN: "(\d+)"', job)
    assert m_limit is not None and m_budget is not None
    limit, budget = int(m_limit.group(1)), int(m_budget.group(1))
    assert limit <= 360 and budget * 60 <= ir.MAX_BUDGET_S
    assert limit - budget >= 30 + 5  # the serve step's own 30-minute limit, and margin
    # a re-run replays an older workflow file (200-minute job, no REVIEW_BUDGET_MIN)
    assert 200 - ir.BUDGET_S / 60 >= 30


def _hub(
    monkeypatch: pytest.MonkeyPatch,
    runs: dict[str, list[dict[str, Any]]],
    notes: dict[int, list[dict[str, Any]]],
    attempts: dict[int, int],
) -> list[str]:
    posted: list[str] = []
    pulls = [
        {"number": 713, "head": {"sha": "a" * 40, "repo": {"full_name": "o/r"}}},
        {"number": 9, "head": {"sha": "b" * 40, "repo": {"full_name": "fork/r"}}},
        {"number": 604, "head": {"sha": "c" * 40, "repo": {"full_name": "o/r"}}},
    ]

    def gh(*args: str, **kw: Any) -> Any:
        path = args[0]
        if path.startswith("repos/o/r/pulls?"):
            return [pulls]
        if "/check-runs?" in path:
            return [{"check_runs": runs.get(path.split("/commits/")[1].split("/")[0], [])}]
        if path.endswith("/annotations?per_page=100"):
            return notes.get(int(path.split("/check-runs/")[1].split("/")[0]), [])
        if path.endswith("/rerun"):
            posted.append(path)
            return None
        if "/actions/jobs/" in path:
            return {"run_attempt": attempts[int(path.rsplit("/", 1)[1])]}
        raise AssertionError(path)

    monkeypatch.setattr(rq.gate, "_gh", gh)
    return posted


def _run(i: int, done: str = "2026-11-06T04:51:20Z", **kw: Any) -> dict[str, Any]:
    return {"id": i, "name": "independent-review", "status": "completed", "conclusion": "failure",
            "started_at": "2026-11-06T02:07:56Z", "completed_at": done, **kw}  # fmt: skip


UNAV = [{"title": "REVIEW_UNAVAILABLE"}]


def test_a_queued_review_is_re_run_without_any_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    posted = _hub(monkeypatch, {"a" * 40: [_run(1)], "c" * 40: [_run(2)]},
                  {1: UNAV, 2: [{"title": "FAIL: qwen voted FAIL"}]}, {1: 2, 2: 1})  # fmt: skip
    lines = rq.sweep("o/r", genuine_for=lambda *a: lambda r: True)
    assert posted == ["repos/o/r/actions/jobs/1/rerun"]  # the real FAIL (#604 here) is not
    assert lines == [f"#713 @ {'a' * 9}: re-run requested (attempt 3)"]


def test_the_requeue_keeps_every_gate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # a forged run (not a genuine job of the workflow) is never re-run
    posted = _hub(monkeypatch, {"a" * 40: [_run(1)]}, {1: UNAV}, {1: 1})
    assert rq.sweep("o/r", genuine_for=lambda *a: lambda r: False) == [] and posted == []
    # at the attempt limit: still queued, never bypassed
    posted = _hub(monkeypatch, {"a" * 40: [_run(1)]}, {1: UNAV}, {1: rq.gate.MAX_ATTEMPTS})
    lines = rq.sweep("o/r", genuine_for=lambda *a: lambda r: True)
    assert posted == [] and "never bypassed" in lines[0]
    # too soon after the last attempt
    now = rq.gate.datetime.now(rq.gate.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    posted = _hub(monkeypatch, {"a" * 40: [_run(1, done=now)]}, {1: UNAV}, {1: 1})
    lines = rq.sweep("o/r", genuine_for=lambda *a: lambda r: True)
    assert posted == [] and "re-run due in" in lines[0]


def test_the_requeue_job_can_do_nothing_but_re_run() -> None:
    yml = (ROOT / ".github/workflows/review-requeue.yml").read_text(encoding="utf-8")
    perms = yml.split("permissions:", 1)[1].split("\n\n", 1)[0]
    assert "write" in perms and [x for x in perms.split("\n") if "write" in x] == [
        "  actions: write   # POST .../actions/jobs/{id}/rerun"
    ]
    src = (ROOT / ".github/scripts/review_requeue.py").read_text(encoding="utf-8")
    for word in ("merge", "statuses", "labels", "comments", "_status("):
        assert f"gate.{word}" not in src and f"/{word}" not in src
