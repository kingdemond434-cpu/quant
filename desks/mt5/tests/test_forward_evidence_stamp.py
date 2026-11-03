"""A skipped forward row says so ON the row (audit 2026-10-06, #214).

`shadow_forward` stamps `forward_evidence` MEASURED when it evaluates a row. Six paths skip a row
(banned family, quarantine, universe-policy refusal, no bars, a vanished family constructor,
unavailable inputs) and each left the previous pass's MEASURED stamp behind, so a stale clock read
fresh. Every skip path now writes UNMEASURED with its reason.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_forward as sf  # noqa: E402

SRC = (DESK / "research" / "shadow_forward.py").read_text("utf-8")


def test_unmeasured_overwrites_a_stale_measured_stamp() -> None:
    st = {"status": "BLOCKED_NO_BARS",
          "forward_evidence": {"status": "MEASURED", "at": "2026-10-01T00:00:00+00:00"}}
    sf._unmeasured(st, "BLOCKED_NO_BARS: no H1 bars for XAUUSD")
    assert st["forward_evidence"]["status"] == "UNMEASURED"
    assert "BLOCKED_NO_BARS" in st["forward_evidence"]["why"]
    assert st["forward_evidence"]["at"] > "2026-10-01"


def _main_loop_continues() -> list[tuple[int, bool]]:
    """(line, stamped) for each `continue` in `main` that follows the row's state `st` being
    bound: stamped means an `_unmeasured(` call sits in the same block before it."""
    tree = ast.parse(SRC)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    # the per-row state: `st = state.get(key, {...})`. Skips before it are enrolment refusals
    # with no row to stamp; every skip after it must stamp.
    st_line = min(n.lineno for n in ast.walk(main) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "st" for t in n.targets)
                  and "state.get(key" in ast.unparse(n.value))
    out: list[tuple[int, bool]] = []

    def visit(body: list[ast.stmt]) -> None:
        for i, stmt in enumerate(body):
            if isinstance(stmt, ast.Continue) and stmt.lineno > st_line:
                before = "\n".join(ast.unparse(s) for s in body[:i])
                out.append((stmt.lineno, "_unmeasured(" in before))
            for field in ("body", "orelse", "finalbody"):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and not isinstance(stmt, (ast.FunctionDef,
                                                                     ast.AsyncFunctionDef)):
                    visit(inner)
            for h in getattr(stmt, "handlers", []) or []:
                visit(h.body)
    visit(main.body)
    return out


def test_the_no_bars_skip_and_its_siblings_stamp_unmeasured() -> None:
    no_bars = SRC.index('slog(f"{key}: BLOCKED_NO_BARS -- {st[\'last_error\']}")')
    block = SRC[SRC.rindex("if bars is None:", 0, no_bars):no_bars]
    assert '_unmeasured(st, f"BLOCKED_NO_BARS:' in block
    for marker in ('_unmeasured(st, f"quarantined:',
                   '_unmeasured(st, "refused by universe policy")',
                   '_unmeasured(st, f"constructor for family',
                   '_unmeasured(st, f"inputs unavailable:',
                   'f"family {fam!r} is banned; not evaluated"'):
        assert marker in SRC, marker


def test_no_skip_after_the_row_is_bound_leaves_a_stale_stamp() -> None:
    """Every `continue` in the per-row loop after `st` is bound stamps the row first -- no
    exemptions (audit 2026-10-06: a window heuristic let a bare `slog(...); continue` through)."""
    found = _main_loop_continues()
    assert found, "the per-row loop was not found"
    unstamped = [line for line, stamped in found if not stamped]
    assert not unstamped, (
        f"shadow_forward.main skips rows at lines {unstamped} without stamping "
        "forward_evidence UNMEASURED")
