"""A code_hash-only break whose frozen source is recoverable is HELD, never reset (2026-10-29).

The 10-28 families_vector commits put a speed-only fast path inside 18 family bodies. Every clock
on those families went IDENTITY_BROKEN on adopt, and the hourly healer's `rebase_code()` would
then reset each window -- although the frozen source sat in git one commit back and the signals
were pinned identical by test. These tests pin the hold, the revision lookup it rests on, and the
RED line it publishes.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK / "scripts", DESK / "research", DESK, DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

heal = pytest.importorskip("heal_identity_broken_clocks")
import sleeve_registry as reg  # noqa: E402

V1 = "def family_toy(df, n=3):\n    return df.tail(n)\n"
V2 = ("def family_toy(df, n=3):\n    from mt5desk import families_vector as _vec\n"
      "    if _vec.enabled():\n        pass\n    return df.tail(n)\n")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("toy_family_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.family_toy


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    src = root / "toy.py"
    src.write_text(V1, "utf-8")
    _git(root, "add", "toy.py")
    _git(root, "commit", "-q", "-m", "v1")
    first = _git(root, "rev-parse", "HEAD")
    src.write_text(V2, "utf-8")
    _git(root, "commit", "-q", "-am", "v2: speed-only hook")
    monkeypatch.setattr(heal, "REPO", root.resolve())
    heal._REVISION_HASHES.clear()
    return root, first


def test_the_ast_hash_is_the_registry_code_hash_on_real_families():
    for fam in ("formula", "session_range_breakout", "overnight_gap_decay"):
        fn = heal.family_fn(fam)
        if fn is None:
            continue
        text = Path(sys.modules[fn.__module__].__file__).read_text("utf-8")
        assert heal._def_hash(text, fn.__name__) == reg.code_hash(fn)


def test_the_revision_that_froze_the_clock_is_found(repo):
    root, first = repo
    fn = _load(root / "toy.py")
    v1_hash = heal._def_hash(V1, "family_toy")
    assert v1_hash != reg.code_hash(fn)              # the hook DID move the hash
    assert heal.frozen_source_revision(fn, v1_hash) == first
    assert heal.frozen_source_revision(fn, "0000000000000000") is None


def test_a_recoverable_or_hooked_family_is_held_and_a_plain_edit_is_not(repo, monkeypatch):
    root, first = repo
    fn = _load(root / "toy.py")
    monkeypatch.setattr(heal, "family_fn", lambda fam: fn)
    held = heal.reattach_hold({"identity": {"family": "toy",
                                            "code_hash": heal._def_hash(V1, "family_toy")}})
    assert held and first[:10] in held
    # unknown frozen source, but the family carries the vector hook: still held
    assert heal.reattach_hold({"identity": {"family": "toy", "code_hash": "f" * 16}})
    # unknown frozen source and no hook: the existing rebase path stands
    (root / "toy.py").write_text(V1.replace("n=3", "n=4"), "utf-8")
    plain = _load(root / "toy.py")
    monkeypatch.setattr(heal, "family_fn", lambda fam: plain)
    assert heal.reattach_hold({"identity": {"family": "toy", "code_hash": "f" * 16}}) is None


def test_apply_holds_the_window_and_publishes_red(tmp_path, monkeypatch):
    """The end-to-end property: --apply on a code_hash-only break keeps forward_start, leaves the
    row IDENTITY_BROKEN for the re-attach, and the report reads RED."""
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    ident = {f: f"v-{f}" for f in reg.IDENTITY_FIELDS}
    ident.update(family="toy", code_hash="aaaaaaaaaaaaaaaa")
    registry = {"sleeves": {"K": {"identity": dict(ident), "status": "IDENTITY_BROKEN",
                                  "forward_start": "2026-09-27T00:00:00+00:00"}}}
    path = desk / "data" / "sleeve_registry.json"
    path.write_text(json.dumps(registry), "utf-8")
    monkeypatch.setattr(heal, "DESK", desk)
    monkeypatch.setattr(heal, "REPORT", desk / "reports" / "IDENTITY_HEALER.json")
    monkeypatch.setattr(reg, "REGISTRY", path)
    monkeypatch.setattr(heal, "backfill_behaviour", lambda *a, **k: 0)
    monkeypatch.setattr(heal, "freeze_unfrozen", lambda *a, **k: 0)
    monkeypatch.setattr(heal, "current_identity",
                        lambda row: {**ident, "code_hash": "bbbbbbbbbbbbbbbb"})
    monkeypatch.setattr(heal, "reattach_hold", lambda row: "HELD_FOR_REATTACH: test")
    monkeypatch.setattr(sys, "argv", ["heal", "--apply"])
    assert heal.main() == 0
    row = json.loads(path.read_text("utf-8"))["sleeves"]["K"]
    assert row["forward_start"] == "2026-09-27T00:00:00+00:00"
    assert row["status"] == "IDENTITY_BROKEN" and "window_before_rebase" not in row
    report = json.loads((desk / "reports" / "IDENTITY_HEALER.json").read_text("utf-8"))
    assert report["verdict"] == "RED" and report["held"][0]["key"] == "K"


def test_without_a_hold_the_rebase_path_is_unchanged(tmp_path, monkeypatch):
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    ident = {f: f"v-{f}" for f in reg.IDENTITY_FIELDS}
    ident.update(family="toy", code_hash="aaaaaaaaaaaaaaaa")
    path = desk / "data" / "sleeve_registry.json"
    path.write_text(json.dumps({"sleeves": {"K": {
        "identity": dict(ident), "status": "IDENTITY_BROKEN",
        "forward_start": "2026-09-27T00:00:00+00:00"}}}), "utf-8")
    monkeypatch.setattr(heal, "DESK", desk)
    monkeypatch.setattr(heal, "REPORT", desk / "reports" / "IDENTITY_HEALER.json")
    monkeypatch.setattr(reg, "REGISTRY", path)
    monkeypatch.setattr(heal, "backfill_behaviour", lambda *a, **k: 0)
    monkeypatch.setattr(heal, "freeze_unfrozen", lambda *a, **k: 0)
    monkeypatch.setattr(heal, "current_identity",
                        lambda row: {**ident, "code_hash": "bbbbbbbbbbbbbbbb"})
    monkeypatch.setattr(heal, "reattach_hold", lambda row: None)
    monkeypatch.setattr(sys, "argv", ["heal", "--apply"])
    assert heal.main() == 0
    row = json.loads(path.read_text("utf-8"))["sleeves"]["K"]
    assert row["status"] == "LIVE" and row["window_before_rebase"]["forward_start"]
    report = json.loads((desk / "reports" / "IDENTITY_HEALER.json").read_text("utf-8"))
    assert report["verdict"] == "GREEN" and report["rebased"][0]["key"] == "K"
