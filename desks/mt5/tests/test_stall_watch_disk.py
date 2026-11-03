"""The disk watchdog heals itself, and the four ways it must not.

    "no human decision shud be needed its autopromoted"        -- the principal, 2026-09-08

WHAT THIS PINS. On 2026-09-08 the watchdog found 0.5GB free, pruned its single reclaim pool,
freed exactly nothing, wrote "needs a human decision" and stopped. The desk publisher died ten
minutes later; the gauntlet, allocator, shadow lane and dashboard were stale for twelve hours.
The script is PowerShell and runs only on the box, so these tests assert on its source -- the
same way `test_self_certifying_caps` pins the walk direction in `missed_growth`. A behavioural
test would need Windows and a full C: drive; a source test catches the regression that matters,
which is somebody quietly restoring the single-tier version or the give-up line.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "scripts" / "stall_watch.ps1").read_text("utf-8")
BLOCK = SRC[SRC.index("# DESK DISK FLOOR"):]

#: EXECUTABLE lines only. The invariants below are about what the script DOES; the comment above
#: the block quotes the old give-up string on purpose, to record what the defect was, and a test
#: that forbade the WORDS rather than the behaviour would forbid explaining the bug at all.
CODE = "\n".join(ln for ln in BLOCK.splitlines() if not ln.lstrip().startswith("#"))


# --------------------------------------------------------------- it never waits to be rescued
def test_it_never_terminates_on_a_human_decision() -> None:
    """The exact string that took the desk down. It may appear only as the thing being escalated
    past, never as the last word."""
    assert "needs a human decision" not in CODE
    assert "escalating automatically on the next pass" in CODE


def test_the_critical_line_says_what_is_left_rather_than_stopping() -> None:
    crit = [ln for ln in CODE.splitlines() if "DISK CRITICAL" in ln]
    assert crit, "a breach below 2GB must still be loud"
    assert "every safe pool is already empty" in crit[0]


# ------------------------------------------------------------------------ the ladder escalates
def test_there_is_a_real_ladder_not_one_pool() -> None:
    names = re.findall(r"name\s*=\s*'([^']+)'", BLOCK)
    assert len(names) >= 6, f"only {len(names)} reclaim tiers: {names}"
    # the original two must survive, and be FIRST -- cheapest before anything more costly
    assert names[0] == "logs>14d"
    assert names[1] == "gauntlet_cache"


#: The judge's cache-prune rule, as an AST shape: `_t.time() - <x>.stat().st_mtime > 3 * 86400`.
_DAYS, _DAY_S = 3, 86400
_STOPS = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def _is_const(node: ast.AST, value: object) -> bool:
    return (isinstance(node, ast.Constant) and type(node.value) is type(value)
            and node.value == value)


def _is_prune_rule(test: ast.AST) -> bool:
    """EXACTLY the rule and nothing else: one `>` comparison, no `and`/`or`, no extra factor."""
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Gt) and len(test.comparators) == 1):
        return False
    left, right = test.left, test.comparators[0]
    if not (isinstance(left, ast.BinOp) and isinstance(left.op, ast.Sub)):
        return False
    now, mtime = left.left, left.right
    return (isinstance(now, ast.Call) and not now.args and not now.keywords
            and isinstance(now.func, ast.Attribute) and now.func.attr == "time"
            and isinstance(now.func.value, ast.Name) and now.func.value.id == "_t"
            and isinstance(mtime, ast.Attribute) and mtime.attr == "st_mtime"
            and isinstance(mtime.value, ast.Call) and isinstance(mtime.value.func, ast.Attribute)
            and mtime.value.func.attr == "stat"
            and isinstance(right, ast.BinOp) and isinstance(right.op, ast.Mult)
            and _is_const(right.left, _DAYS) and _is_const(right.right, _DAY_S))


def _is_unlink(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute) and stmt.value.func.attr == "unlink")


def _statically_false(test: ast.AST) -> bool:
    """A guard that can never be true: a falsy constant, `not <truthy constant>`, or an `and`
    with any such operand."""
    if isinstance(test, ast.Constant):
        return not test.value
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return isinstance(test.operand, ast.Constant) and bool(test.operand.value)
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return any(_statically_false(v) for v in test.values)
    return False


def _reaches_live_prune(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, ast.If) and _is_prune_rule(stmt.test):
            for inner in stmt.body:
                if isinstance(inner, _STOPS):
                    break
                if _is_unlink(inner):
                    return True
        guard_false = isinstance(stmt, (ast.If, ast.While)) and _statically_false(stmt.test)
        blocks = [getattr(stmt, f, None) for f in ("orelse", "finalbody")]
        if not guard_false:
            blocks.insert(0, getattr(stmt, "body", None))
        blocks += [h.body for h in getattr(stmt, "handlers", None) or []]
        if any(isinstance(b, list) and b and _reaches_live_prune(b) for b in blocks):
            return True
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return False                  # everything after it in this block is dead code
    return False


def _judge_prunes_past_three_days(src: str) -> bool:
    """The rule is LIVE CODE that DELETES, read from the AST (v2.2, audit of e9175a8aa: a line
    scan still passed `and False`, `if False and`, a nested `if False:`, an early return and a
    `* 0`). True only when an `if` whose test IS the rule -- exactly, with nothing and-ed or
    multiplied into it -- carries an `.unlink(...)` call as a DIRECT statement of its body, with
    no return/raise/break/continue before it in that body, and the `if` is reachable: no
    enclosing `if`/`while` is statically false and no statement before it in any enclosing
    block returns or raises. A string or a docstring is not code and never counts.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    return _reaches_live_prune(tree.body)


def test_the_prune_pin_fails_when_the_rule_is_disarmed() -> None:
    """Each way to keep the text and lose the behaviour reads False."""
    def fn(body: str) -> str:
        return "def prune():\n    import time as _t\n" + body

    live = fn("    for _e in entries:\n"
              "        if _t.time() - _e.stat().st_mtime > 3 * 86400:\n"
              "            Path(_e.path).unlink(missing_ok=True)\n"
              "            n += 1\n")
    assert _judge_prunes_past_three_days(live)
    glob = fn("    try:\n"
              "        for _f in CACHE_DIR.glob('*.npz'):\n"
              "            if _t.time() - _f.stat().st_mtime > 3 * 86400:\n"
              "                _f.unlink(missing_ok=True)\n"
              "    except OSError:\n"
              "        pass\n")
    assert _judge_prunes_past_three_days(glob)
    rule = "_t.time() - _e.stat().st_mtime > 3 * 86400"
    unlink = "Path(_e.path).unlink(missing_ok=True)"
    disarmed = {
        "no_unlink": live.replace(unlink, "pass"),
        "commented": "".join("# " + ln + "\n" for ln in live.splitlines()),
        "unlink_commented": live.replace(unlink, "pass  # " + unlink),
        "rule_in_comment": live.replace(f"if {rule}:", f"if True:  # {rule}"),
        "unlink_outside": live.replace(f"            {unlink}\n", "            pass\n")
        + f"    {unlink}\n",
        "four_days": live.replace("> 3 * 86400", "> 4 * 86400"),
        # the auditor's disarmed variants (audit of e9175a8aa)
        "and_false": live.replace(f"if {rule}:", f"if {rule} and False:"),
        "if_false_and": live.replace(f"if {rule}:", f"if False and {rule}:"),
        "rule_in_docstring": fn(f'    """if {rule}:\n        {unlink}"""\n'),
        "rule_in_string": fn(f"    _s = 'if {rule}: {unlink}'\n"),
        "nested_if_false": live.replace(f"            {unlink}\n",
                                        f"            if False:\n                {unlink}\n"),
        "early_return": live.replace(f"            {unlink}\n",
                                     f"            return\n            {unlink}\n"),
        "early_return_outer": live.replace("    for _e in entries:\n",
                                           "    return\n    for _e in entries:\n"),
        "times_zero": live.replace("> 3 * 86400", "> 3 * 86400 * 0"),
        "rule_times_zero": live.replace(
            f"if {rule}:", "if (_t.time() - _e.stat().st_mtime) * 0 > 3 * 86400:"),
        "outer_if_false": live.replace("    for _e in entries:\n",
                                       "    if False:\n     for _e in entries:\n"),
    }
    for name, src in disarmed.items():
        assert not _judge_prunes_past_three_days(src), (name, src)


def test_todays_gauntlet_cache_goes_last_and_the_shard_plan_never() -> None:
    """The early tier deletes only what the judge's own > 3-day prune would delete next sweep (a
    weekend or a frozen symbol keeps one data-day for days, and a hit never touches mtime); the
    rest goes only as the last tier. The in-flight shard plan is never pruned: deleting it fails
    every shard closed and discards the sweep."""
    tiers = re.findall(r"name\s*=\s*'([^']+)';\s*path\s*=\s*\"[^\"]*\";\s*age\s*=\s*(-?\d+)", BLOCK)
    by = dict(tiers)
    assert by["gauntlet_cache"] == "3"
    judge = (Path(__file__).resolve().parents[1] / "scripts" / "external_gauntlet.py").read_text(
        "utf-8")
    # the rule this tier mirrors: > 3 days by mtime. Pinned by the RULE, not the loop variable:
    # the plan-phase image (a02f095c) reads mtime from an `os.scandir` entry (`_e`) where the
    # 46392548 image stats a globbed Path (`_f`); both are the same 3-day mtime prune.
    assert _judge_prunes_past_three_days(judge), \
        "the judge's own cache prune is no longer > 3 days by mtime; re-derive this tier's age"
    assert tiers[-1] == ("gauntlet_cache_today", "0")
    assert "\\gauntlet_cache\\shards" in BLOCK


def test_it_stops_as_soon_as_the_floor_is_cleared() -> None:
    """A mild shortage must cost a cache and nothing more. Running every tier regardless would
    throw away days of reports to recover a gigabyte nobody needed."""
    assert "if ((Get-PSDrive C).Free / 1GB -ge $DiskFloorGB) { break }" in BLOCK


def test_each_tier_measures_what_it_actually_reclaimed() -> None:
    """The 0.5 -> 0.5 defect: nothing measured bytes freed, so a prune of nothing and a prune of
    a gigabyte printed the same line."""
    assert "$f0 = (Get-PSDrive C).Free" in BLOCK
    assert "$gained = ((Get-PSDrive C).Free - $f0) / 1GB" in BLOCK
    assert "reclaimed $([math]::Round($gained,2))GB" in BLOCK


def test_a_missing_pool_reads_differently_from_an_empty_one() -> None:
    """"the path does not exist" and "there was nothing to delete" demand opposite responses and
    were indistinguishable -- both printed a successful-looking prune."""
    assert "Test-Path -LiteralPath $t.path" in BLOCK
    assert "pool path missing" in BLOCK


# --------------------------------------------------------------------------- the moat is safe
@pytest.mark.parametrize("guarded", [
    "\\data\\tape", "\\data\\secrets", "\\data\\universe",
    "RELEASE.json", "LIVE_MANIFEST.jsonl", "sleeve_registry.json",
])
def test_the_unrecoverable_data_is_refused_at_every_threshold(guarded: str) -> None:
    assert guarded in BLOCK, f"{guarded} is not on the protected list"


def test_every_delete_consults_the_protected_list() -> None:
    """A guard that exists but is not wired into the deletes is decoration. Both prune shapes --
    the directory sweep and the age sweep -- must filter through it."""
    removes = [ln for ln in BLOCK.splitlines() if "Remove-Item" in ln]
    assert len(removes) >= 2
    assert BLOCK.count("Test-DeskProtected") >= 3   # the definition plus both call sites


def test_the_tape_is_named_as_unrecoverable_so_nobody_relaxes_it_later() -> None:
    assert "unrecoverable" in BLOCK
    assert "The floor is never worth the moat." in BLOCK


# ------------------------------------------------------------------ the trigger did not change
def test_the_floor_is_still_five_gigabytes() -> None:
    """This change is about what happens BELOW the floor, not about moving it."""
    assert "$DiskFloorGB = 5" in BLOCK
    assert "if ($free -lt $DiskFloorGB)" in BLOCK


# ------------------------------------------------------------------ the RAM census is published
RAM = SRC[SRC.index("# RAM FLOOR"):SRC.index("# PROGRESS, NOT JUST PULSE")]
RAM_CODE = "\n".join(ln for ln in RAM.splitlines() if not ln.lstrip().startswith("#"))


def test_the_box_publishes_what_it_has_not_only_what_is_free() -> None:
    """A day was spent arguing 80GB against "phys 142MB free". The counter that settles it was
    read on every pass and written nowhere."""
    assert "TotalVisibleMemorySize" in RAM_CODE
    assert "TotalVirtualMemorySize" in RAM_CODE
    for key in ("total_phys_mb", "free_phys_mb", "total_commit_mb", "free_commit_mb"):
        assert key in RAM_CODE, key


def test_the_largest_commit_holders_are_named_across_every_process() -> None:
    """Shedding sorts by commit; the census must show the same ranking, and it must include the
    terminal and the browser, which are never shed but are half the answer."""
    assert "top_commit" in RAM_CODE
    assert ("Get-CimInstance Win32_Process | Sort-Object -Property PageFileUsage -Descending"
            in RAM_CODE)
    assert "-First 6" in RAM_CODE


def test_the_census_travels_with_the_verdict_and_starts_unmeasured() -> None:
    assert "memory = $memCensus" in SRC
    assert "$memCensus = @{ status = 'UNMEASURED' }" in RAM_CODE   # a failed read is not zero


def test_the_shed_still_measures_the_smaller_of_ram_and_commit() -> None:
    """The census is additive; the floor's own arithmetic is untouched."""
    assert "$freeMB = [math]::Min($freePhysMB, $freeVirtMB)" in RAM_CODE
    assert "if ($freeMB -lt 500 -and $strikes -ge 2)" in RAM_CODE
