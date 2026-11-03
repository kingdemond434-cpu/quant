"""Exact legacy-spectrum comparisons and wide-batch census controls."""
from __future__ import annotations

import numpy as np
import pytest

from mt5desk import canonical as c


def _legacy(cols):
    """Independent reference: the former full correlation eigenspectrum."""
    raw = len(cols)
    matrix = np.column_stack(cols)
    if raw < 2:
        return float(max(raw, 1)), []
    keep = matrix.std(axis=0) > 0
    if len(matrix) < c.MIN_SERIES or keep.sum() < 2:
        return float(raw), []
    corr = np.nan_to_num(np.corrcoef(matrix[:, keep], rowvar=False))
    eigen = np.maximum(np.linalg.eigvalsh(corr), 0.)
    rank = max(2., min(float(eigen.sum() ** 2 / np.sum(eigen ** 2)), float(raw)))
    pairs = [(i, j, float(corr[i, j])) for i in range(len(corr))
             for j in range(i + 1, len(corr)) if abs(corr[i, j]) >= c.CLONE_RHO]
    return rank, pairs


@pytest.mark.parametrize("rows, columns", [(60, 80), (250, 30), (60, 12)])
def test_gram_census_matches_legacy_rank_and_all_clone_identities(rows, columns):
    rng = np.random.default_rng(361)
    cols = [rng.normal(size=rows) for _ in range(columns)]
    cols[1] = cols[0].copy()
    cols[2] = -cols[0]
    cols[3] = np.ones(rows)
    rank, pairs = _legacy(cols)
    actual = c.effective_trials(cols)
    assert actual.n_raw == columns
    assert actual.n_effective == pytest.approx(rank, rel=1e-12, abs=1e-12)
    assert [(i, j) for i, j, _ in actual.clone_pairs] == [(i, j) for i, j, _ in pairs]
    assert [rho for _, _, rho in actual.clone_pairs] == pytest.approx(
        [rho for _, _, rho in pairs], abs=1e-12)


def test_fixed_null_draws_and_report_match_legacy_calibration():
    rng = np.random.default_rng(76)
    base = rng.normal(size=100)
    cols = [base.copy() for _ in range(8)] + [rng.normal(size=100) for _ in range(24)]
    observed, _ = _legacy(cols)
    null_rng = np.random.default_rng(c.NULL_CALIBRATION_SEED)
    null = [_legacy([null_rng.permutation(col) for col in cols])[0]
            for _ in range(c.NULL_CALIBRATION_DRAWS)]
    expected = max(2., min(float(len(cols)), observed / float(np.mean(null)) * len(cols)))
    actual = c.null_calibrated_effective_trials(cols)
    assert actual.n_effective == pytest.approx(expected, rel=1e-12)
    assert c.calibrated_census_report(cols, .2) == c.deflation_pair(actual, .2)
    labelled = c.calibrated_census_report(cols, .2, labels=list(range(len(cols))))
    assert labelled["clone_pairs"]
    assert labelled["n_effective"] == round(expected, 2)


@pytest.mark.parametrize("kind", ["short", "constant", "nan_column"])
def test_unmeasurable_and_nonfinite_inputs_keep_legacy_behavior(kind):
    rng = np.random.default_rng(22)
    cols = [rng.normal(size=100), rng.normal(size=100), np.ones(100)]
    if kind == "short":
        cols = [x[:2] for x in cols]
    elif kind == "constant":
        cols = [np.ones(100) for _ in range(3)]
    else:
        cols[2] = np.full(100, np.nan)
    expected, pairs = _legacy(cols)
    actual = c.effective_trials(cols)
    assert actual.n_effective == pytest.approx(expected, rel=1e-12)
    assert actual.clone_pairs == pairs
    if kind != "nan_column":
        assert actual.method == "unmeasurable"


def test_wide_unlabelled_gate_census_never_builds_strategy_correlation_or_eigensystem(monkeypatch):
    rng = np.random.default_rng(58)
    cols = [rng.normal(size=64) for _ in range(3000)]
    def forbidden(*args, **kwargs):
        raise AssertionError("wide census returned to cubic strategy eigenspectrum")
    monkeypatch.setattr(c, "_corr_matrix", forbidden)
    monkeypatch.setattr(c.np.linalg, "eigvalsh", forbidden)
    report = c.calibrated_census_report(cols, .2)
    assert report["n_raw"] == 3000
    assert 2 <= report["n_effective"] <= 3000
    assert report["method"] == "null_calibrated_participation_ratio"
