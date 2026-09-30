"""C9: the residual statistic measures incremental alpha and never becomes a veto."""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation import residual_gate as rg


def _book(rng: np.random.Generator, n: int = 400) -> dict[str, np.ndarray]:
    a = rng.normal(0.0, 1.0, n)
    b = rng.normal(0.0, 1.0, n)
    return {"sleeve_a": a, "sleeve_b": b}


def test_a_re_spelling_of_the_book_keeps_almost_no_alpha() -> None:
    rng = np.random.default_rng(7)
    book = _book(rng)
    clone = 0.9 * book["sleeve_a"] + 0.1 * book["sleeve_b"] + rng.normal(0.0, 0.05, 400)
    v = rg.residual_alpha(clone, book, name="clone")
    assert v.status == rg.MEASURED
    assert v.explained_share is not None and v.explained_share > 0.9
    assert abs(v.residual_t or 0.0) < 1.0


def test_an_orthogonal_edge_keeps_its_t() -> None:
    rng = np.random.default_rng(11)
    book = _book(rng)
    fresh = rng.normal(0.25, 1.0, 400)
    v = rg.residual_alpha(fresh, book, name="fresh")
    assert v.status == rg.MEASURED
    assert (v.residual_t or 0.0) > 3.0
    assert v.explained_share is not None and v.explained_share < 0.2


def test_collinear_controls_are_dropped_rather_than_inverted() -> None:
    """The defect the first pass measured: an exactly singular design read every candidate as
    explained, because a ridge inverse turned a 1e-8 eigenvalue into 1e8."""
    rng = np.random.default_rng(3)
    x = rng.normal(0.0, 1.0, (300, 2))
    doubled = np.column_stack([x, x])        # each column repeated exactly
    keep = rg.independent_columns(doubled)
    assert keep == [0, 1]


def test_short_overlap_is_unmeasured_not_zero() -> None:
    rng = np.random.default_rng(5)
    book = {"sleeve_a": rng.normal(0, 1, 10), "sleeve_b": rng.normal(0, 1, 10)}
    v = rg.residual_alpha(rng.normal(0, 1, 10), book, name="short")
    assert v.status == rg.UNMEASURED
    assert v.residual_t is None
    assert str(rg.MIN_OBS) in v.why


def test_run_all_never_blocks() -> None:
    rng = np.random.default_rng(13)
    book = _book(rng)
    cells = {"one": rng.normal(0.2, 1, 400), "two": rng.normal(0.0, 1, 400)}
    out = rg.run_all(cells, book)
    assert out["blocking"] is False
    assert all(r["blocking"] is False for r in out["rows"])
    assert out["n_cells"] == 2
    assert next(r["name"] for r in out["ranked"]) == "one"


@pytest.mark.parametrize("name,expect", [
    ("CADJPY_asia_FAILED_BREAK", "failed_breakout"),
    ("EURZAR_overnight_drift_asia", "overnight_drift"),
    ("gold_asia", ""),
])
def test_mount_maps_sleeve_names_to_registered_families(name: str, expect: str) -> None:
    from desks.mt5.research import residual_gate_mount as mount
    fams = mount._registered_families()
    if not fams:                                            # pragma: no cover - import env
        pytest.skip("mt5desk.families is not importable on this host")
    assert mount._family_of(name, fams) == expect
