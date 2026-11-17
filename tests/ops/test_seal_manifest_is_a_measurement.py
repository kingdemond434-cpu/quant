"""A seal is a measurement or it is nothing, and the sha and the hashes move together.

WHAT HAPPENED, measured on the trading box 2026-09-24 22:00 UTC. `release_identity` refused NEW
risk with

    running the sealed commit 6bd53e64c325; money path drifted on disk:
    ['desks/mt5/mt5desk/gateway.py', 'desks/mt5/mt5desk/decision_core.py', ...]

and the money path had not drifted. Every one of the twenty-two files was byte-identical to
`git show HEAD:<path>`, the tree was clean on those paths, and `code_sha` equalled HEAD -- so the
commit comparison passed and every investigation stopped there. The lie was one layer down:

    per-file digests equal to the '<absent>' digest: 19 of 22
    all 22 money-path files ARE in the tree at 6bd53e64c325

`_read` returned None for two different facts -- "git says this path is not in that commit" and
"git would not answer" -- and `hash_paths` hashed the sentinel `<absent>` for both. A seal taken
while git was intermittently failing recorded nineteen present files as absent and wrote it as a
signed fact. 1,222 of the last 1,266 decisions in `decision_ledger.jsonl` were
`release_identity_refused`; 42 were `placed`.

The flap hit the same record three more ways, which is the measure of how intermittent it was:
`config_hash` came out half-absent, `allocator_hash` came out correct, and `canon_sha256` and
`immutable_manifest` came out NULL for two files that are in the tree -- nulls that read as
"there wasn't one" and meant "nobody could look".

THE TESTS BELOW ARE THE TWO HALVES OF THE FIX. `_Blobs` asks `git ls-tree` which kind of None it
has and raises on the unmeasured one; `manifest_describes_commit` re-derives the manifest from
the commit it names and `seal()` refuses to write when they disagree. Neither weakens the rail:
the last two tests pin that a genuine drift and a genuine absence both still behave exactly as
before.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from libs.ops import release

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required")

SIZING = "desks/mt5/mt5desk/sizing.py"
GATEWAY = "desks/mt5/mt5desk/gateway.py"


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)
    return r.stdout.strip()


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


def _absent_digest(rel: str) -> str:
    return hashlib.sha256(rel.encode() + release.ABSENT).hexdigest()[:16]


# ------------------------------------------------- the failure that actually happened
def test_a_read_that_fails_refuses_the_seal_instead_of_recording_absent(
        repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE REGRESSION. git answers for most files and not for `gateway.py`; before the fix that
    produced a happily-written manifest calling a present file absent."""
    real = release._read

    def flaky(rel: str, root: Path, commit: str | None) -> bytes | None:
        return None if rel == GATEWAY and commit is not None else real(rel, root, commit)

    monkeypatch.setattr(release, "_read", flaky)
    with pytest.raises(release.SealReadError, match="UNMEASURED"):
        release.seal(root=repo)
    assert not (repo / release.RELEASE_REL).exists(), "a failed seal must write nothing"


def test_a_failed_seal_leaves_the_previous_honest_record_in_place(
        repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed means the LAST GOOD record survives. A red rail telling the truth beats a
    green one that is not, and it beats no rail at all."""
    good = release.seal(root=repo)
    before = (repo / release.RELEASE_REL).read_text("utf-8")
    real = release._read
    monkeypatch.setattr(release, "_read", lambda rel, root, commit: (
        None if commit is not None else real(rel, root, commit)))
    with pytest.raises(release.SealReadError):
        release.seal(root=repo)
    assert (repo / release.RELEASE_REL).read_text("utf-8") == before
    assert json.loads(before)["money_path_hash"] == good["money_path_hash"]


def test_a_tree_git_cannot_list_is_unmeasured_not_absent(
        repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If `ls-tree` itself will not answer, NOTHING about the commit is known -- so absence
    cannot be distinguished from failure and the seal must not guess either way."""
    real = release._git

    def no_ls_tree(args: list[str], root: Path, timeout: float = 10.0) -> str | None:
        return None if args and args[0] == "ls-tree" else real(args, root, timeout)

    monkeypatch.setattr(release, "_git", no_ls_tree)
    with pytest.raises(release.SealReadError, match="list the tree"):
        release.seal(root=repo)
    assert not (repo / release.RELEASE_REL).exists()


# --------------------------------------------- the invariant, stated so a machine checks it
def test_every_seal_writes_a_manifest_that_describes_the_sha_it_names(repo: Path) -> None:
    """The property, checked on a real seal: `money_path_files` and `money_path_hash` ARE the
    blobs of `code_sha`, and nothing is recorded as absent."""
    doc = release.seal(root=repo)
    assert release.manifest_describes_commit(doc, root=repo) == []
    assert doc["money_path_absent"] == []
    on_disk = json.loads((repo / release.RELEASE_REL).read_text("utf-8"))
    assert release.manifest_describes_commit(on_disk, root=repo) == []
    for rel in release.MONEY_PATH:
        assert doc["money_path_files"][rel] != _absent_digest(rel), rel


def test_the_checker_catches_a_manifest_filed_under_a_sha_it_does_not_describe(
        repo: Path) -> None:
    """THE EXACT BOX RECORD, reconstructed: a correct `code_sha` with nineteen digests replaced by
    the absent sentinel. The commit comparison passes and this is what says otherwise."""
    doc = release.seal(root=repo)
    forged = dict(doc)
    forged["money_path_files"] = dict(doc["money_path_files"])
    hit = list(release.MONEY_PATH)[:19]
    for rel in hit:
        forged["money_path_files"][rel] = _absent_digest(rel)
    bad = release.manifest_describes_commit(forged, root=repo)
    assert sorted(bad) == sorted(hit), bad

    # ... and an aggregate that does not match the commit is named even when the per-file
    # digests do, which is the case a per-file-only check would wave through.
    agg = dict(doc)
    agg["money_path_hash"] = "0" * 16
    assert release.manifest_describes_commit(agg, root=repo) == [
        "<money_path_hash disagrees with the commit it names>"]

    short = dict(doc)
    short["money_path_files"] = {k: v for k, v in doc["money_path_files"].items() if k != SIZING}
    assert "<money_path_files does not cover money_path>" in release.manifest_describes_commit(
        short, root=repo)


def test_seal_refuses_when_its_own_manifest_would_not_describe_the_commit(
        repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Belt to the strict reader's braces. `_describe` is made to build EXACTLY the record the
    box was running -- a correct `code_sha` with every money-path digest the absent sentinel --
    and the post-condition must stop it reaching disk even though no read failed."""
    real = release._describe

    def absent_manifest(root: Path, commit: str | None, *, strict: bool = False) -> dict:
        doc = real(root, commit, strict=strict)
        doc["money_path_files"] = {rel: _absent_digest(rel) for rel in release.MONEY_PATH}
        return doc

    monkeypatch.setattr(release, "_describe", absent_manifest)
    with pytest.raises(release.SealReadError, match="does not describe"):
        release.seal(root=repo)
    assert not (repo / release.RELEASE_REL).exists()


# ------------------------------------------------------- the rail is not weakened by any of it
def test_a_real_on_disk_drift_still_refuses(repo: Path) -> None:
    """The whole point of the money-path stage. Edit a sealed file on the box and the identity
    must still say no -- that behaviour is why the stage exists and it is untouched."""
    doc = release.seal(root=repo)
    (repo / GATEWAY).write_text("# edited on the box after the seal\n", "utf-8")
    assert release.hash_paths(release.MONEY_PATH, repo) != doc["money_path_hash"]
    v = release.verify(root=repo)
    assert not v["ok"] and "money_path_hash" in v["diffs"]
    assert release.manifest_describes_commit(doc, root=repo) == [], (
        "the manifest still describes its commit; only the working tree moved")


def test_a_file_the_commit_genuinely_does_not_carry_is_still_sealed_as_absent(
        repo: Path) -> None:
    """Absence is a real, hashable fact and must not start refusing: `UNIVERSAL_SURVIVORS.canon`
    is untracked on the box by design, and a seal that refused on it would never be taken."""
    _git(repo, "rm", "-q", "--", SIZING)
    _git(repo, "commit", "-qm", "drop sizing")
    doc = release.seal(root=repo)
    assert doc["money_path_files"][SIZING] == _absent_digest(SIZING)
    assert doc["money_path_absent"] == [SIZING]
    assert release.manifest_describes_commit(doc, root=repo) == []
    ok, why, _code = release.accepts(doc["code_sha"], doc, root=repo)
    assert ok, why


def test_absence_and_unreadability_are_different_answers(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    b = release._Blobs(repo, head, strict=True)
    assert b.present(GATEWAY) and not b.present("desks/mt5/not/a/file.py")
    assert b.read("desks/mt5/not/a/file.py") is None          # absent: answered, not refused
    assert b.read(GATEWAY) is not None
    # Reads are cached, so one describe reads each blob once and cannot disagree with itself.
    assert b.read(GATEWAY) is b.read(GATEWAY)


def test_the_absent_sentinel_is_the_wire_format() -> None:
    """The box side (mt5desk/release_identity.py) hashes this literal for a file the sealed
    commit does not carry; its mirror constant and the phantom-drift diagnosis are the SEALED
    half of patch 39 (/mnt/project-files/patches/recovered_breadth/sealed/39/)."""
    assert release.ABSENT == b"<absent>"
