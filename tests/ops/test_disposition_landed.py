"""R0742: a row closed as `implemented` must cite a commit that is in the branch.

Every case is built as a REAL git repo rather than by monkeypatching the git calls, because the
subject IS the git topology -- a mocked `merge-base` would prove only that the mock was consistent
with itself, which is how a detector ends up validated on its silences alone.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from libs.ops.disposition_landed import LEDGER_REL, census


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs/research").mkdir(parents=True)
    env = {"GIT_CONFIG_GLOBAL": str(tmp_path / "gc"), "GIT_CONFIG_NOSYSTEM": "1",
           "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}

    def git(*a: str) -> None:
        subprocess.run(["git", *a], cwd=root, env=env, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    _ledger(root, [])
    git("add", "-A")
    git("commit", "-qm", "init")
    return root


def _git(root: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def _run(root: Path, *a: str) -> None:
    subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)


def _ledger(root: Path, rows: list[dict]) -> None:
    (root / LEDGER_REL).write_text(json.dumps({"recommendations": rows}, indent=1), "utf-8")


def test_a_commit_on_an_unmerged_branch_is_stranded_and_the_branch_is_named(tmp_path) -> None:
    """THE POSITIVE CONTROL. A detector never shown to CONVICT has only had its silences observed,
    and this is the exact shape measured live: the ledger merged, the code did not."""
    root = _repo(tmp_path)
    _run(root, "checkout", "-qb", "side")
    (root / "fix.py").write_text("# the fix\n", "utf-8")
    _run(root, "add", "fix.py")
    _run(root, "commit", "-qm", "the fix")
    sha = _git(root, "rev-parse", "HEAD")
    _run(root, "checkout", "-q", "main")
    # The ledger disposition lands on main -- as it really does, being a file every session touches.
    _ledger(root, [{"id": "R0001", "status": "implemented", "commit": sha}])
    _run(root, "commit", "-qam", "dispose")

    cen = census(root, ref="main")
    assert cen.status == "STRANDED"
    assert [s.id for s in cen.stranded] == ["R0001"]
    assert "side" in cen.stranded[0].branches, "the repair must NAME the branch that holds it"
    assert cen.stranded[0].repair == "git merge --ff-only side"
    assert cen.n_resolved == 1 and cen.n_unresolvable == 0

    # ...and it clears by LANDING the work, never by editing the row.
    _run(root, "merge", "--no-edit", "-q", "side")
    assert census(root, ref="main").status == "OK"


def test_a_landed_commit_is_not_flagged(tmp_path) -> None:
    root = _repo(tmp_path)
    (root / "fix.py").write_text("# fix\n", "utf-8")
    _run(root, "add", "fix.py")
    _run(root, "commit", "-qm", "fix")
    sha = _git(root, "rev-parse", "HEAD")
    _ledger(root, [{"id": "R0001", "status": "implemented", "commit": sha}])
    cen = census(root, ref="main")
    assert cen.status == "OK" and not cen.stranded and cen.n_resolved == 1


def test_an_unresolvable_sha_is_counted_never_convicted(tmp_path) -> None:
    """L1.60: a sha this clone cannot see is not a stranded commit. On a shallow CI clone most
    history is simply absent, and reporting that as hundreds of stranded rows is a fence crying
    wolf about its own environment -- but it must never vanish silently either."""
    root = _repo(tmp_path)
    _ledger(root, [{"id": "R0001", "status": "implemented", "commit": "0" * 40}])
    cen = census(root, ref="main")
    assert cen.n_unresolvable == 1
    assert cen.unresolvable_ids == ("R0001",)
    assert not cen.stranded
    # ...and with nothing resolved there is no evidence either way.
    assert cen.status == "UNMEASURED", "resolving nothing may not read as a clean board (L1.28a)"


def test_rows_that_claim_nothing_are_out_of_scope(tmp_path) -> None:
    """Only `implemented` asserts code is in the tree. An open or rejected row claims nothing, and
    a row with no sha cannot be checked -- neither may inflate the denominator (L1.57)."""
    root = _repo(tmp_path)
    _ledger(root, [
        {"id": "R0001", "status": "open", "commit": None},
        {"id": "R0002", "status": "rejected", "commit": None},
        {"id": "R0003", "status": "implemented", "commit": None},
        {"id": "R0004", "status": "implemented", "commit": "short"},
    ])
    cen = census(root, ref="main")
    assert cen.n_implemented == 0 and cen.n_resolved == 0
    assert cen.status == "UNMEASURED"


def test_an_unreadable_ledger_is_unmeasured(tmp_path) -> None:
    root = _repo(tmp_path)
    (root / LEDGER_REL).write_text("{not json", "utf-8")
    cen = census(root, ref="main")
    assert cen.status == "UNMEASURED" and cen.notes


def test_a_ref_that_does_not_resolve_is_unmeasured(tmp_path) -> None:
    """A fence measuring a branch that does not exist has measured nothing, and must say so
    rather than reporting every row clean against a ref it never found."""
    root = _repo(tmp_path)
    _ledger(root, [{"id": "R0001", "status": "implemented", "commit": "0" * 40}])
    cen = census(root, ref="no-such-branch")
    assert cen.status == "UNMEASURED" and cen.notes


def test_scripts_check_disposition_landed_EXITS_2_on_a_stranded_row(tmp_path) -> None:
    """The exit code IS the interface -- the cron line reads nothing else, and a fence that finds
    the defect and exits 0 is decoration.

    Driven as a subprocess against a planted repo rather than by importing main(), and it asserts
    BOTH ends: red on a stranded row, green once the work lands. A detector shown only to stay
    quiet has not been validated.
    """
    import os
    import sys

    root = _repo(tmp_path)
    _run(root, "checkout", "-qb", "side")
    (root / "fix.py").write_text("# the fix\n", "utf-8")
    _run(root, "add", "fix.py")
    _run(root, "commit", "-qm", "the fix")
    sha = _git(root, "rev-parse", "HEAD")
    _run(root, "checkout", "-q", "main")
    _ledger(root, [{"id": "R0001", "status": "implemented", "commit": sha}])
    _run(root, "commit", "-qam", "dispose")

    fence = Path(__file__).resolve().parents[2] / "scripts/check_disposition_landed.py"
    env = {**os.environ, "QUANT_LAW_GUARD": "off"}       # the guard is not what is under test
    red = subprocess.run([sys.executable, str(fence), "--root", str(root), "--ref", "main"],
                         env=env, capture_output=True, text=True)
    assert red.returncode == 2, red.stdout + red.stderr
    assert "STRANDED" in red.stdout
    assert "git merge --ff-only side" in red.stdout, "the repair must be printed, not just named"

    _run(root, "merge", "--no-edit", "-q", "side")
    green = subprocess.run([sys.executable, str(fence), "--root", str(root), "--ref", "main"],
                           env=env, capture_output=True, text=True)
    assert green.returncode == 0, green.stdout + green.stderr
    assert "OK" in green.stdout


def test_the_fence_refuses_to_pass_when_it_resolved_nothing(tmp_path) -> None:
    """L1.57 at the exit site: a pass over a zero denominator is vacuous and must be refused."""
    import os
    import sys

    root = _repo(tmp_path)
    _ledger(root, [{"id": "R0001", "status": "implemented", "commit": "0" * 40}])
    _run(root, "commit", "-qam", "dispose")
    fence = Path(__file__).resolve().parents[2] / "scripts/check_disposition_landed.py"
    r = subprocess.run([sys.executable, str(fence), "--root", str(root), "--ref", "main"],
                       env={**os.environ, "QUANT_LAW_GUARD": "off"}, capture_output=True, text=True)
    assert r.returncode != 0, "UNMEASURED may not exit 0 (L1.28a)"
    assert "UNMEASURED" in r.stdout
