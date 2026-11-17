"""The 101 formulaic alphas as a causal cross-sectional panel (libs/research/formulaic_alphas.py)
and the adapter that charges and donates them (libs/research/adapters/alpha101.py).

What is pinned: every operator is strictly causal (a future bar never changes a past value), on a
panel whose symbols print on different bars; decay_linear never back-fills; all 101 alphas exist,
are causal, and carry a MEASURED status (cap -> UNMEASURED by name, every proxy named); the
two-lane order sets share CFDs aside; and every donation names a registered family with keyword
parameters that family actually takes.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from libs.research import adapters as A
from libs.research import formulaic_alphas as F
from libs.research.adapters import alpha101

ROOT = Path(__file__).resolve().parents[2]
N, K, CUT = 260, 6, 180


def _panel(seed: int = 4, gaps: bool = True) -> F.Panel:
    p = F.planted_panel(n=N, n_sym=K, seed=seed)
    pres = p.present.copy()
    if gaps:
        rng = np.random.default_rng(seed + 100)
        pres[rng.random(pres.shape) < 0.1] = False
    return F.Panel(p.symbols, p.times, p.o.copy(), p.h.copy(), p.lo.copy(), p.c.copy(),
                   p.v.copy(), pres, p.groups)


def _perturbed(p: F.Panel, cut: int = CUT, seed: int = 9) -> F.Panel:
    rng = np.random.default_rng(seed)
    q = F.Panel(p.symbols, p.times, p.o.copy(), p.h.copy(), p.lo.copy(), p.c.copy(),
                p.v.copy(), p.present, p.groups)
    for arr in (q.o, q.h, q.lo, q.c, q.v):
        arr[cut:] *= np.exp(rng.normal(0, 0.2, arr[cut:].shape))
    return q


def _same_past(a: np.ndarray, b: np.ndarray, cut: int = CUT) -> bool:
    return bool(np.array_equal(a[:cut], b[:cut], equal_nan=True))


OPERATORS: dict[str, Callable[[F.Panel], np.ndarray]] = {
    "delay": lambda p: p.delay(p.close, 3),
    "delta": lambda p: p.delta(p.close, 2.7),
    "sum": lambda p: p.sum(p.close, 5),
    "product": lambda p: p.product(p.close / 100.0, 4),
    "stddev": lambda p: p.stddev(p.close, 6),
    "ts_min": lambda p: p.ts_min(p.low, 7),
    "ts_max": lambda p: p.ts_max(p.high, 7),
    "ts_argmin": lambda p: p.ts_argmin(p.close, 9),
    "ts_argmax": lambda p: p.ts_argmax(p.close, 9),
    "ts_rank": lambda p: p.ts_rank(p.close, 8),
    "decay_linear": lambda p: p.decay_linear(p.close, 10),
    "correlation": lambda p: p.correlation(p.close, p.volume, 10),
    "covariance": lambda p: p.covariance(p.close, p.volume, 10),
    "rank": lambda p: p.rank(p.close),
    "scale": lambda p: p.scale(p.close - p.open),
    "indneutralize": lambda p: p.indneutralize(p.close),
    "signedpower": lambda p: F.signedpower(p.close - p.open, 2.0),
    "adv": lambda p: p.adv(20),
    "returns": lambda p: p.returns,
    "vwap_proxy": lambda p: p.vwap,
}


@pytest.mark.parametrize("name", sorted(OPERATORS))
def test_every_operator_is_strictly_causal(name: str) -> None:
    p = _panel()
    with np.errstate(all="ignore"):
        a = OPERATORS[name](p)
        b = OPERATORS[name](_perturbed(p))
    assert np.isfinite(a[:CUT]).any(), f"{name} produced nothing to compare"
    assert _same_past(a, b), f"{name}: a future bar changed a past value"
    assert not _same_past(a, b, cut=N), f"{name}: the perturbation never reached it"


def test_time_series_operators_run_over_each_symbols_own_bars() -> None:
    """A window of d is the last d bars the SYMBOL printed, not d rows of the union grid."""
    p = _panel()
    j = 0
    idx = np.flatnonzero(p.present[:, j])
    got = p.delay(p.close, 1)[idx, j]
    own = p.close[idx, j]
    assert np.allclose(got[1:], own[:-1])
    assert np.isnan(p.delay(p.close, 1)[~p.present[:, j], j]).all()


def test_decay_linear_weights_this_bar_most_and_never_back_fills() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0])
    assert F.k_decay_linear(x, 3)[-1] == pytest.approx((2 * 1 + 3 * 2 + 4 * 3) / 6.0)
    y = np.array([np.nan, 2.0, 3.0, 4.0, 5.0])
    out = F.k_decay_linear(y, 3)
    assert np.isnan(out[:3]).all() and np.isfinite(out[3:]).all()


def test_ts_argmax_and_ts_rank_follow_the_papers_definitions() -> None:
    x = np.array([1.0, 5.0, 2.0, 3.0])
    assert F.k_argmax(x, 3)[-1] == 0.0          # the window [5, 2, 3]: max at its oldest bar
    assert F.k_tsrank(x, 4)[-1] == pytest.approx(2.0 / 3.0)
    assert np.isnan(F.k_correlation(np.ones(10), np.arange(10.0), 5)[-1])   # flat: no corr


def test_rank_and_indneutralize_are_cross_sectional_within_the_registry_class() -> None:
    p = _panel(gaps=False)
    r = p.rank(p.close)
    assert np.nanmin(r) == 0.0 and np.nanmax(r) == 1.0
    z = p.indneutralize(p.close)
    for g in set(p.groups):
        cols = [j for j, gg in enumerate(p.groups) if gg == g]
        assert np.allclose(z[:, cols].sum(axis=1), 0.0)


def test_all_101_alphas_exist_and_are_causal() -> None:
    assert sorted(F.ALPHAS) == [f"alpha{i:03d}" for i in range(1, 102)]
    p = _panel()
    q = _perturbed(p)
    for aid in F.ALPHAS:
        a, why = F.evaluate(aid, p)
        b, _ = F.evaluate(aid, q)
        if a is None:
            assert b is None and why
            continue
        assert b is not None and _same_past(a, b), f"{aid} reads the future"


def test_status_is_measured_and_every_proxy_is_named() -> None:
    rows = F.census()
    counts = F.census_counts(rows)
    assert sum(counts.values()) == 101
    assert rows["alpha056"]["status"] == "UNMEASURED" and "cap" in rows["alpha056"]["why"]
    assert rows["alpha101"]["status"] == "EXACT" and rows["alpha101"]["proxies"] == []
    assert rows["alpha041"]["status"] == "PROXIED" and rows["alpha041"]["proxies"] == ["vwap"]
    assert "indclass" in rows["alpha048"]["proxies"]
    assert "adv" in rows["alpha007"]["proxies"]
    for r in rows.values():
        assert set(r["proxies"]) <= set(F.PROXIES)
        assert r["horizon_bars"] >= 1


def test_no_third_party_alpha_lineage_is_imported() -> None:
    src = (ROOT / "libs/research/formulaic_alphas.py").read_text(encoding="utf-8")
    imports = {ln.split()[1].split(".")[0] for ln in src.splitlines()
               if ln.startswith(("import ", "from "))}
    assert imports <= {"__future__", "math", "collections", "dataclasses", "typing", "numpy"}
    assert "yli188" not in src and "bfill" not in src


def test_registry_classes_enforce_the_two_lane_order() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import universe_policy as up
    equity = up.class_members("equity")[0]
    cls = F.registry_classes(["EURUSD", "USDJPY", equity, "NOTREAL"])
    assert cls["EURUSD"]["hypothesis"] and cls["EURUSD"]["group"] == "fx_usd"
    assert cls["USDJPY"]["orientation"] == -1
    assert not cls[equity]["hypothesis"] and cls[equity]["class_book"]
    assert not cls["NOTREAL"]["hypothesis"] and not cls["NOTREAL"]["class_book"]


def _family_kwargs(family: str) -> set[str]:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    fams = importlib.import_module("mt5desk.families")
    return set(inspect.signature(getattr(fams, f"family_{family}")).parameters)


def test_the_adapter_charges_every_alpha_and_donates_registered_families() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import universe_policy as up
    equity = up.class_members("equity")[0]
    bundle = A.synthetic_bundle(seed=2, n=700, budget_s=120,
                                symbols=("EURUSD", "USDJPY", "GBPUSD", "XAUUSD", equity))
    pkt = alpha101.run(bundle)
    census = pkt.representations[0]
    assert census["kind"] == "formulaic_alpha_census" and census["n_alphas"] == 101
    assert census["UNMEASURED"] == 1 and not census["not_reached_this_pass"]
    assert [r["symbol"] for r in census["set_aside_by_lane"]] == [equity]
    alphas = [r for r in pkt.representations[1:] if r["kind"] == "formulaic_alpha"]
    assert len(alphas) == 101
    measured = [r for r in alphas if r["status"] != "UNMEASURED"]
    assert pkt.trials_charged == len(measured) * (1 + len(census["panel_symbols"]))
    assert pkt.candidates
    for c in pkt.candidates:
        assert c["family"] in A.FAMILIES and c["symbols"] != [equity]
        assert set(c["evidence"]["parameters"]) <= _family_kwargs(c["family"])
