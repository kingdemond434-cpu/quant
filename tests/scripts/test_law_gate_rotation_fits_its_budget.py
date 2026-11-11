"""MT5-LawGate's rotation never judges a fence on a clock the BUDGET cut short.

Desk health, 2026-11-06 00:47Z: passes ran 1,800-2,027 s against `--budget-s 1800` and five fences
were recorded FAILED as "unrunnable ... timed out". Those verdicts were about the budget, not the
desk. The fix is an efficiency fix only: a fence starts only when the budget left covers its own
expected time, a budget-truncated run gives no verdict, and a fence that times out on the FULL
per-fence clock still FAILS. No fence is dropped and no bar moves.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import run_law_gate as lg

T0 = datetime(2026, 11, 6, 1, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.t = T0

    def now(self, tz: object = None) -> datetime:
        return self.t


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock()

    class _DT(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
            return c.t

    monkeypatch.setattr(lg, "datetime", _DT)
    return c


def _battery(monkeypatch: pytest.MonkeyPatch, names: list[str]) -> None:
    monkeypatch.setattr(lg, "_LAW_FENCES", tuple((n, ()) for n in names))
    monkeypatch.setattr(lg, "_STATE_FENCES", ())


def _prior(root: Path, rows: dict[str, tuple[float, float]]) -> None:
    """rows: name -> (hours ago it ran, elapsed_s it took)."""
    (root / "data").mkdir(exist_ok=True)
    fences = {
        n: {"fence": n, "ok": True, "ran_at": (T0 - timedelta(hours=h)).isoformat(),
            "elapsed_s": e}
        for n, (h, e) in rows.items()
    }  # fmt: skip
    (root / "data/law_gate.json").write_text(json.dumps({"fences": fences}), "utf-8")


def _fake(clock: Clock, cost: dict[str, float], calls: list[tuple[str, float]]):
    def run(root: Path, script: str, extra: tuple[str, ...], timeout: float) -> dict:
        calls.append((script, timeout))
        need = cost[script]
        if need > timeout:
            clock.t += timedelta(seconds=timeout)
            return {
                "fence": script,
                "ok": False,
                "timed_out": True,
                "timeout_s": round(timeout, 1),
                "detail": "unrunnable: timed out",
            }
        clock.t += timedelta(seconds=need)
        return {"fence": script, "ok": True, "rc": 0, "detail": "ok"}

    return run


def test_a_slow_fence_that_does_not_fit_is_deferred_not_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    _battery(monkeypatch, ["a.py", "slow.py", "c.py"])
    _prior(tmp_path, {"a.py": (5, 100), "slow.py": (4, 400), "c.py": (3, 50)})
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(lg, "_run_fence", _fake(clock, {"a.py": 100, "slow.py": 400,
                                                        "c.py": 50}, calls))  # fmt: skip
    rep = lg.rotate_gate(tmp_path, budget_s=400.0)
    assert [c[0] for c in calls] == ["a.py", "c.py"]  # slow.py needs ~510 s; 300 s were left
    assert rep["rotation"]["deferred_this_pass"] == ["slow.py"]
    assert rep["fences"]["slow.py"]["ok"] is True  # its last real verdict, with its own hour
    assert rep["fences"]["slow.py"]["ran_at"] == (T0 - timedelta(hours=4)).isoformat()
    assert rep["ok"]
    # It is the oldest now, so the next pass starts with it, on the full per-fence clock.
    (tmp_path / "data/law_gate.json").write_text(json.dumps(rep), "utf-8")
    calls.clear()
    rep2 = lg.rotate_gate(tmp_path, budget_s=1800.0)
    assert calls[0] == ("slow.py", lg.ROTATION_FENCE_TIMEOUT_S)
    assert "slow.py" in rep2["rotation"]["ran_this_pass"]


def test_a_budget_cut_run_is_no_verdict_but_a_full_clock_timeout_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    _battery(monkeypatch, ["first.py", "hang.py"])
    _prior(tmp_path, {"first.py": (5, 10), "hang.py": (4, 10)})  # hang.py looks fast
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(lg, "_run_fence", _fake(clock, {"first.py": 10, "hang.py": 10_000},
                                                calls))  # fmt: skip
    rep = lg.rotate_gate(tmp_path, budget_s=300.0)
    assert calls[1][0] == "hang.py" and calls[1][1] < lg.ROTATION_FENCE_TIMEOUT_S
    assert rep["rotation"]["deferred_this_pass"] == ["hang.py"]
    assert rep["fences"]["hang.py"]["ok"] is True  # no verdict from a clock the budget cut
    (tmp_path / "data/law_gate.json").write_text(json.dumps(rep), "utf-8")
    rep2 = lg.rotate_gate(tmp_path, budget_s=1800.0)
    row = rep2["fences"]["hang.py"]
    assert row["ok"] is False and "timed out" in row["detail"]  # full clock: FAILED, as before
    assert not rep2["ok"]


def test_the_pass_never_runs_past_its_budget_when_estimates_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    names = [f"f{i:02d}.py" for i in range(30)]
    _battery(monkeypatch, names)
    _prior(tmp_path, {n: (10 + i, 90) for i, n in enumerate(names)})
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(lg, "_run_fence", _fake(clock, dict.fromkeys(names, 90.0), calls))
    lg.rotate_gate(tmp_path, budget_s=1800.0)
    assert (clock.t - T0).total_seconds() <= 1800.0


def test_a_never_measured_fence_still_runs() -> None:
    assert lg._expected_s({}) == lg._ROTATION_FLOOR_S
    assert lg._expected_s({"elapsed_s": 10_000}) == lg.ROTATION_FENCE_TIMEOUT_S


def test_the_first_fence_gets_the_full_clock_on_every_argument_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    """Auditor SF1 on 6c98f5ff9: a multi-argument fence at the head of the queue is never cut
    by the budget on a later argument set."""
    monkeypatch.setattr(lg, "_LAW_FENCES", (("multi.py", ()), ("multi.py", ("--x",))))
    monkeypatch.setattr(lg, "_STATE_FENCES", ())
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(lg, "_run_fence", _fake(clock, {"multi.py": 500}, calls))
    rep = lg.rotate_gate(tmp_path, budget_s=700.0)
    assert [c[1] for c in calls] == [lg.ROTATION_FENCE_TIMEOUT_S] * 2
    assert rep["fences"]["multi.py"]["ok"] is True
    assert rep["fences"]["multi.py"]["n_invocations"] == 2


def test_repeated_budget_cuts_are_counted_and_then_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    """Auditor SF2 on 6c98f5ff9: a fence the budget keeps cutting is FAILED after
    ROTATION_MAX_BUDGET_CUTS passes, so the deferral can never repeat silently."""
    _battery(monkeypatch, ["head.py", "liar.py"])
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(lg, "_run_fence", _fake(clock, {"head.py": 10, "liar.py": 400}, calls))
    for n in range(1, lg.ROTATION_MAX_BUDGET_CUTS + 1):
        # liar.py claims 10 s, so it is started, then cut; head.py is always older.
        _prior(tmp_path, {"head.py": (10, 10), "liar.py": (5, 10)})
        doc = json.loads((tmp_path / "data/law_gate.json").read_text("utf-8"))
        doc["fences"]["liar.py"]["budget_cuts"] = n - 1
        (tmp_path / "data/law_gate.json").write_text(json.dumps(doc), "utf-8")
        rep = lg.rotate_gate(tmp_path, budget_s=300.0)
        row = rep["fences"]["liar.py"]
        if n < lg.ROTATION_MAX_BUDGET_CUTS:
            assert row["ok"] is True and row["budget_cuts"] == n
            assert rep["rotation"]["deferred_this_pass"] == ["liar.py"]
        else:
            assert row["ok"] is False and "cut short by the rotation budget" in row["detail"]
            assert not rep["ok"]
