"""THE ROTATION ENDS INSIDE ITS BUDGET, AND A BUDGET CUT IS NEVER A VERDICT (hourly pass P81).

Measured 2026-11-06 on the box: MT5-LawGate ran 1800-2027 s against --budget-s 1800 and wrote
five fences "unrunnable ... timed out". Each was started with the budget's remainder as its
timeout, killed, recorded FAILED with a fresh `ran_at`, and so sent to the BACK of the queue to be
started late again. These tests pin the cure with a fake clock and fake fences.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("run_law_gate_fit", ROOT / "scripts/run_law_gate.py")
assert _spec and _spec.loader
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)

T0 = datetime(2026, 11, 6, 1, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.t = T0


def _wire(monkeypatch, tmp_path: Path, fences: dict[str, float], prior: dict[str, dict]):
    """`fences` maps a name to the seconds it really takes; the clock advances by them."""
    clock = Clock()

    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.t

    monkeypatch.setattr(lg, "datetime", FakeDT)
    monkeypatch.setattr(lg, "_LAW_FENCES", tuple((n, ()) for n in fences))
    monkeypatch.setattr(lg, "_STATE_FENCES", ())
    calls: list[tuple[str, float]] = []

    def run(root, script, extra, timeout):
        calls.append((script, timeout))
        cost = fences[script]
        if cost > timeout:
            clock.t += timedelta(seconds=timeout)
            return {"fence": script, "ok": False,
                    "detail": f"unrunnable: Command timed out after {timeout} seconds"}
        clock.t += timedelta(seconds=cost)
        return {"fence": script, "ok": True, "rc": 0, "detail": "ok"}

    monkeypatch.setattr(lg, "_run_fence", run)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/law_gate.json").write_text(json.dumps({"fences": prior}), "utf-8")
    return clock, calls


def _row(hours_ago: float, elapsed: float, detail: str = "ok", ok: bool = True) -> dict:
    return {"ran_at": (T0 - timedelta(hours=hours_ago)).isoformat(), "elapsed_s": elapsed,
            "ok": ok, "detail": detail}


def test_a_heavy_fence_waits_and_the_cheap_ones_behind_it_finish(monkeypatch, tmp_path):
    # three 550 s fences leave 150 s; the 400 s fence (need 600 s) waits, the cheap one runs
    fences = {"a.py": 550.0, "b.py": 550.0, "c.py": 550.0, "b_heavy.py": 400.0,
              "c_cheap.py": 10.0}
    prior = {"a.py": _row(12, 400), "b.py": _row(11, 400), "c.py": _row(10, 400),
             "b_heavy.py": _row(9, 400), "c_cheap.py": _row(8, 10)}
    clock, _ = _wire(monkeypatch, tmp_path, fences, prior)
    rep = lg.rotate_gate(tmp_path, budget_s=1800.0)
    ran = rep["rotation"]["ran_this_pass"]
    assert "b_heavy.py" in rep["rotation"]["deferred_needs_more_than_left"]
    assert "c_cheap.py" in ran and "b_heavy.py" not in ran
    assert (clock.t - T0).total_seconds() <= 1800.0
    # the deferred fence keeps its old verdict and its age, so it leads the next pass
    assert rep["fences"]["b_heavy.py"]["ran_at"] == prior["b_heavy.py"]["ran_at"]


def test_a_budget_cut_is_not_written_as_a_failed_verdict(monkeypatch, tmp_path):
    """A fence with no measured need starts on the floor; cut short by the budget, it leaves
    the prior verdict standing and is owed the full bound next pass."""
    fences = {"a.py": 550.0, "b.py": 550.0, "c.py": 550.0, "b_unknown.py": 300.0}
    prior = {"a.py": _row(12, 400), "b.py": _row(11, 400), "c.py": _row(10, 400),
             "b_unknown.py": _row(9, 0, "")}
    prior["b_unknown.py"].pop("elapsed_s")
    _wire(monkeypatch, tmp_path, fences, prior)
    rep = lg.rotate_gate(tmp_path, budget_s=1800.0)
    assert rep["rotation"]["budget_truncated_no_verdict"] == ["b_unknown.py"]
    row = rep["fences"]["b_unknown.py"]
    assert row["ok"] is True and row["ran_at"] == prior["b_unknown.py"]["ran_at"]
    assert row["need_s"] == lg.ROTATION_FENCE_TIMEOUT_S
    assert lg._need_s(row) == lg.ROTATION_FENCE_TIMEOUT_S


def test_the_oldest_fence_always_gets_the_full_bound(monkeypatch, tmp_path):
    """Nothing is starved: the fence at the head of the queue runs first, with the bound."""
    fences = {"heavy.py": 550.0, "cheap.py": 5.0}
    prior = {"heavy.py": _row(20, 0, "unrunnable: Command timed out after 200 seconds", False),
             "cheap.py": _row(1, 5)}
    _, calls = _wire(monkeypatch, tmp_path, fences, prior)
    rep = lg.rotate_gate(tmp_path, budget_s=1800.0)
    assert calls[0] == ("heavy.py", lg.ROTATION_FENCE_TIMEOUT_S)
    assert rep["fences"]["heavy.py"]["ok"] is True


def test_a_real_timeout_at_the_bound_is_still_a_failed_verdict(monkeypatch, tmp_path):
    fences = {"stuck.py": 10_000.0}
    _wire(monkeypatch, tmp_path, fences, {"stuck.py": _row(5, 30)})
    rep = lg.rotate_gate(tmp_path, budget_s=1800.0)
    row = rep["fences"]["stuck.py"]
    assert row["ok"] is False and "timed out" in row["detail"]
    assert not rep["ok"]
