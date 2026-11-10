"""ARCH-31: the consolidated design is derived from the component registry, names every
contradiction class with its resolution, and renders a committed document that is never edited."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_institution_design as bid  # noqa: E402


def _s(cid: str, code: str, *, outputs: tuple[str, ...] = (), inputs: tuple[str, ...] = (),
       cadence: int | None = 3600, silence: int | None = 7200, kind: str = "leg") -> Any:
    return SimpleNamespace(component_id=cid, code_paths=(code,), outputs=outputs, inputs=inputs,
                           consumers=(), owner="department:test", cadence_s=cadence,
                           max_silence_s=silence, kind=kind, scheduled=True,
                           criticality="optional", restart_action="run_once:x",
                           progress_metric="leg_completions", resource_budget={"budget_s": 60},
                           timeout_s=60)


def test_two_organs_writing_one_path_is_contested_with_one_owner() -> None:
    specs = [_s("leg:a", "a.py", outputs=("r/X.json",)), _s("leg:b", "b.py", outputs=("r/X.json",)),
             _s("exe:a", "a.py", outputs=("r/X.json",)), _s("leg:c", "c.py", outputs=("r/Y.json",))]
    own, rows = bid.state_ownership(specs)
    assert own["contested"] == 1 and own["single_owner"] == 1
    assert rows[0]["subject"] == "r/X.json" and rows[0]["parties"] == ["a.py", "b.py"]
    assert rows[0]["owner"] and rows[0]["resolution"] == bid.RESOLUTION["CONTESTED_STATE"]


def test_a_consumer_less_patient_than_its_producer_is_stale_by_design() -> None:
    specs = [_s("leg:slow", "slow.py", outputs=("r/S.json",), cadence=86400),
             _s("exe:fast", "fast.py", inputs=("r/S.json",), cadence=300, silence=600),
             _s("exe:ok", "ok.py", inputs=("r/S.json",), cadence=3600, silence=200000)]
    tim, rows = bid.timing(specs)
    assert [r["subject"] for r in rows] == ["exe:fast"]
    assert rows[0]["producer_cadence_s"] == 86400 and tim["stale_by_design"] == 1


def test_budget_below_floor_and_dead_budgets_are_named(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "hourly_cycle.py"
    src.write_text('LEG_BUDGET_SEC: dict[str, int] = {\n    "a": 60,\n    "ghost": 1_000,\n}\n'
                   'LEG_BUDGET_FLOOR_SEC: dict[str, int] = {\n    "a": 300,\n}\n'
                   'x = _costed("a", lambda: 1)\n')
    monkeypatch.setattr(bid, "HOURLY", src)
    _, rows = bid.budgets([])
    got = {(r["class"], r["subject"]) for r in rows}
    assert got == {("BUDGET_BELOW_FLOOR", "a"), ("DEAD_BUDGET", "ghost")}


def test_opposite_metric_directions_are_a_contradiction(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps({"legs": {
        "a": {"metric": {"organ": "report:X.json", "metric": "n", "better": "up"}},
        "b": {"metric": {"organ": "report:X.json", "metric": "n", "better": "down"}},
        "c": {"metric": {"organ": "report:Y.json", "metric": "n", "better": "up"}}}}))
    monkeypatch.setattr(bid, "CONTRACTS", c)
    rows = bid.contract_directions()
    assert len(rows) == 1 and rows[0]["parties"] == {"down": ["b"], "up": ["a"]}


def test_the_real_tree_builds_and_every_class_has_a_resolution() -> None:
    doc = bid.build()
    assert doc["interfaces"]["components"] > 500
    for k in ("interfaces", "timing", "state_ownership", "resource_budgets",
              "failure_and_uncertainty", "contradictions"):
        assert k in doc
    for r in doc["contradictions"]["rows"]:
        assert r["class"] in bid.RESOLUTION and r["resolution"]
    md = bid.render(doc)
    for h in ("## Interfaces", "## Timing", "## State ownership", "## Uncertainty",
              "## Failure handling", "## Resource budgets",
              "## Contradictions and how each is resolved"):
        assert h in md


def test_the_committed_design_is_derived_not_hand_written() -> None:
    text = (ROOT / "docs" / "research" / "INSTITUTION_DESIGN.md").read_text("utf-8")
    assert text.startswith("# Institution design (derived)")
    assert "Never edit this file" in text
    assert "/home/" not in text and "C:\\\\" not in text
