"""The sign train runs on the box: the audit-signed re-sign of a sealed judge file (gap 7)."""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import box_ci  # noqa: E402
from ops.box_git import box_loop as L  # noqa: E402

LIVE, SIGNED = "a" * 40, "b" * 40


def _cfg(tmp: Path) -> L.Config:
    (tmp / "t").mkdir()
    (tmp / "t" / "merge-gate.token").write_text("x", "utf-8")
    return L.Config(forge_url="https://127.0.0.1:443", bare=tmp / "b.git", work=tmp / "w",
                    tokens=tmp / "t", ca=tmp / "ca.pem", state=tmp / "s.json")


def _fake(monkeypatch, tmp: Path, *, train_rc=0, train_out="", moves=True, parent=LIVE,
          files=" ".join(L.SIGNED_PATHS), push_rc=0, trigger_diff="x"):
    wt = tmp / "wt"
    (wt / "scripts").mkdir(parents=True)
    (wt / L.SIGN_TRAIN).write_text("", "utf-8")
    calls: list[list[str]] = []

    @contextlib.contextmanager
    def worktree(cfg, sha):
        calls.append(["worktree", sha])
        yield wt

    def run(argv, *, cwd=None, env=None, timeout=0, idle=False):
        a = list(argv)
        calls.append(a)
        if a[:3] == ["git", "-C", str(tmp / "b.git")] and "diff" in a:
            return 0, trigger_diff
        if a[1:2] == [L.SIGN_TRAIN]:
            return train_rc, train_out
        if a == ["git", "rev-parse", "HEAD"]:
            return 0, SIGNED if moves else LIVE
        if a == ["git", "rev-parse", "HEAD~1"]:
            return 0, parent
        if a[:3] == ["git", "diff", "--name-only"]:
            return 0, files
        if a[:2] == ["git", "push"]:
            return push_rc, ""
        return 0, ""
    monkeypatch.setattr(L, "worktree", worktree)
    monkeypatch.setattr(L, "_run", run)
    return calls


def test_a_signed_commit_on_live_is_fast_forwarded(tmp_path: Path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    calls = _fake(monkeypatch, tmp_path, train_out="signed")
    out = L.sign_tick(cfg, LIVE)
    assert out.startswith("SIGNED") and SIGNED[:12] in out
    push = [c for c in calls if c[:2] == ["git", "push"]]
    assert push and push[0][-1] == f"{SIGNED}:refs/heads/{L.LIVE}"
    assert box_ci.load_state(cfg.state)["sign_checked"] == SIGNED


def test_nothing_to_sign_marks_the_head_checked_and_pushes_nothing(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    calls = _fake(monkeypatch, tmp_path, train_out="nothing to sign", moves=False)
    assert "nothing to sign" in L.sign_tick(cfg, LIVE)
    assert not [c for c in calls if c[:2] == ["git", "push"]]
    assert L.sign_tick(cfg, LIVE).endswith("already checked for a sign")


def test_a_refused_train_is_reported_and_never_pushed(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    calls = _fake(monkeypatch, tmp_path, train_rc=2, train_out="REFUSED: no CLEAR row",
                  moves=False)
    assert "rc 2: REFUSED: no CLEAR row" in L.sign_tick(cfg, LIVE)
    assert not [c for c in calls if c[:2] == ["git", "push"]]


def test_a_commit_off_live_or_touching_other_files_is_refused(tmp_path, monkeypatch) -> None:
    for kw in ({"parent": "c" * 40}, {"files": "desks/mt5/scripts/external_gauntlet.py"}):
        sub = tmp_path / str(len(kw["parent"] if "parent" in kw else kw["files"]))
        sub.mkdir()
        cfg = _cfg(sub)
        calls = _fake(monkeypatch, sub, **kw)
        assert L.sign_tick(cfg, LIVE).startswith("REFUSED to push")
        assert not [c for c in calls if c[:2] == ["git", "push"]]
        assert "sign_checked" not in box_ci.load_state(cfg.state)


def test_no_checkout_when_nothing_sealed_moved_since_the_last_check(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    box_ci.save_state(cfg.state, {"sign_checked": "d" * 40})
    calls = _fake(monkeypatch, tmp_path, trigger_diff="")
    assert "nothing to sign" in L.sign_tick(cfg, LIVE)
    assert not [c for c in calls if c[0] == "worktree"]
    assert box_ci.load_state(cfg.state)["sign_checked"] == LIVE
