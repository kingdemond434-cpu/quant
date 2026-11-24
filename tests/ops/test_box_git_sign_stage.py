"""The sign train runs on the box: the audit-signed re-sign of a sealed judge file (gap 7)."""
from __future__ import annotations

import contextlib
import json
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
          files=" ".join(L.SIGNED_PATHS), push_rc=0, trigger_diff="x", diff_problems=()):
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
    monkeypatch.setattr(L, "sign_diff_problems", lambda *a: list(diff_problems))
    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: type(
        "P", (), {"returncode": 0, "stdout": ""})())
    return calls


def test_a_sign_whose_diff_is_not_exactly_a_sign_is_never_pushed(tmp_path, monkeypatch) -> None:
    cfg = _cfg(tmp_path)
    calls = _fake(monkeypatch, tmp_path, train_out="signed",
                  diff_problems=["manifest key 'append_only' changed"])
    out = L.sign_tick(cfg, LIVE)
    assert out.startswith("REFUSED") and "append_only" in out
    assert not [c for c in calls if c[:2] == ["git", "push"]]


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


# --------------------------------------------------- Audit HOLD on 389704797: trust + diff check
def test_the_signers_and_the_stage_are_in_the_trust_set() -> None:
    """An ORDINARY edit to the train, the evaluator, the CLEAR rows or the stage would otherwise be
    run by the box and pushed straight to LIVE."""
    pol = json.loads((Path(__file__).resolve().parents[2] / "ops/box_git/TRUST_SET.json")
                     .read_text("utf-8"))
    for f in ("scripts/sign_train.py", "scripts/check_immutable_evaluator.py",
              "desks/mt5/data/SEAL_CLEARS.jsonl"):
        assert f in pol["files"], f
    assert "desks/mt5/data/SEAL_CLEARS.jsonl" in pol["grow_only"]
    names = {"sign_tick", "sign_diff_problems", "SIGNED_PATHS", "SIGN_TRIGGERS", "SIGN_TRAIN"}
    assert names <= set(pol["symbols"]["ops/box_git/box_loop.py"])
    assert names <= set(pol["contracts"]["gate"]["authority"]["ops/box_git/box_loop.py"])


_SHA = "ab" * 32
_MAN = {"signed_utc": "t0", "signed_by": "a", "files": {"x.py": "1111111111111111",
                                                       "y.py": "2222222222222222"},
        "append_only": {"l.jsonl": {"n": 3}}, "record_rule": "r", "rotation_signers": {"x": "s"}}
_QB = 'X_SEAL_ROTATION = {\n    "path": "x.py",\n    "from": "f",\n    "to": "old",\n' \
      '    "signed_by": "principal",\n}\n'
_ROW = json.dumps({"path": "x.py", "sha256": _SHA, "verdict": "CLEAR"})


def _signed(**over) -> dict:
    return {**_MAN, "signed_utc": "t1", "signed_by": "auditor-clear",
            "files": {**_MAN["files"], "x.py": _SHA[:16]}, **over}


def _qb_signed() -> str:
    return _QB.replace('"to": "old"', f'"to": "{_SHA}"').replace("principal", "auditor-clear")


def test_an_exact_sign_passes() -> None:
    assert L.sign_diff_problems(json.dumps(_MAN), json.dumps(_signed()), _QB, _qb_signed(),
                                   _ROW) == []


def test_a_re_sign_without_a_clear_row_is_refused() -> None:
    bad = L.sign_diff_problems(json.dumps(_MAN), json.dumps(_signed()), _QB, _qb_signed(),
                                  json.dumps({"path": "x.py", "sha256": "cd" * 32,
                                              "verdict": "CLEAR"}))
    assert any("no CLEAR row" in b for b in bad)


def test_the_record_wall_and_signers_must_be_byte_identical() -> None:
    wall = _signed(append_only={"l.jsonl": {"n": 2}})
    assert any("append_only" in b for b in L.sign_diff_problems(
        json.dumps(_MAN), json.dumps(wall), _QB, _qb_signed(), _ROW))
    rot = _signed(rotation_signers={"x": "someone"})
    assert any("rotation_signers" in b for b in L.sign_diff_problems(
        json.dumps(_MAN), json.dumps(rot), _QB, _qb_signed(), _ROW))


def test_quantbench_may_change_only_rotation_to_and_signed_by_lines() -> None:
    worse = _qb_signed().replace('"from": "f"', '"from": "g"')
    bad = L.sign_diff_problems(json.dumps(_MAN), json.dumps(_signed()), _QB, worse, _ROW)
    assert any("outside a rotation" in b for b in bad)
    assert L.sign_diff_problems("", json.dumps(_signed()), _QB, _qb_signed(), _ROW)
