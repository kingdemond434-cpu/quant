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
