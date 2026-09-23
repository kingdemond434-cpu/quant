"""The organs behind the closed-loop attestation's flags (Tier-1 B28).

THE RULE THIS FILE ENFORCES, and it is the item's whole point: a flag is driven true by fixing the
ORGAN that owns it, never by loosening the checker. So the tests here are about the producers --
does the bandit publish where its readers look, does the attestation derive rather than assert,
is `complete` generated -- and not one of them asserts a flag's value, because the flags are a
measurement of a live box and would then be a test of the box's mood.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_the_bandit_publishes_where_every_reader_looks() -> None:
    """THE DEFECT THIS CLOSED (2026-09-22). `research_bandit` wrote `data/research_budget.json`;
    `research_budget`, `research_os_archive`, `cycle_pricing`, `libs/ops/allocators`,
    `libs/ops/capability_graph` and `scripts/check_closed_loop` all read
    `reports/RESEARCH_BANDIT.json`, and NOTHING wrote it. The producer published to a path with
    no readers while the readers read a path with no producer -- so the shares reached nothing
    and the attestation read `evig_controller_authoritative` false, correctly."""
    src = (_DESK / "research" / "research_bandit.py").read_text("utf-8")
    assert 'rep = _DESK / "reports" / "RESEARCH_BANDIT.json"' in src
    assert "rep.write_text(" in src
    # And every named reader still names that path, so the two cannot silently diverge again.
    for reader, needle in (
            (_DESK / "research" / "research_budget.py",
             'DESK / "reports" / "RESEARCH_BANDIT.json"'),
            (_DESK / "research" / "cycle_pricing.py", 'R / "RESEARCH_BANDIT.json"'),
            (_ROOT / "scripts" / "check_closed_loop.py", '"RESEARCH_BANDIT.json"')):
        assert needle in reader.read_text("utf-8"), f"{reader.name} no longer reads the report"


def test_complete_is_generated_and_cannot_be_set(tmp_path: Path, monkeypatch: Any) -> None:
    """`complete` must be a conjunction over derived flags, never a field anyone writes. Driven
    through the real `measure()` with every input redirected at an empty tmp tree: with nothing
    to read, every flag is UNMEASURED and `complete` must be false -- a desk cannot declare
    itself closed by having no artifacts (L1.28a)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_closed_loop_probe", _ROOT / "scripts" / "check_closed_loop.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "ROOT", tmp_path, raising=True)
    monkeypatch.setattr(mod, "DESK", tmp_path / "desks" / "mt5", raising=True)
    monkeypatch.setattr(mod, "OUT", tmp_path / "att.json", raising=True)
    doc = mod.measure()
    assert doc["complete"] is False
    assert doc["summary"]["true"] == 0, "a flag read true off an empty tree"
    assert doc["summary"]["unmeasured"] > 0
    # The rule is stated in the artifact itself, so a reader never has to infer it.
    assert "null is UNMEASURED and never a pass" in doc["rule"]


def test_the_attestation_derives_every_flag_from_another_organs_artifact() -> None:
    """No flag may be a literal. Every one is read from a file some other organ writes, which is
    what makes the attestation a measurement instead of a self-report."""
    src = (_ROOT / "scripts" / "check_closed_loop.py").read_text("utf-8")
    assert '"complete": bool(items) and landed == len(items) and n_false == 0 and n_unm == 0' in src
    for block in ("release_authority", "truth", "forward", "research", "meta", "control_plane"):
        assert f"def {block}(" in src, f"the {block} block is not a measurement function"


def test_a_false_flag_names_the_artifact_it_waits_on(tmp_path: Path, monkeypatch: Any) -> None:
    """A flag that is false or UNMEASURED must say WHY, naming what it needs. An attestation of
    bare booleans sends the next session hunting for the organ; a `_why` beside each one is the
    difference between a report and a work queue."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_closed_loop_probe2", _ROOT / "scripts" / "check_closed_loop.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path, raising=True)
    monkeypatch.setattr(mod, "DESK", tmp_path / "desks" / "mt5", raising=True)
    monkeypatch.setattr(mod, "OUT", tmp_path / "att.json", raising=True)
    doc = mod.measure()
    for block in ("truth", "forward", "research", "meta", "control_plane"):
        whys = [k for k in doc[block] if k.endswith("_why") or k == "why"]
        assert whys, f"{block} reports flags with no reason attached"


def test_the_checker_runs_on_a_clock_and_writes_its_artifact() -> None:
    """LAWS 7. The attestation is leg `closed_loop` of the hourly cycle and its artifact path is
    the one the ledger cites."""
    hc = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("closed_loop"' in hc and "scripts/check_closed_loop.py" in hc
    src = (_ROOT / "scripts" / "check_closed_loop.py").read_text("utf-8")
    assert 'OUT = DESK / "data" / "architecture" / "closed_loop_attestation.json"' in src


def test_the_published_attestation_is_shaped_as_the_ledger_claims() -> None:
    """The artifact on this box, when it exists, carries the fields the Tier-1 row cites. Skipped
    rather than failed where the box has not run the leg: this is a shape check, not a box test."""
    p = _DESK / "data" / "architecture" / "closed_loop_attestation.json"
    if not p.exists():                                         # pragma: no cover - fresh clone
        return
    doc = json.loads(p.read_text("utf-8"))
    assert set(doc) >= {"at", "complete", "summary", "rule", "architecture_28_census"}
    assert isinstance(doc["complete"], bool)
    assert set(doc["summary"]) >= {"true", "false", "unmeasured", "open"}
