"""The E8 news fence's liveness check and missed-growth line are REACHED, not merely present.

After the merge of LIVE's rotation (`run_law_gate.rotate_gate`, #791) a source-text assertion
no longer shows the clock gets there: the box runs `run_law_gate.py --rotate`, and the daily
cycle's `missed_growth` leg calls `missed_growth.run`. Both are driven here.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

FENCE = "check_news_fence_liveness.py"


def test_the_rotation_runs_the_liveness_fence(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import run_law_gate as lg
    assert (FENCE, ()) in lg._STATE_FENCES
    assert (_ROOT / "scripts" / FENCE).exists()
    calls: list[str] = []

    def fake(root: Path, script: str, extra: tuple[str, ...], timeout: float) -> dict[str, Any]:
        calls.append(script)
        return {"fence": script, "ok": True, "rc": 0, "detail": ""}

    monkeypatch.setattr(lg, "_run_fence", fake)
    # No prior record: every fence is equally overdue, so one roomy pass reaches the whole roster.
    rep = lg.rotate_gate(tmp_path, budget_s=1e9)
    assert FENCE in calls
    assert FENCE in rep["rotation"]["ran_this_pass"] and FENCE in rep["fences"]
    assert FENCE not in rep["rotation"]["never_recorded"]


def test_it_rides_the_state_battery_not_the_laws_only_half() -> None:
    from scripts import run_law_gate as lg
    assert FENCE not in {s for s, _ in lg._LAW_FENCES}      # a STATE fence: reads the host


def test_the_producer_publishes_the_fence_line(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "E8_INTENTS", tmp_path / "e8_gold_intents.jsonl")
    monkeypatch.setattr(mg, "E8_GOLD_REPORT", tmp_path / "E8_GOLD.json")
    doc = mg.run(write=False, today="2026-11-10")
    line = doc["published_gate_lines"]["e8_news_fence"]
    assert line["verdict"] == mg.UNMEASURED and line["absent"] == ["e8_gold_intents.jsonl"]
    assert line["held"] == {"n": 0} and line["shadow"] == {"n": 0}
