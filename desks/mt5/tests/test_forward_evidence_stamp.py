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


def _main_loop_continues(src: str = SRC) -> list[tuple[int, bool]]:
    """(line, stamped) for each `continue`, `break` or `return` in `main` that follows the row's
    state `st` being bound -- inside if/for/while/try/with and match/case blocks alike: stamped
    means an `_unmeasured(` call sits in the same block before it."""
    tree = ast.parse(src)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    # the per-row state: `st = state.get(key, {...})`. Skips before it are enrolment refusals
    # with no row to stamp; every skip after it must stamp.
    st_line = min(n.lineno for n in ast.walk(main) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "st" for t in n.targets)
                  and "state.get(key" in ast.unparse(n.value))
    out: list[tuple[int, bool]] = []

    def visit(body: list[ast.stmt]) -> None:
        for i, stmt in enumerate(body):
            if isinstance(stmt, (ast.Continue, ast.Break, ast.Return)) and stmt.lineno > st_line:
                before = "\n".join(ast.unparse(s) for s in body[:i])
                out.append((stmt.lineno, "_unmeasured(" in before))
            for field in ("body", "orelse", "finalbody"):
                inner = getattr(stmt, field, None)
                if isinstance(inner, list) and not isinstance(stmt, (ast.FunctionDef,
                                                                     ast.AsyncFunctionDef)):
                    visit(inner)
            for h in getattr(stmt, "handlers", []) or []:
                visit(h.body)
            for case in getattr(stmt, "cases", []) or []:      # match/case
                visit(case.body)
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


def test_a_failed_evaluation_blocks_a_promotion_candidate() -> None:
    """Audit 2026-10-07: reverting the failed-evaluation fix must fail a test. A candidate in
    either spelling whose pass raised loses the status and its promotion authority."""
    for spelling in ("PROMOTION CANDIDATE", "PROMOTION_CANDIDATE"):
        st = {"status": spelling, "promotion_authority": True,
              "forward_evidence": {"status": "MEASURED", "at": "2026-10-01T00:00:00+00:00"}}
        detail = sf._fail_row(st, ValueError("session-window migration"))
        assert detail == "ValueError: session-window migration"
        assert st["status"] == "BLOCKED_SLEEVE_ERROR"
        assert st["promotion_authority"] is False
        assert st["forward_evidence"]["status"] == "UNMEASURED"
        assert st["last_error"] == detail


def test_a_failed_evaluation_blocks_an_active_row_and_keeps_a_final_verdict() -> None:
    st = {"status": "ACTIVE", "promotion_authority": True}
    sf._fail_row(st, RuntimeError("x"))
    assert st["status"] == "BLOCKED_SLEEVE_ERROR" and st["promotion_authority"] is False
    for final in ("KILL", "PROMOTED", "KILL_DD"):
        st = {"status": final}
        sf._fail_row(st, RuntimeError("x"))
        assert st["status"] == final and "promotion_authority" not in st
        assert st["forward_evidence"]["status"] == "UNMEASURED"


def test_the_main_loop_routes_every_sleeve_failure_through_fail_row() -> None:
    tree = ast.parse(SRC)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    handlers = [h for n in ast.walk(main) if isinstance(n, ast.Try) for h in n.handlers
                if "isolate ONE sleeve" in SRC.splitlines()[h.lineno - 1]]
    assert len(handlers) == 1
    assert "_fail_row(st, exc)" in ast.unparse(handlers[0])


def test_the_guard_sees_break_return_and_match() -> None:
    """The walker reaches every exit kind, so a new `break`/`return`/`case` skip cannot slip by."""
    probe = (
        "def main():\n"
        "    for key in keys:\n"
        "        st = state.get(key, {})\n"
        "        if a:\n"
        "            break\n"
        "        match st:\n"
        "            case 1:\n"
        "                continue\n"
        "        if b:\n"
        "            _unmeasured(st, 'x')\n"
        "            return\n")
    found = dict(_main_loop_continues(probe))
    assert found == {5: False, 8: False, 11: True}
