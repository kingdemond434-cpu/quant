"""THE DEPLOY GATE MUST NOT EXECUTE FETCHED CODE FROM THE LIVE TREE (R0246).

deploy/pull_deploy.sh runs from cron every 10 minutes on the box that owns
data/secrets/binance_live.json. It used to `git merge --ff-only FETCH_HEAD` and only THEN run
run_ci.py -- from the already-merged tree. So the control the desk counted on as its safety gate
was itself the first attacker-controlled thing to execute, and two more paths inherited the same
inversion on the following tick (the pre-push hook this script copies into .git/hooks and chmods
+x, and reconstitute_cron.sh installing an arbitrary crontab on a manifest-hash change).

THESE ARE END-TO-END TESTS AGAINST A REAL SCRATCH REPO, not string matches on the source. The
property under test is an ORDERING between two processes, and the only honest way to test an
ordering is to observe it: the fake gate records the LIVE tree's HEAD at the moment it executes,
which is exactly the observation the old code could never have satisfied.

This path had no end-to-end coverage of any kind before this file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "deploy/pull_deploy.sh"

#: Stands in for scripts/run_ci.py inside the fetched commit. It is the ATTACKER-CONTROLLED file
#: in this story, so it does what a payload would: records what it could see when it ran. Verdict
#: is keyed off a file tracked in the same commit, so a test can ship a red or green upstream.
_FAKE_CI = '''\
import json, os, subprocess, sys
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
live = os.getcwd()          # the shell cd'd to the LIVE root before invoking us
def head(d):
    try:
        return subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=False).stdout.strip()
    except OSError:
        return "?"
with open(os.path.join(live, "gate_observations.jsonl"), "a") as fh:
    fh.write(json.dumps({"ran_from": here, "live_head": head(live),
                         "gate_head": head(here), "argv": sys.argv[1:]}) + "\\n")
sys.exit(0 if os.path.exists(os.path.join(here, "CI_GREEN")) else 1)
'''


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout.strip()


@pytest.fixture
def desk(tmp_path):
    """An origin + a 'live box' clone, with the real pull_deploy.sh installed."""
    if not shutil.which("git"):
        pytest.skip("git unavailable")
    origin, box = tmp_path / "origin", tmp_path / "box"
    src = tmp_path / "src"
    for d in (src,):
        d.mkdir()
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True,
                   capture_output=True)
    subprocess.run(["git", "init", "-b", "main", str(src)], check=True, capture_output=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(src, "config", k, v)
    (src / "scripts").mkdir()
    (src / "scripts/run_ci.py").write_text(_FAKE_CI, "utf-8")
    (src / "CI_GREEN").write_text("", "utf-8")
    (src / "payload.txt").write_text("original", "utf-8")
    _git(src, "add", "-A")
    _git(src, "commit", "-m", "base")
    _git(src, "remote", "add", "origin", str(origin))
    _git(src, "push", "-u", "origin", "main")
    subprocess.run(["git", "clone", str(origin), str(box)], check=True, capture_output=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(box, "config", k, v)
    (box / "deploy").mkdir()
    shutil.copy(_SCRIPT, box / "deploy/pull_deploy.sh")
    return {"origin": origin, "box": box, "src": src}


def _push(desk, *, green: bool, payload: str = "upstream") -> str:
    src = desk["src"]
    (src / "payload.txt").write_text(payload, "utf-8")
    if green:
        (src / "CI_GREEN").write_text("", "utf-8")
    elif (src / "CI_GREEN").exists():
        (src / "CI_GREEN").unlink()
    _git(src, "add", "-A")
    _git(src, "commit", "-m", payload)
    _git(src, "push", "origin", "main")
    return _git(src, "rev-parse", "HEAD")


def _run(desk) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["sh", "deploy/pull_deploy.sh", "--branch", "main"],
                          cwd=str(desk["box"]), capture_output=True, text=True, check=False,
                          env=env, timeout=120)


def _observations(desk) -> list[dict]:
    p = desk["box"] / "gate_observations.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()]


def _state(desk) -> dict:
    return json.loads((desk["box"] / "data/pull_deploy_state.json").read_text("utf-8"))


class TestTheLiveTreeIsNeverAheadOfTheGate:
    def test_fetched_code_executes_while_the_live_tree_is_still_on_the_old_commit(self, desk):
        """THE CORE PROPERTY. The old order made this assertion impossible to satisfy."""
        old = _git(desk["box"], "rev-parse", "HEAD")
        new = _push(desk, green=True)
        _run(desk)
        obs = _observations(desk)
        assert obs, "the gate never ran -- the test proves nothing"
        assert obs[0]["live_head"] == old, (
            "the live tree had ALREADY been fast-forwarded when the fetched commit executed -- "
            "this is exactly the inversion R0246 reported")
        assert obs[0]["gate_head"] == new, "the gate must test the FETCHED commit, not the old one"

    def test_the_gate_runs_from_a_worktree_not_the_live_tree(self, desk):
        _push(desk, green=True)
        _run(desk)
        obs = _observations(desk)
        assert obs and obs[0]["ran_from"] != str(desk["box"].resolve()), (
            f"gate executed from the live tree: {obs[0]['ran_from']}")

    def test_the_strict_lock_verdict_is_still_demanded(self, desk):
        """A lock-skip exits 0 for organs; for a deploy decision that is not green (R0145)."""
        _push(desk, green=True)
        _run(desk)
        assert _observations(desk)[0]["argv"] == ["--fail-on-lock"]


class TestRedUpstreamNeverReachesTheBox:
    def test_a_red_commit_is_not_merged(self, desk):
        old = _git(desk["box"], "rev-parse", "HEAD")
        _push(desk, green=False, payload="malicious")
        r = _run(desk)
        assert _git(desk["box"], "rev-parse", "HEAD") == old, (
            "a commit that failed its own gate reached the live tree")
        assert r.returncode == 1
        assert (desk["box"] / "payload.txt").read_text("utf-8") == "original"

    def test_a_red_commit_records_that_the_tree_was_untouched(self, desk):
        _push(desk, green=False)
        _run(desk)
        st = _state(desk)
        assert st["status"] == "ci-red"
        assert "untouched" in st["note"]

    def test_a_green_commit_is_merged(self, desk):
        new = _push(desk, green=True)
        r = _run(desk)
        assert _git(desk["box"], "rev-parse", "HEAD") == new, r.stdout + r.stderr
        assert (desk["box"] / "payload.txt").read_text("utf-8") == "upstream"
        assert _state(desk)["status"].startswith("deployed")

    def test_a_red_tick_does_not_wedge_the_next_green_one(self, desk):
        """A leaked worktree would make every later tick fail at `git worktree add`."""
        _push(desk, green=False)
        _run(desk)
        new = _push(desk, green=True, payload="recovered")
        r = _run(desk)
        assert _git(desk["box"], "rev-parse", "HEAD") == new, (
            f"the box could not recover after a red tick: {r.stdout}{r.stderr}")


class TestTheGateLeavesNothingBehind:
    def test_the_worktree_is_removed_after_a_green_run(self, desk):
        _push(desk, green=True)
        _run(desk)
        assert not (desk["box"].parent / ".pull_deploy_gate").exists()
        assert "pull_deploy_gate" not in _git(desk["box"], "worktree", "list")

    def test_the_worktree_is_removed_after_a_red_run(self, desk):
        _push(desk, green=False)
        _run(desk)
        assert not (desk["box"].parent / ".pull_deploy_gate").exists()
        assert "pull_deploy_gate" not in _git(desk["box"], "worktree", "list")


class TestTheDestructiveRevertIsGoneByConstruction:
    def test_the_script_can_no_longer_reset_hard(self):
        """2026-07-31 (R0144): an unconditional revert destroyed a session's only copy of its work.

        Guarding the revert was the old fix; not having one is the better one, so this pins the
        stronger property -- the dangerous verb is absent from the file entirely.
        """
        code = [ln for ln in _SCRIPT.read_text("utf-8").splitlines()
                if not ln.lstrip().startswith("#")]
        assert not [ln for ln in code if "reset --hard" in ln], (
            "the verb is back in EXECUTABLE code (prose about its removal is fine)")

    def test_the_gate_precedes_the_merge_in_the_source(self):
        """Cheap structural backstop for the ordering the end-to-end tests observe."""
        src = _SCRIPT.read_text("utf-8")
        assert src.index("run_ci.py\" --fail-on-lock") < src.index('git merge --ff-only "$NEW"')
