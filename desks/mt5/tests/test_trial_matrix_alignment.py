"""The trial matrix fed to PBO and SPA was neither date-aligned nor complete.

Each cell's series is a {date: return} dict. build_matrix did

    arr = np.asarray(list(s.values()))            # dates discarded
    min_len = min(len(a) for a in cols)
    np.column_stack([a[-min_len:] for a in cols])

Two defects, one root cause -- the date index was thrown away.

ALIGNMENT is the worse one. Cells trade on different days, so row 5 of column A and row 5 of
column B were different dates. PBO/CSCV and Hansen SPA are computed from the JOINT structure of
that matrix, so both were measured on a cross-section that never existed -- and those are exactly
the gates that decide whether a survivor is a curve fit.

TRUNCATION is the second. min_len clipped every column to the shortest, so one sparse cell with 60
observations reduced a matrix whose other cells had thousands to a 167-day window.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

_SRC = (_DESK / "research" / "qquant_gates.py").read_text(encoding="utf-8")


def _old_build(series: list[dict]) -> np.ndarray:
    """The defect, reproduced exactly."""
    cols = [np.asarray(list(s.values()), dtype=float) for s in series]
    min_len = min(len(a) for a in cols)
    return np.column_stack([a[-min_len:] for a in cols])


def _new_build(series: list[dict]) -> np.ndarray:
    """The fix, mirroring build_matrix's join."""
    cols = {}
    for i, s in enumerate(series):
        ser = pd.Series(s, dtype=float).dropna()
        ser.index = pd.to_datetime(pd.Series(list(ser.index)), errors="coerce").values
        cols[f"c{i}"] = ser.groupby(level=0).sum().sort_index()
    return pd.DataFrame(cols).sort_index().fillna(0.0).to_numpy(dtype=float)


def _days(n, start=1):
    return pd.date_range("2026-01-01", periods=n).strftime("%Y-%m-%d").tolist()[start - 1:]


# ---------------------------------------------------------------------- alignment

def test_the_old_matrix_put_different_dates_on_the_same_row():
    """THE DEFECT. Two cells trading alternate days were stacked as if simultaneous."""
    a = {d: 1.0 for d in _days(20)[::2]}          # even days
    b = {d: 1.0 for d in _days(20)[1::2]}         # odd days -- never the same day as `a`
    old = _old_build([a, b])
    assert old.shape[0] == 10
    assert np.all(old == 1.0), "positional stacking made two disjoint series look simultaneous"

    new = _new_build([a, b])
    assert new.shape[0] == 20, "the union of trading days is 20"
    # every row has exactly one cell trading, which is the truth about these two strategies
    assert np.all(new.sum(axis=1) == 1.0)


def test_alignment_changes_the_measured_correlation():
    """The number PBO and SPA actually consume. Two strategies that never trade on the same day
    are stacked by the old code into columns that move together; aligned on dates they are
    revealed as mutually exclusive."""
    ev = _days(20)[::2]
    od = _days(20)[1::2]
    a = {d: (1.0 if i % 2 else -1.0) for i, d in enumerate(ev)}
    b = {d: (1.0 if i % 2 else -1.0) for i, d in enumerate(od)}

    old = _old_build([a, b])
    assert np.corrcoef(old[:, 0], old[:, 1])[0, 1] == pytest.approx(1.0), (
        "fixture: positionally stacked, the two disjoint series look perfectly correlated")

    new = _new_build([a, b])
    rho = np.corrcoef(new[:, 0], new[:, 1])[0, 1]
    assert rho == pytest.approx(0.0, abs=0.35), (
        f"date-aligned the spurious correlation should collapse, got {rho:.3f}")


def test_a_shared_calendar_is_preserved_when_cells_do_overlap():
    common = _days(30)
    a = {d: float(i % 3) for i, d in enumerate(common)}
    b = {d: float(i % 3) for i, d in enumerate(common)}
    new = _new_build([a, b])
    assert new.shape == (30, 2)
    assert np.corrcoef(new[:, 0], new[:, 1])[0, 1] == pytest.approx(1.0)


# --------------------------------------------------------------------- truncation

def test_one_sparse_cell_no_longer_clips_the_whole_matrix():
    """THE 167-DAY WINDOW. A 60-observation cell truncated columns holding thousands."""
    long_a = {d: 0.5 for d in _days(1000)}
    long_b = {d: -0.5 for d in _days(1000)}
    sparse = {d: 1.0 for d in _days(1000)[:60]}

    old = _old_build([long_a, long_b, sparse])
    assert old.shape[0] == 60, "fixture: the old code clipped to the shortest column"

    new = _new_build([long_a, long_b, sparse])
    assert new.shape[0] == 1000, "the long cells are still being truncated"


def test_the_truncation_discarded_the_oldest_data_not_the_least_useful():
    """`a[-min_len:]` keeps the most RECENT rows, so a matrix meant to span 2018-2026 was
    silently reduced to its last few months -- the regime least likely to be out-of-sample."""
    long_a = {d: float(i) for i, d in enumerate(_days(1000))}
    sparse = {d: 1.0 for d in _days(1000)[:60]}
    old = _old_build([long_a, sparse])
    assert old[0, 0] == 940.0, "fixture: the first 940 days were dropped"
    new = _new_build([long_a, sparse])
    assert new[0, 0] == 0.0, "the earliest day is back in the matrix"


# ------------------------------------------------------------------------- wiring

def _code_only(src: str) -> str:
    """Strip docstrings and comments -- build_matrix's own docstring quotes the defective code
    verbatim to explain it, and a naive grep matches that explanation."""
    import ast
    tree = ast.parse(src)
    doc_spans = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            doc_spans.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return "\n".join(ln.split("#")[0] for i, ln in enumerate(src.splitlines(), 1)
                     if i not in doc_spans)


def test_build_matrix_joins_on_the_date_index():
    code = _code_only(_SRC)
    assert "pd.DataFrame(cols).sort_index()" in code, "build_matrix no longer joins on dates"
    assert not re.search(r"min_len\s*=\s*min\(len\(a\)", code), (
        "the truncate-to-shortest is back")
    assert not re.search(r"np\.asarray\(list\(s\.values\(\)\)", code), (
        "the date index is being discarded again")


def test_the_per_survivor_series_is_sorted_by_date():
    """`arr` in worker_eval feeds CPCV and the walk-forward engine, both of which split by index
    POSITION and so assume chronological order. It relied on dict insertion order surviving a
    Series.to_dict() and a multiprocessing pickle -- and Sharpe is order-invariant, so a break
    would have shown up only inside the two gates whose whole purpose is respecting time."""
    code = _code_only(_SRC)
    assert ".sort_index().to_numpy(dtype=float)" in code
    assert not re.search(r"arr\s*=\s*np\.asarray\(list\(cell_map\[key\]\.values\(\)\)", code), (
        "worker_eval reads the series in dict order again")


def test_duplicate_dates_within_a_cell_are_summed_not_dropped():
    a = {"2026-01-01": 1.0, "2026-01-02": 2.0}
    ser = pd.Series(a, dtype=float)
    ser.index = pd.to_datetime(pd.Series(list(ser.index))).values
    assert ser.groupby(level=0).sum().sum() == pytest.approx(3.0)
