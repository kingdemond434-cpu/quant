"""TIER-3 rail guard: the dead-man's state write must be atomic.

The rail's job is to work during ABNORMAL conditions, and abnormal conditions are exactly when
hosts OOM and reboot. A truncate-then-write in that window loses the high-water mark, which
silently moves the 35% fire line DOWN -- the failure is not a crash, it is a quieter rail."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "scripts/run_deadman_switch.py"


def _load(tmp: Path):
    """Import the rail with its paths pointed at a tmpdir -- never touches real desk state."""
    spec = importlib.util.spec_from_file_location("deadman_under_test", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    (tmp / "data").mkdir(parents=True, exist_ok=True)
    mod._STATE = tmp / "data/deadman_state.json"
    return mod


class TestAtomicStateWrite:
    def test_state_round_trips(self, tmp_path: Path) -> None:
        m = _load(tmp_path)
        m._write_state({"hw": 15700.0, "same_count": 2, "fired": False})
        assert json.loads(m._STATE.read_text("utf-8"))["hw"] == 15700.0

    def test_no_temp_file_is_left_behind(self, tmp_path: Path) -> None:
        m = _load(tmp_path)
        m._write_state({"hw": 1.0})
        assert list((tmp_path / "data").glob("*.tmp")) == []

    def test_overwrite_never_leaves_a_partial_file(self, tmp_path: Path) -> None:
        # the whole point: a reader mid-write sees the OLD complete state, never a truncated one
        m = _load(tmp_path)
        m._write_state({"hw": 15700.0, "n": 1})
        big = {"hw": 15700.0, "pad": "x" * 200_000}
        m._write_state(big)
        loaded = json.loads(m._STATE.read_text("utf-8"))
        assert loaded["hw"] == 15700.0 and len(loaded["pad"]) == 200_000

    def test_high_water_mark_survives_repeated_writes(self, tmp_path: Path) -> None:
        m = _load(tmp_path)
        for i in range(50):
            m._write_state({"hw": 15700.0, "i": i})
        s = json.loads(m._STATE.read_text("utf-8"))
        assert s["hw"] == 15700.0 and s["i"] == 49

    def test_the_rail_still_uses_no_libs_imports(self) -> None:
        # TIER-3 isolation: no LLM, no strategy logic, no libs/ imports. The atomic-write change
        # must not have quietly coupled the rail to the codebase it is meant to be independent of.
        # Parsed from the AST, not grepped -- the module DOCSTRING states the constraint in prose
        # ("no imports from libs/"), and a substring check flags its own description.
        import ast
        tree = ast.parse(_SRC.read_text("utf-8"))
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                imported.add(n.module.split(".")[0])
        assert "libs" not in imported, f"TIER-3 isolation broken: {imported}"
        assert imported <= {"__future__", "hashlib", "hmac", "json", "os", "time", "urllib",
                            "pathlib"}, f"unexpected dependency added to the rail: {imported}"

    def test_the_rail_is_not_in_the_mypy_files_list(self) -> None:
        """The rail must stay OUT of mypy's `files`, or the gate itself pressures a Tier-3 edit.

        2026-07-26: an automated typing pass added the rail to mypy `files`. Strict mode then
        demanded `Any` for its heterogeneous JSON state bags, so the pass added
        `from typing import Any` -- which trips the import allowlist above -- and, while there,
        rewrote `should_fire`'s return to `bool(int(...))`, a BEHAVIOUR change on the trigger
        path (a corrupt `breaches: "5"` went from TypeError to firing). CI went red and stayed
        red until the rail was reverted.

        The lesson generalises: putting a never-touch file under a checker that DEMANDS edits
        sets the two guards fighting, and the checker wins because it runs on every commit.
        Isolation is this rail's protection; type coverage is not worth trading it for.
        """
        import tomllib
        cfg = tomllib.loads((_SRC.parents[1] / "pyproject.toml").read_text("utf-8"))
        listed = cfg["tool"]["mypy"]["files"]
        assert not any("run_deadman_switch" in f for f in listed), (
            "TIER-3 rail is under mypy again -- strict mode will demand an import the rail's "
            f"allowlist forbids, taking CI red. Remove it from [tool.mypy] files: {listed}"
        )
