"""Control variates for tail simulations and portfolio stress (ROMAN-0970/0971)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from libs.portfolio import control_variates as cv


def test_the_indices_are_marginally_uniform_so_the_control_mean_is_exact() -> None:
    idx = cv.stationary_indices(50, 40, 20000, 5.0, np.random.default_rng(0))
    assert idx.min() == 0 and idx.max() == 49
    counts = np.bincount(idx.ravel(), minlength=50) / idx.size
    assert np.allclose(counts, 1 / 50, atol=0.002)
    # Within a block the next row follows the last, wrapping at n.
    steps = (idx[:, 1:] - idx[:, :-1]) % 50
    assert np.mean(steps == 1) > 0.75


def test_cv_mean_is_unbiased_and_tighter_on_a_correlated_target() -> None:
    rng = np.random.default_rng(1)
    plain, adj = [], []
    for _ in range(300):
        x = rng.normal(0.0, 1.0, 400)
        y = 2.0 + 3.0 * x + rng.normal(0, 0.5, 400)
        m = cv.cv_mean(y, x, 0.0)
        plain.append(m["plain"])
        adj.append(m["cv"])
    assert np.mean(adj) == pytest.approx(2.0, abs=0.01)
    assert np.std(adj) < 0.25 * np.std(plain)
    m = cv.cv_mean(rng.normal(0, 1, 400), rng.normal(0, 1, 400), 0.0)
    assert m["variance_reduction"] < 0.05


def test_cv_cvar_matches_the_plain_definition_and_reports_its_reduction() -> None:
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 5000)
    loss = -x + rng.normal(0, 0.3, 5000)
    d = cv.cv_cvar(loss, x, 0.0, alpha=0.05)
    var = np.quantile(loss, 0.95)
    assert d["plain"] == pytest.approx(var + np.maximum(loss - var, 0).mean() / 0.05)
    assert d["variance_reduction"] > 0 and d["cv_se"] <= d["plain_se"]
    assert cv.cv_cvar(loss[:10], x[:10], 0.0)["status"] == "UNMEASURED"


def test_stress_runs_side_by_side_and_shrinks_the_terminal_error() -> None:
    rng = np.random.default_rng(3)
    r = rng.normal(0.002, 0.02, (600, 6))
    d = cv.stress(r, np.full(6, 0.3), horizon=250, draws=1500)
    assert d["status"] == "MEASURED" and d["horizon"] == 250
    tg = d["terminal_log_growth"]
    assert tg["cv_se"] < 0.2 * tg["plain_se"]
    assert d["control_mean"] == pytest.approx(float((r @ np.full(6, 0.3)).mean()))
    for v in d["p_drawdown"].values():
        assert 0.0 <= v["cv"] <= 1.0
    assert "control variates" in cv.headline(d)


def test_stress_says_unmeasured_instead_of_guessing() -> None:
    r = np.zeros((10, 2))
    assert cv.stress(r, [0.1, 0.1])["status"] == "UNMEASURED"
    r = np.zeros((100, 2))
    assert cv.stress(r, {"a": 0.1})["status"] == "UNMEASURED"           # mapping, no names
    assert cv.stress(r, [0.1])["status"] == "UNMEASURED"                 # shape mismatch
    r[5, 0] = -20.0
    assert cv.stress(r, [0.1, 0.0])["status"] == "UNMEASURED"           # ruin day


def test_the_allocator_publishes_the_stress_report() -> None:
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    pa = pytest.importorskip("research.pf_allocator")
    rng = np.random.default_rng(4)
    daily = pd.DataFrame(rng.normal(0.01, 0.5, (300, 3)), columns=["a", "b", "c"])
    doc = pa.stress_control_variates(daily, {"a": 0.1, "b": 0.1})
    assert doc["status"] == "MEASURED" and doc["horizon"] == pa.STRESS_HORIZON_DAYS
    assert isinstance(doc["elapsed_s"], float) and doc["elapsed_s"] >= 0
    assert pa.stress_control_variates(daily, {"zz": 0.2})["status"] == "UNMEASURED"
    src = (desk / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert '"stress_control_variates": stress_control_variates(daily, funded)' in src
