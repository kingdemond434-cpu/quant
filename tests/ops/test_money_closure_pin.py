"""The reviewer's money closure list covers the box entry points' real import closure (#547).

A RISK SUITE (ops/release/risk_suites.txt): risk-invariants runs the BASE copy of this file
against the PR's tree, so a PR that grows the closure cannot also skip or weaken the pin that
makes it carry the new rows (#547 audit v4 MF-C)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops/release" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_committed_money_closure_covers_the_box_entry_points_import_closure() -> None:
    ir, rs = _load("independent_review"), _load("replay_shadow")
    rows = ir.closure_rows((ROOT / ir.CLOSURE_FILE).read_text(encoding="utf-8"))
    real = rs.import_closure(ROOT)
    assert real, "the import closure came back empty: the pin would prove nothing"
    missing = sorted(real - rows)
    assert not missing, f"append these rows to {ir.CLOSURE_FILE}: {missing}"
    assert all(p.startswith(ir.CLOSURE_ROOTS) for p in real)  # the fail-closed rule holds too


def test_growing_the_closure_list_is_not_itself_a_money_path_change() -> None:
    """Under desks/mt5/ops/ the list was money path, so every PR that appended its new rows failed
    replay-shadow as UNMEASURED for a file the live book never reads (#547, 2026-10-29)."""
    ir, rs = _load("independent_review"), _load("replay_shadow")
    real = rs.import_closure(ROOT)
    assert not rs.is_money(ir.CLOSURE_FILE, real)
    assert ir.CLOSURE_FILE not in real
