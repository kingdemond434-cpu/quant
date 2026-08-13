"""L1.60: a denominator that silently loses members is a coverage claim the desk cannot cash.

The cases below are the four the detector has to separate, because getting any one of them wrong
retires the fence: a miss lets a hollow verdict through, and a false positive on the desk's own
correct practice gets the whole check switched off (L1.43).
"""
from __future__ import annotations

from pathlib import Path

from libs.ops.attrition import analyse_paths, analyse_source, summarise

# The canonical leak: 991 unreadable files vanish from a count that is then declared to
# fence_exit as the denominator of a passing verdict.
LEAKING = '''
def scan(paths):
    n = 0
    for p in paths:
        try:
            text = p.read_text("utf-8")
        except OSError:
            continue
        n += 1
    return fence_exit("OK", {"OK"}, scanned=n, of="*.py")
'''

# The L2.4 exemplar, live at scripts/check_funding_capture.py:168 -- the discard is COUNTED.
COUNTED_DISCARD = '''
def scan(rows):
    n = malformed = 0
    for r in rows:
        if r is None:
            malformed += 1
            continue
        n += 1
    return fence_exit("OK", {"OK"}, scanned=n, of="rows")
'''

# The prescribed repair: one tally above the first skip, so every discard is visible at once.
ATTEMPTED_FIRST = '''
def scan(paths):
    n = attempted = 0
    for p in paths:
        attempted += 1
        if p.suffix != ".py":
            continue
        try:
            text = p.read_text("utf-8")
        except OSError:
            continue
        n += 1
    return fence_exit("OK", {"OK"}, scanned=n, of="*.py")
'''

# NOT a scope denominator: a log-rank risk-set guard, live at scripts/check_row_atomicity.py.
# `var` is a divisor, but it makes no claim about how much of the world was examined.
STATISTICAL_ACCUMULATOR = '''
def logrank(times, a, b):
    var = 0.0
    for t in times:
        n = len(a) + len(b)
        d = sum(1 for o in a if o["days"] == t)
        if n < 2 or d == 0:
            continue
        var += d * (n - d) / (n - 1)
    return (obs - exp) ** 2 / var
'''


def test_flags_the_uncounted_handler_skip() -> None:
    res = analyse_source(LEAKING, "leaky.py")
    assert len(res.findings) == 1, res.findings
    f = res.findings[0]
    assert f.counter == "n"
    assert f.has_handler, "a skip inside `except` is the sharp case and must be labelled"
    assert "attempted" in f.as_row()["repair"]


def test_counted_discard_is_not_a_finding() -> None:
    """The desk's own L2.4 practice must not be punished, or the fence gets switched off."""
    assert analyse_source(COUNTED_DISCARD, "ok.py").findings == []


def test_attempted_tally_before_first_skip_is_not_a_finding() -> None:
    """The fence must go quiet after the exact repair it prescribes."""
    assert analyse_source(ATTEMPTED_FIRST, "fixed.py").findings == []


def test_statistical_accumulator_is_not_a_scope_denominator() -> None:
    """Precision: flagging every divisor would bury the real findings in arithmetic."""
    assert analyse_source(STATISTICAL_ACCUMULATOR, "stats.py").findings == []


def test_a_sum_before_the_skip_does_not_excuse_the_leak() -> None:
    """`total += price` runs unconditionally too, but a SUM cannot report members lost."""
    src = LEAKING.replace("    n = 0\n", "    n = 0\n    total = 0\n").replace(
        "    for p in paths:\n", "    for p in paths:\n        total += p.size\n")
    assert len(analyse_source(src, "sum.py").findings) == 1


def test_guard_shape_feeding_a_dict_pct_key_is_flagged() -> None:
    """The money-path shape, pinned. It is a plain `if`, not an `except`, and the ratio lives in
    a dict key -- the exact form that hid at check_coverage_floors.py:141 until 2026-08-12."""
    src = '''
def measure(report, MONEY_PATH):
    stmts = covered = 0
    for rel in MONEY_PATH:
        s = report["files"].get(rel, {}).get("summary")
        if not s:
            continue
        stmts += int(s["num_statements"])
        covered += int(s["covered_lines"])
    return {"money_path_pct": round(100.0 * covered / stmts, 2) if stmts else 0.0}
'''
    res = analyse_source(src, "money.py")
    assert len(res.findings) == 1, res.findings
    assert res.findings[0].counter == "stmts"
    assert not res.findings[0].has_handler, "this one is a guard, and it still leaks"


def test_unparseable_source_stays_in_the_denominator() -> None:
    """A scanner that drops what it cannot read reports a smaller, cleaner world (L2.4)."""
    res = analyse_source("def broken(:\n", "bad.py")
    assert res.parsed is False and res.error
    s = summarise([res])
    assert s["n_examined"] == 1, "the unparseable file must remain counted"
    assert s["n_parsed"] == 0 and s["n_unparsed"] == 1


def test_unreadable_path_becomes_a_row_not_a_skip(tmp_path: Path) -> None:
    missing = tmp_path / "gone.py"
    results = analyse_paths([missing], tmp_path)
    assert len(results) == 1 and results[0].parsed is False
    assert summarise(results)["n_examined"] == 1


def test_tagged_exemption_is_reported_never_hidden() -> None:
    src = LEAKING.replace("        except OSError:\n",
                          "        except OSError:  # attrition-ok: venue 404s are the signal\n")
    res = analyse_source(src, "tagged.py")
    assert res.findings == []
    assert len(res.exempt) == 1
    assert "venue 404s" in res.exempt[0].exempt_reason
    assert summarise([res])["n_exempt"] == 1


def test_summarise_counts_every_path_handed_in() -> None:
    """This module is subject to its own law: n_examined is its denominator."""
    results = [analyse_source(LEAKING, "a.py"), analyse_source("def x(:", "b.py"),
               analyse_source(COUNTED_DISCARD, "c.py")]
    s = summarise(results)
    assert s["n_examined"] == 3
    assert s["n_findings"] == 1 and s["n_from_handler"] == 1
