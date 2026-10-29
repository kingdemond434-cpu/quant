"""The written rules for formula, cross_asset_residual and relative_value in the replication lane.

Two kinds of proof. SYNTHETIC: each rule does what its text says on bars built so the answer is
known, every wrapper the held certificates carry is applied as written, and any other key or
value is refused BY NAME (UNMEASURED), never ignored. DIFFERENTIAL: on the box's own parquets,
the desk's family run through its own call path (`family_call.signals`) and engine
(`engine.run_backtest`) and the lane's rebuild agree -- per-day Sharpe within the lane's own
tolerance (`judge_certificate` says REPLICATED) and the entry times almost identical. The test
may import the originals; the lane may not (test_replication_civilization pins that).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402
import replication_families as rf  # noqa: E402

UNIVERSE = DESK / "data" / "universe"
HOUR = 3_600_000_000_000


def _bars(n: int = 3000, seed: int = 3, spread: bool = True) -> rc.Bars:
    rng = np.random.default_rng(seed)
    t = np.datetime64("2024-01-01T00:00:00", "ns").astype("int64") + np.arange(n) * HOUR
    c = 1.2 + np.cumsum(rng.normal(0, 0.001, n))
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + 0.0005
    lo = np.minimum(o, c) - 0.0005
    sp = rng.integers(5, 40, n).astype(float) if spread else None
    return rc.bars_from_arrays(t, o, h, lo, c, spread=sp, tick_volume=None)


# ------------------------------------------------------------------------------ synthetic
def test_formula_follow_and_fade_are_mirror_images_and_the_dsl_parses_both_forms() -> None:
    b = _bars()
    base = {"expr": ["neg", ["mean", "spread", 5]], "hold_bars": 8}
    fol, why = rc.resolve_spec("formula", {**base, "side_mode": "follow"}, "asia", "LONG")
    fad, _ = rc.resolve_spec("formula", {**base, "side_mode": "fade"}, "asia", "LONG")
    assert fol is not None and fad is not None, why
    a, c = rf.SPECS["formula"].build(b, fol), rf.SPECS["formula"].build(b, fad)
    assert a and [o.t_ns for o in a] == [o.t_ns for o in c]
    assert all(x.side == -y.side for x, y in zip(a, c, strict=True))
    # one signal per hold_bars at most
    gaps = np.diff([int(o.t_ns // HOUR) for o in a])
    assert gaps.min() >= 8
    # the rendered call form reads as the same tree
    rend, _ = rc.resolve_spec("formula", {"expr": "neg(mean(spread, 5))"}, "asia", "LONG")
    assert rend is not None and rend["expr"] == ["neg", ["mean", "spread", 5]]
    # no spread column: the terminal is absent, so the rule never fires (no invented series)
    assert rf.SPECS["formula"].build(_bars(spread=False), fol) == []


def test_formula_operators_match_their_written_definitions() -> None:
    b = _bars(n=400)
    fr = rf._terminals(b, 20)
    n = len(b)
    sp = fr["spread"].to_numpy()
    dec = rf.evaluate(["decay", "spread", 3], fr, n).to_numpy()
    assert dec[10] == pytest.approx((3 * sp[10] + 2 * sp[9] + sp[8]) / 6)
    rank = rf.evaluate(["ts_rank", "spread", 5], fr, n).to_numpy()
    assert rank[20] == pytest.approx(np.mean(sp[15:20] <= sp[20]))
    bsm = rf.evaluate(["bars_since_min", "close", 5], fr, n).to_numpy()
    assert bsm[30] == 4 - int(np.argmin(b.c[26:31]))
    tw = rf.evaluate(["trade_when", ["delta", "close", 1], "spread"], fr, n).to_numpy()
    up = np.diff(b.c) > 0
    k = int(np.flatnonzero(~up[50:])[0]) + 51          # a bar where the gate is shut
    assert tw[k] == tw[k - 1]
    assert np.isnan(rf.evaluate(["mean", "spread", 10_000], fr, n)).all()


def test_cross_asset_residual_fades_a_planted_dislocation() -> None:
    rng = np.random.default_rng(11)
    n = 2400
    t = np.datetime64("2024-01-01T00:00:00", "ns").astype("int64") + np.arange(n) * HOUR
    f = 1.0 + np.cumsum(rng.normal(0, 0.001, n))
    noise = np.zeros(n)
    noise[1500:1510] = 0.02                         # the target alone jumps, then reverts
    y = 2.0 * np.exp(np.log(f) + np.cumsum(rng.normal(0, 0.0002, n)) + noise)
    def mk(c: np.ndarray) -> rc.Bars:
        return rc.bars_from_arrays(t, c, c * 1.0005, c * 0.9995, c)

    own, fac = mk(y), mk(f)
    p, why = rc.resolve_spec("cross_asset_residual",
                             {"factor_symbols": ["F"], "lookback": 240, "beta_win": 240,
                              "entry_z": 3.0, "ttl_bars": 8}, "asia", "LONG")
    assert p is not None, why
    p["_inputs"] = [fac]
    orders = rf.SPECS["cross_asset_residual"].build(own, p)
    near = [o for o in orders if 1500 <= (o.t_ns - t[0]) // HOUR <= 1510]
    assert near and all(o.side == -1 for o in near)     # rich residual -> short (revert)
    q = dict(p, side_mode="continue")
    assert all(o.side == 1 for o in rf.SPECS["cross_asset_residual"].build(own, q)
               if 1500 <= (o.t_ns - t[0]) // HOUR <= 1510)


def test_relative_value_target_is_written_with_abs_of_z_minus_exit() -> None:
    rng = np.random.default_rng(5)
    n = 1200
    t = np.datetime64("2024-01-01T00:00:00", "ns").astype("int64") + np.arange(n) * HOUR
    a = 1.0 + np.cumsum(rng.normal(0, 0.002, n))
    peer = a * np.exp(rng.normal(0, 0.003, n))
    def mk(c: np.ndarray) -> rc.Bars:
        return rc.bars_from_arrays(t, c, c * 1.001, c * 0.999, c)

    p, why = rc.resolve_spec("relative_value", {"peer_symbol": "P"}, "asia", "LONG")
    assert p is not None, why
    p["_inputs"] = [mk(peer)]
    orders = rf.SPECS["relative_value"].build(mk(a), p)
    assert orders and {o.side for o in orders} == {-1, 1}
    for o in orders[:20]:
        assert o.ttl_bars == 48 and (o.target - o.stop) * o.side > 0


def test_wrappers_are_applied_as_written() -> None:
    b = _bars()
    orders = [rc.Order(int(b.t[i]), 1, b.c[i] - 0.01, b.c[i] + 0.01, 4) for i in range(30, 400)]
    asia = rf.apply_wrappers(b, orders, {"session": (0, 8)})
    assert asia and all(int((o.t_ns // HOUR) % 24) < 8 for o in asia)
    late = rf.apply_wrappers(b, orders, {"delayed": True})
    assert [o.t_ns for o in late] == [o.t_ns + HOUR for o in orders]
    assert [o.stop for o in late] == [o.stop for o in orders]
    rev = rf.apply_wrappers(b, orders[:5], {"side_mode": "revert"})
    for o, r in zip(orders[:5], rev, strict=True):
        ref = b.c[int(np.searchsorted(b.t, o.t_ns))]
        assert r.side == -1 and r.stop == pytest.approx(2 * ref - o.stop)
    hv = rf.apply_wrappers(b, orders, {"regime": "high_vol"})
    lv = rf.apply_wrappers(b, orders, {"regime": "low_vol"})
    assert hv and lv and not {o.t_ns for o in hv} & {o.t_ns for o in lv}


@pytest.mark.parametrize(("family", "params", "needle"), [
    ("formula", {"expr": ["xrank", "spread"]}, "operator 'xrank'"),
    ("formula", {"expr": ["mean", "usd", 5]}, "terminal 'usd'"),
    ("formula", {"expr": ["mean", "spread", 5], "regime": "risk_on"}, "regime='risk_on'"),
    ("formula", {"expr": ["mean", "spread", 5], "entry_timing": "next_session"},
     "entry_timing='next_session'"),
    ("formula", {"expr": ["mean", "spread", 5], "execution_style": "limit"},
     "execution_style='limit'"),
    ("formula", {"expr": ["mean", "spread", 5], "conditioner": "carry"}, "conditioner"),
    ("formula", {"expr": ["mean", "spread", 5], "session": "sydney"}, "session='sydney'"),
    ("formula", {"expr": ["mean", "spread", 5], "side_mode": "revert"}, "side_mode='revert'"),
    ("cross_asset_residual", {"lookback": 240}, "no factor_symbols"),
    ("cross_asset_residual", {"factor_symbols": ["A"], "cost_aware": True}, "cost_aware"),
    ("relative_value", {"peer_symbol": "A", "residual": "pca"}, "residual"),
])
def test_a_param_with_no_written_rule_is_refused_by_name(family: str, params: dict[str, Any],
                                                          needle: str) -> None:
    p, why = rc.resolve_spec(family, params, "asia", "LONG")
    assert p is None and needle in why, why


def test_a_short_certificate_of_a_sideless_rule_is_refused() -> None:
    p, why = rc.resolve_spec("relative_value", {"peer_symbol": "A"}, "asia", "SHORT")
    assert p is None and "SHORT" in why


def test_a_missing_input_is_unmeasured_by_name() -> None:
    b = _bars()
    row = {"shadow_spec": {"symbol": "TESTFX", "family": "relative_value", "selector": "asia",
                           "params": {"peer_symbol": "NOPE"}},
           "gates": {"in_sample_screen": {"sharpe": 0.2}}}
    out = rc.replicate_certificate(row, meta={}, bars=b, inputs_loader=lambda s, t: None)
    assert out["verdict"] == rc.UNMEASURED and "NOPE" in out["why"][0]


def test_factor_symbols_read_as_a_list_or_its_printed_repr() -> None:
    assert rf.input_symbols("cross_asset_residual",
                            {"factor_symbols": "['USDCHF', 'USDDKK']"}) == ["USDCHF", "USDDKK"]
    assert rf.input_symbols("cross_asset_residual",
                            {"factor_symbols": ["USDCHF"]}) == ["USDCHF"]


# --------------------------------------------------------------------------- differential
F = {"atr_n": 20, "entry_z": 1.5, "hold_bars": 8, "norm": 240, "rr": 1.5, "stop_atr": 2.0}
CELLS: list[tuple[str, str, dict[str, Any]]] = [
    # held certificates, exactly as their keys spell them
    ("CHFJPY", "cross_asset_residual",
     {"beta_win": 240, "entry_z": 3.0, "factor_symbols": ["USDCHF", "USDJPY"], "lookback": 240,
      "session": "asia", "side_mode": "revert", "ttl_bars": 8}),
    ("CHFJPY", "cross_asset_residual",
     {"beta_win": 240, "entry_z": 3.0, "factor_symbols": ["USDCHF", "USDJPY"], "lookback": 240,
      "side_mode": "revert", "ttl_bars": 8}),
    ("AUDCAD", "formula", {"timeframe": "M15", **F, "side_mode": "follow",
                           "expr": ["max", ["mean", "spread", 8], 48]}),
    ("AUDCAD", "formula", {"timeframe": "M15", **F, "side_mode": "follow",
                           "expr": ["delay", ["decay", "spread", 3], 3]}),
    # held expressions and wrappers on the bars this tree holds
    ("CHFJPY", "cross_asset_residual",
     {"beta_win": 240, "entry_z": 2.0, "factor_symbols": ["USDCHF", "USDJPY"], "lookback": 240,
      "regime": "low_vol", "entry_timing": "delayed", "execution_style": "market",
      "side_mode": "revert", "ttl_bars": 8}),
    ("AUDNZD", "formula", {"timeframe": "M15", **F, "side_mode": "fade", "session": "asia",
                           "expr": ["zscore", ["ts_backfill", ["trade_when", "range", "spread"],
                                                240], 24]}),
    ("AUDNZD", "formula", {"timeframe": "M15", **F, "side_mode": "fade", "session": "asia",
                           "expr": ["group_rank", ["decay", "spread", 5],
                                    ["abs", ["ts_backfill", "body", 120]], 48]}),
    ("AUDCAD", "formula", {"timeframe": "M15", **F, "side_mode": "follow",
                           "expr": ["trade_when", ["sign", ["bars_since_min",
                                                            ["delta", "close", 2], 5]],
                                    ["delta", "close", 2]]}),
    ("AUDCAD", "formula", {"timeframe": "M15", **F, "side_mode": "fade", "session": "asia",
                           "expr": "neg(mean(std(spread, 12), 5))"}),
    # relative_value: the held peers' bars are not on this tree; same rule, pairs that are
    ("EURCHF", "relative_value", {"peer_symbol": "USDCHF"}),
    ("AUDNZD", "relative_value", {"timeframe": "M15", "peer_symbol": "NZDCAD",
                                  "session": "asia"}),
]


def _original(sym: str, fam: str, params: dict[str, Any], costs: Any) -> list[Any]:
    import pandas as pd
    from mt5desk import families, family_call
    from mt5desk.engine import run_backtest
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    from mt5desk.family_formula import family_formula

    tf = params.get("timeframe", "H1")

    def frame(s: str) -> Any:
        return families._h1(pd.read_parquet(UNIVERSE / f"{s}_{tf}.parquet"))

    cp = {k: v for k, v in params.items() if k != "timeframe"}
    if fam == "cross_asset_residual":
        cp["factors"] = [frame(s) for s in cp.pop("factor_symbols")]
    if fam == "relative_value":
        cp["peer"] = frame(cp.pop("peer_symbol"))
    fn = family_formula if fam == "formula" else ORTHOGONAL_FAMILIES[fam]
    df = frame(sym)
    return list(run_backtest(df, family_call.signals(fn, df, side=1, params=cp), costs).trades)


@pytest.mark.parametrize(("sym", "fam", "params"), CELLS,
                         ids=[f"{s}-{f}-{i}" for i, (s, f, _p) in enumerate(CELLS)])
def test_the_rebuild_agrees_with_the_desks_implementation(sym: str, fam: str,
                                                          params: dict[str, Any]) -> None:
    tf = params.get("timeframe", "H1")
    need = [sym, *rf.input_symbols(fam, params)]
    if any(not (UNIVERSE / f"{s}_{tf}.parquet").exists() for s in need):
        pytest.skip(f"bars for {need} at {tf} are not on this tree")
    import pandas as pd
    from mt5desk.engine import Costs

    meta = (json.loads((UNIVERSE / "universe.json").read_text("utf-8")).get(sym) or {}
            if (UNIVERSE / "universe.json").exists() else {})
    cs = rc.cost_spec(meta)
    costs = Costs(spread_per_lot=cs.spread_per_lot, commission_per_lot=cs.commission_per_lot,
                  contract_oz=cs.contract_size, quote_per_account=cs.quote_per_account)
    trades = _original(sym, fam, params, costs)
    daily = pd.Series([t.r_multiple for t in trades],
                      index=[pd.Timestamp(t.entry_time).date() for t in trades]
                      ).groupby(level=0).sum()
    theirs = float(daily.mean() / daily.std(ddof=1))

    p, why = rc.resolve_spec(fam, params, "asia", "LONG")
    assert p is not None, why
    assert rc.attach_inputs(fam, params, p) is None
    bars = rc.load_bars(sym, tf)
    assert bars is not None
    _orders, fills = rc.rebuild(fam, bars, p, cs.price_units)
    ours, _ = rc.sharpe(fills)
    verdict, reasons = rc.judge_certificate(theirs, ours, len(fills))
    assert verdict == rc.REPLICATED, (theirs, ours, reasons)
    a = {pd.Timestamp(t.entry_time).value for t in trades}
    b = {f.entry_t for f in fills}
    assert len(a & b) / max(1, len(a | b)) >= 0.95, (len(a), len(b), len(a & b))
    assert ours is not None and abs(ours - theirs) <= 0.05 * max(abs(theirs), 0.05)
