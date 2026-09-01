"""Both universal validators must take every threshold from ONE authority.

gate_policy is "the single immutable authority for MT5 shadow admission" and loads its numbers
from desks/mt5/policy/gate_spec.yaml. universal_gate imported them; qquant_gates carried its own
copies. They agreed on 2026-09-01 -- verified value by value -- so nothing was mis-certified,
but an edit to gate_spec.yaml would have moved one validator and not the other, and the two
would then certify different candidates from the same evidence while both reporting a ten-gate
pass. A threshold that lives in two places is a threshold nobody controls.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
for p in (str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import gate_policy as gp  # noqa: E402
import qquant_gates as qq  # noqa: E402

#: Every number that decides a ten-gate verdict.
SHARED = ("TRIALS_MULTIPLIER", "DSR_THRESHOLD", "PBO_THRESHOLD", "SPA_ALPHA",
          "WF_SPLITS", "WF_MIN_STABILITY", "COST_SCENARIO")


def test_qquant_gates_uses_the_policy_values() -> None:
    for name in SHARED:
        assert getattr(qq, name) == getattr(gp, name), (
            f"{name} differs between qquant_gates and gate_policy -- two validators are "
            f"judging the same evidence by different numbers")


def test_qquant_gates_does_not_redefine_them_locally() -> None:
    """Equal values are not enough: a local literal can be edited without touching policy."""
    src = (DESK / "research" / "qquant_gates.py").read_text("utf-8")
    tree = ast.parse(src)
    assigned = {
        t.id
        for node in tree.body if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    }
    leaked = sorted(assigned & set(SHARED))
    assert not leaked, (
        f"qquant_gates assigns {leaked} at module level; these must be IMPORTED from "
        f"gate_policy so gate_spec.yaml stays the only place a bar can move")


def test_the_multiplicity_charge_in_particular_is_not_local() -> None:
    """gate_policy pins the trial charge so a candidate does not face a higher bar for having
    been scheduled into a wider sweep. A private copy could raise that silently."""
    assert qq.TRIALS_MULTIPLIER == gp.TRIALS_MULTIPLIER


def test_both_validators_build_the_matrix_by_calendar_join() -> None:
    """PBO and SPA are cross-sectional: every row must be the same DAY across trials.

    Truncate-to-shortest compared cell A's Tuesday against cell B's Thursday. Both files now
    join on the date index; this pins that neither regresses (it already regressed once, via
    an hourly sync).
    """
    for fname in ("qquant_gates.py", "universal_gate.py"):
        src = (DESK / "research" / fname).read_text("utf-8")
        assert "sort_index().fillna(0.0)" in src, f"{fname} no longer joins on the date index"
        assert "min_len" not in src, f"{fname} reintroduced truncate-to-shortest"
