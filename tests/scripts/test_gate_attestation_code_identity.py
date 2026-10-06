"""THE ATTESTATION BINDS TO THE CODE, AND A BOX STATE COMMIT CANNOT UNBIND IT.

Measured on the box 2026-10-06 15:43Z: release 659bf9ddb3cb adopted and sealed, but
`RELEASE_AUTHORITY.tested` false -- gates green on code tree e32ad9b77db4 while the box's tree read
c9e138c447cc. `gate_attestation.code_hash` excluded state through a private eight-prefix copy of
release.py's classification that lacked `desks/mt5/frontier_intel/data/`,
`desks/mt5/side_channels/data/` and every STATE_FILES entry. The box commits exactly those paths
hourly (Adopt-Release keeps them as box state), so each state commit moved the "code" hash.

Pinned both ways: state commits leave the hash alone, and ANY code change still moves it -- the
check that the code tested is the code running is not weakened, only aimed correctly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts", ROOT / "desks" / "mt5" / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gate_attestation as ga  # noqa: E402
import release_authority as ra  # noqa: E402

from libs.ops import release  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


def _commit(repo: Path, files: dict[str, str]) -> str:
    for rel, body in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, "utf-8")
        _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "--no-verify", "-m", "c")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    monkeypatch.setattr(ga, "ROOT", r)
    return r


def test_the_fallback_mirror_is_release_whole() -> None:
    """The mirror is used only without libs/; if it drifts, that is where the bug comes back."""
    assert set(ga._STATE_PREFIXES) == set(release.STATE_PREFIXES)
    assert ga._STATE_FILES == release.STATE_FILES
    assert ga._IS_STATE is release.is_state_path


def test_a_box_state_commit_leaves_the_code_hash_alone(repo: Path) -> None:
    first = _commit(repo, {"desks/mt5/mt5desk/gateway.py": "x = 1\n", "libs/a.py": "a = 1\n"})
    tested = ga.code_hash(first)
    after = _commit(repo, {
        "desks/mt5/frontier_intel/data/frontier_queue.jsonl": "{}\n",
        "desks/mt5/side_channels/data/intelligence/latest_discoveries.json": "{}\n",
        "desks/mt5/gateway_state.json": "{}\n",
        "desks/mt5/swap_exposure.json": "{}\n",
        "context/decision_journal.jsonl": "{}\n",
        "desks/mt5/data/RELEASE.json": "{}\n",
        "desks/mt5/reports/BOX_RELEASE_SEAL.json": "{}\n",
    })
    assert ga.code_hash(after) == tested


def test_any_code_change_still_moves_it(repo: Path) -> None:
    first = _commit(repo, {"desks/mt5/mt5desk/gateway.py": "x = 1\n"})
    for rel in ("desks/mt5/mt5desk/gateway.py", "desks/mt5/frontier_intel/miner.py",
                "desks/mt5/new_module.py", "ops/githooks/pre-push"):
        nxt = _commit(repo, {rel: f"# {rel} changed\n"})
        assert ga.code_hash(nxt) != ga.code_hash(first), rel
        first = nxt


def test_release_authority_stays_tested_across_a_state_commit(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = _commit(repo, {"desks/mt5/mt5desk/gateway.py": "x = 1\n"})
    att, ident, rel = tmp_path / "att.json", tmp_path / "ident.json", tmp_path / "rel.json"
    monkeypatch.setattr(ra, "ATTESTATION", att)
    monkeypatch.setattr(ra, "IDENTITY", ident)
    monkeypatch.setattr(ra, "RELEASE", rel)
    att.write_text(json.dumps({"result": "pass", "tested_sha": sealed,
                               "tested_code_hash": ga.code_hash(sealed)}), "utf-8")
    rel.write_text(json.dumps({"code_sha": sealed}), "utf-8")
    running = _commit(repo, {"desks/mt5/frontier_intel/data/frontier_queue.jsonl": "{}\n",
                             "desks/mt5/gateway_state.json": "{}\n"})
    ident.write_text(json.dumps({"running_sha": running, "verdict": "OK"}), "utf-8")
    doc = ra.measure()
    assert doc["clauses"]["tested"]["ok"], doc["clauses"]["tested"]["why"]
    assert doc["clauses"]["sealed"]["ok"], doc["clauses"]["sealed"]["why"]

    moved = _commit(repo, {"desks/mt5/mt5desk/gateway.py": "x = 2\n"})
    ident.write_text(json.dumps({"running_sha": moved, "verdict": "OK"}), "utf-8")
    doc = ra.measure()
    assert not doc["clauses"]["tested"]["ok"]
    assert doc["may_create_exposure"] is False
