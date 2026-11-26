"""Box state onto claude/box-state (Audit route C, 2026-11-26): the byte-pinned fence, the loop
stage and the door. Real git throughout."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import protect  # noqa: E402
from ops.box_git import state_fence as F  # noqa: E402
from ops.box_git import state_publish as P  # noqa: E402

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"


def _g(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                          text=True).stdout.strip()


def _runner(repo: Path):
    def git(args):
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                           env={"GIT_AUTHOR_NAME": "b", "GIT_AUTHOR_EMAIL": "b@x",
                                "GIT_COMMITTER_NAME": "b", "GIT_COMMITTER_EMAIL": "b@x",
                                "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo)})
        return r.returncode, r.stdout
    return git


@pytest.fixture()
def world(tmp_path):
    """(box work tree, forge bare, LIVE tip)."""
    box = tmp_path / "box"
    box.mkdir()
    _g(box, "init", "-q", "-b", LIVE)
    _g(box, "config", "user.email", "t@x")
    _g(box, "config", "user.name", "t")
    (box / "libs").mkdir()
    (box / "libs" / "a.py").write_text("x = 1\n")
    (box / "desks/mt5/data").mkdir(parents=True)
    (box / "desks/mt5/data/old.json").write_text("{}\n")
    _g(box, "add", "-A")
    _g(box, "commit", "-q", "-m", "live")
    live = _g(box, "rev-parse", "HEAD")
    bare = tmp_path / "forge.git"
    _g(tmp_path, "clone", "-q", "--bare", str(box), str(bare))
    return box, bare, live


def _state_commit(box: Path, live: str, files: dict[str, str | None], parents=None) -> str:
    _g(box, "checkout", "-q", "--detach", live)
    for rel, body in files.items():
        p = box / rel
        if body is None:
            _g(box, "rm", "-q", rel)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        _g(box, "add", rel)
    tree = _g(box, "write-tree")
    args = ["commit-tree", tree, "-m", "state"]
    for par in parents or [live]:
        args += ["-p", par]
    c = _g(box, *args)
    _g(box, "reset", "-q", "--hard", live)
    return c


def _fence(box: Path, c: str, live: str) -> list[str]:
    return F.refusals(_runner(box), c, live)


def test_a_state_only_commit_on_the_live_tip_passes(world):
    box, _bare, live = world
    c = _state_commit(box, live, {"desks/mt5/data/STATE.json": "{}\n", "reports/r.md": "r\n"})
    assert _fence(box, c, live) == []


@pytest.mark.parametrize("files", [{"libs/a.py": "x = 2\n"}, {"desks/mt5/data/run.py": "1\n"},
                                   {"desks/mt5/data/GATE_KILL.json": "{}\n"},
                                   {"desks/mt5/data/ADOPT_CLEARS.jsonl": "{}\n"},
                                   {".gitignore": "x\n"}])
def test_a_code_switch_governed_or_ignore_path_is_refused(world, files):
    box, _bare, live = world
    c = _state_commit(box, live, files)
    assert _fence(box, c, live)


def test_a_deletion_is_refused(world):
    box, _bare, live = world
    c = _state_commit(box, live, {"desks/mt5/data/old.json": None})
    assert any("status D" in r for r in _fence(box, c, live))


def test_a_two_parent_commit_is_refused(world):
    box, _bare, live = world
    other = _state_commit(box, live, {"reports/x.md": "x\n"})
    c = _state_commit(box, live, {"reports/y.md": "y\n"}, parents=[live, other])
    assert _fence(box, c, live) == ["2 parents: exactly one is allowed"]


def test_a_stale_parent_is_refused(world):
    box, _bare, live = world
    c = _state_commit(box, live, {"reports/y.md": "y\n"})
    newer = _state_commit(box, live, {"reports/z.md": "z\n"})
    assert _fence(box, c, newer)[0].startswith("stale parent")


def test_publishable_pins():
    assert F.publishable("desks/mt5/reports/HEADLINE.json")
    assert F.publishable("context/decision_journal.jsonl")
    for bad in ("desks/mt5/reports/x.py", "data/secrets/k.json", "libs/x.json", "../data/x",
                "desks/mt5/data/IMMUTABLE_MANIFEST.json", "desks/mt5/data/TRADING_HALT.json"):
        assert not F.publishable(bad), bad


def _bundle(box: Path, c: str, live: str, outbox: Path) -> None:
    outbox.mkdir(exist_ok=True)
    _g(box, "update-ref", P.PENDING_REF, c)
    _g(box, "bundle", "create", str(outbox / P.BUNDLE), P.PENDING_REF, f"^{live}")


def _publish(bare: Path, outbox: Path, status: Path) -> str:
    git = _runner(bare)

    def push(sha, ref):
        return git(["update-ref", ref, sha])  # stands in for the forge push (door tested below)

    def remote_tip(ref):
        rc, out = git(["rev-parse", "--verify", "-q", ref])
        return out.strip() if rc == 0 and out.strip() else None

    return P.publish(outbox, status, git=git, push=push, remote_tip=remote_tip, live=LIVE)


def test_the_stage_publishes_then_fast_forwards_and_never_touches_live(world, tmp_path):
    box, bare, live = world
    outbox, status = tmp_path / "outbox", tmp_path / "STATE_PUBLISH.json"
    c1 = _state_commit(box, live, {"desks/mt5/reports/A.json": "1\n"})
    _bundle(box, c1, live, outbox)
    assert "published" in _publish(bare, outbox, status)
    assert _g(bare, "rev-parse", f"refs/heads/{P.BRANCH}") == c1
    c2 = _state_commit(box, live, {"desks/mt5/reports/A.json": "2\n"})
    _bundle(box, c2, live, outbox)
    assert "published" in _publish(bare, outbox, status)
    tip = _g(bare, "rev-parse", f"refs/heads/{P.BRANCH}")
    assert _g(bare, "rev-parse", f"{tip}^") == c1                         # a fast-forward
    assert _g(bare, "rev-parse", f"{tip}^{{tree}}") == _g(bare, "rev-parse", f"{c2}^{{tree}}")
    assert _g(bare, "rev-parse", f"refs/heads/{LIVE}") == live           # LIVE untouched
    assert _g(bare, "log", "-1", "--format=%s", tip) == "state"          # the box's own subject
    assert f"Box-State-Commit: {c2}" in _g(bare, "log", "-1", "--format=%B", tip)
    assert (outbox / "done" / "last.bundle").is_file() and not (outbox / P.BUNDLE).exists()
    doc = json.loads(status.read_text())
    assert doc["last_ok"]["commit"] == c2 and doc["last_attempt"]["ok"]


def test_a_refused_bundle_is_kept_with_its_reasons_and_nothing_moves(world, tmp_path):
    box, bare, live = world
    outbox, status = tmp_path / "outbox", tmp_path / "STATE_PUBLISH.json"
    c = _state_commit(box, live, {"libs/a.py": "x = 3\n"})
    _bundle(box, c, live, outbox)
    assert "REFUSED" in _publish(bare, outbox, status)
    assert subprocess.run(["git", "-C", str(bare), "rev-parse", "--verify", "-q",
                           f"refs/heads/{P.BRANCH}"], capture_output=True).returncode != 0
    why = next((outbox / "refused").glob("*.why.txt")).read_text()
    assert "libs/a.py" in why and next((outbox / "refused").glob("*.bundle"))
    assert json.loads(status.read_text())["last_ok"] is None


def test_the_door_refuses_a_non_fast_forward_of_box_state():
    ref = f"refs/heads/{P.BRANCH}"
    v = protect.decide("a" * 40, "b" * 40, ref, "thread", lambda a, b: False)
    assert not v.ok and "fast-forward" in v.why
    assert protect.decide("a" * 40, "b" * 40, ref, "thread", lambda a, b: True).ok
    assert not protect.decide("a" * 40, protect.ZERO, ref, "thread", lambda a, b: True).ok


def test_state_fence_is_byte_pinned_by_the_immutable_manifest():
    src = (ROOT / "scripts" / "check_immutable_evaluator.py").read_text(encoding="utf-8")
    assert '"ops/box_git/state_fence.py"' in src


def test_a_newer_hand_over_never_replaces_the_bundle_being_judged(world, tmp_path):
    """Audit nit: the stage takes pending.bundle under a private name before judging it, so a
    bundle ShadowSync renames in mid-pass waits for the next pass instead of being filed away."""
    box, bare, live = world
    outbox, status = tmp_path / "outbox", tmp_path / "STATE_PUBLISH.json"
    c1 = _state_commit(box, live, {"desks/mt5/reports/A.json": "1\n"})
    _bundle(box, c1, live, outbox)
    c2 = _state_commit(box, live, {"desks/mt5/reports/A.json": "2\n"})
    git = _runner(bare)
    real = git

    def git_with_handover(args):
        if args[:2] == ["bundle", "list-heads"]:          # ShadowSync renames a newer one in
            _bundle(box, c2, live, outbox)
        return real(args)

    def push(sha, ref):
        return git(["update-ref", ref, sha])

    def remote_tip(ref):
        rc, out = git(["rev-parse", "--verify", "-q", ref])
        return out.strip() if rc == 0 and out.strip() else None

    out = P.publish(outbox, status, git=git_with_handover, push=push, remote_tip=remote_tip,
                    live=LIVE)
    assert "published" in out and _g(bare, "rev-parse", f"refs/heads/{P.BRANCH}") == c1
    assert (outbox / P.BUNDLE).is_file() and not (outbox / P.INFLIGHT).exists()
    assert "published" in _publish(bare, outbox, status)                 # the next pass
    tip = _g(bare, "rev-parse", f"refs/heads/{P.BRANCH}")
    assert _g(bare, "rev-parse", f"{tip}^{{tree}}") == _g(bare, "rev-parse", f"{c2}^{{tree}}")
