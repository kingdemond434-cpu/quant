"""L1.65 must stay WIRED. Built is not a status (III.16).

An unwired capability and a working one are byte-identical in every report that counts modules or
passes tests; the only question that separates them is WHAT RUNS IT. These tests are that
question, asked mechanically. Each fails if the corresponding wiring is deleted.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_law_is_in_the_constitution() -> None:
    text = (ROOT / "docs/CONSTITUTION.md").read_text("utf-8")
    assert "## L1.65" in text, "the law must exist in the constitution"
    assert "check_data_recoverability.py" in text, "the law must name its fence"


def test_law_is_mapped_in_the_enforcement_matrix() -> None:
    """A law with no mapping is DECORATIVE (L1.36) -- fenced, but reaching nothing."""
    src = (ROOT / "scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.65"' in src, "L1.65 must be mapped"
    assert "scripts/check_data_recoverability.py" in src
    assert "libs/research/recoverability.py" in src


def test_fence_is_scheduled() -> None:
    """A fence that runs on no schedule is a detector nobody runs (L1.28c/III.16)."""
    manifest = (ROOT / "ops/crontab.manifest").read_text("utf-8")
    lines = [ln for ln in manifest.splitlines()
             if "check_data_recoverability.py" in ln and not ln.lstrip().startswith("#")]
    assert lines, "the fence must have a scheduler line, not only a comment"
    assert "EVIDENCE:" in manifest and "CONSTITUTION L1.65" in manifest


def test_fence_declares_its_denominator() -> None:
    """L1.57: a passing verdict must carry a count of what THIS RUN examined."""
    src = (ROOT / "scripts/check_data_recoverability.py").read_text("utf-8")
    assert "scanned=rep.n_streams" in src, "the denominator must be measured, not hardcoded"
    assert "fence_exit(" in src


def test_fence_calls_the_law_guard() -> None:
    """L1.42: every entry point passes the laws."""
    tree = ast.parse((ROOT / "scripts/check_data_recoverability.py").read_text("utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {n.func.id for n in ast.walk(main)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_law_guard" in called, "main() must call guard() at the top (L1.42)"


def test_listener_flush_clears_only_after_a_durable_write() -> None:
    """REGRESSION on the 41-day defect: `_BUF.clear()` must not precede the archive read.

    Pinned structurally rather than behaviourally so the ordering cannot silently regress even if
    someone rewrites the body: in the fixed implementation the clear happens after the write, so
    no `read_parquet` call may appear at a later line than the clear.
    """
    src = (ROOT / "scripts/liquidation_listener.py").read_text("utf-8")
    tree = ast.parse(src)
    flush = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_flush")
    clears = [n.lineno for n in ast.walk(flush)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "clear"]
    reads = [n.lineno for n in ast.walk(flush)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "read_parquet"]
    assert clears and reads, "_flush must both read the archive and clear the buffer"
    assert min(clears) > max(reads), (
        "the buffer must be cleared AFTER the archive is read -- the original order destroyed "
        "41 days of liquidations against a corrupt archive")
    assert "replace(" in src, "the archive write must be atomic (tmp + replace)"
