"""The Level 2 state publisher pushes the box's STATE only (ops/release/publisher/publish.py)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
BR = "claude/llm-auto-upgrade-verify-gcjac3"


def _mod() -> Any:
    path = ROOT / "ops/release/publisher/publish.py"
    spec = importlib.util.spec_from_file_location("state_publisher", path)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    sys.modules["state_publisher"] = m
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("path,ok", [
    ("desks/mt5/data/shadow.jsonl", True),
    ("desks/mt5/reports/x.json", True),
    ("desks/mt5/data/gateway.py", False),
    ("desks/mt5/data/run.ps1", False),
    ("desks/mt5/data/GENERIC_EXEC_ENABLED", False),
    ("desks/mt5/data/MARGIN_CLAUSE_DISABLED", False),
    ("desks/mt5/data/ALLOCATOR_SOVEREIGN.json", False),
    ("docs/LAWS.md", False),
    (".github/workflows/ci.yml", False),
    ("desks/mt5/gateway.py", False),
    ("data/../ops/x.json", False),
    ("data/secrets/fred.key", False),
    ("desks/mt5/data/SEAL_CLEARS.jsonl", False),
    ("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json", False),
    ("data/FTMO_ALLOCATOR_ARMED", False),
    ("web/index.html", False),
    ("desks/mt5/data/OVERRIDE_SIGNIFICANCE_ENFORCE.json", False),
    ("data/RECORDERS_OFF", False),
    ("desks/mt5/data/DEACTIVATE", False),
    ("desks/mt5/data/PRINCIPAL_STOP.json", False),
    ("desks/mt5/data/.gitattributes", False),
    ("desks/mt5/data/.gitmodules", False),
    ("desks/mt5/gateway_state.json", True),
])  # fmt: skip
def test_publishable(path: str, ok: bool) -> None:
    assert _mod().publishable(path) is ok


def test_publishable_is_a_subset_of_release_state_and_never_governed() -> None:
    spec = importlib.util.spec_from_file_location("rel_for_pub", ROOT / "libs/ops/release.py")
    assert spec is not None and spec.loader is not None
    rel = importlib.util.module_from_spec(spec)
    sys.modules["rel_for_pub"] = rel
    spec.loader.exec_module(rel)
    m = _mod()
    for p in m.PUBLISH_PREFIXES:
        assert rel.is_state_path(p + "x.json"), p
    for f in m.PUBLISH_FILES:
        assert rel.is_state_path(f) and not rel.is_governed_state(f), f
    for f in rel.GOVERNED_STATE_FILES:
        assert not m.publishable(f), f


def _g(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                          text=True).stdout  # fmt: skip


def _commit(repo: Path, files: dict[str, str | None], msg: str) -> None:
    for rel, text in files.items():
        p = repo / rel
        if text is None:
            _g(repo, "rm", "-q", rel)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        _g(repo, "add", rel)
    _g(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify", "-m", msg)


def _pending(box: Path, files: dict[str, str | None], msg: str = "pending") -> str:
    """What sync_shadow_to_git.ps1's Publish-StateOnto does: one commit on origin's tip, built
    in a private index, never on the box's HEAD, and named by refs/publish/pending."""
    _g(box, "fetch", "-q", "origin", BR)
    idx = box / ".git" / "pending-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(idx)}

    def run(*a: str, stdin: str | None = None) -> str:
        return subprocess.run(["git", "-C", str(box), *a], check=True, capture_output=True,
                              text=True, env=env, input=stdin).stdout  # fmt: skip

    run("read-tree", "FETCH_HEAD")
    for rel, text in files.items():
        if text is None:
            run("update-index", "--force-remove", rel)
            continue
        blob = run("hash-object", "-w", "--stdin", stdin=text).strip()
        run("update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}")
    tree = run("write-tree").strip()
    commit = run("-c", "user.name=t", "-c", "user.email=t@t", "commit-tree", tree, "-p",
                 "FETCH_HEAD", "-m", msg).strip()  # fmt: skip
    idx.unlink()
    _g(box, "update-ref", "refs/publish/pending", commit)
    return commit


def _three(tmp_path: Path, base: dict[str, str | None]) -> tuple[Path, Path, Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", BR, str(origin)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True,
                   capture_output=True)  # fmt: skip
    _g(seed, "checkout", "-q", "-b", BR)
    _commit(seed, base, "base")
    _g(seed, "push", "-q", "origin", BR)
    box, work = tmp_path / "box", tmp_path / "work"
    for d in (box, work):
        subprocess.run(["git", "clone", "-q", "-b", BR, str(origin), str(d)], check=True,
                       capture_output=True)  # fmt: skip
    return origin, seed, box, work


def test_publishes_the_pending_state_commit_and_nothing_else(tmp_path: Path) -> None:
    m = _mod()
    _, seed, box, work = _three(tmp_path, {
        "libs/ops/release.py": "ORIGIN = 1\n", "desks/mt5/gateway.py": "v1\n",
        "desks/mt5/data/shadow.jsonl": "a\n", "desks/mt5/data/old.json": "x\n",
        "desks/mt5/reports/r.json": "origin\n"})  # fmt: skip
    assert m.main(["--src", str(box), "--work", str(work)]) == 0  # no pending ref yet: nothing
    # origin moves on: a code change and an origin-side state edit the box never touched
    _commit(seed, {"desks/mt5/gateway.py": "v2\n", "desks/mt5/data/new_by_origin.json": "o\n"},
            "origin code")  # fmt: skip
    _g(seed, "push", "-q", "origin", BR)
    # the box builds its pending commit: state writes, a deletion, a code edit, a switch flip
    # and a docs edit (the last three must never travel)
    _pending(box, {"desks/mt5/data/shadow.jsonl": "a\nb\n", "desks/mt5/data/old.json": None,
                   "desks/mt5/gateway_state.json": "{}\n", "desks/mt5/gateway.py": "EVIL\n",
                   "desks/mt5/data/GENERIC_EXEC_ENABLED": "1\n", "docs/LAWS.md": "x\n",
                   "libs/ops/release.py": "EVIL = 1\n"})  # fmt: skip
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    _g(seed, "pull", "-q", "origin", BR)

    def show(p: str) -> str | None:
        return (seed / p).read_text(encoding="utf-8") if (seed / p).exists() else None

    assert show("desks/mt5/data/shadow.jsonl") == "a\nb\n"
    assert show("desks/mt5/data/old.json") is None
    assert show("desks/mt5/gateway_state.json") == "{}\n"
    assert show("desks/mt5/gateway.py") == "v2\n"
    assert show("desks/mt5/data/GENERIC_EXEC_ENABLED") is None
    assert show("docs/LAWS.md") is None
    assert show("libs/ops/release.py") == "ORIGIN = 1\n"
    assert show("desks/mt5/data/new_by_origin.json") == "o\n"
    n = _g(seed, "log", "--oneline").count("\n")
    # the same pending commit is published once: a later origin edit to one of its paths stands
    _commit(seed, {"desks/mt5/data/shadow.jsonl": "a\nb\nc\n"}, "newer on origin")
    _g(seed, "push", "-q", "origin", BR)
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    _g(seed, "pull", "-q", "origin", BR)
    assert show("desks/mt5/data/shadow.jsonl") == "a\nb\nc\n"
    assert _g(seed, "log", "--oneline").count("\n") == n + 1


def test_the_box_head_is_never_the_source(tmp_path: Path) -> None:
    """The measured failure (2026-11-05): the box commits no state on HEAD, so HEAD is far behind
    LIVE; overlaying it would have laid 98,001 old box copies over newer LIVE state."""
    m = _mod()
    _, seed, box, work = _three(tmp_path, {"desks/mt5/data/ledger.jsonl": "1\n"})
    _commit(seed, {"desks/mt5/data/ledger.jsonl": "1\n2\n3\n"}, "newer state on LIVE")
    _g(seed, "push", "-q", "origin", BR)
    _commit(box, {"desks/mt5/data/ledger.jsonl": "1\n", "desks/mt5/data/stale.json": "s\n"},
            "an old box HEAD commit")  # fmt: skip
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    _g(seed, "pull", "-q", "origin", BR)
    assert (seed / "desks/mt5/data/ledger.jsonl").read_text(encoding="utf-8") == "1\n2\n3\n"
    assert not (seed / "desks/mt5/data/stale.json").exists()


def test_a_merge_shaped_pending_commit_is_refused(tmp_path: Path) -> None:
    m = _mod()
    _, _, box, work = _three(tmp_path, {"desks/mt5/data/a.json": "1\n"})
    _commit(box, {"desks/mt5/data/a.json": "2\n"}, "side")
    head = _g(box, "rev-parse", "HEAD").strip()
    _g(box, "fetch", "-q", "origin", BR)
    tree = _g(box, "rev-parse", "HEAD^{tree}").strip()
    merge = _g(box, "-c", "user.name=t", "-c", "user.email=t@t", "commit-tree", tree, "-p",
               "FETCH_HEAD", "-p", head, "-m", "two parents").strip()  # fmt: skip
    _g(box, "update-ref", "refs/publish/pending", merge)
    assert m.main(["--src", str(box), "--work", str(work)]) == 2


def test_symlinks_never_travel(tmp_path: Path) -> None:
    m = _mod()
    _, _, box, work = _three(tmp_path, {"desks/mt5/data/a.json": "1\n"})
    _g(box, "fetch", "-q", "origin", BR)
    idx = box / ".git" / "pending-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(idx)}

    def run(*a: str, stdin: str | None = None) -> str:
        return subprocess.run(["git", "-C", str(box), *a], check=True, capture_output=True,
                              text=True, env=env, input=stdin).stdout  # fmt: skip

    run("read-tree", "FETCH_HEAD")
    blob = run("hash-object", "-w", "--stdin", stdin="2\n").strip()
    link = run("hash-object", "-w", "--stdin", stdin="../../../ops/x.py").strip()
    run("update-index", "--add", "--cacheinfo", f"100644,{blob},desks/mt5/data/a.json")
    run("update-index", "--add", "--cacheinfo", f"120000,{link},desks/mt5/data/link.json")
    tree = run("write-tree").strip()
    c = run("-c", "user.name=t", "-c", "user.email=t@t", "commit-tree", tree, "-p", "FETCH_HEAD",
            "-m", "p").strip()  # fmt: skip
    _g(box, "update-ref", "refs/publish/pending", c)
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    _g(work, "fetch", "-q", "origin")
    tree_out = _g(work, "ls-tree", "-r", f"origin/{BR}")
    assert "link.json" not in tree_out and "a.json" in tree_out
    assert _g(work, "show", f"origin/{BR}:desks/mt5/data/a.json") == "2\n"


def test_authority_detects_a_state_app_push_of_code() -> None:
    path = ROOT / "ops/release/authority/authority.py"
    spec = importlib.util.spec_from_file_location("auth_for_pub", path)
    assert spec is not None and spec.loader is not None
    a = importlib.util.module_from_spec(spec)
    sys.modules["auth_for_pub"] = a
    spec.loader.exec_module(a)
    m = _mod()
    bot = "quant-state-publisher[bot]"
    acts = [
        {"id": 5, "activity_type": "push", "actor": {"login": bot}, "before": "a", "after": "b"},
        {"id": 6, "activity_type": "push", "actor": {"login": bot}, "before": "b", "after": "c"},
        {"id": 7, "activity_type": "push", "actor": {"login": "zuck"}, "before": "c", "after": "d"},
        {"id": 8, "activity_type": "push", "actor": {"login": bot}, "before": "d", "after": "e"},
        {"id": 9, "activity_type": "force_push", "actor": {"login": "zuck"}},
    ]
    files = {("a", "b"): ["desks/mt5/data/x.json"], ("b", "c"): ["desks/mt5/gateway.py"],
             ("c", "d"): ["desks/mt5/gateway.py"], ("d", "e"): None}  # fmt: skip
    got = a.state_app_violations(acts, bot, lambda x, y: files[(x, y)], m.publishable)
    assert got == [
        f"activity 6 push by {bot}: desks/mt5/gateway.py",
        f"activity 8 push by {bot}: file list unreadable or truncated",
        "activity 9 force_push by zuck",
    ]


def test_activity_paging_follows_the_link_cursor_and_freezes_on_a_torn_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = ROOT / "ops/release/authority/authority.py"
    spec = importlib.util.spec_from_file_location("auth_for_paging", path)
    assert spec is not None and spec.loader is not None
    a = importlib.util.module_from_spec(spec)
    sys.modules["auth_for_paging"] = a
    spec.loader.exec_module(a)
    out = (
        "HTTP/2.0 200 OK\r\nLink: <https://api.github.com/repositories/9/activity?after=X>; "
        'rel="next"\r\n\r\n[{"id": 3}]'
    )
    monkeypatch.setattr(a.subprocess, "run", lambda *x, **k: subprocess.CompletedProcess(
        [], 0, stdout=out, stderr=""))  # fmt: skip
    got, nxt = a.activity_page("o/r", "repos/o/r/activity")
    assert got == [{"id": 3}] and nxt == "repositories/9/activity?after=X"
    att = tmp_path / "attestations"
    att.mkdir()
    (tmp_path / "STATE_APP.json").write_text('{"login": "bot[bot]"}', encoding="utf-8")
    (att / a.CURSOR_FILE).write_text('{"last_', encoding="utf-8")
    msg = a.check_state_app(object(), "o/r", "live", att)
    assert msg is not None and msg.startswith("RED") and (att / "DEACTIVATE").exists()


def test_detector_fails_closed_after_three_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = ROOT / "ops/release/authority/authority.py"
    spec = importlib.util.spec_from_file_location("auth_for_fails", path)
    assert spec is not None and spec.loader is not None
    a = importlib.util.module_from_spec(spec)
    sys.modules["auth_for_fails"] = a
    spec.loader.exec_module(a)

    def boom(*_: Any) -> str:
        raise RuntimeError("api down")

    monkeypatch.setattr(a, "check_state_app", boom)
    got = [a.detector_pass(None, "o/r", "live", tmp_path) for _ in range(3)]
    assert not got[0].startswith("RED") and not got[1].startswith("RED")
    assert got[2].startswith("RED") and (tmp_path / "DEACTIVATE").exists()
    monkeypatch.setattr(a, "check_state_app", lambda *_: "clean")
    (tmp_path / "DEACTIVATE").unlink()
    assert a.detector_pass(None, "o/r", "live", tmp_path) == "clean"
    assert not (tmp_path / a.FAILS_FILE).exists()
