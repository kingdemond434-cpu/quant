"""A long-running miner must not append directly into the git-TRACKED data tree.

WHY THIS TEST EXISTS (2026-08-28, found live). Two FX Blue harvesters ran for six minutes
reporting row 50 while their output files held 28 rows. The `shell`/`dead` counts matched
exactly and only the large `has_data` records were missing -- not a parse bug.
`/proc/<pid>/fd/4` read `...track_records_wave2a.jsonl (deleted)`: this box's own automation
(`auto_push.sh` every 10 minutes, the hourly cycle) had checked the file out from under the
running process, and both workers carried on appending into orphaned inodes. Nothing errored,
and a reader would have seen a clean, short, plausible file.

The rule the test enforces: append to a staging path OUTSIDE the repository and publish to the
tracked artifact in ONE pass at the end, so the window a checkout can eat is a single rename.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MINER = REPO / "desks" / "mt5" / "scripts" / "fxblue_track_record_miner.py"


def _appended_paths(tree: ast.AST) -> list[str]:
    """Every `<expr>.open("a", ...)` receiver, rendered back to source."""
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "a"
        ):
            out.append(ast.unparse(node.func.value))
    return out


def test_harvest_loop_appends_to_a_staging_path_not_the_tracked_artifact() -> None:
    assert MINER.exists(), f"{MINER} moved -- update this test, do not delete it"
    tree = ast.parse(MINER.read_text(encoding="utf-8"))
    appended = _appended_paths(tree)
    assert appended, "the miner no longer appends anywhere -- if the write moved, re-point this"
    # The row-by-row append (the one that runs for the whole harvest) must target staging.
    assert any("stage" in a for a in appended), (
        "the harvest loop appends straight into the tracked tree; a checkout mid-run will unlink "
        f"it and the process will keep writing to an orphaned inode. Appends found: {appended}"
    )


def test_staging_directory_is_outside_the_repository() -> None:
    src = MINER.read_text(encoding="utf-8")
    assert "FXBLUE_STAGE" in src, "the staging path must be overridable by environment"
    tree = ast.parse(src)
    defaults = [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "FXBLUE_STAGE"
        and isinstance(node.args[1], ast.Constant)
    ]
    assert defaults, "FXBLUE_STAGE needs a default staging directory"
    for d in defaults:
        assert REPO not in Path(d).resolve().parents and Path(d).resolve() != REPO, (
            f"staging default {d!r} is inside the repo, which is the exact tree a checkout rewrites"
        )
