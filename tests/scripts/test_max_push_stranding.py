"""DETECTION WITHOUT RANKING IS HALF A CONTROL.

The max-push queue merges every "not yet at 100%" source into one ranked list. Its dormant-
capability source reads `wiring_agent.json`, which counts scripts nothing SCHEDULES -- so it
structurally cannot see the two states an importer count never reaches (L1.54(a)): a module
IMPORTED and never called, and a module that runs while nothing reads its output.

MEASURED 2026-08-08: the stranding detector found `capital_reallocator` and `health_monitor`
imported by `run_intelligence_cycle` purely to prove they import, then reported ACTIVE without
ever being invoked. The queue could not see the finding, so the desk could discover a real gap
the same morning and still never prioritise it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import scripts.run_max_push as MP


def _cycle(rows: list[dict[str, Any]] | None, scanned: int) -> dict[str, Any]:
    report: dict[str, Any] = {"scanned": {"modules": scanned, "scripts": 0}}
    if rows is not None:
        report["imported_but_never_called"] = rows
    return {"capabilities": [{"name": "dormancy_hunter", "report": report}]}


def _with_artifact(tmp_path: Path, monkeypatch, doc: Any) -> list[dict[str, Any]]:
    """Serialise through JSON on purpose: the real source reads a file, so every value the
    function touches must survive a round trip rather than being a live Python object."""
    p = tmp_path / "intelligence_cycle.json"
    p.write_text(json.dumps(doc), "utf-8") if doc is not None else None
    monkeypatch.setattr(MP, "_json", lambda _rel: json.loads(p.read_text("utf-8"))
                        if p.exists() else None)
    return MP._from_stranding()


def test_A_CONVERSION_FAILURE_REACHES_THE_QUEUE(tmp_path, monkeypatch) -> None:
    rows = [{"path": "libs/self_improvement/capital_reallocator.py", "lines": 51},
            {"path": "libs/self_improvement/health_monitor.py", "lines": 21}]
    out = _with_artifact(tmp_path, monkeypatch, _cycle(rows, 400))
    assert len(out) == 1
    item = out[0]
    assert item["aspect"] == "capability::conversion_failures"
    assert item["measured"] is True
    assert "capital_reallocator" in item["detail"]
    assert item["gap_fraction"] > 0, "two stranded modules must produce a non-zero gap"


def test_AN_ABSENT_CYCLE_ARTIFACT_IS_UNMEASURED_NOT_ZERO(tmp_path, monkeypatch) -> None:
    """Letting an absent scan read as 'no conversion failures' is WS-005 aimed at the queue's own
    inputs -- and UNMEASURED outranks a partial number by design."""
    out = _with_artifact(tmp_path, monkeypatch, None)
    assert len(out) == 1 and out[0]["measured"] is False
    assert out[0]["gap_fraction"] == 1.0
    assert "has not run" in out[0]["detail"]


def test_A_CLEAN_SCAN_IS_AT_CEILING_NOT_ABSENT(tmp_path, monkeypatch) -> None:
    """Zero stranded modules is a real measurement and must still appear in the queue, so the
    anti-complacency escalation can count it among the aspects that ARE at their ceiling."""
    out = _with_artifact(tmp_path, monkeypatch, _cycle([], 400))
    assert len(out) == 1 and out[0]["measured"] is True
    assert out[0]["gap_fraction"] == 0.0


def test_IT_IS_SCORED_AS_DORMANT_CAPABILITY_RATHER_THAN_A_NEW_CLASS(tmp_path, monkeypatch) -> None:
    """It IS paid-for engineering returning zero. Inventing a weight would rank worse while
    looking more precise -- the module's own rule about declared-not-computed leverage."""
    out = _with_artifact(tmp_path, monkeypatch, _cycle([{"path": "x.py", "lines": 9}], 100))
    assert out[0]["source"] == "dormant_capability"
    assert out[0]["leverage"] == MP._LEVERAGE["dormant_capability"][0]


def test_THE_SOURCE_IS_ACTUALLY_IN_THE_BUILD(tmp_path) -> None:
    """A source function nobody calls is the exact defect this whole commit is about."""
    src = Path("scripts/run_max_push.py").read_text("utf-8")
    assert "+ _from_stranding())" in src or "_from_stranding()" in src.split("def build")[1]
