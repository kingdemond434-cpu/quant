"""The bars a verdict was measured on get an identity, so a re-run can tell code from data."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.data import input_identity as ii  # noqa: E402


def _uni(tmp_path: Path, files: dict[str, bytes]) -> Path:
    root = tmp_path / "universe"
    root.mkdir(exist_ok=True)
    for name, body in files.items():
        (root / name).write_bytes(body)
    return root


def test_an_appended_bar_changes_the_digest(tmp_path: Path) -> None:
    root = _uni(tmp_path, {"EURUSD_H1.parquet": b"a" * 200000})
    first = ii.build(root)
    (root / "EURUSD_H1.parquet").write_bytes(b"a" * 200000 + b"NEWBAR")
    second = ii.build(root)
    assert first["files"]["EURUSD_H1.parquet"]["sha"] != \
        second["files"]["EURUSD_H1.parquet"]["sha"]
    assert first["rollup"] != second["rollup"]
    d = ii.compare(first, second)
    assert d["changed"] == ["EURUSD_H1.parquet"] and d["same"] is False


def test_an_untouched_tree_is_the_same_identity(tmp_path: Path) -> None:
    root = _uni(tmp_path, {"a.parquet": b"x" * 10, "b.parquet": b"y" * 300000})
    a, b = ii.build(root), ii.build(root)
    assert a["rollup"] == b["rollup"] and ii.compare(a, b)["same"] is True
    assert a["mode"] == "head_tail" and ii.build(root, full=True)["mode"] == "full"


def test_a_small_file_is_hashed_whole_and_a_middle_edit_is_caught(tmp_path: Path) -> None:
    root = _uni(tmp_path, {"small.parquet": b"abcdef"})
    before = ii.build(root)
    (root / "small.parquet").write_bytes(b"abXdef")
    assert before["files"]["small.parquet"]["sha"] != \
        ii.build(root)["files"]["small.parquet"]["sha"]


def test_an_unreadable_file_is_recorded_not_skipped(tmp_path: Path) -> None:
    root = _uni(tmp_path, {"gone.parquet": b"x"})
    (root / "gone.parquet").unlink()
    (root / "gone.parquet").mkdir()          # a directory where a file should be
    doc = ii.build(root)
    assert "gone.parquet" in doc["unreadable"]
    assert doc["files"]["gone.parquet"]["sha"] is None
    assert "error" in doc["files"]["gone.parquet"]


def test_added_and_removed_inputs_are_named(tmp_path: Path) -> None:
    root = _uni(tmp_path, {"a.parquet": b"1"})
    first = ii.build(root)
    (root / "a.parquet").unlink()
    (root / "b.parquet").write_bytes(b"2")
    d = ii.compare(first, ii.build(root))
    assert d["added"] == ["b.parquet"] and d["removed"] == ["a.parquet"] and d["same"] is False


def test_two_methods_are_not_comparable(tmp_path: Path) -> None:
    root = _uni(tmp_path, {"a.parquet": b"z" * 300000})
    d = ii.compare(ii.build(root), ii.build(root, full=True))
    assert d["comparable"] is False and "cannot be compared" in d["why"]


def test_main_writes_the_identity_and_the_first_run_says_it_cannot_compare(
        tmp_path: Path) -> None:
    root = _uni(tmp_path, {"a.parquet": b"1"})
    out = tmp_path / "identity.json"
    assert ii.main(["--root", str(root), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["n_files"] == 1 and "no previous identity" in doc["since_last"]["why"]
    (root / "a.parquet").write_bytes(b"12")
    assert ii.main(["--root", str(root), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["since_last"]["changed"] == ["a.parquet"]
