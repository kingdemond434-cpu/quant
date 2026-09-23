"""THE NO-QUEUES FENCE, tested against the law it enforces (principal 2026-09-23).

The fence's one sentence is "a queue whose oldest row is older than ONE CYCLE of the organ that
owns it is a BREACH". These tests pin that sentence and the three ways it can be evaded:
a queue with no drainer at all (PARKED), rows whose age cannot be measured (UNMEASURED, which
must FAIL -- L1.28a), and a census too old to be evidence (STALE).

tmp_path only. Nothing here writes a tracked file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str) -> ModuleType:
    """Import a repository script BY PATH.

    THIS DIRECTORY IS ITSELF A PACKAGE NAMED `scripts`, and pytest imports it as top-level
    `scripts` during collection -- before any `sys.path` line in this module can run. A plain
    `import scripts.check_no_queues` therefore resolves into the TEST package and raises
    ModuleNotFoundError. Loading by file path sidesteps the name collision entirely and pins the
    exact file the law gate runs.
    """
    path = _REPO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fence = _load("_quant_check_no_queues", "scripts/check_no_queues.py")
build_report = fence.build_report
main = fence.main


def _census(tmp: Path, queues: list[dict[str, Any]], *, at: datetime | None = None,
            rows_waiting: int = 0) -> Path:
    """Write a census artifact under a fake repo root and return that root."""
    stamp = at or datetime.now(tz=UTC)
    out = tmp / "desks" / "mt5" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "QUEUE_CENSUS.json").write_text(json.dumps({
        "at": stamp.isoformat(timespec="seconds"),
        "rule": "a row is processed on arrival",
        "queues": queues,
        "totals": {"rows_waiting": rows_waiting},
    }), "utf-8")
    return tmp


def _queue(qid: str, state: str, **kw: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": qid, "depth": kw.get("depth", 1),
                           "oldest_age_h": kw.get("oldest_age_h"),
                           "cycle_h": kw.get("cycle_h", 1.0),
                           "owner_leg": kw.get("owner_leg", "some_leg"),
                           "drainer": kw.get("drainer", "some_organ"),
                           "verdict": {"state": state, "why": kw.get("why", "because")}}
    return row


def test_clean_census_passes(tmp_path: Path) -> None:
    """Rows inside one cycle are CARRY, not a park: the fence passes and says so."""
    root = _census(tmp_path, [_queue("carry", "CLEAN", depth=4, oldest_age_h=0.4)],
                   rows_waiting=4)
    rep = build_report(root)
    assert rep["status"] == "CLEAN"
    assert rep["scanned"] == 1
    assert rep["breaches"] == [] and rep["parked"] == [] and rep["unmeasured"] == []


def test_row_older_than_one_cycle_is_a_breach(tmp_path: Path) -> None:
    """THE FENCE'S WHOLE SENTENCE. 1.5 h in a 1 h cycle is a row that survived its own drain."""
    root = _census(tmp_path, [_queue("slow", "BREACH", depth=9, oldest_age_h=1.5, cycle_h=1.0)],
                   rows_waiting=9)
    rep = build_report(root)
    assert rep["status"] == "QUEUED"
    assert [b["id"] for b in rep["breaches"]] == ["slow"]
    assert "1 with NO DRAINER" not in rep["detail"] or rep["parked"] == []


def test_a_long_cycle_is_not_a_breach_at_the_same_age(tmp_path: Path) -> None:
    """The bar is the OWNER'S cycle, not a global clock: 1.5 h against a 24 h lease is carry.

    This is the half of the rule that keeps the fence honest rather than merely strict -- a
    24-hourly organ is not in breach for holding a row for ninety minutes.
    """
    root = _census(tmp_path, [_queue("daily", "CLEAN", depth=3, oldest_age_h=1.5, cycle_h=24.0)])
    assert build_report(root)["status"] == "CLEAN"


def test_queue_with_no_drainer_is_parked_and_fails(tmp_path: Path) -> None:
    """A queue nothing drains has no cycle to measure against, which is the worst version of
    the same defect -- it is reported separately so it cannot hide inside the breach count."""
    root = _census(tmp_path, [_queue("orphan", "PARKED", depth=17749, drainer=None,
                                     owner_leg=None)], rows_waiting=17749)
    rep = build_report(root)
    assert rep["status"] == "QUEUED"
    assert [p["id"] for p in rep["parked"]] == ["orphan"]
    assert "NO DRAINER" in rep["detail"]


def test_unmeasurable_row_age_fails_it_is_never_a_pass(tmp_path: Path) -> None:
    """L1.28a: absence is never a clean verdict. 28,450 rows with no enqueue timestamp is a
    DEFECT whose fix is to stamp the rows -- a fence that passed here would make that optional
    forever."""
    root = _census(tmp_path, [_queue("no_stamps", "UNMEASURED", depth=28450, oldest_age_h=None)],
                   rows_waiting=28450)
    rep = build_report(root)
    assert rep["status"] == "QUEUED"
    assert [u["id"] for u in rep["unmeasured"]] == ["no_stamps"]


def test_stale_census_fails(tmp_path: Path) -> None:
    """A census older than the limit describes a desk that has moved on; it is not evidence."""
    old = datetime.now(tz=UTC) - timedelta(hours=9)
    root = _census(tmp_path, [_queue("fine", "CLEAN", depth=0)], at=old)
    rep = build_report(root, max_age_h=3.0)
    assert rep["status"] == "STALE"
    assert "9.0 h" in rep["detail"]


def test_absent_census_is_dark_not_clean(tmp_path: Path) -> None:
    """A gate that never ran is a claim the desk cannot cash (L1.49). Missing != empty != fine."""
    rep = build_report(tmp_path)
    assert rep["status"] == "DARK"
    assert rep["scanned"] == 0
    assert "queue_census" in rep["detail"]


def test_census_naming_no_queues_at_all_is_dark(tmp_path: Path) -> None:
    """L1.57: a passing verdict over a denominator of zero examined nothing and is a false GREEN."""
    root = _census(tmp_path, [])
    assert build_report(root)["status"] == "DARK"


@pytest.mark.parametrize("state", ["BREACH", "PARKED", "UNMEASURED"])
def test_every_failing_state_reaches_the_report(tmp_path: Path, state: str) -> None:
    root = _census(tmp_path, [_queue("q", state, depth=2, oldest_age_h=99.0)])
    rep = build_report(root)
    assert rep["status"] == "QUEUED"
    assert rep["breaches"] or rep["parked"] or rep["unmeasured"]


def test_report_only_exits_zero_while_the_gate_does_not(monkeypatch: pytest.MonkeyPatch,
                                                        tmp_path: Path,
                                                        capsys: pytest.CaptureFixture[str]
                                                        ) -> None:
    """`--report-only` is a reading mode for a session; the law gate never passes it, so the
    two exit codes must differ on the same failing census."""
    root = _census(tmp_path, [_queue("slow", "BREACH", depth=1, oldest_age_h=50.0)])
    monkeypatch.setattr(fence, "_ROOT", root)
    monkeypatch.setattr(fence, "CENSUS", root / "desks/mt5/reports/QUEUE_CENSUS.json")
    assert main(["--report-only"]) == 0
    assert main([]) != 0
    assert "BREACH" in capsys.readouterr().out


def test_the_fence_is_registered_in_the_law_gate() -> None:
    """UNWIRED OR IDLE IS A DEFECT (LAWS 7): a fence nobody runs is not a fence."""
    gate = _load("_quant_run_law_gate", "scripts/run_law_gate.py")
    assert "check_no_queues.py" in {name for name, _ in gate._STATE_FENCES}


def test_the_census_organ_has_a_clock_and_a_layer() -> None:
    """The other half of "done means wired": the artifact this fence reads must be produced by
    something on a clock, and that leg must be assigned to a layer."""
    from libs.research.layers import LEG_LAYER

    assert LEG_LAYER.get("queue_census") == "meta"
    cycle = (_REPO / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("queue_census"' in cycle
    assert '"queue_census": qcn' in cycle
