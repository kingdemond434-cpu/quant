"""The L1.48 calendar-gate scanner: what it counts, and the two things it must stop counting.

Both repairs pinned here remove ITEMS FROM A WORK QUEUE, which is the direction that needs the
tightest guard -- a scanner made quieter is indistinguishable from a codebase made cleaner unless
something asserts exactly which hits went away and why. So each test that removes a hit is paired
with one that proves the neighbouring real gate SURVIVES:

  prose      a day number inside a docstring cannot execute      <-> `.days > 14` beside a string
  duplicate  a nested checkout is the same lines at another sha  <-> the same file in the real tree
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


def _fence() -> Any:
    """A FRESH module per test: scan() publishes its denominator through module globals."""
    spec = importlib.util.spec_from_file_location(
        "_ccg", _ROOT / "scripts" / "check_calendar_gates.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, "utf-8")
    return p


def test_a_day_number_in_a_docstring_is_prose_not_a_gate(tmp_path: Path) -> None:
    """The module that DESCRIBES the habit L1.48 kills was reported as four offenders."""
    _write(tmp_path, "libs/clock.py", '''"""Prose about the defect.

    A lifecycle that says days < 90 is measuring the wrong quantity.
    So is one that says fwd_days >= 30.
    PROBATION_DAYS = 14 is the same mistake with a constant's name on it.
    """
X = 1
''')
    mod = _fence()
    violations, exempt = mod.scan(tmp_path)
    assert violations == [] and exempt == []
    # Retired, and SAID SO. A hit this fence declines to count is a claim that must be auditable.
    assert mod.N_PROSE == 3
    assert mod.N_SCANNED == 1


def test_code_beside_a_string_is_still_a_gate(tmp_path: Path) -> None:
    """The regression that a line-level fix would cause -- and that the measuring pass DID cause.

    scripts/max_audit.py:887 is `(now - fromisoformat(f["raised"])).days > 14`: a real gate on a
    line that also holds a string. Asking "is line 887 touched by a string token" answers yes and
    retires a live defect. Only the COLUMNS separate the two cases.
    """
    _write(tmp_path, "libs/organ.py",
           'import datetime\n'
           'def f(rows, now):\n'
           '    return [r for r in rows\n'
           '            if (now - datetime.datetime.fromisoformat(r["raised"])).days > 14]\n')
    mod = _fence()
    violations, _ = mod.scan(tmp_path)
    assert [(v[1], v[2]) for v in violations] == [(4, "days > 14")]
    assert mod.N_PROSE == 0


def test_a_nested_checkout_is_a_copy_not_a_site(tmp_path: Path) -> None:
    """Five agent worktrees made 83% of the published checklist un-closable by any commit."""
    _write(tmp_path, "scripts/organ.py", "PROBATION_DAYS = 14\n")
    _write(tmp_path, ".claude/worktrees/agent-a/scripts/organ.py", "PROBATION_DAYS = 14\n")
    _write(tmp_path, ".claude/worktrees/agent-a/.git", "gitdir: /elsewhere\n")
    mod = _fence()
    violations, _ = mod.scan(tmp_path)
    # The site is reported ONCE, from the tree a commit can actually change.
    assert [v[0] for v in violations] == ["scripts/organ.py"]
    assert mod.N_DUPLICATE == 1
    assert mod.N_SCANNED == 1


def test_the_real_tree_is_not_mistaken_for_a_nested_checkout(tmp_path: Path) -> None:
    """`root` has a .git of its own. Skipping IT would empty the scan and read as CLEAN."""
    (tmp_path / ".git").mkdir()
    _write(tmp_path, "scripts/organ.py", "PROBATION_DAYS = 14\n")
    mod = _fence()
    violations, _ = mod.scan(tmp_path)
    assert [v[0] for v in violations] == ["scripts/organ.py"]
    assert mod.N_DUPLICATE == 0


def test_an_unparseable_file_keeps_every_hit(tmp_path: Path) -> None:
    """No string map means UNKNOWN, and unknown reports MORE, never less (L1.28a)."""
    _write(tmp_path, "libs/broken.py", "def f(:\nPROBATION_DAYS = 14\n")
    mod = _fence()
    violations, _ = mod.scan(tmp_path)
    assert [(v[1], v[2]) for v in violations] == [(2, "PROBATION_DAYS = 14")]
    assert mod.N_UNPARSED == 1
    assert mod.N_PROSE == 0


def test_every_offered_path_is_accounted_for(tmp_path: Path) -> None:
    """L1.60: attempted = scanned + unreadable + duplicate + out-of-scope, with nothing left over.

    The identity is the whole guarantee. A future skip added above the counters would break this
    before it could quietly shrink the checklist.
    """
    _write(tmp_path, "scripts/organ.py", "PROBATION_DAYS = 14\n")
    _write(tmp_path, "tests/test_organ.py", "PROBATION_DAYS = 14\n")   # out of scope
    _write(tmp_path, "data/dump.py", "PROBATION_DAYS = 14\n")          # out of scope
    _write(tmp_path, ".claude/worktrees/a/.git", "gitdir: /elsewhere\n")
    _write(tmp_path, ".claude/worktrees/a/scripts/organ.py", "PROBATION_DAYS = 14\n")
    mod = _fence()
    mod.scan(tmp_path)
    out_of_scope = (mod.N_ATTEMPTED - mod.N_SCANNED - mod.N_UNREADABLE - mod.N_DUPLICATE)
    assert mod.N_ATTEMPTED == 4          # the .git marker is not a *.py path
    assert (mod.N_SCANNED, mod.N_DUPLICATE, mod.N_UNREADABLE, out_of_scope) == (1, 1, 0, 2)


def test_the_denominator_line_names_every_discard(tmp_path: Path) -> None:
    """A count nobody prints is a count nobody can dispute."""
    _write(tmp_path, "scripts/organ.py", '"""days >= 90 in prose."""\nX = 1\n')
    _write(tmp_path, ".claude/worktrees/a/.git", "gitdir: /elsewhere\n")
    _write(tmp_path, ".claude/worktrees/a/scripts/organ.py", "PROBATION_DAYS = 14\n")
    mod = _fence()
    mod.scan(tmp_path)
    line = mod._denominator_line()
    assert "1 in nested checkouts" in line
    assert "1 hit(s) retired as PROSE" in line
