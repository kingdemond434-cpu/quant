"""THE PORTABLE HALF NEVER JUDGES BOX STATE (auditor ruling 2026-10-14 route 2, ordered by zuck).

The box publishes JUDGE_COVERAGE.json to origin, so every checkout holds a copy. The portable law
battery (`run_law_gate.py --laws-only`: ops/githooks/pre-push and CI) judged that copy whenever it
was under STALE_H old, so a coverage red on the box wedged every push -- against the gate's own
rule that host state is "STATE, never --laws-only". These tests pin the three properties of the
fix on ONE red, FRESH fixture:

  (a) the portable battery does not read the report and does not fail on it;
  (b) the box-side battery (--require-state, _STATE_FENCES) still fails on the same fixture;
  (c) the record the box escalates from -- `data/law_gate.json` written by the MT5-LawGate
      rotation, and the fence's own audit -- still carries the red, and the readers of that
      record still see it fire.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from scripts import run_law_gate as gate

REPO = Path(__file__).resolve().parents[2]
FENCE = "check_judge_coverage.py"
ENV = "QUANT_LAWGATE_SOURCE_VIEW"


def _load(name: str, rel: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _red(now: datetime) -> dict:
    """A fresh (well under STALE_H) report with a starved family: red on any honest reading."""
    return {"at": (now - timedelta(minutes=20)).isoformat(),
            "families": {"cross_asset_residual": {"unjudged": 5519, "queued": 0,
                                                  "judged_window": 0}},
            "totals": {"prewarm_fail_share": 0.405711, "prior_prewarm_fail_share": 0.094544}}


def _tree(tmp_path: Path) -> Path:
    """A scratch repository root holding the real fence and the one library it imports."""
    root = tmp_path / "repo"
    for rel in ("scripts/check_judge_coverage.py", "libs/__init__.py", "libs/ops/__init__.py",
                "libs/ops/fence_exit.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, root / rel)
    report = root / "desks/mt5/reports/JUDGE_COVERAGE.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps(_red(datetime.now(tz=UTC))), "utf-8")
    return root


def _registered(battery: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple:
    rows = tuple(row for row in battery if row[0] == FENCE)
    assert rows, f"{FENCE} is no longer registered in this battery"
    return rows


@pytest.fixture
def fence(monkeypatch) -> ModuleType:
    monkeypatch.delenv(ENV, raising=False)
    return _load("judge_coverage_portable_state", f"scripts/{FENCE}")


def test_the_fixture_is_red_on_an_honest_reading(tmp_path, fence):
    now = datetime.now(tz=UTC)
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps(_red(now)))
    assert fence.judge(report, now=now)["verdict"] == "FAIL"
    assert fence.judge(report, now=now, require_state=True)["verdict"] == "FAIL"


def test_a_portable_source_view_never_reads_box_state(tmp_path, fence, monkeypatch):
    """(a) unit: under the flag the laws-only battery sets, the report is not even opened."""
    now = datetime.now(tz=UTC)
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps(_red(now)))
    monkeypatch.setenv(ENV, "1")
    opened: list[Path] = []
    real = fence._read
    monkeypatch.setattr(fence, "_read", lambda p: opened.append(p) or real(p))
    doc = fence.judge(report, now=now)
    assert doc["verdict"] == "UNMEASURED"
    assert doc["why"].startswith("box state: judged by the box-side state fence")
    assert "--require-state" in doc["why"]
    assert opened == []
    assert fence._exit(doc["verdict"]) == 0


def test_require_state_binds_even_under_the_source_view_flag(tmp_path, fence, monkeypatch):
    """(b) unit: the box half judges the same red fixture in full, whatever the env says."""
    now = datetime.now(tz=UTC)
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps(_red(now)))
    monkeypatch.setenv(ENV, "1")
    doc = fence.judge(report, now=now, require_state=True)
    assert doc["verdict"] == "FAIL"
    assert {c["metric"] for c in doc["checks"] if c["state"] == "FAIL"} >= {
        "families_starved", "prewarm_fail_ratchet"}


def test_the_thresholds_are_untouched(fence):
    assert fence.STALE_H == 6.0
    assert fence.PREWARM_TOLERANCE == 0.02
    assert fence.WINDOW_SLACK == 2.0


def test_laws_only_battery_passes_on_a_fresh_red_box_report(tmp_path, monkeypatch):
    """(a) end to end: the REAL registration, run the way pre-push and CI run it."""
    monkeypatch.delenv(ENV, raising=False)
    root = _tree(tmp_path)
    before = (root / "desks/mt5/reports/JUDGE_COVERAGE.json").read_bytes()
    monkeypatch.setattr(gate, "_LAW_FENCES", _registered(gate._LAW_FENCES))
    rep = gate.full_gate(root, laws_only=True, in_place=True)
    assert rep["ok"], rep["failures"]
    assert "JUDGE_COVERAGE.json not read" in rep["results"][0]["detail"]
    assert (root / "desks/mt5/reports/JUDGE_COVERAGE.json").read_bytes() == before
    assert not (root / "desks/mt5/reports/judge_coverage_fence.json").exists()


def test_box_state_battery_still_fails_on_the_same_report(tmp_path, monkeypatch):
    """(b) end to end: the box's full battery keeps the red, on BOTH registrations."""
    monkeypatch.delenv(ENV, raising=False)
    root = _tree(tmp_path)
    assert (FENCE, ("--require-state",)) in gate._STATE_FENCES
    monkeypatch.setattr(gate, "_LAW_FENCES", _registered(gate._LAW_FENCES))
    monkeypatch.setattr(gate, "_STATE_FENCES", _registered(gate._STATE_FENCES))
    rep = gate.full_gate(root, laws_only=False)
    assert not rep["ok"]
    assert rep["n_failed"] == 2
    assert all(f.startswith(f"{FENCE} (rc=1)") for f in rep["failures"])


def test_the_box_escalation_record_still_carries_the_red(tmp_path, monkeypatch):
    """(c) the MT5-LawGate rotation (`run_law_gate.py --rotate`, install_law_gate_task.ps1) is
    what writes `data/law_gate.json` on the box; it runs every declared invocation of a fence and
    records the fence red if ANY is. Its readers -- check_fence_yield's `law_gate` RAIL and
    capability_ratchet's `law_fences_passing` -- see that red, and the fence's own audit is still
    written outside a source view."""
    monkeypatch.delenv(ENV, raising=False)
    root = _tree(tmp_path)
    monkeypatch.setattr(gate, "_LAW_FENCES", _registered(gate._LAW_FENCES))
    monkeypatch.setattr(gate, "_STATE_FENCES", _registered(gate._STATE_FENCES))
    rep = gate.rotate_gate(root, budget_s=600.0)
    row = rep["fences"][FENCE]
    assert row["ok"] is False and row["n_invocations"] == 2
    assert not rep["ok"] and any(f.startswith(FENCE) for f in rep["failures"])
    audit = json.loads((root / "desks/mt5/reports/judge_coverage_fence.json").read_text("utf-8"))
    assert audit["verdict"] == "FAIL"

    (root / "data").mkdir()
    (root / "data/law_gate.json").write_text(json.dumps(rep), "utf-8")
    yield_fence = _load("fence_yield_portable_state", "scripts/check_fence_yield.py")
    rel, key, fires, kind = yield_fence._FENCES["law_gate"]
    assert key == "ok"
    assert rel == "data/law_gate.json" and kind == "RAIL"
    assert yield_fence._observe(root)["law_gate"] in fires


# ---- the two twins found by the same audit: the gate's design text gives their state to
# ---- _STATE_FENCES, and on a clean box tree the portable battery runs in place beside it.

def test_coverage_drain_portable_half_reads_no_box_report(tmp_path, monkeypatch):
    drain = _load("coverage_drain_portable_state", "scripts/check_coverage_drain.py")
    report, ledger = tmp_path / "COVERAGE_DRAIN.json", tmp_path / "ledger.json"
    report.write_text("{not json")
    monkeypatch.setenv(ENV, "1")
    opened: list[Path] = []
    real = drain._read
    monkeypatch.setattr(drain, "_read", lambda p: opened.append(p) or real(p))
    doc = drain.judge(report=report, ledger=ledger)
    assert doc["verdict"] == "UNMEASURED" and opened == []
    assert doc["why"].startswith("box state: judged by the box-side state fence")
    assert drain.judge(report=report, ledger=ledger, require_state=True)["verdict"] == "FAIL"
    assert opened == [report]


def test_federation_live_half_is_the_box_fences_and_the_law_half_still_runs(tmp_path,
                                                                            monkeypatch):
    fed_fence = _load("federation_portable_state", "scripts/check_external_federation.py")
    state = tmp_path / "external_federation.json"
    state.write_text(json.dumps({"systems": {"rogue": {"disposition": "DIRECT",
                                                       "scheduled": True,
                                                       "authority_claimed": True}}}))
    monkeypatch.setattr(fed_fence, "STATE", state)
    monkeypatch.setattr(fed_fence, "REPORT", tmp_path / "EXTERNAL_FEDERATION.json")
    monkeypatch.delenv(ENV, raising=False)
    assert any("rogue" in p for p in fed_fence.check()["problems"])      # unchanged off-flag
    monkeypatch.setenv(ENV, "1")
    portable = fed_fence.check()
    assert portable["problems"] == [] and portable["status"] == "UNMEASURED"
    assert any(n.startswith("box state:") for n in portable["notes"])
    assert any("rogue" in p for p in fed_fence.check(require_state=True)["problems"])
    # the law-shaped half needs no state and still bites in a source view
    class _Unsafe:
        @staticmethod
        def violations() -> list[str]:
            return ["network: open"]

    monkeypatch.setattr(fed_fence.fed, "POLICY", _Unsafe())
    assert any("sandbox policy" in p for p in fed_fence.check()["problems"])
