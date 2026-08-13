"""THE PRE-PUSH GATE IS A FILE, NOT A CONVENTION -- and this fences the file.

Three consecutive batches reached the shared branch green on ruff+mypy with pytest never run.
Behind those two clean gates: the L1.6 Holm-bar fence reading `m=0 [REFUSED]` for four days, four
`max_audit` checks silently out of the CHECKS list, and 61 failing tests. Convention demonstrably
does not hold across seats, so the checks live in a tracked script every seat runs identically.

These tests assert the STRUCTURE that makes it a gate rather than a suggestion: the cheap
collection check is present, it runs BEFORE the expensive suite, and the script actually fails
when a step fails. A gate that exits 0 whatever happened is the stale-green failure with extra
steps -- this desk has shipped that exact defect (`ruff | tail`, which exits 0 whatever ruff
found), which is why the exit path is asserted rather than assumed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
GATES = ROOT / "ops/gates.sh"
HOOK = ROOT / "ops/githooks/pre-push"


class TestTheScriptExists:
    def test_both_files_are_present_and_executable(self) -> None:
        for p in (GATES, HOOK):
            assert p.exists(), f"{p.relative_to(ROOT)} is missing"
            assert p.stat().st_mode & 0o111, f"{p.relative_to(ROOT)} is not executable"

    def test_the_hook_delegates_rather_than_duplicating_the_checks(self) -> None:
        """Two copies of the gate list drift, and the copy nobody runs is the one that rots."""
        src = HOOK.read_text("utf-8")
        assert "ops/gates.sh" in src
        assert "ruff" not in src, "the hook must not carry its own copy of the checks"


class TestTheOrderingIsTheValue:
    def test_collection_is_a_step(self) -> None:
        assert "--co" in GATES.read_text("utf-8"), (
            "collection is the gate that catches a dropped name; ruff does not resolve names and "
            "mypy's `files` excludes tests/")

    def test_collection_runs_BEFORE_the_full_suite(self) -> None:
        """8 seconds against 7200. Discovering a collection break last is the whole defect."""
        src = GATES.read_text("utf-8")
        co = src.index("--co")
        full = src.index("--cov=libs")
        assert co < full, "the cheap gate must run first or nobody gets its benefit"

    def test_the_expensive_suite_is_opt_in(self) -> None:
        """A 60-80 minute pre-push hook gets bypassed within a day, and a routinely bypassed gate
        is worse than none because everyone believes it ran."""
        assert "--full" in GATES.read_text("utf-8")


class TestItActuallyFails:
    def test_a_failing_step_makes_the_script_exit_nonzero(self, tmp_path: Path) -> None:
        """THE ONE THAT MATTERS. `ruff check . | tail` exits 0 whatever ruff found -- this desk
        has shipped that defect, so the exit path is proved rather than assumed."""
        src = GATES.read_text("utf-8").replace(
            '$PY -m ruff check .', 'false')
        fake = tmp_path / "gates.sh"
        fake.write_text(src, "utf-8")
        fake.chmod(0o755)
        r = subprocess.run(["bash", str(fake)], cwd=ROOT, capture_output=True, text=True,
                           timeout=600)
        assert r.returncode != 0, "a red step must make the whole gate red"
        assert "Do not push" in r.stdout

    @pytest.mark.timeout(900)
    def test_the_real_gate_is_green_on_this_tree(self) -> None:
        """Guard the guard: a script that can only fail proves nothing about the tree."""
        r = subprocess.run(["bash", str(GATES)], cwd=ROOT, capture_output=True, text=True,
                           timeout=900)
        assert r.returncode == 0, f"gates are RED on this tree:\n{r.stdout[-3000:]}"
        assert "all green" in r.stdout
