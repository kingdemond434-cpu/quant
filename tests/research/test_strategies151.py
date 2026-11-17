"""151 Trading Strategies as the desk's second formulaic source (libs/research/strategies151.py,
libs/research/adapters/kakushadze151.py).

What is pinned: every catalogue row has one disposition and every non-implemented row a reason;
every implemented signal is strictly causal (including the one-sided HP filter and the KNN, the
two places a look-ahead hides most easily); the adapter charges what it measured, donates only
registered families with parameters those families take, keeps share CFDs out of time-series
families while admitting them to the class books, and is on the federation roster so the hourly
sandbox runner schedules it.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

from libs.research import adapters as A
from libs.research import external_federation as fed
from libs.research import formulaic_alphas as F
from libs.research import strategies151 as S
from libs.research.adapters import kakushadze151

ROOT = Path(__file__).resolve().parents[2]
N, K, CUT = 1300, 6, 1000


def test_the_catalogue_disposes_every_row_with_a_reason() -> None:
    c = S.counts()
    assert c["catalogued"] == len(S.CATALOGUE) == S.PAPER_COUNT
    assert c["IMPLEMENTED"] + c["UNMEASURED"] + c["INAPPLICABLE"] == c["catalogued"]
    assert len({r.sid for r in S.CATALOGUE}) == len(S.CATALOGUE)
    for r in S.CATALOGUE:
        assert r.disposition in S.DISPOSITIONS
        if r.disposition != S.IMPLEMENTED:
            assert r.why, f"{r.sid} has no reason"
        else:
            assert r.kind in ("ts", "xs", "pair")
    assert all(r.disposition == S.INAPPLICABLE for r in S.CATALOGUE if r.section == "options")
    assert set(S.TS_IDS) | set(S.XS_IDS) | set(S.PAIR_IDS) == {
        r.sid for r in S.CATALOGUE if r.disposition == S.IMPLEMENTED}


def _panel() -> F.Panel:
    p = F.planted_panel(n=N, n_sym=K, seed=7, groups=["fx_usd"] * K)
    pres = p.present.copy()
    pres[np.random.default_rng(1).random(pres.shape) < 0.05] = False
    return F.Panel(p.symbols, p.times, p.o, p.h, p.lo, p.c, p.v, pres, p.groups)


def _perturbed(p: F.Panel) -> F.Panel:
    rng = np.random.default_rng(3)
    arrs = [a.copy() for a in (p.o, p.h, p.lo, p.c, p.v)]
    for a in arrs:
        a[CUT:] *= np.exp(rng.normal(0, 0.1, a[CUT:].shape))
    o, h, lo, c, v = arrs
    return F.Panel(p.symbols, p.times, o, h, lo, c, v, p.present, p.groups)


@pytest.mark.parametrize("sid", S.TS_IDS)
def test_every_time_series_strategy_is_causal(sid: str) -> None:
    p = _panel()
    a, b = S.ts_signal(sid, p), S.ts_signal(sid, _perturbed(p))
    assert np.isfinite(a[:CUT]).any()
    assert np.array_equal(a[:CUT], b[:CUT], equal_nan=True), f"{sid} reads the future"


@pytest.mark.parametrize("sid", S.XS_IDS)
def test_every_class_book_strategy_is_causal(sid: str) -> None:
    p = _panel()
    if S.BY_ID[sid].only_class not in ("", "*"):
        groups = [S.BY_ID[sid].only_class] * K
        p = F.Panel(p.symbols, p.times, p.o, p.h, p.lo, p.c, p.v, p.present, tuple(groups))
    o = np.ones(K)
    a, _ = S.xs_signal(sid, p, o, 5)
    b, _ = S.xs_signal(sid, _perturbed(p), o, 5)
    assert np.isfinite(a[:CUT]).any(), f"{sid} produced nothing"
    assert np.array_equal(a[:CUT], b[:CUT], equal_nan=True), f"{sid} reads the future"


def test_pairs_are_causal() -> None:
    p = _panel()
    a = S.pair_signals(p, max_pairs=3)
    b = S.pair_signals(_perturbed(p), max_pairs=3)
    assert len(a) == 3
    for (_, _, s1, _), (_, _, s2, _) in zip(a, b, strict=True):
        assert np.array_equal(s1[:CUT], s2[:CUT], equal_nan=True)


def test_the_hp_filter_is_one_sided() -> None:
    w = S.hp_endpoint_weights(60, 1600.0)
    assert w.sum() == pytest.approx(1.0)
    x = np.linspace(0.0, 1.0, 60)
    assert w @ x == pytest.approx(1.0)        # a line is its own trend, read at its endpoint


def _family_kwargs(family: str) -> set[str]:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    fams = importlib.import_module("mt5desk.families")
    return set(inspect.signature(getattr(fams, f"family_{family}")).parameters)


def test_declared_families_take_the_declared_parameters() -> None:
    for r in S.CATALOGUE:
        for pair in (r.aligned, r.mirror):
            if pair is not None:
                assert pair[0] in A.FAMILIES
                assert set(pair[1]) <= _family_kwargs(pair[0]), r.sid
        if r.desk_family:
            sys.path.insert(0, str(ROOT / "desks" / "mt5"))
            from research import universe_policy as up
            assert r.desk_family in up.CROSS_SECTIONAL_FAMILIES


def test_the_adapter_measures_donates_and_respects_the_two_lanes() -> None:
    sys.path.insert(0, str(ROOT / "desks" / "mt5"))
    from research import universe_policy as up
    equity = up.class_members("equity")[0]
    syms = ("EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD", equity)
    bundle = A.synthetic_bundle(seed=4, n=1300, budget_s=120, symbols=syms)
    pkt = kakushadze151.run(bundle)
    census = pkt.representations[0]
    assert census["kind"] == "strategy151_census" and census["catalogued"] == 151
    assert equity in census["panel_symbols"] and not census["not_reached_this_pass"]
    assert pkt.trials_charged > 0 and pkt.candidates
    for c in pkt.candidates:
        assert c["family"] in A.FAMILIES and c["symbols"] != [equity]
    xs = [r for r in pkt.representations if r.get("shape") == "cross_sectional"]
    assert {r["strategy"] for r in xs} == set(S.XS_IDS)
    mom = next(r for r in xs if r["strategy"] == "stk.price_momentum")
    assert mom["by_class"]["fx_usd"]["xs_ic_mean"] is not None


def test_the_second_source_is_wired_into_the_federation() -> None:
    assert "kakushadze151" in A.SPECS and "kakushadze151" in fed.SEED_BY_ID
    assert fed.SEED_BY_ID["kakushadze151"].integration == "REBUILT"
    assert kakushadze151.RUNS_WITHOUT_LIBRARY
