"""The box backlog drain: state-only commits are superseded, box-only code goes to a review branch.

Measured 2026-10-06: the box's branch was 823 commits ahead of origin. Pushing it whole died on
HTTP 408 (#181), so the state travels as one commit on origin's tip, and this drain lifts any
box-only CODE to `box/backlog-<stamp>` -- never the live branch -- and reports the counts.
"""
from __future__ import annotations

import base64
import bz2
import gzip
import json
import lzma
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.ops import box_backlog as bb
from libs.ops.box_git_env import git_env


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True,
                          text=True, env=env).stdout


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")


@pytest.fixture()
def box(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(remote))
    repo = tmp_path / "box"
    _git(tmp_path, "init", "-q", "-b", "live", str(repo))
    _git(repo, "config", "commit.gpgsign", "false")
    _write(repo, "libs/a.py", "A = 1\n")
    _write(repo, "desks/mt5/data/state.json", "{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "live")
    # backlog: two state-only commits, one code-touching commit, one code change origin also has
    _write(repo, "desks/mt5/data/state.json", '{"n": 1}')
    _git(repo, "commit", "-qam", "state 1")
    _write(repo, "libs/a.py", "A = 2  # box fix\n")
    _write(repo, "desks/mt5/data/state.json", '{"n": 2}')
    _git(repo, "commit", "-qam", "box hand fix")
    _write(repo, "desks/mt5/data/state.json", '{"n": 3}')
    _git(repo, "commit", "-qam", "state 2")
    return repo, remote


def test_classifies_state_only_and_code_touching(box: tuple[Path, Path]) -> None:
    repo, _ = box
    doc = bb.run(repo, upstream="origin/live", push=False)
    assert doc["verdict"] == "MEASURED"
    assert (doc["ahead"], doc["state_only"], doc["code_touching"]) == (3, 2, 1)
    assert doc["code_paths"] == ["libs/a.py"]
    assert doc["push"]["pushed"] is False


def test_pushes_box_code_to_a_review_branch_only(box: tuple[Path, Path], tmp_path: Path) -> None:
    repo, remote = box
    now = datetime(2026, 10, 6, 16, 30, tzinfo=UTC)
    out = tmp_path / "BOX_BACKLOG.json"
    doc = bb.run(repo, upstream="origin/live", push=True, now=now, out=out)
    assert doc["push"]["pushed"] is True, doc
    assert doc["push"]["branch"] == "box/backlog-20261006-1630"
    heads = _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")
    assert "refs/heads/box/backlog-20261006-1630" in heads
    shown = _git(remote, "show", "box/backlog-20261006-1630:libs/a.py")
    assert "box fix" in shown
    # the review commit sits on origin's tip and carries no state
    assert _git(remote, "rev-parse", "box/backlog-20261006-1630^") == _git(remote, "rev-parse",
                                                                           "live")
    assert _git(remote, "show", "box/backlog-20261006-1630:desks/mt5/data/state.json") == "{}"
    # the live branch itself is untouched
    assert "box fix" not in _git(remote, "show", "live:libs/a.py")
    # a second run with the same box code does not mint another branch
    out.write_text(json.dumps(doc), "utf-8")
    again = bb.run(repo, upstream="origin/live", push=True,
                   now=datetime(2026, 10, 7, 16, 30, tzinfo=UTC), out=out)
    assert again["push"].get("repeated") is True
    assert "20261007" not in _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")


@pytest.mark.parametrize("ref", ["claude/llm-auto-upgrade-verify-gcjac3", "production", "master",
                                 "release/x", "refs/heads/production", "feature/x"])
def test_refuses_every_ref_but_a_review_branch(ref: str) -> None:
    with pytest.raises(ValueError):
        bb._assert_review_ref(ref)


def test_code_origin_already_has_is_not_drained(box: tuple[Path, Path]) -> None:
    repo, remote = box
    other = remote.parent / "other"
    _git(remote.parent, "clone", "-q", "-b", "live", str(remote), str(other))
    _write(other, "libs/a.py", "A = 2  # box fix\n")
    _git(other, "commit", "-qam", "origin caught up")
    _git(other, "push", "-q", "origin", "live")
    _git(repo, "fetch", "-q", "origin")
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert doc["code_touching"] == 1 and doc["code_paths_differing"] == 0
    assert doc["push"]["pushed"] is False


def test_unreadable_backlog_is_unmeasured(tmp_path: Path) -> None:
    doc = bb.run(tmp_path, upstream="origin/live", push=False)
    assert doc["verdict"] == "UNMEASURED"


def test_git_env_appends_safe_directory_and_keeps_the_callers_entries() -> None:
    base = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic eA=="}
    env = git_env(Path("C:\\opt\\quant"), base)
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("safe.directory",
                                                                     "C:/opt/quant")
    assert git_env(Path("C:\\opt\\quant"), env)["GIT_CONFIG_COUNT"] == "2", "idempotent"


def test_an_adopted_origin_version_is_not_drained(tmp_path: Path) -> None:
    """Audit D1: Adopt-Release records an adoption as a NON-merge commit of origin's code. The box
    adopts v1, origin moves to v2: the box's v1 blob differs from origin's tip but is origin's own
    history, and draining it would revert origin."""
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(remote))
    dev = tmp_path / "dev"
    _git(tmp_path, "init", "-q", "-b", "live", str(dev))
    _git(dev, "config", "commit.gpgsign", "false")
    _write(dev, "libs/a.py", "A = 0\n")
    _git(dev, "add", ".")
    _git(dev, "commit", "-q", "-m", "v0")
    _git(dev, "remote", "add", "origin", str(remote))
    _git(dev, "push", "-q", "-u", "origin", "live")
    box = tmp_path / "box"
    _git(tmp_path, "clone", "-q", "-b", "live", str(remote), str(box))
    _write(dev, "libs/a.py", "A = 1  # v1\n")
    _git(dev, "commit", "-qam", "v1")
    _git(dev, "push", "-q", "origin", "live")
    # the box ADOPTS v1 as a non-merge commit of origin's tree (Adopt-Release's shape)
    _write(box, "libs/a.py", "A = 1  # v1\n")
    _git(box, "commit", "-qam", "adopt release v1")
    _write(dev, "libs/a.py", "A = 2  # v2\n")
    _git(dev, "commit", "-qam", "v2")
    _git(dev, "push", "-q", "origin", "live")
    _git(box, "fetch", "-q", "origin")
    doc = bb.run(box, upstream="origin/live", push=True)
    assert doc["code_touching"] == 1
    assert doc["code_paths_differing"] == 0, doc
    assert any("origin's history" in s["why"] for s in doc["skipped"])
    assert doc["push"]["pushed"] is False


def test_a_planted_secret_refuses_the_whole_push(box: tuple[Path, Path]) -> None:
    """Audit D2: the repository is public. A box-local credential file is denied by name, and a
    credential inside a code file refuses the whole push -- only path names are recorded."""
    repo, remote = box
    _write(repo, "desks/mt5/terminal.ini", "[login]\npassword=hunter2\n")
    _write(repo, "libs/b.py", 'KEY = "ghp_' + "a" * 36 + '"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "box local config")
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert "desks/mt5/terminal.ini" in doc["denied_paths"]
    assert doc["secret_screen_hits"] == ["libs/b.py"]
    assert doc["push"]["pushed"] is False and doc["push"]["why"].startswith("REFUSED")
    assert "hunter2" not in json.dumps(doc) and "ghp_" not in json.dumps(doc)
    heads = _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")
    assert "box/backlog" not in heads


@pytest.mark.parametrize("rel", ["desks/mt5/terminal.ini", "x/.env", ".env.local", "a/my_secret.py",
                                 "creds/credentials.json", "k/server.pem", "k/id.key", "c.pfx",
                                 "data/secrets/x.json", "ops/github_token.txt"])
def test_denied_names(rel: str) -> None:
    assert bb._denied_name(rel)


def test_ordinary_code_is_not_denied() -> None:
    assert not bb._denied_name("libs/ops/box_backlog.py")


def test_a_weak_hit_withholds_one_file_and_never_wedges_the_drain(box: tuple[Path, Path]) -> None:
    """Audit D2, third condition: one suspicious file is withheld, the rest still drains."""
    repo, remote = box
    _write(repo, "libs/c.py", 'password = "hunter2"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "box code that reads a token")
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert doc["withheld_paths"] == ["libs/c.py"] and doc["secret_screen_hits"] == []
    assert doc["push"]["pushed"] is True, doc
    branch = doc["push"]["branch"]
    files = _git(remote, "ls-tree", "-r", "--name-only", branch)
    assert "libs/a.py" in files and "libs/c.py" not in files


@pytest.mark.parametrize("text", [
    "run the task-scheduler and the desk-sync job", "risk-free rate", "the sk-learn wrapper",
    "-----BEGIN CERTIFICATE-----",
])
def test_ordinary_text_is_never_a_strong_hit(text: str) -> None:
    assert bb.secret_strength(text) != "strong"


@pytest.mark.parametrize("text", [
    "ghp_" + "A" * 36, "github_pat_" + "a" * 70, "sk-proj-" + "x" * 30, "AKIA" + "Q" * 16,
    "-----BEGIN OPENSSH PRIVATE KEY-----",
])
def test_real_credential_shapes_are_strong(text: str) -> None:
    assert bb.secret_strength(text) == "strong"


def test_the_pushed_range_is_one_commit_on_origins_tip(box: tuple[Path, Path]) -> None:
    """Only scanned blobs and our own message are added: no box commit reaches the remote."""
    repo, remote = box
    doc = bb.run(repo, upstream="origin/live", push=True)
    branch = doc["push"]["branch"]
    added = _git(remote, "rev-list", f"live..{branch}").split()
    assert len(added) == 1
    box_shas = set(_git(repo, "rev-list", "origin/live..HEAD").split())
    assert not box_shas & set(added)


# AUDIT HOLD (2026-10-06): one row per bypass the audit listed. Every row must at least WITHHOLD
# its file; the credential FORMATS must refuse the whole push.
_GH = "ghp_" + "Ab1" * 14                                   # 42 chars after the prefix
_WITHHELD = [
    '{"password": "hunter2"}', '{"apikey": "abc123"}', '{"access_key": "abc123"}',
    '{"Authorization": "Bearer abc.def.123"}', "MT5_PASSWORD=hunter2", "db_password = 'x'",
    "$mt5Password = 'x'", "GITHUB_TOKEN=abc", "access_token=abc", "FRED_API_KEY=abc",
    "EIA_KEY=abc", "aws_secret_access_key=abc", "url?password%3Dhunter2", "q=token%3Aabc",
    "Authorization: Bearer abcdef123456", "X-Api-Key: abc", "https://user:pw@example.com/x",
    "ftp://bot:s3cret@10.0.0.1",
]
_STRONG = [
    _GH, "xoxb-1234567890-abcdefghij", "AIza" + "B" * 35,
    "123456789:AA" + "c" * 33, "ASIA" + "Q" * 16,
    'KEY = "-----BEGIN RSA " + "PRIVATE KEY-----"',
    base64.b64encode(f"token={_GH}".encode()).decode(),
]


@pytest.mark.parametrize("text", _WITHHELD + _STRONG)
def test_every_audited_bypass_is_at_least_withheld(text: str) -> None:
    assert bb.secret_strength(text) in ("weak", "strong"), text


@pytest.mark.parametrize("text", _STRONG)
def test_credential_formats_refuse_the_push(text: str) -> None:
    assert bb.secret_strength(text) == "strong", text


@pytest.mark.parametrize("data", [
    f"KEY = '{_GH}'\n".encode("utf-16"),
    gzip.compress(f"KEY = '{_GH}'\n".encode()),
])
def test_encoded_blobs_holding_a_token_refuse_the_push(data: bytes) -> None:
    assert bb.screen_bytes(data) == "strong"


@pytest.mark.parametrize("data", [b"\x00\x01\x02 just bytes", gzip.compress(b"plain"),
                                  b"PK\x03\x04 zipped", "plain".encode("utf-16")])
def test_any_unscreenable_blob_is_withheld(data: bytes) -> None:
    assert bb.screen_bytes(data) in ("weak", "strong")


@pytest.mark.parametrize("text", [
    "def f(xs): return sorted(xs, key=len)", 'row = {"key": 1}',
    "the basic functionality of the module",
    # audit rescore 2026-10-06: the broad pattern 0 flagged 23.5% of code files on these
    '{"authority": "ramp"}', '{"passed": true}', "author: zuck", "pass: the next slot retries",
    "def f(token: str) -> None:", '{"api_key": key}', "secret: the reason it stays local",
    'token = os.environ.get("GITHUB_TOKEN")', "password = None", "sort_key=by_date",
])
def test_ordinary_code_is_not_withheld(text: str) -> None:
    assert bb.secret_strength(text) is None


def test_a_binary_blob_is_withheld_not_drained(box: tuple[Path, Path]) -> None:
    repo, _ = box
    (repo / "libs" / "d.py").write_bytes(f"KEY = '{_GH}'\n".encode("utf-16"))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "utf-16 file")
    doc = bb.run(repo, upstream="origin/live", push=False)
    assert doc["secret_screen_hits"] == ["libs/d.py"]
    assert doc["push"]["pushed"] is False and doc["push"]["why"].startswith("REFUSED")


def test_an_adoption_hidden_by_history_simplification_is_still_dropped(tmp_path: Path) -> None:
    """Audit HOLD, MUST-FIX 2: origin's v1 lived only on a side branch whose merge kept main's
    version of the path. Plain `git log -- path` simplifies that branch away, so the box's adopted
    v1 read as box code; --full-history -m must find it."""
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "live", str(remote))
    dev = tmp_path / "dev"
    _git(tmp_path, "init", "-q", "-b", "live", str(dev))
    _git(dev, "config", "commit.gpgsign", "false")
    _write(dev, "libs/a.py", "A = 0\n")
    _git(dev, "add", ".")
    _git(dev, "commit", "-q", "-m", "v0")
    _git(dev, "remote", "add", "origin", str(remote))
    _git(dev, "push", "-q", "-u", "origin", "live")
    box = tmp_path / "box"
    _git(tmp_path, "clone", "-q", "-b", "live", str(remote), str(box))
    _git(dev, "checkout", "-q", "-b", "side")
    _write(dev, "libs/a.py", "A = 1  # side v1\n")
    _git(dev, "commit", "-qam", "side v1")
    _git(dev, "checkout", "-q", "live")
    _write(dev, "other.py", "x = 1\n")
    _git(dev, "add", ".")
    _git(dev, "commit", "-qm", "main moves")
    _git(dev, "merge", "-q", "-s", "ours", "--no-edit", "side")     # keeps main's a.py (v0)
    _git(dev, "push", "-q", "origin", "live")
    plain = _git(dev, "log", "--format=%s", "live", "--", "libs/a.py")
    assert "side v1" not in plain, "fixture must reproduce the simplification"
    _write(box, "libs/a.py", "A = 1  # side v1\n")      # the box adopted the side branch's v1
    _git(box, "commit", "-qam", "adopt side v1")
    _git(box, "fetch", "-q", "origin")
    doc = bb.run(box, upstream="origin/live", push=False)
    assert doc["code_paths_differing"] == 0, doc
    assert any("origin's history" in s["why"] for s in doc["skipped"])


def test_a_failed_history_read_is_unmeasured_and_pushes_nothing(
        box: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, remote = box
    real = bb._git

    def broken(root: Path, *args: str, **kw: object) -> tuple[int, str, str]:
        if args and args[0] == "log" and "--full-history" in args:
            return 128, "", "fatal: bad object"
        return real(root, *args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(bb, "_git", broken)
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert doc["verdict"] == "UNMEASURED" and doc["push"]["pushed"] is False
    assert "box/backlog" not in _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads")


def test_a_failed_ignore_read_is_unmeasured(box: tuple[Path, Path],
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _ = box
    real = bb._git

    def broken(root: Path, *args: str, **kw: object) -> tuple[int, str, str]:
        if args and args[0] == "check-ignore":
            return 128, "", "fatal: broken"
        return real(root, *args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(bb, "_git", broken)
    doc = bb.run(repo, upstream="origin/live", push=True)
    assert doc["verdict"] == "UNMEASURED" and doc["push"]["pushed"] is False


# AUDIT RESCORE (2026-10-06, rescore/PR210_v3.md): what --push still needs.
_HEX32 = "0123456789abcdef" * 2


@pytest.mark.parametrize("text", [
    f"eia_key={_HEX32}", f"Eia_Key = '{_HEX32}'", f"https://api.eia.gov/v2/x?key={_HEX32}",
    f"https://x.org/q?a=1&api_key={_HEX32}", f'{{"key": "{_HEX32}"}}', f'{{"key":"{_HEX32}"}}',
])
def test_any_key_name_with_a_long_value_is_withheld(text: str) -> None:
    assert bb.secret_strength(text) in ("weak", "strong"), text


@pytest.mark.parametrize("data", [
    lzma.compress(b"plain text"), bz2.compress(b"plain text"),
    b"7z\xbc\xaf\x27\x1c\x00\x04" + b"\x80" * 16,      # a 7z header
    "caf\u00e9 latin-1".encode("latin-1"),
])
def test_any_blob_that_is_not_utf8_is_withheld(data: bytes) -> None:
    assert bb.screen_bytes(data) in ("weak", "strong")


def test_the_screen_withholds_few_of_this_repositorys_own_code_files() -> None:
    """The rescore measured 23.5% of code files withheld by the broad pattern. A screen that
    withholds a quarter of the tree drains nothing; this pins the narrowed rate below 5%."""
    import subprocess as sp
    files = sp.run(["git", "-C", str(bb.ROOT), "ls-files", "*.py", "*.ps1", "*.sh"],
                   capture_output=True, text=True, check=True).stdout.split()
    assert len(files) > 100
    held = 0
    for rel in files:
        try:
            data = (bb.ROOT / rel).read_bytes()
        except OSError:
            continue
        held += bb.screen_bytes(data) is not None
    assert held / len(files) < 0.05, f"{held}/{len(files)} withheld"
