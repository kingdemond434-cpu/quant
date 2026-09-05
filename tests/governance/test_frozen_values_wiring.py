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


#: REPOINTED 2026-09-05 (MT5 universe mandate, 2026-08-18). The two tests below fenced
#: `scripts/run_recorder.py`, `run_recorder_spot.py` and `run_recorder_bybit.py` -- the Binance
#: futures/spot and Bybit collectors of the retired crypto-exchange desk, deleted with it. The
#: INVARIANT they pinned did not retire with the venue; it is the one `MOAT_NODE_SPEC.md` states
#: for the MT5 node in as many words ("universe discovered dynamically each cycle --
#: `symbols_get()`, registry not hardcode"), and `tick_recorder` records why: the broker lists and
#: delists instruments, so a frozen list means a hunt ran on a stale universe and nothing said so.
#: So the fence follows the invariant to the recorders that write the tape today.
_RECORDERS = ("desks/mt5/moat/moat_recorder.py", "desks/mt5/recorders/tick_recorder.py")


def test_the_recorders_refresh_their_universe_inside_the_loop() -> None:
    """REGRESSION -- the defect L1.66's first run found, and the reason it is a regression site.

    The retired Bybit collector froze ``_SYMBOLS = _universe()`` at import with no refresh anywhere
    in its loop while both siblings re-polled. Same shape here, and worse consequence: a broker
    that lists a symbol after the recorder started would never be recorded, and the tape's own gap
    would be invisible because the recorder believes it covered its whole universe.

    Pinned STRUCTURALLY -- the symbol call must be reachable from the cycle function, not only from
    module scope -- so a refresh cannot be reduced to an import-time constant again.
    """
    for rel in _RECORDERS:
        src = (_ROOT / rel).read_text("utf-8")
        tree = ast.parse(src)
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        refreshers = [
            f for f in funcs
            if any(
                (isinstance(n.func, ast.Attribute) and n.func.attr in ("symbols_get", "symbols"))
                or (isinstance(n.func, ast.Name) and "universe" in n.func.id.lower())
                or (isinstance(n.func, ast.Attribute) and "universe" in n.func.attr.lower())
                for n in ast.walk(f) if isinstance(n, ast.Call))]
        assert refreshers, (
            f"{rel} never re-derives its symbol universe inside a function -- a universe fixed at "
            "import is a universe that stops matching the broker the first time it lists anything")
        module_level = {t.id for n in tree.body if isinstance(n, ast.Assign)
                        for t in n.targets if isinstance(t, ast.Name)}
        for n in tree.body:
            if not (isinstance(n, ast.Assign) and any(
                    isinstance(c.func, ast.Attribute) and c.func.attr in ("symbols_get", "symbols")
                    for c in ast.walk(n) if isinstance(c, ast.Call))):
                continue
            names = {t.id for t in n.targets if isinstance(t, ast.Name)}
            assert not names, (
                f"{rel}: {sorted(names)} is a symbol list frozen at import ({sorted(module_level)} "
                "are module-level). The universe must be re-derived per cycle.")


def test_every_recorder_agrees_on_the_refresh_cadence() -> None:
    """The asymmetry R0220 was supposed to end: one recorder silently on a different cadence.

    Each recorder must name its own refresh interval as a CONFIGURABLE value, so the cadence is a
    stated number somebody can compare rather than an accident of whichever loop it sits in.
    """
    for rel in _RECORDERS:
        src = (_ROOT / rel).read_text("utf-8")
        assert "UNIVERSE_REFRESH_S" in src or "universe_refresh_s" in src, (
            f"{rel} has no named universe-refresh cadence")
