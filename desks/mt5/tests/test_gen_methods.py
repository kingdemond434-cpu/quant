"""gbm_classifier and coint_pairs: the two generator methods the coverage map lacked (2026-11-25).

Pinned here: both are causal under a PERTURBATION of future bars (not only a truncation), the
boosted trees learn a learnable label, the Engle-Granger pieces measure what they name, both are
registered where their siblings are, and both reach a producer that mints cells.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mt5desk.families_orthogonal as fo  # noqa: E402
from mt5desk import family_coint_pairs as cp  # noqa: E402
from mt5desk import family_hypgen_models as fm  # noqa: E402
from mt5desk.families import FAMILY_REGISTRY, get_family_func  # noqa: E402


def _frame(c: np.ndarray, seed: int, start: str = "2019-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(c)
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    o = np.concatenate([[c[0]], c[:-1]])
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 3e-4, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 3e-4, n)))
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c,
                         "tick_volume": rng.integers(100, 1000, n).astype(float)}, index=idx)


def _bars(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return _frame(1.1 * np.exp(np.cumsum(rng.normal(0, 0.002, n))), seed + 100)


def _perturb_after(d: pd.DataFrame, cut: int, seed: int = 99) -> pd.DataFrame:
    """Every bar from `cut` on replaced by a different path; bars before it untouched."""
    rng = np.random.default_rng(seed)
    out = d.copy()
    k = len(d) - cut
    mult = np.exp(np.cumsum(rng.normal(0.001, 0.01, k)))
    for col in ("open", "high", "low", "close"):
        out.iloc[cut:, out.columns.get_loc(col)] = d[col].to_numpy()[cut:] * mult
    out.iloc[cut:, out.columns.get_loc("tick_volume")] = rng.integers(1, 5000, k).astype(float)
    return out


def _sig_key(sigs, before) -> list[tuple]:
    return [(s.time, s.side, round(s.stop, 12), round(s.target, 12), s.ttl_bars)
            for s in sigs if s.time < before]


# --------------------------------------------------------------------------- gbm
FEATS = ["ret_1", "ret_4", "z_20", "rsi_14"]


def test_gbm_learns_a_learnable_label_and_stumps_work():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(2000, 3))
    y = ((x[:, 0] > 0.2) ^ (x[:, 1] < -0.5)).astype(float)       # an interaction a tree finds
    for depth in (1, 2):
        m = fm.gbm_fit(x[:1500], y[:1500], n_trees=60, depth=depth)
        acc = ((fm.gbm_predict(m, x[1500:]) > 0.5) == y[1500:].astype(bool)).mean()
        assert acc > (0.7 if depth == 1 else 0.9), (depth, acc)


def test_gbm_no_lookahead_under_future_perturbation():
    d = _bars(2600, seed=4)
    cut = 2000
    args = (FEATS, 4, 400, 60, 0.52, 20, 2, 0.1)
    full = fm.gbm_sides(d, *args)
    pert = fm.gbm_sides(_perturb_after(d, cut), *args)
    part = fm.gbm_sides(d.iloc[:cut], *args)
    assert np.abs(full[:cut]).sum() > 0                            # it actually trades
    assert np.array_equal(full[:cut], pert[:cut])
    assert np.array_equal(full[:cut], part)
    assert not np.array_equal(full[cut:], pert[cut:])              # the perturbation is real


def test_gbm_fit_never_reads_the_decision_bar(monkeypatch):
    """The fit for the block starting at t0 sees only rows whose label closed by bar t0 - 1."""
    d = _bars(1200, seed=2)
    seen: list[int] = []
    real = fm.gbm_fit

    def spy(xs, ys, **kw):
        seen.append(len(xs))
        return real(xs, ys, **kw)

    monkeypatch.setattr(fm, "gbm_fit", spy)
    h, window, refit = 4, 300, 100
    fm.gbm_sides(d, FEATS, h, window, refit, 0.55, 5, 1, 0.1)
    assert seen and max(seen) <= window
    y = fm.hf.forward_log_return(d, h)
    t0 = window + h + 2
    hi = t0 - h - 2                     # row hi's label reads opens hi+1 .. hi+h+1 = t0-1
    o = np.log(d["open"].to_numpy())
    assert math.isclose(y[hi], o[t0 - 1] - o[hi + 1])


def test_gbm_family_emits_and_is_registered():
    sigs = get_family_func("gbm_classifier")(_bars(2500), features=FEATS, h=4, window=400,
                                             refit=100, thr=0.52, n_trees=20)
    assert sigs and all(s.side in (-1, 1) and s.wait_bars == 1 for s in sigs)
    assert "gbm_classifier" in FAMILY_REGISTRY and "gbm_classifier" in fo.ORTHOGONAL_FAMILIES
    assert fo.FAMILY_INPUTS["gbm_classifier"][0] == "price and tick volume only"


def test_gbm_seat_is_a_hypgen_space_and_an_hourly_leg():
    import hypgen_engine as he
    sp = he.SPACES["gbm_learner"]
    assert sp.family == "gbm_classifier"
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"hypgen_gbm_learner"' in src and '"gbm_learner")' in src


# --------------------------------------------------------------------------- cointegration
def _pair(n: int = 3000, seed: int = 0, coint: bool = True):
    rng = np.random.default_rng(seed)
    lb = np.cumsum(rng.normal(0, 0.003, n)) + np.log(1.3)
    if coint:
        e = np.zeros(n)
        for t in range(1, n):
            e[t] = 0.9 * e[t - 1] + rng.normal(0, 0.002)
        la = 0.2 + 1.4 * lb + e
    else:
        la = np.cumsum(rng.normal(0, 0.003, n)) + np.log(1.1)
    return _frame(np.exp(la), seed + 1), _frame(np.exp(lb), seed + 2)


def test_adf_and_half_life_measure_what_they_name():
    rng = np.random.default_rng(3)
    ar = np.zeros(800)
    for t in range(1, 800):
        ar[t] = 0.8 * ar[t - 1] + rng.normal()
    rw = np.cumsum(rng.normal(size=800))
    assert cp.adf_tstat(ar) < cp.ADF_CRIT_5PCT_2VAR < cp.adf_tstat(rw)
    assert abs(cp.half_life(ar) - (-math.log(2) / math.log(0.8))) < 1.0
    a, b = rng.normal(size=500), rng.normal(size=500)
    alpha, beta = cp.ols_hedge(0.3 + 2.0 * a + 0.01 * b, a)
    assert abs(beta - 2.0) < 0.01 and abs(alpha - 0.3) < 0.01


def test_coint_trades_a_cointegrated_pair_and_steps_away_from_a_spurious_one():
    a, b = _pair(coint=True)
    st = cp.coint_state(np.log(a["close"].to_numpy()), np.log(b["close"].to_numpy()), 500, 24,
                        1, cp.ADF_CRIT_5PCT_2VAR)
    assert st["coint"][500:].mean() > 0.9
    sigs = cp.family_coint_pairs(a, peer_bars=b)
    assert len(sigs) >= 10 and {s.side for s in sigs} == {-1, 1}
    assert all(2 <= s.ttl_bars <= 480 and s.wait_bars == 1 for s in sigs)
    a2, b2 = _pair(coint=False, seed=7)
    st2 = cp.coint_state(np.log(a2["close"].to_numpy()), np.log(b2["close"].to_numpy()), 500,
                         24, 1, cp.ADF_CRIT_5PCT_2VAR)
    assert st2["coint"][500:].mean() < 0.3
    assert len(cp.family_coint_pairs(a2, peer_bars=b2)) < len(sigs) / 3


def test_coint_no_lookahead_under_future_perturbation():
    a, b = _pair(3000, seed=5)
    cut = 2200
    before = a.index[cut]
    full = cp.family_coint_pairs(a, peer_bars=b)
    pert = cp.family_coint_pairs(_perturb_after(a, cut, 11), peer_bars=_perturb_after(b, cut, 12))
    part = cp.family_coint_pairs(a.iloc[:cut], peer_bars=b.iloc[:cut])
    k = _sig_key(full, before)
    assert len(k) >= 5
    assert k == _sig_key(pert, before)
    assert k == _sig_key(part, before)


def test_coint_reads_the_peer_by_name_and_the_forward_engine_hands_it_over(monkeypatch):
    a, b = _pair(2000, seed=8)
    from mt5desk import family_inputs as fi
    monkeypatch.setattr(fi, "bars_named", lambda sym, like: b if sym == "PEER" else None)
    direct = cp.family_coint_pairs(a, peer_bars=b)
    assert _sig_key(cp.family_coint_pairs(a, peer_symbol="PEER"), a.index[-1]) == \
        _sig_key(direct, a.index[-1])
    assert cp.family_coint_pairs(a) == [] and cp.family_coint_pairs(a, peer_symbol="NONE") == []
    monkeypatch.setattr(fi, "_runtime_bars", lambda inputs, sym, tf, h1: b)
    extra, why = fi.resolve("EURUSD", "coint_pairs", {"peer_symbol": "GBPUSD"}, a)
    assert why == "ok" and extra["peer_bars"] is b
    assert fi.resolve("EURUSD", "coint_pairs", {}, a)[0] is None
    assert "peer_symbol" not in fi.runtime_call_params("coint_pairs", {"peer_symbol": "X"})


def test_coint_is_registered_where_relative_value_is():
    from libs.research.mechanism_genome import FAMILY_GENOME, compatible, from_family
    assert "coint_pairs" in FAMILY_REGISTRY and "coint_pairs" in fo.ORTHOGONAL_FAMILIES
    assert fo.FAMILY_INPUTS["coint_pairs"] == fo.FAMILY_INPUTS["relative_value"]
    assert fo.timeframe_refusal("coint_pairs", "M5") and not fo.timeframe_refusal("coint_pairs",
                                                                                 "H4")
    assert "coint_pairs" in FAMILY_GENOME and compatible(from_family("coint_pairs"))[0]


def test_coint_is_buildable_by_the_sealed_gauntlet_without_a_branch():
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    verdict, why = cell_verdict("coint_pairs", {"peer_symbol": "GBPUSD"})
    assert verdict == BUILDABLE, why


# --------------------------------------------------------------------------- producers
def test_breadth_sweep_mints_coint_pairs_without_exotics_and_gbm_at_defaults():
    import breadth_sweep as bs
    spec = bs.READY["coint_pairs"]
    syms = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "XAUUSD", "XAGUSD", "USDZAR", "EURNOK"]
    tg = bs._targets("coint_pairs", spec, syms)
    assert ("EURUSD", {"peer_symbol": "GBPUSD"}) in tg
    for a, extra in tg:
        assert not bs.is_exotic(a) and not bs.is_exotic(extra["peer_symbol"])
        assert {a, extra["peer_symbol"]}.isdisjoint({"USDZAR", "EURNOK"})
    ok, blocked = bs.default_families()
    assert "gbm_classifier" in ok and "coint_pairs" not in ok and "coint_pairs" not in blocked


def test_generator_coverage_rows_point_at_the_new_code():
    import generator_coverage as gc
    rows = {m[0]: m for m in gc.METHODS}
    co = rows["cointegration / statistical-arbitrage pair search"]
    assert co[2] == ("desks/mt5/mt5desk/family_coint_pairs.py",) and co[3]
    gb = rows["gradient-boosted trees feature-to-label (LightGBM/XGBoost style, numpy)"]
    assert gb[3] == "desks/mt5/reports/HYPGEN_GBM_LEARNER.json"
    assert gc._num({"families": {"coint_pairs": 7}}, "families.coint_pairs") == 7.0
    assert gc._num({"families": {}}, "families.coint_pairs") is None
