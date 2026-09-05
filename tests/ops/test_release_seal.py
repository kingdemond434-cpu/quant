"""The seal survives the chicken-and-egg, and the acceptance rule admits exactly two shapes.

A manifest cannot carry the SHA of the commit that carries it. So the seal names HEAD and is
committed ALONE; a running SHA is the release when it is that HEAD, or when everything between
the two is the manifest and the box's own state files. These tests build a throwaway repository
and walk the sequence the desk actually goes through: code -> seal -> seal commit -> a state-sync
commit on the box -> the next code commit, and assert which of those the release admits.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from libs.ops import release

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required")

ROOT = Path(__file__).resolve().parents[2]
SIZING = "desks/mt5/mt5desk/sizing.py"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _commit(cwd: Path, rel: str, text: str | None, msg: str) -> str:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        p.write_text(text, "utf-8")
    _git(cwd, "add", "--", rel)
    _git(cwd, "commit", "-qm", msg)
    return _git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    for rel in (*release.MONEY_PATH, *release.CONFIG_FILES, release.SURVIVORS):
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {rel}\n", "utf-8")
    (r / release.IMMUTABLE_MANIFEST).write_text(json.dumps(
        {"signed_utc": "2026-09-05T00:00:00+00:00", "signed_by": "t", "files": {}}), "utf-8")
    (r / release.PYPROJECT).write_text(
        '[project]\nname = "x"\ndependencies = ["numpy>=2"]\n', "utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "code")
    return r


# ---------------------------------------------------------------------------- the seal
def test_seal_names_head_and_hashes_the_commit_not_the_checkout(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    (repo / SIZING).write_text("# edited on disk, never committed\n", "utf-8")
    with pytest.raises(RuntimeError, match="dirty"):
        release.seal(root=repo)
    doc = release.seal(root=repo, allow_dirty=True, tested=True, by="t")
    assert doc["code_sha"] == head == doc["live_sha"] == doc["tested_sha"]
    assert doc["tree_sha"] == _git(repo, "rev-parse", "HEAD^{tree}")
    assert doc["parent_sha"] is None                     # a root commit has none
    assert doc["worktree_dirty"] == [SIZING]
    assert doc["sealed"] and doc["sealed_at"] == doc["generated_utc"] and doc["sealed_by"] == "t"
    assert doc["canon_sha256"] and doc["dependency_hash"]
    assert doc["immutable_manifest"]["signed_by"] == "t" and doc["immutable_manifest"]["sha256_16"]
    assert doc["allocator_certificate"] is None          # no proof in this repo
    assert set(doc["money_path_files"]) == set(release.MONEY_PATH)
    assert set(doc["non_code"]) == release.NON_CODE
    # The digest is of the committed blob: restoring the file makes the disk agree with it.
    _git(repo, "checkout", "--", SIZING)
    assert release.hash_paths(release.MONEY_PATH, repo) == doc["money_path_hash"]
    # Every field the 2026-09-04 readers depend on is still there, under its old name.
    for k in ("generated_utc", "live_sha", "config_hash", "survivor_registry_hash",
              "allocator_hash", "money_path_hash", "data_schema_version", "money_path",
              "release_id"):
        assert k in doc, k
    assert json.loads((repo / release.RELEASE_REL).read_text("utf-8"))["code_sha"] == head


def test_release_id_keeps_its_formula(repo: Path) -> None:
    import hashlib
    doc = release.seal(root=repo)
    want = hashlib.sha256(json.dumps(
        {k: doc[k] for k in ("live_sha", "config_hash", "survivor_registry_hash",
                             "allocator_hash", "money_path_hash", "data_schema_version")},
        sort_keys=True).encode()).hexdigest()[:12]
    assert doc["release_id"] == want


def test_dependency_hash_reads_the_dependency_tables_only(repo: Path) -> None:
    a = release.seal(root=repo)["dependency_hash"]
    _commit(repo, release.PYPROJECT,
            '# a comment\n[project]\nname = "x"\ndependencies = ["numpy>=2"]\n', "comment")
    assert release.seal(root=repo)["dependency_hash"] == a
    _commit(repo, release.PYPROJECT, '[project]\nname = "x"\ndependencies = ["numpy>=3"]\n',
            "bump")
    assert release.seal(root=repo)["dependency_hash"] != a


# ------------------------------------------------------------------------ the acceptance
def test_the_sealed_commit_and_the_pure_seal_commit_are_both_accepted(repo: Path) -> None:
    doc = release.seal(root=repo)
    head = doc["code_sha"]
    ok, why, code = release.accepts(head, doc, root=repo)
    assert ok and code == [] and head[:12] in why
    s = _commit(repo, release.RELEASE_REL, None, "seal release")
    assert s != head
    ok, why, code = release.accepts(s, doc, root=repo)
    assert ok and code == [] and "seal/state" in why
    v = release.verify(root=repo)
    assert v["ok"] and v["sealed"] and v["diffs"] == {}, v


def test_a_state_sync_commit_on_top_of_the_seal_is_the_same_code(repo: Path) -> None:
    """The box commits its state files every fifteen minutes; a rule that refused those would
    refuse the desk within a quarter hour of every seal."""
    doc = release.seal(root=repo)
    _commit(repo, release.RELEASE_REL, None, "seal release")
    _commit(repo, "desks/mt5/data/gateway_state.json", '{"armed": true}\n', "mt5 shadow sync")
    b = _commit(repo, "desks/mt5/reports/shadow/shadow_health.json", '{"status": "OPERATING"}\n',
                "mt5 shadow sync")
    ok, why, code = release.accepts(b, doc, root=repo)
    assert ok and code == [], why
    assert release.verify(root=repo)["ok"]


def test_a_diverged_sha_is_refused_and_names_the_code(repo: Path) -> None:
    doc = release.seal(root=repo)
    _commit(repo, release.RELEASE_REL, None, "seal release")
    _commit(repo, "desks/mt5/data/gateway_state.json", "{}\n", "mt5 shadow sync")
    c = _commit(repo, SIZING, "# new sizing\n", "code")
    ok, why, code = release.accepts(c, doc, root=repo)
    assert not ok and code == [SIZING] and "never named" in why
    v = release.verify(root=repo)
    assert not v["ok"] and "live_sha" in v["diffs"] and "money_path_hash" in v["diffs"]
    # A commit that bundles the manifest WITH code is the old defect, and is refused the same.
    doc2 = release.seal(root=repo)
    (repo / SIZING).write_text("# bundled\n", "utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "code + manifest together")
    bundled = _git(repo, "rev-parse", "HEAD")
    ok, _why, code = release.accepts(bundled, doc2, root=repo)
    assert not ok and code == [SIZING]


def test_without_git_only_equality_is_a_yes(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = release.seal(root=repo)
    s = _commit(repo, release.RELEASE_REL, None, "seal release")
    monkeypatch.setattr(release, "_git", lambda *a, **k: None)
    assert release.accepts(doc["code_sha"], doc, root=repo)[0]
    ok, why, _ = release.accepts(s, doc, root=repo)
    assert not ok and "git unavailable" in why
    assert not release.accepts(None, doc, root=repo)[0]
    assert not release.accepts(s, {"live_sha": "unknown"}, root=repo)[0]


def test_a_record_without_non_code_uses_the_module_default(repo: Path) -> None:
    doc = release.seal(root=repo)
    doc.pop("non_code")
    s = _commit(repo, release.RELEASE_REL, None, "seal release")
    assert release.accepts(s, doc, root=repo)[0]


# ------------------------------------------------------------------------------ the CLI
def test_cli_seal_is_idempotent_with_if_needed_and_identity_exits_by_verdict(repo: Path) -> None:
    script = str(ROOT / "scripts" / "release_manifest.py")

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, script, "--root", str(repo), *args],
                              capture_output=True, text=True, timeout=120)

    r = run("--seal", "--tested", "--by", "ci")
    assert r.returncode == 0 and "sealed" in r.stdout and "ALONE" in r.stdout, r.stdout + r.stderr
    before = (repo / release.RELEASE_REL).read_text("utf-8")
    assert json.loads(before)["tested_sha"] == _git(repo, "rev-parse", "HEAD")
    _commit(repo, release.RELEASE_REL, None, "seal release")
    r = run("--seal", "--if-needed")
    assert r.returncode == 0 and "seal not needed" in r.stdout, r.stdout + r.stderr
    assert (repo / release.RELEASE_REL).read_text("utf-8") == before
    assert run("--identity").returncode == 0
    assert run("--verify").returncode == 0
    _commit(repo, SIZING, "# new\n", "code")
    r = run("--identity")
    assert r.returncode == 1 and "REFUSED" in r.stdout
    assert run("--verify").returncode == 1
    (repo / SIZING).write_text("# dirty\n", "utf-8")
    r = run("--seal")
    assert r.returncode == 2 and "SEAL REFUSED" in r.stdout


def test_legacy_build_and_verify_still_describe_the_working_tree(repo: Path) -> None:
    d = release.build(write=True, root=repo)
    assert d["sealed"] is False and d["live_sha"] == _git(repo, "rev-parse", "HEAD")
    assert release.verify(root=repo)["ok"]
    (repo / SIZING).write_text("# edited\n", "utf-8")
    v = release.verify(root=repo)
    assert not v["ok"] and "money_path_hash" in v["diffs"] and "live_sha" not in v["diffs"]


# -------------------------------------------------------------- parity with the box side
def _box_identity() -> object:
    spec = importlib.util.spec_from_file_location(
        "release_identity_under_test", ROOT / "desks" / "mt5" / "mt5desk" / "release_identity.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod        # dataclasses resolve string annotations via sys.modules
    spec.loader.exec_module(mod)
    return mod


def test_the_box_side_mirror_hashes_and_allowlists_identically(tmp_path: Path) -> None:
    """release_identity.py may not import libs/, so it carries its own copy of the digest and
    of NON_CODE. Either drifting from the seal would refuse every release, silently."""
    ri = _box_identity()
    assert ri.NON_CODE == release.NON_CODE                     # type: ignore[attr-defined]
    (tmp_path / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    (tmp_path / "b.py").write_bytes(b"x = 1\ny = 2\n")
    paths = ("a.py", "b.py", "absent.py")
    want = release.hash_paths(paths, tmp_path)
    assert ri.hash_paths(paths, tmp_path) == want           # type: ignore[attr-defined]
    assert release.hash_paths(("a.py",), tmp_path) == release.hash_paths(("a.py",), tmp_path)
    # CRLF and LF bodies digest alike once the path prefix is the same.
    (tmp_path / "c.py").write_bytes(b"x = 1\ny = 2\n")
    (tmp_path / "d.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    import hashlib
    h_lf = hashlib.sha256(b"c.py" + b"x = 1\ny = 2\n").hexdigest()[:16]
    assert release.hash_paths(("c.py",), tmp_path) == h_lf
    assert release.hash_paths(("d.py",), tmp_path) != h_lf          # different name prefix
    assert release._norm(b"x\r\ny\r\n") == b"x\ny\n"
