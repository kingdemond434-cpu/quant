"""The box inbox: a thread's packet becomes a branch, a PR and its comments, or is refused and kept.
Real git bundles against a real bare repository; the forge API is a recording fake."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import box_loop as L  # noqa: E402
from ops.box_git import inbox as I  # noqa: E402

LIVE = I.LIVE


def _g(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                          text=True).stdout.strip()


def _world(tmp: Path) -> tuple[Path, Path, str]:
    """(bare forge repo holding LIVE, a thread's clone, LIVE sha)."""
    work = tmp / "thread"
    work.mkdir()
    _g(work, "init", "-q", "-b", LIVE)
    _g(work, "config", "user.email", "t@x")
    _g(work, "config", "user.name", "t")
    (work / "a.txt").write_text("a\n")
    _g(work, "add", "a.txt")
    _g(work, "commit", "-q", "-m", "base")
    live = _g(work, "rev-parse", "HEAD")
    bare = tmp / "forge.git"
    _g(tmp, "clone", "-q", "--bare", str(work), str(bare))
    return bare, work, live


def _packet(tmp: Path, work: Path, live: str, branch: str, **extra: Any) -> tuple[str, Path]:
    _g(work, "checkout", "-q", "-b", branch.replace("/", "_"), live)
    (work / "b.txt").write_text(branch + "\n")
    _g(work, "add", "b.txt")
    _g(work, "commit", "-q", "-m", "work")
    head = _g(work, "rev-parse", "HEAD")
    _g(work, "branch", "-f", branch, head)
    box = tmp / "inbox"
    box.mkdir(exist_ok=True)
    _g(work, "bundle", "create", str(box / "p1.bundle"), f"{live}..{branch}")
    man = {"branch": branch, "head": head, "title": "t", "body": "b",
           "comments": ["ready for review"], **extra}
    (box / "p1.json").write_text(json.dumps(man))
    return head, box


class FakeForge:
    def __init__(self) -> None:
        self.prs: list[dict[str, Any]] = []
        self.comments: dict[int, list[dict[str, Any]]] = {}

    def __call__(self, method: str, path: str, body: Any) -> Any:
        if method == "GET" and "/pulls" in path:
            return self.prs
        if method == "POST" and path.endswith("/pulls"):
            pr = {"number": 7 + len(self.prs), "head": {"ref": body["head"]},
                  "base": {"ref": body["base"]}}
            self.prs.append(pr)
            return pr
        n = int(path.split("/issues/")[1].split("/")[0])
        if method == "GET":
            return self.comments.get(n, [])
        self.comments.setdefault(n, []).append({"body": body["body"]})
        return {}


def _git_for(bare: Path, pushes: list[tuple[str, str]], refuse: bool = False):
    def run(*args: str, push_as: str | None = None) -> tuple[int, str]:
        if push_as:
            assert push_as == "claude"
            if refuse:
                return 1, "box-git: REFUSED"
            pushes.append(args[1:])
            _g(bare, "update-ref", args[2], args[1])
            return 0, ""
        p = subprocess.run(["git", "-C", str(bare), *args], capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr
    return run


def test_a_packet_becomes_a_branch_a_pr_and_its_clear_once(tmp_path: Path) -> None:
    bare, work, live = _world(tmp_path)
    head, box = _packet(tmp_path, work, live, "claude/feature-x")
    pushes: list[tuple[str, str]] = []
    forge = FakeForge()
    rows = I.drain(box, git=_git_for(bare, pushes), api=forge)
    assert rows[0].startswith("IMPORTED") and pushes == [(head, "refs/heads/claude/feature-x")]
    assert forge.comments[7] == [{"body": "ready for review"}]
    assert (box / "done" / "p1.bundle").exists() and not (box / "p1.bundle").exists()
    # the same packet again: no second PR, no duplicate CLEAR
    _g(work, "bundle", "create", str(box / "p1.bundle"), f"{live}..claude/feature-x")
    (box / "p1.json").write_text((box / "done" / "p1.json").read_text())
    I.drain(box, git=_git_for(bare, pushes), api=forge)
    assert len(forge.prs) == 1 and len(forge.comments[7]) == 1


def test_a_packet_can_never_move_live_or_lie_about_its_head(tmp_path: Path) -> None:
    assert I.parse_manifest({"branch": LIVE, "head": "a" * 40})[0] is None
    assert I.parse_manifest({"branch": "production", "head": "a" * 40})[0] is None
    assert I.parse_manifest({"branch": "claude/../x", "head": "a" * 40})[0] is None
    bare, work, live = _world(tmp_path)
    _head, box = _packet(tmp_path, work, live, "claude/y", head="b" * 40)
    pushes: list[tuple[str, str]] = []
    rows = I.drain(box, git=_git_for(bare, pushes), api=FakeForge())
    assert rows[0].startswith("REFUSED") and "does not carry" in rows[0] and not pushes
    assert (box / "refused" / "p1.bundle").exists()
    assert "does not carry" in (box / "refused" / "p1.why.txt").read_text()


def test_a_bundle_missing_its_base_or_a_hook_refusal_is_refused_and_kept(tmp_path: Path) -> None:
    bare, work, live = _world(tmp_path)
    other = tmp_path / "other.git"
    _g(tmp_path, "init", "-q", "--bare", str(other))
    _head, box = _packet(tmp_path, work, live, "claude/z")
    rows = I.drain(box, git=_git_for(other, []), api=FakeForge())
    assert "does not verify" in rows[0]
    _head, box = _packet(tmp_path / ".", work, live, "claude/z2")
    rows = I.drain(box, git=_git_for(bare, [], refuse=True), api=FakeForge())
    assert "refused the push" in rows[0]


def test_the_gate_runs_from_live_once_live_contains_the_cleared_boot_head(tmp_path: Path) -> None:
    bare, work, live = _world(tmp_path)
    head, _box = _packet(tmp_path, work, live, "claude/box-git")
    _g(bare, "fetch", "-q", str(work), "claude/box-git:claude/box-git")
    cfg = L.Config(forge_url="https://127.0.0.1:443", bare=bare, work=tmp_path / "w",
                   tokens=tmp_path / "t", ca=tmp_path / "ca", state=tmp_path / "s", boot=head)
    assert L.gate_code(cfg, live) == head          # LIVE predates the forge gate: boot runs
    assert L.gate_code(cfg, head) == head          # merged: LIVE is the boot head itself
    _g(work, "checkout", "-q", "claude/box-git")
    (work / "c.txt").write_text("c\n")
    _g(work, "add", "c.txt")
    _g(work, "commit", "-q", "-m", "later")
    later = _g(work, "rev-parse", "HEAD")
    _g(bare, "fetch", "-q", str(work), f"{later}:refs/heads/tmp")
    assert L.gate_code(cfg, later) == later        # LIVE has moved past it: LIVE runs
    assert L.gate_code(L.Config(**{**cfg.__dict__, "boot": None}), live) == live


def test_an_author_packet_can_never_carry_a_verdict_or_an_authorization(tmp_path: Path) -> None:
    bare, work, live = _world(tmp_path)
    head, box = _packet(tmp_path, work, live, "claude/self", comments=["AUDIT CLEAR " + "a" * 40])
    pushes: list[tuple[str, str]] = []
    rows = I.drain(box, git=_git_for(bare, pushes), api=FakeForge())
    assert rows[0].startswith("REFUSED") and "verdict" in rows[0] and not pushes
    for line in (f"  AUDIT HOLD {head}", f"AUTHORIZE TRUST {head}", "UNCOUNTED CLEAR x"):
        assert I.parse_manifest({"branch": "claude/x", "head": head, "body": line})[0] is None


def test_verdict_packets_wait_for_their_pr_then_post_once_as_the_auditor(tmp_path: Path) -> None:
    forge = FakeForge()
    vd = tmp_path / "verdicts"
    vd.mkdir()
    line = "AUDIT CLEAR " + "c" * 40 + " merge"
    (vd / "v1.json").write_text(json.dumps({"branch": "claude/x", "line": line}))
    (vd / "bad.json").write_text(json.dumps({"branch": "claude/x", "line": "AUDIT CLEAR yes"}))
    rows = I.drain_verdicts(vd, api=forge)
    assert any(r.startswith("WAITING v1.json") for r in rows) and (vd / "v1.json").exists()
    assert any(r.startswith("REFUSED bad.json") for r in rows)
    forge.prs.append({"number": 7, "head": {"ref": "claude/x"}, "base": {"ref": LIVE}})
    assert I.drain_verdicts(vd, api=forge)[0].startswith("POSTED v1.json")
    assert forge.comments[7] == [{"body": line}] and (vd / "done" / "v1.json").exists()
    assert I.parse_verdict({"branch": LIVE, "line": line})[0] is None
