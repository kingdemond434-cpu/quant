"""A package __init__ that imports eagerly makes every submodule cost the whole subtree.

WHAT HAPPENED (gap-fixer 2026-08-28). `libs/ops/__init__.py` re-exported seven names by
importing `backup`, `errors` and `watchdog` at module level. Python runs a package's `__init__`
before ANY submodule, so `from libs.ops.disk import headroom` -- a helper whose own imports are
`shutil`, `pathlib` and `typing` -- paid for all three. `watchdog` reaches `libs.risk.drawdown`
and `backup` reaches `libs.store.connection`, and the chain ended in numpy and scipy.

MEASURED: `libs.ops.disk` cost 107.5 MB through the package and 13.8 MB loaded alone -- 93.7 MB
per process to reach a disk-space helper. 255 files import `libs.ops.*`, 157 of them in
`scripts/`: the timer-driven organs, dozens of which run concurrently on a 3.8 GB box with NO
SWAP. That is the memory behind an OOM storm whose symptoms were being read as unrelated unit
bugs -- quant-cadence killed 37 times in 24h (18 of 55 runs completed), the auto-push guard 19.

These tests pin the property rather than the implementation: import a leaf submodule in a CLEAN
interpreter and assert the scientific stack did not come with it. The eager form fails the first
test; a future edit that re-adds a top-level `from libs.ops.backup import ...` fails it again.
"""

from __future__ import annotations

import subprocess
import sys


#: Run in a FRESH interpreter every time. Measuring inside this one proves nothing: pytest has
#: already imported numpy long before any test body runs, so the check would pass unconditionally.
def _in_clean_interpreter(code: str) -> str:
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, f"subprocess failed: {out.stderr[-2000:]}"
    return out.stdout.strip()


def test_importing_a_leaf_submodule_does_not_drag_in_the_scientific_stack() -> None:
    """The 93.7 MB. `disk` needs shutil and pathlib; it must not cost numpy and scipy."""
    got = _in_clean_interpreter(
        "import sys; from libs.ops.disk import headroom; "
        "print(','.join(m for m in ('numpy','scipy','pandas','pyarrow') if m in sys.modules))"
    )
    assert got == "", f"libs.ops.disk pulled in {got} -- the package __init__ is eager again"


def test_every_public_re_export_still_resolves_to_the_real_object() -> None:
    """Laziness may not cost the API: the names, and their identity, are unchanged."""
    got = _in_clean_interpreter(
        "from libs.ops import (BackupManager, BackupManifest, RestoreDrill, OpsError, "
        "HaltDecision, ProcessWatchdog, SafeHaltController); "
        "from libs.ops.backup import BackupManager as B; print(BackupManager is B)"
    )
    assert got == "True", "a re-exported name is not the object its own submodule defines"


def test_the_lazy_map_and_dunder_all_cannot_drift_apart() -> None:
    """Adding a re-export to one list and not the other is the way this decays silently."""
    import libs.ops as ops
    assert sorted(ops.__all__) == sorted(ops._LAZY), (
        "__all__ and _LAZY disagree: a name in one and not the other is either an export that "
        "cannot resolve or a resolvable name that `import *` will not deliver"
    )


def test_unknown_attributes_raise_AttributeError_so_submodule_imports_still_work() -> None:
    """`from libs.ops import desk_host` needs __getattr__ to FAIL, not to raise ImportError."""
    got = _in_clean_interpreter(
        "import libs.ops\n"
        "try:\n"
        "    libs.ops.nope\n"
        "    print('NO-RAISE')\n"
        "except AttributeError:\n"
        "    from libs.ops import desk_host, platform_paths\n"
        "    print('ok')\n"
    )
    assert got == "ok", "submodule import fell over -- __getattr__ must raise AttributeError"


# ---------------------------------------------------------------------------------------------
# The type-safety half of the same property (gap-fixer 2026-08-29).
#
# The lazy form above is correct and keeps its 93.7 MB. What it ALSO did, silently, was blind
# mypy: a module-level `__getattr__` returning `Any` tells mypy that every attribute of
# `libs.ops` exists, so `from libs.ops import <anything>` type-checked clean across the 255
# files that import `libs.ops.*`. That is a gate passing 100% of the time, which carries zero
# information (RESEARCH §6, gate-optimality).
#
# HOW IT SURFACED, and why it was expensive: the deliberate fail-closed
# `# type: ignore[attr-defined]` at libs/ops/deepseek_cycle.py:249 became `[unused-ignore]`,
# which took `ops/gates.sh` RED -- and the red gate is the pre-push hook, so NOTHING on the box
# could push. The desk's whole output path was blocked by a type annotation.
#
# The fix wraps `__getattr__` in `if not TYPE_CHECKING:`. Runtime is byte-identical (the guard
# is False there); mypy falls back to the `if TYPE_CHECKING` re-exports plus ordinary submodule
# resolution. This test pins the recovered property, not the guard: any future edit that makes
# a bogus `libs.ops` attribute type-check clean fails here.
# ---------------------------------------------------------------------------------------------


def _mypy_verdict_on(snippet: str) -> str:
    """Type-check a snippet against the REAL project config, in a temp file mypy has not seen."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "probe.py"
        f.write_text(snippet)
        out = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-incremental", str(f)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        return out.stdout + out.stderr


def test_mypy_still_rejects_an_attribute_libs_ops_does_not_have() -> None:
    """The blindness. Before the `if not TYPE_CHECKING` guard this snippet was 'Success'."""
    got = _mypy_verdict_on("from libs.ops import totally_bogus_module_xyz\n")
    assert "attr-defined" in got, (
        "mypy accepted a name libs.ops does not define -- the package __init__ is exposing a "
        f"module-level __getattr__ to the type checker again. mypy said:\n{got[:800]}"
    )


def test_mypy_still_resolves_the_real_re_exports_and_the_real_submodules() -> None:
    """The other direction: the guard must not cost what the eager form gave the checker."""
    got = _mypy_verdict_on(
        "from libs.ops import BackupManager, OpsError, SafeHaltController\n"
        "from libs.ops.disk import headroom\n"
        "_ = (BackupManager, OpsError, SafeHaltController, headroom)\n"
    )
    assert "Success" in got, f"a genuine libs.ops import stopped type-checking:\n{got[:800]}"
