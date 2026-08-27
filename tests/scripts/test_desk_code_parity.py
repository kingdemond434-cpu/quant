"""Byte parity is a HALF verdict: matching bytes that no commit records are one checkout from gone.

TWO MEASURED FAILURES, one per direction, both from 2026-08-27.

  * THIS SIDE. An earlier draft of this organ hashed the working tree and immediately certified
    "25/25 byte-identical" for `families_orthogonal.py`, whose content existed in NO COMMIT --
    a sibling's in-flight edit already shipped to the trading box. A fence built to catch that
    class cannot be measured against an unrecorded tree.
  * THE OTHER SIDE. `shadow_forward.py` was byte-identical on both boxes -- this check read
    green -- while existing on the desk box only as an uncommitted working-tree edit; and
    `shadow_cycle.py` beside it had reverted to its 2026-08-23 form. The newer `shadow_forward`
    no longer defined `UNIVERSE_SLEEVES`, the older `shadow_cycle` still read it, every run died
    on AttributeError, and the desk's entire forward book stopped accruing for 5.5 hours.

So the organ reports both, and reports UNMEASURED as its own verdict on both. The heal path is
deliberately unchanged: it runs the money-path fence first and refuses to ship a tree that fence
cannot bring to canon, which is the guard that matters when SHIPPING rather than when reporting.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "scripts" / "check_desk_code_parity.py").read_text("utf-8")


def _load():
    spec = importlib.util.spec_from_file_location(
        "_dcp", ROOT / "scripts" / "check_desk_code_parity.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_both_uncommitted_dimensions_are_measured_and_reported() -> None:
    body = SRC.split("def main(", 1)[1]
    assert "uncommitted_on_desk(" in body, "the desk box's git state is never consulted"
    assert "uncommitted_here(" in body, "this checkout's git state is never consulted"
    assert '"uncommitted_on_desk": uncommitted' in body
    assert '"uncommitted_here": here' in body


def test_uncommitted_here_finds_a_dirty_money_path_file(tmp_path, monkeypatch) -> None:
    """Behavioural, not textual: an untracked path inside the repo must come back dirty."""
    mod = _load()
    probe = ROOT / "desks" / "mt5" / "research" / "_parity_probe_delete_me.py"
    probe.write_text("# transient probe written by test_desk_code_parity\n", "utf-8")
    try:
        rel = str(probe.relative_to(ROOT))
        assert mod.uncommitted_here([rel]) == [rel]
        # And a file that is genuinely clean must NOT be reported. The clean file is DERIVED at
        # runtime rather than named: any path this test hardcoded could be legitimately dirty in
        # whichever tree the suite runs in, and a fixture that only works on a pristine checkout
        # tests the checkout rather than the function.
        import subprocess
        tracked = subprocess.run(["git", "ls-files", "scripts/"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout.split()
        dirty = set(mod.uncommitted_here(tracked) or [])
        clean = [f for f in tracked if f not in dirty]
        assert clean, "no clean tracked file to compare against"
        assert mod.uncommitted_here(clean[:5]) == []
    finally:
        probe.unlink()


def test_neither_dimension_reports_an_empty_list_when_it_could_not_look() -> None:
    """`[]` means 'looked, found none'. Not-looking must be `None` and must not read as clean."""
    assert "None means UNMEASURED -- never an empty list" in SRC
    assert '"uncommitted_here": here' in SRC
    assert "UNCOMMITTED_UNMEASURED" in SRC


def test_an_uncommitted_desk_file_is_a_nonzero_exit() -> None:
    body = SRC.split("def main(", 1)[1]
    assert "return 1 if (diverged or uncommitted is None or uncommitted) else 0" in body, (
        "a byte-correct but uncommitted money path exits 0, which is the verdict that let the "
        "forward book stop for 5.5 hours")


def test_unreachable_is_never_reported_as_parity() -> None:
    assert '"status": "UNREACHABLE"' in SRC
    assert "parity is UNMEASURED, not clean" in SRC


def test_the_orchestrator_of_the_forward_pipeline_is_a_protected_file() -> None:
    """`shadow_cycle.py` runs every forward leg AND the promoter AND owns the pre-registration
    stamp, and it was absent from the money-path registry this organ reads -- so both were blind
    while the box ran a four-day-old copy of it."""
    mod = _load()
    protected = mod.protected_files()
    assert "desks/mt5/research/shadow_cycle.py" in protected
