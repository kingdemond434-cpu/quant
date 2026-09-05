"""THE LAUNDER DETECTOR IS ITSELF UNDER TEST -- with a POSITIVE CONTROL, not just silences.

`scripts/check_sync_launder.py` exists because two prior defences are LIST-shaped: the pre-commit
guard is future-tense, and the content fence restores only files somebody had already added to a
hand-maintained map. `desks/mt5/research/regime_monitor.py` lost 122 authored lines to a sync
commit and sat dead in HEAD for two days precisely because it was in no list.

A detector for that class is worthless if it has only ever been observed returning nothing. The
first test below BUILDS the measured 2026-08-26 launder in a scratch repo -- authored work, then a
sync commit reverting it -- and asserts the tool names it. The second builds the shape that must
NOT fire: a legitimate rewrite on top of a sync, where restoring the parent blob would destroy
newer work. Precision matters more than recall here; the guard's own quarantine comment records a
sync shipping a legitimately NEWER file through the same pipe that trampled an older one an hour
before.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_TOOL = _ROOT / "scripts" / "check_sync_launder.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _commit(repo: Path, rel: str, body: str, subject: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, "utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", subject)


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", str(_TOOL), "--root", str(repo)], cwd=repo,
                          capture_output=True, text=True, check=False)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    # `--root` is what makes this testable: the tool resolves ROOT from its own __file__, and a
    # `cwd=` does NOT redirect that -- the first version of this test silently scanned the REAL
    # repo and "passed" on nine unrelated production rows.
    _commit(r, "seed.txt", "seed\n", "seed")
    return r


_AUTHORED = "\n".join(f"AUTHORED_LINE_{i} = 'real desk work'" for i in range(40)) + "\n"
_STALE = "STALE = 'the Dell copy'\n"


def test_the_measured_launder_is_named_and_healable(repo: Path) -> None:
    """POSITIVE CONTROL: authored work, then a sync commit reverting it wholesale."""
    _commit(repo, "desks/mt5/research/organ.py", _AUTHORED, "GAP 130 fixed: real work")
    _commit(repo, "desks/mt5/research/organ.py", _STALE, "mt5 desk hourly sync 2026-08-26_0102")

    out = _run(repo)
    assert out.returncode == 1, f"the detector stayed silent on a real launder:\n{out.stdout}"
    assert "desks/mt5/research/organ.py" in out.stdout
    assert "CLEAN-REVERT" in out.stdout, "nothing was authored on top -- this is the healable half"

    healed = subprocess.run(["python3", str(_TOOL), "--heal", "--root", str(repo)], cwd=repo,
                            capture_output=True, text=True, check=False)
    assert "healed" in healed.stdout
    assert (repo / "desks/mt5/research/organ.py").read_text("utf-8") == _AUTHORED
    quarantine = list((repo / "data" / "sync_refused").rglob("organ.py"))
    assert quarantine, ("the refused bytes must survive -- a restore that cannot be "
                        "undone is itself a launder")


def test_a_rewrite_on_top_is_REVIEW_and_is_never_auto_healed(repo: Path) -> None:
    """The precision half: restoring the parent would overwrite work authored AFTER the sync."""
    _commit(repo, "desks/mt5/research/organ.py", _AUTHORED, "GAP 130 fixed: real work")
    _commit(repo, "desks/mt5/research/organ.py", _STALE, "mt5 desk hourly sync 2026-08-26_0102")
    newer = _STALE + "\n".join(f"NEWER_LINE_{i} = 'authored after the sync'" for i in range(40))
    _commit(repo, "desks/mt5/research/organ.py", newer, "genuine rewrite on top")

    out = _run(repo)
    assert "REVIEW" in out.stdout
    assert "CLEAN-REVERT" not in out.stdout
    assert out.returncode == 0, "a row nobody can close mechanically must not hold the gate red"

    subprocess.run(["python3", str(_TOOL), "--heal", "--root", str(repo)], cwd=repo,
                   capture_output=True, text=True, check=False)
    assert (repo / "desks/mt5/research/organ.py").read_text("utf-8") == newer, \
        "--heal overwrote a post-sync rewrite: the tool became the defect it detects"


def test_a_clean_history_reports_nothing(repo: Path) -> None:
    """The silence has to be earned: no sync commit, no residue."""
    _commit(repo, "desks/mt5/research/organ.py", _AUTHORED, "GAP 130 fixed: real work")
    out = _run(repo)
    assert out.returncode == 0
    assert "no launder residue" in out.stdout
