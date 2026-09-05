"""Tests for the cross-section floor (L1.62 family) and its fence.

The regression these pin is the one that produced the module: a per-date cross-sectional collapse
over a thin cross-section manufactures serial structure in the resulting SERIES. Measured on the
desk's own panel at rho=+0.856 against a floored truth of -0.06, with 4% of dates carrying 98% of
the statistic.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.research.cross_section_floor import (
    DEFAULT_MIN_SYMBOLS,
    apply_floor,
    measure_cross_section,
)

ROOT = Path(__file__).resolve().parents[2]


def _load_fence():
    spec = importlib.util.spec_from_file_location(
        "check_cross_section_floor", ROOT / "scripts/check_cross_section_floor.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_cross_section_floor"] = mod
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------- the instrument


def test_thin_dates_are_identified_and_counted() -> None:
    a = np.random.default_rng(0).normal(size=(20, 12))
    a[3, 4:] = np.nan          # 4 finite -> thin
    a[7, 2:] = np.nan          # 2 finite -> thin
    cs = measure_cross_section(a, min_symbols=8)
    assert cs.measured
    assert cs.n_thin == 2
    assert cs.thin_dates == (3, 7)
    assert cs.n_usable == 18
    assert cs.finite_min == 2
    assert not cs.mask[3] and not cs.mask[7] and cs.mask[0]


def test_declared_width_is_reported_beside_the_thinnest_row() -> None:
    """The near-miss, made visible: shape[1] says 300, the thinnest date carries 3."""
    a = np.full((10, 300), 1.0)
    a[5, 3:] = np.nan
    cs = measure_cross_section(a, min_symbols=8)
    assert cs.n_columns == 300          # what `shape[1]` would have reported
    assert cs.finite_min == 3           # what the collapse actually rests on
    assert cs.n_thin == 1


@pytest.mark.parametrize("panel,why", [
    (np.zeros((0, 5)), "empty"),
    (np.zeros((5, 0)), "empty"),
    (np.zeros(7), "2-D"),
    (np.full((6, 3), 1.0), "below"),                     # narrower than the floor
])
def test_unmeasurable_panels_refuse(panel: np.ndarray, why: str) -> None:
    cs = measure_cross_section(panel, min_symbols=8)
    assert cs.status == "UNMEASURABLE"
    assert why in cs.why
    assert not cs.measured


def test_refusal_masks_everything_never_nothing() -> None:
    """L1.28a: absence resolves to the TIGHTER answer.

    A caller that ignores the status and uses the mask must get NO dates, never every date.
    """
    a = np.full((9, 4), 1.0)                              # 4 columns, floor 8 -> unmeasurable
    cs = measure_cross_section(a, min_symbols=8)
    assert cs.status == "UNMEASURABLE"
    assert cs.mask.shape == (9,)
    assert not cs.mask.any()


def test_no_date_clears_the_floor_is_a_refusal() -> None:
    a = np.full((10, 20), np.nan)
    a[:, :3] = 1.0                                        # every date carries 3
    cs = measure_cross_section(a, min_symbols=8)
    assert cs.status == "UNMEASURABLE"
    assert "thickest is 3" in cs.why
    assert not cs.mask.any()


def test_apply_floor_pandas_blanks_thin_rows_and_keeps_shape() -> None:
    df = pd.DataFrame(np.ones((6, 10)), index=pd.date_range("2026-01-01", periods=6))
    df.iloc[2, 3:] = np.nan
    out, cs = apply_floor(df, min_symbols=8)
    assert out.shape == df.shape
    assert list(out.index) == list(df.index)
    assert out.iloc[2].isna().all()
    assert not out.iloc[0].isna().any()
    assert cs.n_thin == 1


def test_apply_floor_numpy_and_unmeasurable_returns_all_nan() -> None:
    out, cs = apply_floor(np.ones((5, 3)), min_symbols=8)
    assert cs.status == "UNMEASURABLE"
    assert np.isnan(out).all()


def test_default_floor_is_at_least_two() -> None:
    assert DEFAULT_MIN_SYMBOLS >= 2
    assert measure_cross_section(np.ones((4, 9)), min_symbols=1).min_symbols == 2


def test_thin_dates_manufacture_serial_structure_that_the_floor_removes() -> None:
    """THE MEASURED DEFECT, reproduced.

    Independent noise everywhere. A handful of consecutive dates carry a tiny cross-section, so
    their means are wild -- and the resulting SERIES shows strong lag-1 autocorrelation that the
    underlying data does not have.
    """
    rng = np.random.default_rng(7)
    a = rng.normal(size=(200, 60))
    for d in (100, 101, 102, 103):
        a[d, 1:] = np.nan
        a[d, 0] = 40.0                      # one wild name, no cross-section to average it away

    def lag1(x: np.ndarray) -> float:
        x = x[np.isfinite(x)]
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])

    unfloored = lag1(np.nanmean(a, axis=1))
    cs = measure_cross_section(a, min_symbols=8)
    # Collapse only the rows the floor admits: masking them to NaN first and averaging would hit
    # numpy's empty-slice warning, which this suite treats as an error.
    floored = lag1(np.nanmean(a[cs.mask], axis=1))

    assert unfloored > 0.30, "the artifact should be present without the floor"
    assert abs(floored) < 0.15, "the floor should remove it"
    assert cs.n_thin == 4


# ----------------------------------------------------------------- the fence


def test_fence_scores_a_real_call_as_floored() -> None:
    fence = _load_fence()
    src = (
        "import numpy as np\n"
        "from libs.research.cross_section_floor import measure_cross_section\n"
        "def f(panel):\n"
        "    cs = measure_cross_section(panel, min_symbols=8)\n"
        "    panel = panel[cs.mask]\n"
        "    return panel.mean(axis=1)\n"
    )
    rows = fence.analyse(Path(fence.ROOT / "scripts/x.py"), src)
    assert [r["classification"] for r in rows] == ["FLOORED"]


def test_fence_is_not_satisfied_by_a_comment_describing_the_fix() -> None:
    """The false positive this fence shipped with, pinned so it cannot come back.

    Prose about a guard is not a guard. A fence satisfiable by DESCRIBING the fix certifies
    exactly the files whose authors thought about the problem and then did nothing.
    """
    fence = _load_fence()
    src = (
        "def f(panel):\n"
        "    # we should floor this with notna().sum(axis=1) >= 8 and isfinite one day\n"
        '    """Docstring mentioning measure_cross_section and apply_floor."""\n'
        "    return panel.mean(axis=1)\n"
    )
    rows = fence.analyse(Path(fence.ROOT / "scripts/x.py"), src)
    assert [r["classification"] for r in rows] == ["UNFLOORED"]


def test_fence_flags_the_width_guard_as_a_near_miss() -> None:
    fence = _load_fence()
    src = (
        "def f(panel):\n"
        "    if panel.shape[1] < 8:\n"
        "        return None\n"
        "    return panel.mean(axis=1)\n"
    )
    rows = fence.analyse(Path(fence.ROOT / "scripts/x.py"), src)
    assert [r["classification"] for r in rows] == ["NEAR-MISS"]


def test_fence_ignores_axis0_and_out_of_scope_ops() -> None:
    fence = _load_fence()
    src = (
        "def f(panel, w):\n"
        "    a = panel.mean(axis=0)\n"          # time axis, not the cross-section
        "    b = w.abs().sum(axis=1)\n"         # weight normalisation: declared out of scope
        "    return a, b\n"
    )
    assert fence.analyse(Path(fence.ROOT / "scripts/x.py"), src) == []


def test_fence_reports_unmeasured_rather_than_ok_on_an_empty_scan(monkeypatch) -> None:
    """WS-005: absence must never resolve to a clean verdict (L1.28a)."""
    fence = _load_fence()
    monkeypatch.setattr(fence, "_SCOPE", ())
    rep = fence.build()
    assert rep["status"] == "UNMEASURED"
    assert rep["n_sites"] == 0
    assert fence.fence_exit(rep["status"], fence._PASSING, scanned=0, of="t", fence="t") != 0


def test_fence_fails_on_a_regression_below_the_recorded_floor(monkeypatch, tmp_path) -> None:
    """Coverage floors ratchet UP only (L1.0/L1.50)."""
    fence = _load_fence()
    high = tmp_path / "floor.json"
    high.write_text('{"n_floored": 999999}', "utf-8")
    monkeypatch.setattr(fence, "_FLOOR", high)
    rep = fence.build()
    assert rep["status"] == "REGRESSED"
    assert fence.fence_exit(rep["status"], fence._PASSING,
                            scanned=rep["n_files_examined"], of="t", fence="t") != 0


def test_fence_counts_unreadable_files_in_its_denominator(monkeypatch, tmp_path) -> None:
    """L1.60: a fence going blind must not read as a fence finding nothing wrong."""
    fence = _load_fence()
    bad = tmp_path / "libs"
    bad.mkdir()
    (bad / "broken.py").write_text("def f(:\n", "utf-8")
    (bad / "ok.py").write_text("def g(p):\n    return p.mean(axis=1)\n", "utf-8")
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    monkeypatch.setattr(fence, "_SCOPE", ("libs",))
    rep = fence.build()
    assert rep["n_unreadable"] == 1
    assert rep["n_files_examined"] == 2          # the unreadable file stays in the denominator
    assert any("broken.py" in u for u in rep["unreadable"])


# ------------------------------------------------- the locked-mirror invariant (the live repair)


# ---------------------------------------------------------------------------------------------
# RETIRED 2026-09-05. The tests removed here drove `scripts/run_derivative_shadow.py` and
# `scripts/backfill_oi_ls_oos.py`, deleted in 1657d5f7 with the
# retired crypto desk (MT5 universe mandate, 2026-08-18). They had been failing on
# ModuleNotFoundError ever since, which is not a verdict on anything -- it is a test for code the
# desk decided on purpose not to have, and a permanently red test is a disabled gate that also
# trains its reader to skip the file.
#
# Everything in this file that tests code which still EXISTS is untouched: the properties worth
# keeping are asserted above against modules that are here.
# ---------------------------------------------------------------------------------------------
