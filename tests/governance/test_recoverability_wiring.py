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


# THE 41-DAY DEFECT'S REGRESSION SITE IS GONE, AND HALF OF IT IS REPOINTED (2026-09-05).
#
# `test_listener_flush_clears_only_after_a_durable_write` stood here. It read
# `scripts/liquidation_listener.py` and pinned, structurally, that `_BUF.clear()` could not appear
# at a line before the `read_parquet` that loaded the archive -- because the original order cleared
# the buffer first and destroyed 41 days of liquidations against an archive that turned out to be
# corrupt. That listener collected crypto-exchange liquidations; it was deleted with the retired
# desk under the MT5 universe mandate, and its systemd row is parked in ops/crontab.manifest.
#
# THE ORDERING HALF IS NOT REPOINTED, deliberately. No MT5 recorder buffers-then-clears -- they
# write straight through -- so aiming that assertion at one would invent a regression site rather
# than guard one, and a fence that cannot fail on the code it reads is worse than no fence.
# THE ATOMICITY HALF IS repointed below, because that one IS live: every tape writer on the money
# path still has to make a partial write impossible, and that is what actually made the archive
# corrupt in the first place.


def test_the_tape_writers_make_a_partial_write_impossible() -> None:
    """A half-written archive is the precondition for the whole 41-day loss, not a detail of it.

    The listener cleared its buffer against an archive it believed it had read; the archive was
    truncated because the write was not atomic. Ordering protected the data only if the file on
    disk was either the old one or the new one and never something in between. So the surviving
    assertion is the one that still has live code under it: a tape file is written to a temporary
    path and moved into place with `os.replace`, which is atomic on POSIX and on Windows.
    """
    for rel in ("desks/mt5/recorders/tape_store.py", "desks/mt5/moat/moat_recorder.py"):
        src = (ROOT / rel).read_text("utf-8")
        tree = ast.parse(src)
        replaces = [n for n in ast.walk(tree)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "replace"
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "os"]
        assert replaces, (
            f"{rel} never moves a finished file into place with os.replace -- a reader can then "
            "see a partially written tape file, which is the state the archive was in when "
            "clearing the buffer against it destroyed 41 days of data")
