"""The PIT census reads both trees the compiler reads, or it measures the wrong population."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import check_pit as cp  # noqa: E402


def test_the_census_roots_are_the_compilers_roots() -> None:
    src = (ROOT / "desks" / "mt5" / "research" / "miner_candidate_compiler.py").read_text("utf-8")
    assert 'INTEL_ROOTS = (BASE / "data" / "intelligence", ROOT / "data" / "intelligence")' in src
    names = [r.as_posix() for r in cp.INTEL_ROOTS]
    assert names == [(ROOT / "desks" / "mt5" / "data" / "intelligence").as_posix(),
                     (ROOT / "data" / "intelligence").as_posix()], \
        "the census must read exactly the trees the compiler compiles from"


def test_a_source_under_the_repo_root_tree_is_censused(tmp_path: Path, monkeypatch) -> None:
    desk_tree, repo_tree = tmp_path / "desk_intel", tmp_path / "repo_intel"
    (desk_tree / "reddit").mkdir(parents=True)
    (repo_tree / "kimi").mkdir(parents=True)
    (desk_tree / "reddit" / "discoveries_1.json").write_text(
        json.dumps({"discoveries": [{"title": "a"}]}), "utf-8")
    (repo_tree / "kimi" / "discoveries_1.json").write_text(
        json.dumps({"discoveries": [{"title": "b"}]}), "utf-8")
    monkeypatch.setattr(cp, "INTEL_ROOTS", (desk_tree, repo_tree))
    monkeypatch.setattr(cp, "OUT", tmp_path / "census.json")
    doc = cp.run()
    assert set(doc["per_source"]) == {"reddit", "kimi"}, \
        "a seat donating to the repo-root tree was invisible to this census before 2026-09-09"
    assert doc["n_sources"] == 2 and len(doc["roots_read"]) == 2 and doc["roots_absent"] == []


def test_one_source_name_under_both_trees_is_added_not_replaced(tmp_path: Path,
                                                                monkeypatch) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    for tree, n in ((a, 2), (b, 3)):
        (tree / "kimi").mkdir(parents=True)
        (tree / "kimi" / "discoveries_1.json").write_text(
            json.dumps({"discoveries": [{"title": f"r{i}"} for i in range(n)]}), "utf-8")
    monkeypatch.setattr(cp, "INTEL_ROOTS", (a, b))
    monkeypatch.setattr(cp, "OUT", tmp_path / "census.json")
    doc = cp.run()
    assert doc["per_source"]["kimi"]["rows"] == 5, "one tree must not silently replace the other"
    assert len(doc["per_source"]["kimi"]["roots"]) == 2


def test_an_absent_tree_is_named_not_silently_skipped(tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a"
    (a / "reddit").mkdir(parents=True)
    (a / "reddit" / "discoveries_1.json").write_text(
        json.dumps({"discoveries": [{"title": "x"}]}), "utf-8")
    monkeypatch.setattr(cp, "INTEL_ROOTS", (a, tmp_path / "gone"))
    monkeypatch.setattr(cp, "OUT", tmp_path / "census.json")
    doc = cp.run()
    assert doc["roots_absent"] == [(tmp_path / "gone").as_posix()]
    assert len(doc["roots_read"]) == 1
