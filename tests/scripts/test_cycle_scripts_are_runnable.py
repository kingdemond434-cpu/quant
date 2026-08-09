"""EVERY SCRIPT THE CYCLE INVOKES MUST IMPORT ON ITS OWN.

`python scripts/x.py` puts `scripts/` on `sys.path`, NOT the repo root. So `from libs...` resolves
only when the project happens to be pip-installed into whichever interpreter the cycle picked --
and `ops/run_research_cycle.sh` picks between `.venv/bin/python`, `.venv/bin/python` and `python3`
at runtime. A script that works under one and not another is a scheduling coin flip.

**THE FAILURE IS SILENT, WHICH IS WHY IT NEEDS A TEST RATHER THAN A CONVENTION.**
`scripts/run_trade_forensics.py` wrapped its tape section in a broad `except Exception` and shipped

    "execution_tape": {"error": "ModuleNotFoundError: No module named 'libs'"}

into `web/trade_forensics.json`. Nothing crashed, the cycle reported success, and the dashboard
would have rendered an error string in a slot that reads as data. An observer that swallows an
import error reports the same shape whether the analysis ran or not.

These tests do not import the modules (many have side effects at import time and some hit the
network). They assert the STRUCTURAL precondition -- a path bootstrap exists -- which is cheap,
deterministic, and the thing that actually differs between a script that works and one that does
not.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
OPS = ROOT / "ops"


#: Named exemptions, with the reason. An exemption without a reason is an oversight with a
#: config entry, and the reason is what makes it reviewable when the blocker clears.
_EXEMPT: dict[str, str] = {
    "run_cashcarry_executor.py": (
        "ORDER PATH, and the Codex seat rewrote ~840 lines of it on the VPS branch. A three-line "
        "edit here would manufacture a merge conflict on the one file where a bad resolution can "
        "place a trade. Bootstrap it AFTER that branch merges -- see TestKnownExemption below, "
        "which fails once the exemption is spent"),
}


def _ops_invoked_scripts() -> list[Path]:
    """Every scripts/*.py named by any shell file under ops/."""
    named: set[str] = set()
    for sh in OPS.glob("*.sh"):
        named |= set(re.findall(r"scripts/[a-zA-Z0-9_]+\.py", sh.read_text("utf-8")))
    return sorted({ROOT / n for n in named if (ROOT / n).exists()})


def _imports_libs(src: str) -> bool:
    """True if the module imports `libs` ANYWHERE -- including inside a function.

    Function-level imports are the dangerous case: they are the ones a broad `except` around the
    call site can swallow, and the tape defect was exactly that shape.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:                                    # pragma: no cover - would fail lint
        return "libs." in src
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("libs"):
            return True
        if isinstance(node, ast.Import) and any(a.name.startswith("libs") for a in node.names):
            return True
    return False


def _has_bootstrap(src: str) -> bool:
    return "sys.path" in src or "_sys.path" in src


class TestEveryCycleScriptResolvesLibs:
    def test_the_scan_finds_the_cycle(self) -> None:
        """Guard the guard: an empty scan would make every assertion below vacuously true."""
        found = _ops_invoked_scripts()
        assert len(found) >= 10, f"only found {len(found)} ops-invoked scripts -- scan is broken"

    @pytest.mark.parametrize("path", _ops_invoked_scripts(), ids=lambda p: p.name)
    def test_script_can_resolve_libs_standalone(self, path: Path) -> None:
        src = path.read_text("utf-8")
        if not _imports_libs(src):
            pytest.skip(f"{path.name} does not import libs")
        if path.name in _EXEMPT:
            pytest.skip(f"{path.name}: {_EXEMPT[path.name]}")
        assert _has_bootstrap(src), (
            f"{path.relative_to(ROOT)} imports `libs` but has no sys.path bootstrap. Run by path "
            "from the cycle, `scripts/` is on sys.path and the repo root is not, so the import "
            "resolves only if the project is pip-installed into the interpreter that happened to "
            "be chosen. Add:\n"
            "    import sys; from pathlib import Path\n"
            "    _R = Path(__file__).resolve().parent.parent\n"
            "    if str(_R) not in sys.path: sys.path.insert(0, str(_R))")


class TestTheForensicsDefectSpecifically:
    """The instance that was live, kept as its own test because it shipped a wrong artifact."""

    def test_trade_forensics_has_a_bootstrap(self) -> None:
        src = (ROOT / "scripts" / "run_trade_forensics.py").read_text("utf-8")
        assert _has_bootstrap(src)

    def test_an_error_string_never_reaches_the_artifact_slot(self) -> None:
        """If the tape section is present, it must carry data -- never an exception's text.

        Skipped when the artifact has not been generated on this host. Present-and-erroring is the
        state that must fail, because that is what a reader would render as a measurement.
        """
        art = ROOT / "web" / "trade_forensics.json"
        if not art.exists():
            pytest.skip("no trade_forensics artifact on this host")
        import json
        tape = json.loads(art.read_text("utf-8")).get("execution_tape")
        if not isinstance(tape, dict):
            pytest.skip("no execution_tape section")
        assert "ModuleNotFoundError" not in str(tape.get("error", "")), (
            "the tape section is reporting an import error as though it were an observation -- "
            "the exact defect the bootstrap was added to remove")


class TestKnownExemption:
    def test_the_executor_is_named_rather_than_silently_skipped(self) -> None:
        """scripts/run_cashcarry_executor.py is the one ops script left without a bootstrap.

        DELIBERATE, and recorded here so it is a decision rather than an oversight: the Codex seat
        rewrote ~840 lines of that file on the VPS branch, and it is the order path. A three-line
        edit here would manufacture a merge conflict on the one file where a bad resolution can
        place a trade. It gets the bootstrap after that branch is merged, not before.
        """
        src = (ROOT / "scripts" / "run_cashcarry_executor.py").read_text("utf-8")
        if _has_bootstrap(src):
            pytest.skip("executor now has a bootstrap -- exemption is spent, delete this test")
        assert _imports_libs(src), (
            "the exemption assumes this file imports libs; if it no longer does, the exemption is "
            "stale and should be removed rather than left as decoration")
