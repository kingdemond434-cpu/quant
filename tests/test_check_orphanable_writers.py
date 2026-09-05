"""The test that would have caught the 2026-08-28 orphaned-inode loss.

`scan` is the whole verdict, and it is pure -- it takes a path and returns hits -- so the fence
is testable without touching the repo tree it normally walks.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "check_orphanable_writers",
    Path(__file__).resolve().parents[1] / "scripts" / "check_orphanable_writers.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

VULNERABLE = '''
import time, requests
def go(items, out):
    with out.open("a", encoding="utf-8") as fh:
        for it in items:
            time.sleep(1.0)
            fh.write(requests.get(it).text)
'''

FAST_LOOP = '''
def go(rows, out):
    with out.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(r)
'''

REPAIRED = '''
import time, requests
def go(items, out, stage):
    with stage.open("w", encoding="utf-8") as fh:
        for it in items:
            time.sleep(1.0)
            fh.write(requests.get(it).text)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(stage.read_text())
'''


def _scan_src(tmp_path: Path, src: str, name: str = "m.py") -> list:
    p = tmp_path / name
    p.write_text(src, encoding="utf-8")
    return MOD.scan(p)


def test_flags_append_handle_held_across_a_waiting_loop(tmp_path: Path) -> None:
    assert _scan_src(tmp_path, VULNERABLE), "the exact 2026-08-28 shape must be reported"


def test_does_not_flag_a_loop_that_only_writes(tmp_path: Path) -> None:
    # A list flushed in milliseconds cannot be interrupted by a checkout in any meaningful
    # sense. The first draft of this fence reported 58 of these and buried the one real hit.
    assert _scan_src(tmp_path, FAST_LOOP) == []


def test_does_not_flag_the_staging_then_publish_repair(tmp_path: Path) -> None:
    # The publish append holds no loop, and the staging handle is opened "w" outside the tree.
    assert _scan_src(tmp_path, REPAIRED) == []


def test_tracked_filter_clears_a_module_writing_only_ignored_paths() -> None:
    # An artifact git does not track has no checkout to unlink it; reporting one is noise.
    assert MOD._writes_tracked('p = "definitely_not_a_tracked_basename_xyz.jsonl"', set()) is False
    assert MOD._writes_tracked('p = "observations.jsonl"', {"observations.jsonl"}) is True
