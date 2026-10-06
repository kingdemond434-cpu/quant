"""A STATE-ONLY PUSH SKIPS THE CODE GATES; ANY CODE PATH, OR ANY DOUBT, RUNS THEM.

Post-merge audit of #181 (2026-10-06): `ops/githooks/pre-push` ran `ops/gates.sh` and the law gate
on the trading box's own state publications, so an unrelated red fence anywhere in the box's tree
refused the box's evidence. The skip is pinned here in both directions -- a hook that skipped a
code push would be a gate disarmed, which is worse than the stall it fixes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "ops" / "githooks" / "pre-push"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import push_scope  # noqa: E402

ZERO = "0" * 40


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def _commit(repo: Path, rel: str, body: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, "utf-8")
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "--no-verify", "-m", rel)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _commit(r, "desks/mt5/mt5desk/gateway.py", "x = 1\n")
    return r


def test_the_classifier_is_releases_minus_docs() -> None:
    assert push_scope.is_push_state("desks/mt5/data/gateway_state.json")
    assert push_scope.is_push_state("desks/mt5/reports/BOX_STATE_FLOW.json")
    assert push_scope.is_push_state("desks/mt5/gateway_state.json")          # a STATE_FILES entry
    assert not push_scope.is_push_state("desks/mt5/mt5desk/gateway.py")
    assert not push_scope.is_push_state("scripts/run_law_gate.py")
    # release.py calls docs/ state; the law fences read it, so a push of docs is judged.
    assert not push_scope.is_push_state("docs/LAWS.md")
    assert not push_scope.is_push_state("docs/desk_lessons.jsonl")


def test_a_state_only_push_is_state_only(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    tip = _commit(repo, "desks/mt5/data/sleeves.json", "{}\n")
    ok, why = push_scope.verdict(repo, [f"refs/heads/b {tip} refs/heads/b {base}"])
    assert ok, why


def test_one_code_path_runs_the_gate(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "desks/mt5/data/sleeves.json", "{}\n")
    tip = _commit(repo, "desks/mt5/mt5desk/gateway.py", "x = 2\n")
    ok, why = push_scope.verdict(repo, [f"refs/heads/b {tip} refs/heads/b {base}"])
    assert not ok and "gateway.py" in why


def test_doubt_runs_the_gate(repo: Path) -> None:
    tip = _git(repo, "rev-parse", "HEAD")
    assert push_scope.verdict(repo, [])[0] is False                         # no ref lines
    missing = "1" * 40                                                      # remote obj absent
    assert push_scope.verdict(repo, [f"refs/heads/b {tip} refs/heads/b {missing}"])[0] is False
    # A brand-new remote ref with no remote-tracking refs: every commit is new, and the root
    # commit carries code.
    assert push_scope.verdict(repo, [f"refs/heads/b {tip} refs/heads/b {ZERO}"])[0] is False


def _hook_sandbox(repo: Path) -> Path:
    """The real hook and push_scope.py, with gates.sh and the law gate stubbed to leave a marker
    and fail -- so 'skipped' and 'ran' are both observable."""
    (repo / "ops" / "githooks").mkdir(parents=True)
    shutil.copy(HOOK, repo / "ops" / "githooks" / "pre-push")
    (repo / "scripts").mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts" / "push_scope.py", repo / "scripts" / "push_scope.py")
    (repo / "scripts" / "run_law_gate.py").write_text(
        "import pathlib; pathlib.Path('LAW_RAN').write_text('1'); raise SystemExit(1)\n", "utf-8")
    gates = repo / "ops" / "gates.sh"
    gates.write_text("#!/usr/bin/env bash\ntouch \"$(git rev-parse --show-toplevel)/GATES_RAN\"\n"
                     "exit 1\n", "utf-8")
    gates.chmod(0o755)
    os.symlink(ROOT / "libs", repo / "libs")
    _git(repo, "add", "--", "ops", "scripts")
    _git(repo, "commit", "-q", "--no-verify", "-m", "hook")
    return repo / "ops" / "githooks" / "pre-push"


@pytest.mark.skipif(os.name == "nt", reason="symlinked libs/ and bash hook: POSIX sandbox")
def test_the_hook_skips_state_and_gates_code(repo: Path) -> None:
    hook = _hook_sandbox(repo)
    base = _git(repo, "rev-parse", "HEAD")
    tip = _commit(repo, "desks/mt5/reports/BOX_RELEASE_SEAL.json", "{}\n")
    r = subprocess.run(["bash", str(hook), "origin", "x"], cwd=repo, capture_output=True,
                       text=True, input=f"refs/heads/b {tip} refs/heads/b {base}\n", timeout=120)
    assert r.returncode == 0, r.stderr
    assert not (repo / "GATES_RAN").exists() and not (repo / "LAW_RAN").exists()

    code = _commit(repo, "desks/mt5/mt5desk/gateway.py", "x = 3\n")
    r = subprocess.run(["bash", str(hook), "origin", "x"], cwd=repo, capture_output=True,
                       text=True, input=f"refs/heads/b {code} refs/heads/b {tip}\n", timeout=120)
    assert r.returncode != 0
    assert (repo / "GATES_RAN").exists(), "a code push must run the gates"


def test_the_hook_keeps_its_interpreter_fallback() -> None:
    """The box has no venv: the 2026-10-01 fallback to the first python that starts must stay,
    and the scope check must run through that same interpreter, after it is chosen."""
    src = HOOK.read_text("utf-8")
    assert '.venv/Scripts/python.exe' in src and "for cand in python3 python" in src
    assert src.index("for cand in python3 python") < src.index("push_scope.py")
    assert src.index("push_scope.py") < src.index('"$ROOT/ops/gates.sh"')
    assert src.index("push_scope.py") < src.index("run_law_gate.py")


def test_every_verdict_is_recorded_with_a_running_tally(tmp_path: Path) -> None:
    """A skipped gate leaves evidence: the verdict, its reason and the skip/run tally."""
    import json

    rec = tmp_path / "data" / "push_scope.json"
    assert push_scope.record(rec, True, "state-only push: 3 path(s), all box state")
    assert push_scope.record(rec, False, "1 non-state path(s) in this push (e.g. libs/x.py)")
    assert push_scope.record(rec, True, "state-only push: 1 path(s), all box state")
    doc = json.loads(rec.read_text("utf-8"))
    assert doc["verdict"] == "SKIP_GATES" and doc["state_only"] is True
    assert doc["tally"] == {"skipped": 2, "gated": 1}
    assert "state-only" in doc["why"]


def test_a_corrupt_record_restarts_the_tally_and_an_unwritable_one_never_raises(
        tmp_path: Path) -> None:
    import json

    rec = tmp_path / "push_scope.json"
    rec.write_text("{not json", "utf-8")
    assert push_scope.record(rec, False, "push scope UNMEASURED -- running the full gate")
    assert json.loads(rec.read_text("utf-8"))["tally"] == {"skipped": 0, "gated": 1}
    blocker = tmp_path / "file"
    blocker.write_text("x", "utf-8")
    assert push_scope.record(blocker / "sub" / "push_scope.json", True, "x") is False


def test_the_record_is_gitignored_host_state() -> None:
    """Writing the record during a push must never dirty the tree that push is judging."""
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q",
                        str(push_scope.RECORD.relative_to(ROOT))], check=False)
    assert r.returncode == 0
