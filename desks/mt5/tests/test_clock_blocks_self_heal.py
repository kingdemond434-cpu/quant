"""A BLOCK MUST CLEAR ITSELF WHEN ITS CAUSE IS REPAIRED -- NO CLOCK IS EVER FROZEN.

Principal, 2026-09-23: forward clocks and certificate clocks must "permanently always work never
blocked unmeasured stale or broken". A frozen clock is as severe as a missing one, and neither may
need a human to unfreeze it.

THE TWO FREEZES THIS FILE PINS, both measured on the trading box 2026-09-23:

  REFUSED_BY_UNIVERSE_POLICY  was written TERMINAL, reasoning that a symbol's lane changes only
                              when the registry learns its asset class and that the certificate
                              could then "be re-enrolled DELIBERATELY". The lane also changes when
                              the LANE CODE is repaired -- which is exactly what happened: all 96
                              FX symbols read UNCLASSIFIED because `universe_policy` declared its
                              FX class names in a spelling its own normaliser could never produce.
                              With that fixed, the symbols were admitted and the rows evaluated
                              end to end again while the STATUS stayed pinned at a refusal that no
                              longer held. 92 clocks, 24 of them certificates.

  BLOCKED_NO_BARS             the clearing clause beside it named ONE status, `BLOCKED_SLEEVE_
                              ERROR`. The four XAUUSD certificates took BLOCKED_NO_BARS from a
                              pass that caught the H1 parquet mid-rewrite and kept it while every
                              later pass fetched 41,811 bars and evaluated them.

Both are ALWAYS-RED DETECTORS describing repaired causes, which is what L1.37 retires on sight.

THE OTHER DIRECTION IS FENCED TOO, and it is the one that would do real harm: a KILL or a
PROMOTION CANDIDATE is a VERDICT the desk reached, and no block-clearing may ever turn one back
into an unevaluated row -- that would put a killed sleeve back in the book.
"""

from __future__ import annotations

import ast
import pathlib

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "research" / "shadow_forward.py"


def _clearing_clauses() -> list[ast.If]:
    """Every `if <status> in (...)` / `== ...` guard that assigns `st["status"] = "ACTIVE"`."""
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    out: list[ast.If] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for stmt in node.body:
            if (isinstance(stmt, ast.Assign)
                    and isinstance(stmt.value, ast.Constant) and stmt.value.value == "ACTIVE"
                    and any(isinstance(t, ast.Subscript) for t in stmt.targets)):
                out.append(node)
                break
    return out


def _names_in(node: ast.AST) -> set[str]:
    return {n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def test_a_repaired_lane_verdict_clears_itself() -> None:
    """REFUSED_BY_UNIVERSE_POLICY must be cleared somewhere, not left for a human."""
    cleared: set[str] = set()
    for clause in _clearing_clauses():
        cleared |= _names_in(clause.test)
    assert "REFUSED_BY_UNIVERSE_POLICY" in cleared, (
        "nothing clears a universe-policy refusal, so a clock refused by a lane defect stays "
        "frozen after the defect is fixed and only a human can revive it")


def test_every_block_clears_itself_when_the_sleeve_evaluates() -> None:
    cleared: set[str] = set()
    for clause in _clearing_clauses():
        cleared |= _names_in(clause.test)
    for status in ("BLOCKED_SLEEVE_ERROR", "BLOCKED_NO_BARS", "BLOCKED_INPUTS_UNAVAILABLE"):
        assert status in cleared, (
            f"{status} says `this pass could not evaluate`; once a pass DOES evaluate, leaving it "
            f"set is an always-red detector describing a repaired cause (L1.37)")


def test_no_verdict_is_ever_cleared_back_into_the_book() -> None:
    """The fence on the fix: a KILL or a PROMOTION CANDIDATE must never be revived by this."""
    forbidden = {"KILL", "PROMOTED", "DEAD", "REJECTED", "PROMOTION CANDIDATE"}
    for clause in _clearing_clauses():
        revived = _names_in(clause.test) & forbidden
        assert not revived, (
            f"a clearing clause tests for {sorted(revived)}: a verdict the desk already reached "
            f"must never be turned back into an unevaluated row")


def test_the_engine_still_refuses_a_symbol_the_lane_excludes() -> None:
    """Self-healing must not become 'always admit'. The refusal itself has to still be written."""
    text = ENGINE.read_text(encoding="utf-8")
    assert 'st["status"] = "REFUSED_BY_UNIVERSE_POLICY"' in text
    assert "may_hypothesise" in text, "the lane door must still be consulted before enrolling"
