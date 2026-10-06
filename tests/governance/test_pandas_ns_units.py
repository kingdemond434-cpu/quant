"""LAW: a datetime becomes an integer only through an EXPLICIT unit.

Measured 2026-10-06: pandas 3 builds `date_range` and parses ISO strings at MICROSECOND
resolution, so `idx.asi8`, `idx.view("int64")` and `series.astype("int64")` return microseconds
where the code beside them divides by 1e9 or compares against 3_600_000_000_000. The EventClock
read a 10-bar distance as 0.01, replication's bar clock read hourly bars as one minute apart, and
the gauntlet's daily cache wrote 1970 dates. The production pin is pandas 2.3.3 and the test
container runs 3.x, and nothing failed loudly -- the numbers were just wrong by 1000x.

The rule this file enforces, over every tracked .py file: `.asi8`, `.view(<int>)`, and an
int cast of anything datetime-shaped must carry its unit in the same expression --
`.as_unit("ns")` (or another explicit unit), `datetime64[<unit>]`, or `np.datetime64(x, unit)`.
`Timestamp.value` is NOT checked: it is nanoseconds on every resolution, by pandas' contract.

An entry in ALLOW is a measured false positive with its reason. PENDING names a real hit whose
fix lives outside this branch (a sealed file's patch, or another open PR); it may vanish.
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_INT = {"int64", "i8", "<i8", "int", "int_"}
#: Receivers that look like a datetime. Deliberately excludes "time": MT5's `time`/`time_msc`
#: columns are already epoch integers, and integer clock arithmetic is not a datetime.
_HINTS = ("index", "idx", "to_datetime", "DatetimeIndex", "date_range", ".dt",
          "datetime64", "Timestamp", "stamp", "date")
_EXPLICIT = re.compile(r"as_unit\(|(?:datetime|timedelta)64\[\w+\]|M8\[\w+\]")

#: Path segments never scanned: retired code runs on no clock.
SKIP_SEGMENTS = ("/_retired/",)

#: (path, unparsed expression) -> why it is not the bug.
ALLOW: dict[tuple[str, str], str] = {
    ("desks/mt5/scripts/check_asi8.py", "idx_tz.asi8"):
        "diagnostic that PRINTS the raw resolution-dependent value on purpose",
    ("desks/mt5/scripts/check_asi8.py", "idx_naive.asi8"):
        "diagnostic that PRINTS the raw resolution-dependent value on purpose",
    ("desks/mt5/scripts/check_parquet_idx.py", "h1.index.asi8"):
        "diagnostic that PRINTS the raw resolution-dependent value on purpose",
    ("libs/data/feature_store.py", "series.index.to_numpy(dtype='int64')"):
        "an Int64 index of ns already, built by _utc_ns (as_unit('ns')), not a DatetimeIndex",
    ("libs/data/feature_store.py", "z.index.to_numpy(dtype='int64')"):
        "an Int64 index of ns already, built by _utc_ns (as_unit('ns')), not a DatetimeIndex",
}

#: (path, unparsed expression) -> where the fix lives.
PENDING: dict[tuple[str, str], str] = {
    ("desks/mt5/scripts/external_gauntlet.py", "pd.to_datetime(common).astype('int64')"):
        "SEALED: /mnt/project-files/patches/pandas_ns_units.patch",
    ("desks/mt5/research/replication_civilization.py", "stamps[keep].astype('int64')"):
        "PR #240 (claude/replication-bars-ns)",
}


def _files() -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.py"], check=True,
                             capture_output=True, text=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        out = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py") if ".git" not in p.parts]
    return [f for f in out if not any(s in f"/{f}" for s in SKIP_SEGMENTS)]


def _is_int(node: ast.AST | None) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value in _INT
    if isinstance(node, ast.Attribute):
        return node.attr == "int64"
    return isinstance(node, ast.Name) and node.id == "int"


def _explicit(src: str) -> bool:
    return bool(_EXPLICIT.search(src))


def _np_datetime64_with_unit(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "datetime64" and len(node.args) >= 2)


def hits(path: Path, rel: str) -> list[tuple[str, int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    out: list[tuple[str, int, str]] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr == "asi8":
            recv = ast.unparse(n.value)
            if not _explicit(recv):
                out.append((rel, n.lineno, ast.unparse(n)))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            attr, recv_node = n.func.attr, n.func.value
            recv = ast.unparse(recv_node)
            if _explicit(recv) or _np_datetime64_with_unit(recv_node):
                continue
            if attr == "view" and n.args and _is_int(n.args[0]):
                out.append((rel, n.lineno, ast.unparse(n)))
            elif attr in ("astype", "to_numpy"):
                arg = n.args[0] if n.args else next(
                    (k.value for k in n.keywords if k.arg == "dtype"), None)
                if _is_int(arg) and any(h in recv for h in _HINTS):
                    out.append((rel, n.lineno, ast.unparse(n)))
    return out


def test_no_datetime_becomes_an_integer_without_its_unit() -> None:
    found = [h for f in _files() for h in hits(ROOT / f, f)]
    bad = [f"{p}:{ln}: {s}" for p, ln, s in found
           if (p, s) not in ALLOW and (p, s) not in PENDING]
    assert not bad, (
        "a datetime is cast to an integer with no explicit unit; under pandas 3 that is "
        "microseconds, not nanoseconds. Use `.as_unit(\"ns\")` (or name the unit) in the same "
        "expression:\n  " + "\n  ".join(bad))


def test_every_allowlist_entry_is_still_a_live_false_positive() -> None:
    """The allowlist cannot outlive the code it excuses."""
    found = {(p, s) for f in _files() for p, _, s in hits(ROOT / f, f)}
    stale = [f"{p}: {s}" for (p, s) in ALLOW if (p, s) not in found]
    assert not stale, "remove stale ALLOW entries:\n  " + "\n  ".join(stale)


def test_the_scanner_still_sees_the_bug_it_was_written_for(tmp_path: Path) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import pandas as pd\n"
        "idx = pd.date_range('2024-01-01', periods=3, freq='h', tz='UTC')\n"
        "a = idx.asi8 / 1e9\n"
        "b = idx.view('int64')\n"
        "c = pd.to_datetime(['2024-01-01']).astype('int64')\n"
        "ok1 = idx.as_unit('ns').asi8\n"
        "ok2 = idx.to_numpy().astype('datetime64[ns]').astype('int64')\n"
        "ok3 = df['time_msc'].astype('int64')\n", encoding="utf-8")
    got = sorted(s for _, _, s in hits(probe, "probe.py"))
    assert got == sorted(["idx.asi8", "idx.view('int64')",
                          "pd.to_datetime(['2024-01-01']).astype('int64')"])
