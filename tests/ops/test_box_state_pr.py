"""ops/box/box_state_pr.py: the box's ungoverned state travels as an App-authored PR; governed
and authority-granting paths keep their own route (Governance + Architecture, 2026-11-14)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_box_state_pr", ROOT / "ops/box/box_state_pr.py")
assert _spec is not None and _spec.loader is not None
bsp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bsp
_spec.loader.exec_module(bsp)

#: A stand-in for libs/ops/release.py: data/ is state, data/governed/ is governed state.
REL = SimpleNamespace(
    is_state_path=lambda p: p.startswith(("data/", "desks/mt5/data/")),
    is_governed_state=lambda p: p.startswith("data/governed/"),
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout.strip()  # fmt: skip


def _write(repo: Path, files: dict[str, str | None]) -> None:
    for rel, text in files.items():
        p = repo / rel
        if text is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")


def _repo(
    tmp_path: Path, before: dict[str, str | None], after: dict[str, str | None]
) -> tuple[Path, str, str]:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _write(repo, before)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "parent")
    parent = _git(repo, "rev-parse", "HEAD")
    _write(repo, after)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "pending")
    return repo, parent, _git(repo, "rev-parse", "HEAD")


class FakeApi:
    def __init__(self, *, same_tree: bool = False, open_prs: list[dict[str, Any]] | None = None):
        self.calls: list[tuple[str, str, Any]] = []
        self.same_tree = same_tree
        self.open_prs = open_prs or []
        self.n = 0

    def __call__(self, method: str, path: str, body: Any = None) -> Any:
        self.calls.append((method, path, body))
        if method == "GET" and "/git/ref/heads/" in path:
            return {"object": {"sha": "tip0"}}
        if method == "GET" and "/git/commits/" in path:
            return {"tree": {"sha": "tiptree"}}
        if method == "POST" and path.endswith("/git/blobs"):
            self.n += 1
            return {"sha": f"blob{self.n}"}
        if method == "POST" and path.endswith("/git/trees"):
            return {"sha": "tiptree" if self.same_tree else "newtree"}
        if method == "POST" and path.endswith("/git/commits"):
            return {"sha": "newcommit"}
        if method == "POST" and path.endswith("/pulls"):
            return {"number": 77}
        if method == "GET" and "/pulls?" in path:
            return [*self.open_prs, {"number": 77, "head": {"ref": "box-state/box"}}]
        return None

    def of(self, method: str, suffix: str) -> list[tuple[str, str, Any]]:
        return [c for c in self.calls if c[0] == method and suffix in c[1]]


@pytest.mark.parametrize(("rel", "ok"), [
    ("data/forward/ledger.jsonl", True),
    ("desks/mt5/data/stall_watch.json", True),
    ("data/governed/caps.json", False),                 # governed state
    ("desks/mt5/data/ADOPT_CLEARS.json", False),        # authority
    ("desks/mt5/data/RELEASE.json", False),
    ("desks/mt5/data/LIVE_ARMED.json", False),
    ("desks/mt5/data/HOLD_gold.json", False),
    ("desks/mt5/data/live_sleeve_policy.json", False),
    ("desks/mt5/data/ALLOCATOR_SOVEREIGN_enabled.json", False),
    ("desks/mt5/data/promotion_approvals.jsonl", False),
    ("desks/mt5/data/MARGIN_CLAUSE_DISABLED", False),   # extensionless switch
    ("desks/mt5/data/gateway.py", False),               # code
    ("docs/research/runtime_state.json", False),        # never-prefix
    (".github/workflows/x.json", False),
    ("data/secrets/k.json", False),
    ("data/../ops/x.json", False),
    ("ops/notes.txt", False),                           # not state per release.py
    ("desks/mt5/data/merge_clears.jsonl", False),       # the gate's *clears.jsonl
    ("desks/mt5/data/armed_sleeves.json", False),       # the gate's *armed_*
    ("desks/mt5/data/release_identity.json", False),    # Governance, 2026-11-14 14:18Z
    ("desks/mt5/data/GATEWAY_LOADED.json", False),
    ("desks/mt5/data/last_adopt_rows.jsonl", False),
])  # fmt: skip
def test_pr_ok_lets_only_ungoverned_data_state_through(rel: str, ok: bool) -> None:
    assert bsp.pr_ok(rel, REL) is ok


def test_state_goes_by_pr_and_authority_keeps_its_route(tmp_path: Path) -> None:
    repo, parent, pending = _repo(
        tmp_path,
        {"data/a.json": "1", "data/gone.csv": "x", "desks/mt5/data/RELEASE.json": "{}"},
        {
            "data/a.json": "2",
            "data/gone.csv": None,
            "data/new.jsonl": "{}\n",
            "desks/mt5/data/RELEASE.json": '{"v": 2}',
        },
    )
    api = FakeApi()
    out = bsp.publish(
        repo,
        pending,
        api,
        "o/r",
        now=datetime(2026, 11, 14, 12, 0, tzinfo=UTC),
        release=REL,
    )
    assert out["mode"] == "pr" and out["pr"] == 77
    assert out["pr_paths"] == ["data/a.json", "data/gone.csv", "data/new.jsonl"]
    assert out["direct"] == ["desks/mt5/data/RELEASE.json"]

    # one blob per surviving path, a null sha for the deletion, one tree over LIVE's tip tree
    assert len(api.of("POST", "/git/blobs")) == 2
    tree = api.of("POST", "/git/trees")[0][2]
    assert tree["base_tree"] == "tiptree"
    by_path = {e["path"]: e["sha"] for e in tree["tree"]}
    assert by_path["data/gone.csv"] is None
    assert "desks/mt5/data/RELEASE.json" not in by_path
    commit = api.of("POST", "/git/commits")[0][2]
    assert commit["parents"] == ["tip0"] and commit["tree"] == "newtree"
    # no custom author or committer: GitHub makes the App both, and signs it (#1218 audit)
    assert "author" not in commit and "committer" not in commit
    ref = api.of("POST", "/git/refs")[0][2]
    assert ref == {"ref": "refs/heads/box-state/box-20261114T120000Z", "sha": "newcommit"}
    pr = api.of("POST", "/pulls")[0][2]
    assert pr["draft"] is False and pr["base"] == bsp.LIVE
    assert pr["head"] == "box-state/box-20261114T120000Z"

    # the direct commit carries ONLY the withheld path, over the same parent
    dc = out["direct_commit"]
    assert _git(repo, "rev-parse", f"{dc}^") == parent
    names = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", parent, dc)
    assert names.split() == ["desks/mt5/data/RELEASE.json"]
    assert _git(repo, "show", f"{dc}:desks/mt5/data/RELEASE.json") == '{"v": 2}'


def test_a_withheld_deletion_is_deleted_in_the_direct_commit(tmp_path: Path) -> None:
    repo, _, pending = _repo(
        tmp_path,
        {"desks/mt5/data/HOLD_x.json": "{}", "keep.txt": "k"},
        {"desks/mt5/data/HOLD_x.json": None},
    )
    out = bsp.publish(repo, pending, FakeApi(), "o/r", release=REL)
    assert out["mode"] == "nothing" and out["pr_paths"] == []
    dc = out["direct_commit"]
    assert _git(repo, "ls-tree", "-r", "--name-only", dc) == "keep.txt"


def test_nothing_new_against_live_opens_no_pr(tmp_path: Path) -> None:
    repo, _, pending = _repo(tmp_path, {"data/a.json": "1"}, {"data/a.json": "2"})
    api = FakeApi(same_tree=True)
    out = bsp.publish(repo, pending, api, "o/r", release=REL)
    assert out["mode"] == "nothing" and out["pr"] is None and out["direct_commit"] is None
    assert not api.of("POST", "/git/commits") and not api.of("POST", "/pulls")


def test_older_snapshots_with_this_tag_are_closed_and_others_left(tmp_path: Path) -> None:
    repo, _, pending = _repo(tmp_path, {"data/a.json": "1"}, {"data/a.json": "2"})
    api = FakeApi(
        open_prs=[
            {"number": 70, "head": {"ref": "box-state/box-20261114T110000Z"}},
            {"number": 71, "head": {"ref": "box-state/other-20261114T110000Z"}},
            {"number": 72, "head": {"ref": "claude/some-feature"}},
        ]
    )
    bsp.publish(repo, pending, api, "o/r", release=REL)
    assert [c[1] for c in api.of("PATCH", "/pulls/")] == ["repos/o/r/pulls/70"]
    assert [c[1] for c in api.of("DELETE", "/git/refs/")] == [
        "repos/o/r/git/refs/heads/box-state/box-20261114T110000Z"
    ]


def test_a_pending_commit_with_two_parents_is_refused(tmp_path: Path) -> None:
    repo, _, pending = _repo(tmp_path, {"data/a.json": "1"}, {"data/a.json": "2"})
    _git(repo, "checkout", "-qb", "side", f"{pending}^")
    _write(repo, {"data/b.json": "1"})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "side")
    _git(repo, "checkout", "-q", pending)
    _git(repo, "merge", "-q", "--no-edit", "side")
    merge = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(RuntimeError, match="one parent"):
        bsp.publish(repo, merge, FakeApi(), "o/r", release=REL)


GATE_SRC = """
BOX_STATE_REFUSED = ("*seal_clears*", "*/hold_*", "data/odd_one.json")


def merge_box_state(repo, pr):
    return None
"""


def _gate(root: Path, src: str = GATE_SRC, ci_skip: bool = True) -> Path:
    p = root / bsp.GATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src, encoding="utf-8")
    for w in bsp.CI_WORKFLOWS:
        q = root / w
        q.parent.mkdir(parents=True, exist_ok=True)
        skip = "    if: ${{ !startsWith(github.head_ref, 'box-state/') }}\n" if ci_skip else ""
        q.write_text(f"jobs:\n  quality:\n{skip}", encoding="utf-8")
    return root


def test_the_gate_s_own_refusals_are_read_and_applied(tmp_path: Path) -> None:
    refused = bsp.gate_refusals(_gate(tmp_path))
    assert refused == ("*seal_clears*", "*/hold_*", "data/odd_one.json")
    assert bsp.pr_ok("data/odd_one.json", REL) is True
    assert bsp.pr_ok("data/odd_one.json", REL, refused) is False


def test_the_route_stands_aside_until_the_box_s_gate_can_merge_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bsp.gate_refusals(tmp_path) is None  # no gate file at all
    _gate(tmp_path, "BOX_STATE_REFUSED = ()\n")
    assert bsp.gate_refusals(tmp_path) is None  # a gate with no box-state path (pre-#1218)

    def never(repo: Path) -> str:
        raise AssertionError("no token is minted while the gate cannot merge")

    monkeypatch.setattr(bsp, "mint_token", never)
    assert bsp.main(["--repo", str(tmp_path), "--pending", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "no-gate"


def test_no_merger_config_means_no_app_and_the_caller_keeps_its_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bsp.mint_token(tmp_path, home=tmp_path / "absent") is None
    monkeypatch.setattr(bsp, "mint_token", lambda repo: None)
    assert bsp.main(["--repo", str(_gate(tmp_path)), "--pending", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "no-app"


def test_a_failure_exits_1_with_a_failed_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(repo: Path) -> str:
        raise RuntimeError("the quant-merger App token could not be minted")

    monkeypatch.setattr(bsp, "mint_token", boom)
    assert bsp.main(["--repo", str(_gate(tmp_path)), "--pending", "x"]) == 1
    assert json.loads(capsys.readouterr().out)["mode"] == "failed"


def test_slug_reads_the_github_origin(tmp_path: Path) -> None:
    repo, _, _ = _repo(tmp_path, {"a.txt": "1"}, {"a.txt": "2"})
    _git(repo, "remote", "add", "origin", "https://github.com/kingdemond434-cpu/quant.git")
    assert bsp.slug(repo) == "kingdemond434-cpu/quant"


def test_the_machine_name_never_reaches_the_public_repo(tmp_path: Path) -> None:
    """#1219 audit MF: the branch, commit message and PR title are public; the host name stays
    on the box. The program does not even read it."""
    src = (ROOT / "ops/box/box_state_pr.py").read_text(encoding="utf-8")
    assert "gethostname" not in src and "import socket" not in src
    assert "COMPUTERNAME" not in src and "platform.node" not in src
    repo, _, pending = _repo(tmp_path, {"data/a.json": "1"}, {"data/a.json": "2"})
    with pytest.raises(ValueError):
        bsp.publish(repo, pending, FakeApi(), "o/r", tag="VMI3571445.local", release=REL)


def test_the_route_waits_for_both_workflows_to_skip_box_state_heads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def never(repo: Path) -> str:
        raise AssertionError("no token is minted before CI skips box-state PRs")

    monkeypatch.setattr(bsp, "mint_token", never)
    _gate(tmp_path, ci_skip=False)
    assert bsp.ci_skips_box_state(tmp_path) is False
    assert bsp.main(["--repo", str(tmp_path), "--pending", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "no-ci-skip"
    (tmp_path / bsp.CI_WORKFLOWS[0]).write_text("if: box-state/", encoding="utf-8")
    assert bsp.ci_skips_box_state(tmp_path) is False  # one of two is not enough
    _gate(tmp_path)
    assert bsp.ci_skips_box_state(tmp_path) is True
