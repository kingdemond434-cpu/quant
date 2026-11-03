"""The Level 2 state publisher pushes the box's STATE only (ops/release/publisher/publish.py)."""

from __future__ import annotations

import importlib.util
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


def test_publishes_box_state_and_nothing_else(tmp_path: Path) -> None:
    m = _mod()
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", BR, str(origin)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True,
                   capture_output=True)  # fmt: skip
    _g(seed, "checkout", "-q", "-b", BR)
    release = "ORIGIN = 1\n"
    _commit(seed, {"libs/ops/release.py": release, "desks/mt5/gateway.py": "v1\n",
                   "desks/mt5/data/shadow.jsonl": "a\n", "desks/mt5/data/old.json": "x\n",
                   "desks/mt5/reports/r.json": "origin\n"}, "base")  # fmt: skip
    _g(seed, "push", "-q", "origin", BR)
    box = tmp_path / "box"
    subprocess.run(["git", "clone", "-q", "-b", BR, str(origin), str(box)], check=True,
                   capture_output=True)  # fmt: skip
    # origin moves on: a code change and an origin-side report edit the box never touched
    _commit(seed, {"desks/mt5/gateway.py": "v2\n", "desks/mt5/data/new_by_origin.json": "o\n"},
            "origin code")  # fmt: skip
    _g(seed, "push", "-q", "origin", BR)
    # the box: state writes, a deletion, a code edit, a switch flip and a docs edit
    _commit(box, {"desks/mt5/data/shadow.jsonl": "a\nb\n", "desks/mt5/data/old.json": None,
                  "desks/mt5/gateway_state.json": "{}\n", "desks/mt5/gateway.py": "EVIL\n",
                  "desks/mt5/data/GENERIC_EXEC_ENABLED": "1\n", "docs/LAWS.md": "x\n",
                  "libs/ops/release.py": "EVIL = 1\n"},
            "box")  # fmt: skip
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", "-b", BR, str(origin), str(work)], check=True,
                   capture_output=True)  # fmt: skip
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    _g(seed, "pull", "-q", "origin", BR)
    show = lambda p: (seed / p).read_text(encoding="utf-8") if (seed / p).exists() else None  # noqa: E731
    assert show("desks/mt5/data/shadow.jsonl") == "a\nb\n"
    assert show("desks/mt5/data/old.json") is None
    assert show("desks/mt5/gateway_state.json") == "{}\n"
    assert show("desks/mt5/gateway.py") == "v2\n"  # the box's code edit never travels
    assert show("desks/mt5/data/GENERIC_EXEC_ENABLED") is None
    assert show("docs/LAWS.md") is None
    assert show("libs/ops/release.py") == "ORIGIN = 1\n"
    assert show("desks/mt5/data/new_by_origin.json") == "o\n"  # origin's state edit stands
    # a second pass has nothing left to do
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    assert _g(seed, "log", "--oneline").count("\n") == 3


def test_symlinks_never_travel(tmp_path: Path) -> None:
    m = _mod()
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", BR, str(origin)], check=True)
    box = tmp_path / "box"
    subprocess.run(["git", "clone", "-q", str(origin), str(box)], check=True, capture_output=True)
    _g(box, "checkout", "-q", "-b", BR)
    _commit(box, {"desks/mt5/data/a.json": "1\n"}, "base")
    _g(box, "push", "-q", "origin", BR)
    (box / "desks/mt5/data/link.json").symlink_to("../../../ops/x.py")
    _g(box, "add", "desks/mt5/data/link.json")
    _commit(box, {"desks/mt5/data/a.json": "2\n"}, "box")
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", "-b", BR, str(origin), str(work)], check=True,
                   capture_output=True)  # fmt: skip
    assert m.main(["--src", str(box), "--work", str(work)]) == 0
    _g(work, "fetch", "-q", "origin")
    tree = _g(work, "ls-tree", "-r", f"origin/{BR}")
    assert "link.json" not in tree and "a.json" in tree
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
    commits = [{"sha": "1" * 40, "author": {"login": bot}},
               {"sha": "2" * 40, "author": {"login": bot}},
               {"sha": "3" * 40, "author": {"login": "someone"}}]  # fmt: skip
    files = {"1" * 40: ["desks/mt5/data/x.json"], "2" * 40: ["desks/mt5/gateway.py"],
             "3" * 40: ["desks/mt5/gateway.py"]}  # fmt: skip
    got = a.state_app_violations(commits, bot, files.__getitem__, m.publishable)
    assert got == ["222222222222: desks/mt5/gateway.py"]
