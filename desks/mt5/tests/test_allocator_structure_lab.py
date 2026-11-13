"""The allocator structure lab: RMT cleaning, factor risk, neutralisation, diversification
multiplier, crowding and the walk-forward log-growth proof, on a synthetic box with known truth."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import rmt  # noqa: E402
from libs.portfolio import structure as st  # noqa: E402


def _factor_world(seed: int = 3, n: int = 60, t: int = 700):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=t, freq="B", tz="UTC")
    f = pd.DataFrame({"usd": rng.normal(0, 0.004, t), "trend": rng.normal(0, 0.006, t),
                      "gold": rng.normal(0, 0.009, t)}, index=idx)
    beta = np.zeros((n, 3))
    beta[: n // 3, 1] = 1.5            # a third of the sleeves are trend followers
    beta[n // 3: 2 * n // 3, 0] = -1.0  # a third are short USD
    alpha = rng.normal(0.0004, 0.0002, n)
    eps = rng.normal(0, 0.008, (t, n))
    x = alpha + f.to_numpy() @ beta.T + eps
    names = ([f"EURUSD_trendfam_s{i}" for i in range(n // 3)]
             + [f"AUDUSD_carryfam_s{i}" for i in range(n // 3)]
             + [f"XAUUSD_idio_s{i}" for i in range(n - 2 * (n // 3))])
    panel = pd.DataFrame(x, index=idx, columns=names)
    panel.iloc[:100, :5] = np.nan       # unequal histories
    return panel, f, beta


def test_rmt_beats_sample_on_out_of_sample_min_variance() -> None:
    rng = np.random.default_rng(1)
    n, t = 120, 300
    b = np.zeros((n, 5))
    b[:, 0] = 0.3
    for k in range(4):
        b[k * 30:(k + 1) * 30, k + 1] = 0.5
    c = b @ b.T
    np.fill_diagonal(c, 1.0)
    x = (np.linalg.cholesky(c) @ rng.standard_normal((n, t))).T
    cl = rmt.clean(x, [str(i) for i in range(n)])

    def gmv_var(m: np.ndarray) -> float:
        w = np.linalg.solve(m, np.ones(n))
        w /= w.sum()
        return float(w @ c @ w)

    assert gmv_var(cl.rie) < gmv_var(cl.sample)
    assert gmv_var(cl.clipped) < gmv_var(cl.sample)
    assert 3 <= cl.n_signal <= 6
    s = cl.summary()
    assert s["effective_bets"]["rie"] > s["effective_bets"]["sample"] * 0.9
    for k in ("sample", "clipped", "rie", "lw"):
        m = cl.matrix(k)
        assert np.allclose(np.diag(m), 1.0)
        assert np.linalg.eigvalsh(m).min() > -1e-8


def test_pairwise_corr_reads_short_overlap_as_zero() -> None:
    x = np.random.default_rng(0).normal(size=(200, 3))
    x[:180, 2] = np.nan
    corr, ov = rmt.pairwise_corr(x, min_overlap=60)
    assert corr[0, 2] == 0.0 and ov[0, 2] == 20


def test_exposures_recover_betas_with_newey_west_t() -> None:
    panel, f, _beta = _factor_world()
    exp = st.exposures(panel, f)
    trend = [e.beta["trend"] for n, e in exp.items() if "trendfam" in n]
    assert np.mean(trend) == pytest.approx(1.5, abs=0.15)
    assert all(abs(e.t["trend"]) > 5 for n, e in exp.items() if "trendfam" in n)
    idio = [abs(e.t["trend"]) for n, e in exp.items() if "idio" in n]
    assert np.median(idio) < 2.5


def test_neutralise_zeroes_exposure_keeps_heat_and_long_only() -> None:
    rng = np.random.default_rng(5)
    w = rng.uniform(0.001, 0.01, 30)
    a = np.column_stack([rng.normal(0.5, 1.0, 30)])
    wn = st.neutralise(w, a)
    assert wn.sum() == pytest.approx(w.sum())
    assert (wn >= 0).all()
    assert abs(float(a[:, 0] @ wn)) < 1e-6


def test_neutralise_infeasible_returns_book_unchanged() -> None:
    w = np.array([0.1, 0.1])
    a = np.array([[1.0], [1.0]])     # all-positive exposure: no long-only neutral book
    assert np.allclose(st.neutralise(w, a), w)


def test_diversification_multiplier_and_heat_are_two_sided_and_capped() -> None:
    eye = np.eye(10)
    dm, heat = st.idm_heat(eye, np.ones(10))
    assert dm == pytest.approx(min(st.DM_CAP, np.sqrt(10)))
    assert heat == pytest.approx(st.HEAT_CEILING)
    ones = np.ones((10, 10))
    dm1, heat1 = st.idm_heat(ones, np.ones(10))
    assert dm1 == pytest.approx(1.0) and heat1 == pytest.approx(st.HEAT_FLOOR)


def test_crowd_tilt_is_two_sided_and_heat_preserving() -> None:
    w = np.array([0.05, 0.05, 0.05])
    t = st.crowd_tilt(w, np.array([2.0, 0.0, -2.0]))
    assert t.sum() == pytest.approx(w.sum())
    assert t[0] < w[0] and t[2] > w[2]


def test_comomentum_flags_a_family_whose_residuals_fuse() -> None:
    rng = np.random.default_rng(9)
    t = 400
    idx = pd.date_range("2024-01-01", periods=t, freq="B", tz="UTC")
    common = np.concatenate([np.zeros(t - 63), rng.normal(0, 1, 63)])
    fam_a = {f"X_crowd_{i}": rng.normal(0, 1, t) + 2.0 * common for i in range(5)}
    fam_b = {f"Y_calm_{i}": rng.normal(0, 1, t) for i in range(5)}
    resid = pd.DataFrame({**fam_a, **fam_b}, index=idx)
    out = st.comomentum(resid, {n: st.family_of(n) for n in resid.columns})
    assert out["crowd"]["z"] > 3.0
    assert abs(out["calm"]["z"] or 0.0) < 3.0


def test_cot_pressure_signs_by_crowd_alignment() -> None:
    idx = pd.date_range("2020-01-07", periods=200, freq="W-TUE", tz="UTC")
    net = pd.Series(np.linspace(-0.1, 0.4, 200), index=idx)
    net.iloc[-1] = 0.8
    rng = np.random.default_rng(2)
    days = pd.date_range(idx[0], idx[-1], freq="B", tz="UTC")
    dnet = net.diff().reindex(days, method="ffill").fillna(0.0)
    with_crowd = pd.Series(dnet.to_numpy() * 5 + rng.normal(0, 1e-4, len(days)), index=days)
    p = st.cot_pressure(with_crowd, net, sign=1)
    assert p["z"] > 1.5 and p["align"] > 0 and p["pressure"] > 0
    # the quote side only orients the reported crowd side; pressure lives in futures space
    q = st.cot_pressure(with_crowd, net, sign=-1)
    assert q["pressure"] == p["pressure"]
    assert p["crowd_side_on_symbol"] == "long" and q["crowd_side_on_symbol"] == "short"
    against = st.cot_pressure(-with_crowd, net, sign=1)
    assert against["pressure"] < 0


def test_paired_verdict_bands() -> None:
    rng = np.random.default_rng(4)
    assert st.paired_verdict(rng.normal(0.001, 0.001, 500))["verdict"] == "ADOPT"
    assert st.paired_verdict(rng.normal(-0.001, 0.001, 500))["verdict"] == "REJECT"
    assert st.paired_verdict(rng.normal(0.0, 0.01, 500))["verdict"] == "INCONCLUSIVE"
    assert st.paired_verdict(np.zeros(10))["verdict"] == "UNMEASURED"


def test_lab_end_to_end_writes_every_block(tmp_path: Path, monkeypatch) -> None:
    import allocator_structure_lab as lab

    panel, f, _ = _factor_world(n=36, t=650)
    cache = tmp_path / "data" / "pf_allocator_cache"
    cache.mkdir(parents=True)
    panel.index = [str(i.date()) for i in panel.index]
    panel.to_parquet(cache / "daily_r.parquet")
    book = dict.fromkeys(list(panel.columns)[::3], 0.2 / 12)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps({"book": book}))
    for k, v in {"OUT": tmp_path / "reports" / "ALLOCATOR_STRUCTURE.json",
                 "HISTORY": tmp_path / "data" / "allocator_structure_history.jsonl",
                 "PANEL": cache / "daily_r.parquet", "CORR_OUT": cache / "structure_corr.npz",
                 "ALLOCATION": tmp_path / "reports" / "pf_allocation.json"}.items():
        monkeypatch.setattr(lab, k, v)
    p, why = lab.load_panel(cache / "daily_r.parquet")
    b, total = lab.load_book(tmp_path / "reports" / "pf_allocation.json")
    # style factors would come from bars; hand the lab closes whose log-returns are the factors
    closes = np.exp(f.cumsum()) * 100
    closes.columns = ["USDJPY", "XAUUSD", "EURUSD"]
    doc = lab.measure(p, why, b, total, closes, {"EURUSD": 1, "USDJPY": -1}, {},
                      budget_s=120.0)
    assert doc["status"] in ("MEASURED", "PARTIAL")
    for block in ("rmt", "factor_model", "diversification", "crowding", "proof", "adoption"):
        assert block in doc, block
    assert doc["proof"]["rebalances"] > 5
    assert set(doc["adoption"]) == set(lab.ADOPTION_MAP)
    assert all(v in ("ADOPT", "REJECT", "INCONCLUSIVE", "UNMEASURED")
               for v in doc["adoption"].values())
    assert set(doc["proof"]["gmv_oos_var"]) == {"sample", "lw", "clipped", "rie"}
    json.dumps(doc, allow_nan=False)     # strict JSON
    assert (cache / "structure_corr.npz").exists()


def test_lab_without_panel_is_unmeasured_and_named() -> None:
    import allocator_structure_lab as lab
    doc = lab.measure(None, "daily_r.parquet absent", {}, None, pd.DataFrame(), {}, {})
    assert doc["status"] == "UNMEASURED" and "absent" in doc["why"]
    assert set(doc["adoption"].values()) == {"UNMEASURED"}


def test_cot_is_cut_to_what_was_published(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    import allocator_structure_lab as lab

    dates = pd.date_range("2026-01-06", periods=60, freq="W-TUE", tz="UTC")
    df = pd.DataFrame({"report_date": dates, "open_interest_all": 1000.0,
                       "noncomm_positions_long_all": 600.0,
                       "noncomm_positions_short_all": 400.0})
    (tmp_path / "cot").mkdir()
    df.to_parquet(tmp_path / "cot" / "jpy.parquet")
    as_of = (dates[-1] + pd.Timedelta(days=1)).to_pydatetime().astimezone(UTC)
    got = lab.load_cot(tmp_path / "cot", as_of=as_of)["jpy"]
    assert got.index.max() < dates[-1]          # Tuesday's print is not out until Friday
    later = lab.load_cot(tmp_path / "cot", as_of=datetime(2028, 1, 1, tzinfo=UTC))["jpy"]
    assert later.index.max() == dates[-1]


def test_rmt_uses_the_true_aspect_ratio_above_one() -> None:
    rng = np.random.default_rng(1)
    n, t = 300, 100
    b = np.zeros((n, 5))
    b[:, 0] = 0.3
    for k in range(4):
        b[k * 75:(k + 1) * 75, k + 1] = 0.5
    c = b @ b.T
    np.fill_diagonal(c, 1.0)
    x = (np.linalg.cholesky(c) @ rng.standard_normal((n, t))).T
    cl = rmt.clean(x, [str(i) for i in range(n)])
    assert cl.q == pytest.approx(3.0)
    assert cl.n_signal <= 8                      # the bulk is the real MP bulk at q = 3

    def gmv_var(m: np.ndarray) -> float:
        w = np.linalg.solve(m + 1e-9 * np.eye(n), np.ones(n))
        w /= w.sum()
        return float(w @ c @ w)

    assert gmv_var(cl.rie) < gmv_var(cl.lw) < gmv_var(cl.sample)


def test_ledoit_wolf_closed_form_matches_the_tensor() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=(80, 12))
    corr = np.corrcoef(x, rowvar=False)
    _out, delta = rmt.ledoit_wolf_identity(x, corr)
    z = (x - x.mean(0)) / x.std(0)
    pi = float(((np.einsum("ti,tj->tij", z, z) - corr) ** 2).mean(axis=0).sum())
    gamma = float(((corr - np.eye(12)) ** 2).sum())
    assert delta == pytest.approx(max(0.0, min(1.0, pi / gamma / 80)))


def test_inlife_zero_fills_inside_life_only() -> None:
    x = np.array([[np.nan, 1.0], [2.0, np.nan], [np.nan, 3.0], [4.0, np.nan]])
    y = st.inlife_zero(x)
    assert np.isnan(y[0, 0]) and y[2, 0] == 0.0 and np.isnan(y[3, 1]) and y[1, 1] == 0.0


def test_carry_is_point_in_time() -> None:
    idx = pd.date_range("2025-01-01", periods=300, freq="B", tz="UTC")
    rng = np.random.default_rng(0)
    closes = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.005, (300, 3)), axis=0)),
                          index=idx, columns=["EURUSD", "USDJPY", "AUDUSD"])
    since = idx[200]
    f = st.style_factors(closes, {"AUDUSD": 1}, {"AUDUSD": since})
    assert f["carry"].loc[: idx[199]].isna().all()
    assert f["carry"].loc[since:].notna().any()
    g = st.style_factors(closes, {"AUDUSD": 1}, {})       # no observation date: no carry
    assert "carry" not in g.columns


def test_crowding_unmeasured_is_null_and_not_tilted() -> None:
    cz = st.crowding_z({"a": {"style_r2": 0.9}, "b": {"style_r2": 0.1},
                        "c": {"style_r2": 0.5}, "d": {}})
    assert cz["d"] is None and cz["a"] > 0
    w = np.array([0.05, 0.05, 0.05, 0.05])
    t = st.crowd_tilt(w, np.array([cz[k] if cz[k] is not None else np.nan for k in "abcd"]))
    assert t.sum() == pytest.approx(w.sum()) and t[0] < t[3]


def test_walk_forward_reports_clips_and_family_size() -> None:
    rng = np.random.default_rng(2)
    idx = pd.date_range("2022-01-03", periods=600, freq="B", tz="UTC")
    panel = pd.DataFrame(rng.normal(0.001, 0.01, (600, 8)), index=idx)

    def flat(tr: np.ndarray, ctx: dict) -> np.ndarray:
        return np.full(tr.shape[1], 0.2 / tr.shape[1])

    def lever(tr: np.ndarray, ctx: dict) -> np.ndarray:
        return np.full(tr.shape[1], 200.0 / tr.shape[1])

    vs = [st.Variant("base", "flat", flat), st.Variant("a", "flat", flat),
          st.Variant("huge", "200x", lever)]
    res = st.walk_forward(panel, vs, "base")
    assert res.by_variant["huge"]["loss_clip_days"] > 0
    assert res.by_variant["a"]["family_size"] == 2
    assert res.by_variant["a"]["verdict_familywise"] in ("INCONCLUSIVE", "UNMEASURED")
