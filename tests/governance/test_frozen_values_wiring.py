"""Wiring tests for L1.66 -- the frozen-value fence.

An unwired capability and a working one are byte-identical in every report that counts modules or
passes tests; the only question that separates them is WHAT RUNS IT, and it is never asked by
accident (III.16). Each test below turns red if one wiring artifact is removed.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_FENCE = _ROOT / "scripts/check_frozen_values.py"


def test_law_is_in_the_constitution() -> None:
    text = (_ROOT / "docs/CONSTITUTION.md").read_text("utf-8")
    assert "## L1.66" in text
    assert "check_frozen_values.py" in text
    assert "libs/ops/value_staleness.py" in text


def test_law_is_mapped_in_the_enforcement_matrix() -> None:
    src = (_ROOT / "scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.66"' in src
    assert "scripts/check_frozen_values.py" in src
    assert "libs/ops/value_staleness.py" in src


def test_fence_is_scheduled() -> None:
    manifest = (_ROOT / "ops/crontab.manifest").read_text("utf-8")
    lines = [ln for ln in manifest.splitlines()
             if "check_frozen_values.py" in ln and not ln.lstrip().startswith("#")]
    assert lines, "the fence must have a scheduler line, not only a comment"
    assert "EVIDENCE:" in manifest and "CONSTITUTION L1.66" in manifest


def test_fence_is_registered_in_the_build_standard() -> None:
    src = (_ROOT / "scripts/check_build_standard.py").read_text("utf-8")
    assert '"check_frozen_values.py"' in src, "registration in _GOVERNED IS the mechanism (L1.41)"


def test_fence_declares_its_measured_denominator() -> None:
    """L1.57: the denominator must be what the RUN found, never a hardcoded roster."""
    src = _FENCE.read_text("utf-8")
    assert "scanned=rep.n_pairs" in src
    assert 'fence="check_frozen_values.py"' in src, "fence= must carry .py or the row never joins"


def test_fence_calls_the_law_guard() -> None:
    """L1.42: no act is exempt -- every entry point passes the laws."""
    tree = ast.parse(_FENCE.read_text("utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {n.func.id for n in ast.walk(main)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_law_guard" in called


def test_every_non_clean_status_is_visible_in_the_human_output() -> None:
    """REGRESSION -- the first run printed 6 pairs and listed 5.

    SOURCE-DRIFTED was computed, counted in the artifact, and absent from both the summary line
    and the detail loop -- so the only output a human reads said nothing about the one pair the
    fence had refused to certify. A status that fires silently is the defect class this whole law
    exists to end, committed by its own reporting line.
    """
    src = _FENCE.read_text("utf-8")
    for status in ("FROZEN-STALE", "FROZEN-CURRENT", "REFRESHED", "SOURCE-DRIFTED",
                   "UNRESOLVED", "EXEMPT"):
        assert status in src, f"{status} is never printed"
    assert "rep.n_source_drifted" in src, "the count must appear in the summary line"
    # and the detail loop must not filter it out again
    detail = src.split("for p in rep.pairs:")[1].split("\n\n")[0]
    assert "SOURCE_DRIFTED" in detail, "SOURCE-DRIFTED must survive the detail-loop filter"


def test_bybit_recorder_refreshes_its_universe_in_the_loop() -> None:
    """REGRESSION -- the defect L1.66's first run found, and the reason it is a regression site.

    ``run_recorder_bybit.py`` froze ``_SYMBOLS = _universe()`` at import with no refresh anywhere
    in its loop, while both sibling recorders re-poll hourly. That is R0220 repeating one layer
    down on the same file: R0220 made bybit DERIVE the universe instead of hardcoding it, and the
    REFRESH was closed on Binance and spot and never here.

    Pinned STRUCTURALLY -- ``_universe`` must be called from inside ``main`` -- because that is
    exactly the property the fence reads, so this test and the fence cannot disagree.
    """
    tree = ast.parse((_ROOT / "scripts/run_recorder_bybit.py").read_text("utf-8"))
    main = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = {n.func.id for n in ast.walk(main)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_universe" in calls, "the universe must be re-derived inside main(), not only at import"
    # and the write loops must consume the refreshed local, never the import-time constant
    body = ast.get_source_segment((_ROOT / "scripts/run_recorder_bybit.py").read_text("utf-8"),
                                  main) or ""
    assert "for sym in symbols:" in body
    assert "for sym in _SYMBOLS:" not in body, "a loop still reading the frozen tuple is the defect"


def test_all_three_recorders_agree_on_the_refresh_cadence() -> None:
    """The asymmetry R0220 was supposed to end: one recorder silently on a different cadence."""
    for rel in ("scripts/run_recorder.py", "scripts/run_recorder_spot.py",
                "scripts/run_recorder_bybit.py"):
        src = (_ROOT / rel).read_text("utf-8")
        assert "_UNIVERSE_REFRESH_S" in src, f"{rel} has no universe refresh cadence"
