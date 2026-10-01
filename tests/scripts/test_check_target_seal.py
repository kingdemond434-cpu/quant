"""The adopter refuses a fetched commit whose judge is not sealed.

Measured 2026-09-30: origin carried a broken seal for about two minutes (4678fe4f at 515d665e,
until fc6c34e5 re-signed it), and MT5-AdoptRelease checked neither CI nor the seal. These pin
the commit-level check and its wiring into both adoption scripts.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "desks" / "mt5" / "scripts"
_spec = importlib.util.spec_from_file_location("check_target_seal",
                                               ROOT / "scripts" / "check_target_seal.py")
assert _spec and _spec.loader
cts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cts)

EVAL_SRC = 'IMMUTABLE: tuple[str, ...] = (\n    "judge.py",\n)\n'


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          check=True).stdout.strip()


def _h(text: str) -> str:
    return hashlib.sha256(text.encode().replace(b"\r\n", b"\n")).hexdigest()[:16]


def _repo(tmp_path: Path, judge: str, signed: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "desks" / "mt5" / "data").mkdir(parents=True)
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "scripts" / "check_immutable_evaluator.py").write_text(EVAL_SRC, "utf-8")
    (repo / "judge.py").write_text(judge, "utf-8")
    (repo / "desks" / "mt5" / "data" / "IMMUTABLE_MANIFEST.json").write_text(
        json.dumps({"files": {"judge.py": _h(signed)}}), "utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c")
    return repo


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
@pytest.mark.parametrize("judge,signed,rc", [
    ("x = 1\n", "x = 1\n", 0),
    ("x = 1\r\n", "x = 1\n", 0),          # CRLF is the same content, as the evaluator signs it
    ("x = 2\n", "x = 1\n", 1),            # an edited judge without a re-sign
])
def test_a_commit_is_judged_against_its_own_manifest(tmp_path: Path, monkeypatch,
                                                    judge: str, signed: str, rc: int) -> None:
    repo = _repo(tmp_path, judge, signed)
    monkeypatch.setattr(cts, "ROOT", repo)
    got, reasons = cts.judge(_git(repo, "rev-parse", "HEAD"))
    assert got == rc, reasons


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_a_target_cannot_leave_the_fence_by_deleting_its_name(tmp_path: Path,
                                                             monkeypatch) -> None:
    repo = _repo(tmp_path, "x = 1\n", "x = 1\n")
    # The target edits the judge AND drops it from its own frozen list; this checkout's list
    # still names it, so the union keeps it judged.
    (repo / "judge.py").write_text("x = 2\n", "utf-8")
    (repo / "scripts" / "check_immutable_evaluator.py").write_text(
        "IMMUTABLE: tuple[str, ...] = ()\n", "utf-8")
    _git(repo, "commit", "-qam", "escape")
    target = _git(repo, "rev-parse", "HEAD")
    (repo / "scripts" / "check_immutable_evaluator.py").write_text(EVAL_SRC, "utf-8")
    monkeypatch.setattr(cts, "ROOT", repo)
    rc, reasons = cts.judge(target)
    assert rc == 1 and any("judge.py" in r for r in reasons)


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_an_unreadable_target_is_unmeasured_never_sealed(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path, "x = 1\n", "x = 1\n")
    monkeypatch.setattr(cts, "ROOT", repo)
    rc, _ = cts.judge("0" * 40)
    assert rc == 2


def test_this_tree_reads_the_real_frozen_list() -> None:
    names = cts.immutable_list((ROOT / "scripts" / "check_immutable_evaluator.py").read_bytes())
    assert "desks/mt5/scripts/external_gauntlet.py" in names
    assert "desks/mt5/research/promoter.py" in names


def test_adopt_release_refuses_before_it_writes() -> None:
    src = (SCRIPTS / "Adopt-Release.ps1").read_text("utf-8-sig")
    gate = src.index("check_target_seal.py")
    assert src.index("$target = (Invoke-Git @(\"rev-parse\", \"FETCH_HEAD\"))") < gate
    # Before the first write the adoption makes: the box's own state commit in step 1.
    assert gate < src.index("# ---- 1. THE BOX'S OWN UNCOMMITTED STATE")
    block = src[gate:src.index("# ---- 1. THE BOX'S OWN UNCOMMITTED STATE")]
    assert "$sealCheck $target" in block
    assert "exit 7" in block


def test_adopt_and_seal_reports_the_refusal_and_keeps_the_release() -> None:
    src = (SCRIPTS / "Adopt-And-Seal.ps1").read_text("utf-8-sig")
    at = src.index("if ($adoptExit -eq 7)")
    assert src.index("$adoptExit = $LASTEXITCODE") < at < src.index("if ($adoptExit -ne 0)")
    assert 'Done 7 "target-unsealed"' in src[at:at + 800]
