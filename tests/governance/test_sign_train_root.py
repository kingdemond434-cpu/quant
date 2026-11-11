"""THE SIGN TRAIN SIGNS A CLEARED PR HEAD WITH LIVE'S CODE AND LIVE'S RECORD, AND NOTHING ELSE.

`scripts/sign_train.py --root` (2026-11-11, Desk health's read G1-G10). These cases build a
scratch repository: a LIVE checkout carrying the real train, evaluator and quantbench.py, and a
separate PR checkout whose sealed file moved. They drive the real CLI end to end.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sign_train", ROOT / "scripts" / "sign_train.py")
assert SPEC and SPEC.loader
st = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(st)

GAUNTLET = "desks/mt5/scripts/external_gauntlet.py"
REPORT = "reports/audit/2026-11-11/seal_clear_test.md"
A = "a" * 64


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _row(sha: str, head: str | None, verdict: str = "CLEAR", path: str = GAUNTLET) -> str:
    row = {"path": path, "sha256": sha, "verdict": verdict, "report": REPORT}
    if head is not None:
        row["head"] = head
    return json.dumps(row)


@pytest.fixture()
def repo(tmp_path: Path) -> dict[str, object]:
    """LIVE at `live`, a PR head at `pr` (a worktree), the head's new gauntlet sha256."""
    live = tmp_path / "live"
    live.mkdir()
    _git(live, "init", "-q", "-b", "LIVE")
    for k, v in (("user.name", "t"), ("user.email", "t@t.invalid"), ("core.autocrlf", "false")):
        _git(live, "config", k, v)
    for rel in ("scripts/sign_train.py", "scripts/check_immutable_evaluator.py",
                st.QUANTBENCH):  # fmt: skip
        (live / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, live / rel)
    (live / GAUNTLET).parent.mkdir(parents=True, exist_ok=True)
    (live / GAUNTLET).write_text("# the judge, v1\n", "utf-8")
    (live / st.SEAL_CLEARS).parent.mkdir(parents=True, exist_ok=True)
    (live / st.SEAL_CLEARS).write_text("", "utf-8")
    subprocess.run(
        ("python", "-I", "scripts/check_immutable_evaluator.py", "--sign-files", "--by", "t"),
        cwd=live, check=True, capture_output=True,
    )  # fmt: skip
    _git(live, "add", "-A")
    _git(live, "commit", "-q", "-m", "base")
    base = _git(live, "rev-parse", "HEAD")
    # the PR: the judge file moves, on its own branch
    _git(live, "checkout", "-q", "-b", "claude/judge")
    (live / GAUNTLET).write_text("# the judge, v2\n", "utf-8")
    _git(live, "commit", "-q", "-am", "judge change")
    head = _git(live, "rev-parse", "HEAD")
    _git(live, "checkout", "-q", "LIVE")
    pr = tmp_path / "pr"
    _git(live, "worktree", "add", "-q", "--detach", str(pr), head)
    new_sha = st.full_sha(GAUNTLET, pr)
    return {"live": live, "pr": pr, "head": head, "base": base, "sha": new_sha}


def _land_row(live: Path, line: str) -> None:
    with (live / st.SEAL_CLEARS).open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    _git(live, "commit", "-q", "-am", "SEAL_CLEARS row")


def _train(live: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("python", "-I", str(live / "scripts" / "sign_train.py"), *args),
        cwd=live, capture_output=True, text=True, check=False,
    )  # fmt: skip


def test_a_cleared_head_is_signed_in_one_narrow_commit(repo: dict[str, object]) -> None:
    live, pr, head, sha = repo["live"], repo["pr"], repo["head"], repo["sha"]
    assert isinstance(live, Path) and isinstance(pr, Path)
    assert isinstance(head, str) and isinstance(sha, str)
    _land_row(live, _row(sha, head))
    listed = _train(live, "--list-heads")
    assert listed.returncode == 0 and listed.stdout.split() == [head], listed.stdout
    r = _train(live, "--root", str(pr), "--target", head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert st.train_commit_problems(pr, head, _git(pr, "rev-parse", "HEAD")) == []
    manifest = json.loads((pr / st.MANIFEST).read_text("utf-8"))
    assert manifest["files"][GAUNTLET] == sha[:16]
    assert manifest["signed_by"] == st.AUDITOR
    bench = st._constants((pr / st.QUANTBENCH).read_text("utf-8"))["GAUNTLET_SEAL_ROTATION"]
    assert bench["to"] == sha and bench["signed_by"] == st.AUDITOR
    # LIVE's checkout was never touched
    assert _git(live, "status", "--porcelain") == ""


def test_no_row_for_the_exact_head_no_sign(repo: dict[str, object]) -> None:
    live, pr, head, sha = repo["live"], repo["pr"], repo["head"], repo["sha"]
    assert isinstance(live, Path) and isinstance(pr, Path)
    assert isinstance(head, str) and isinstance(sha, str)
    _land_row(live, _row(sha, None))  # a bytes-only row names no head
    assert _train(live, "--list-heads").stdout.strip() == ""
    r = _train(live, "--root", str(pr), "--target", head)
    assert r.returncode == 2 and "REFUSED" in r.stdout
    assert _git(pr, "rev-parse", "HEAD") == head


def test_the_prs_own_record_is_never_read(repo: dict[str, object]) -> None:
    live, pr, head, sha = repo["live"], repo["pr"], repo["head"], repo["sha"]
    assert isinstance(live, Path) and isinstance(pr, Path)
    assert isinstance(head, str) and isinstance(sha, str)
    # The PR carries its own CLEAR row; LIVE carries none for this head.
    (pr / st.SEAL_CLEARS).write_text(_row(sha, head) + "\n", "utf-8")
    _git(pr, "commit", "-q", "-am", "self-cleared")
    selfie = _git(pr, "rev-parse", "HEAD")
    r = _train(live, "--root", str(pr), "--target", selfie)
    assert r.returncode == 2, r.stdout


def test_other_bytes_than_cleared_are_refused(repo: dict[str, object]) -> None:
    live, pr, head = repo["live"], repo["pr"], repo["head"]
    assert isinstance(live, Path) and isinstance(pr, Path) and isinstance(head, str)
    _land_row(live, _row(A, head))
    r = _train(live, "--root", str(pr), "--target", head)
    assert r.returncode == 2 and "not the audited" in r.stdout


def test_a_hold_outranks_the_clear(repo: dict[str, object]) -> None:
    live, pr, head, sha = repo["live"], repo["pr"], repo["head"], repo["sha"]
    assert isinstance(live, Path) and isinstance(pr, Path)
    assert isinstance(head, str) and isinstance(sha, str)
    _land_row(live, _row(sha, head))
    _land_row(live, _row(sha, None, "HOLD"))
    assert _train(live, "--list-heads").stdout.strip() == ""
    assert _train(live, "--root", str(pr), "--target", head).returncode == 2


def test_a_pr_that_touches_the_trains_files_is_refused(repo: dict[str, object]) -> None:
    live, pr, head, sha = repo["live"], repo["pr"], repo["head"], repo["sha"]
    assert isinstance(live, Path) and isinstance(pr, Path)
    assert isinstance(head, str) and isinstance(sha, str)
    with (pr / "scripts" / "sign_train.py").open("a", encoding="utf-8") as fh:
        fh.write("# planted\n")
    _git(pr, "commit", "-q", "-am", "edit the train")
    planted = _git(pr, "rev-parse", "HEAD")
    _land_row(live, _row(sha, planted))
    r = _train(live, "--root", str(pr), "--target", planted)
    assert r.returncode == 2 and "train's own files" in r.stdout


def test_root_refuses_the_human_and_push_paths(repo: dict[str, object]) -> None:
    live, pr, head = repo["live"], repo["pr"], repo["head"]
    assert isinstance(live, Path) and isinstance(pr, Path) and isinstance(head, str)
    for extra in (["--principal"], ["--push"], ["--expect", f"{GAUNTLET}={A}"]):
        assert _train(live, "--root", str(pr), "--target", head, *extra).returncode == 2


def test_root_wants_the_full_head(repo: dict[str, object]) -> None:
    live, pr, head = repo["live"], repo["pr"], repo["head"]
    assert isinstance(live, Path) and isinstance(pr, Path) and isinstance(head, str)
    assert _train(live, "--root", str(pr), "--target", head[:12]).returncode == 2


def test_head_field_must_be_a_full_commit() -> None:
    with pytest.raises(ValueError):
        st.parse_clears(_row(A, "abc123"))
    with pytest.raises(ValueError):
        st.parse_clears(_row(A, "F" * 40))
    assert st.parse_clears(_row(A, "f" * 40)) == {GAUNTLET: {A}}


def test_two_clears_for_one_head_naming_different_bytes_are_refused() -> None:
    h = "f" * 40
    with pytest.raises(ValueError):
        st.head_clears("\n".join([_row(A, h), _row("b" * 64, h)]), h)


def test_head_clears_counts_only_its_own_head() -> None:
    h, other = "f" * 40, "e" * 40
    text = "\n".join([_row(A, h), _row("b" * 64, other, path="x.py"), _row("c" * 64, None)])
    assert st.head_clears(text, h) == {GAUNTLET: A}
    assert st.heads_named(text) == [h, other]
    assert st.head_clears(text + "\n" + _row(A, h, "HOLD"), h) == {}


def test_static_qb002_reads_the_rotation_rule() -> None:
    src = (ROOT / st.QUANTBENCH).read_text("utf-8")
    after = st.repin(src, "GAUNTLET_SEAL_ROTATION", A, st.AUDITOR)
    good = {"signed_by": st.AUDITOR, "files": {GAUNTLET: A[:16]}}
    assert st.static_qb002(src, after, {GAUNTLET: A}, st.AUDITOR, good) == []
    assert st.static_qb002(src, src, {GAUNTLET: A}, st.AUDITOR, good) != []
    wrong_signer = {"signed_by": "principal", "files": {GAUNTLET: A[:16]}}
    assert st.static_qb002(src, after, {GAUNTLET: A}, st.AUDITOR, wrong_signer) != []
    lost_from = after.replace(st._constants(src)["GAUNTLET_SEAL_ROTATION"]["from"], "0" * 64)
    assert st.static_qb002(src, lost_from, {GAUNTLET: A}, st.AUDITOR, good) != []
