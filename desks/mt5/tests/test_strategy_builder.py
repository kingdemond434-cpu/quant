"""The rule-builder family and the genetic strategy builder: no look-ahead, no inflation."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mt5desk.families_orthogonal  # noqa: E402,F401  (registers the family)
import strategy_builder as sb  # noqa: E402
from mt5desk.families import get_family_func  # noqa: E402
from mt5desk.family_rule_builder import BLOCKS, FILTERS, entry_sides  # noqa: E402

META = {"EURUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0,
                   "median_spread_pts": 10}}


def _bars(n: int = 6000, seed: int = 0, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="h", tz="UTC")
    r = rng.normal(drift, 0.002, n)
    c = 1.1 * np.exp(np.cumsum(r))
    o = np.concatenate([[c[0]], c[:-1]])
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 3e-4, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 3e-4, n)))
    v = rng.integers(100, 1000, n).astype(float)
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "tick_volume": v}, index=idx)


def test_family_registered_and_emits_signals():
    fn = get_family_func("rule_builder")
    assert fn is not None
    sigs = fn(_bars(), entry=[{"b": "breakout", "n": 20}], max_hold_bars=12)
    assert sigs and all(s.side in (-1, 1) for s in sigs)


@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_rule_builder_has_no_lookahead(block):
    d = _bars(3000, seed=3)
    params = {k: v[0] for k, v in BLOCKS[block][1].items()}
    entry = [{"b": block, **params}]
    filters = [{"f": "session", "start": 2, "end": 22}, {"f": "trend", "n": 50, "mode": "with"}]
    full = entry_sides(d, entry, filters, False)
    cut = 2000
    part = entry_sides(d.iloc[:cut], entry, filters, False)
    assert np.array_equal(full[:cut], part)


def test_every_filter_runs():
    d = _bars(1500)
    for name, (_, space) in FILTERS.items():
        flt = [{"f": name, **{k: v[0] for k, v in space.items()}}]
        s = entry_sides(d, [{"b": "ma_state", "n": 20}], flt, False)
        assert s.shape == (len(d),)


def test_genome_operators_stay_valid():
    rng = random.Random(1)  # noqa: S311
    gs = [sb.random_genome(rng) for _ in range(30)]
    for _ in range(200):
        a, b = rng.choice(gs), rng.choice(gs)
        c = sb.mutate(rng, sb.crossover(rng, a, b))
        assert 1 <= len(c["entry"]) <= 3 and len(c["filters"]) <= 2
        assert set(sb.EXIT_SPACE) <= set(c)


def test_search_never_reads_the_reserved_tail(tmp_path):
    from mt5desk.engine import Costs
    d = _bars(6000)
    lin = sb.Lineage("EURUSD", "H1", d, Costs.from_symbol(META["EURUSD"], mult=2.0),
                     state_dir=tmp_path)
    assert lin.visible.index[-1] < lin.reserved_from
    assert len(lin.visible) == int(len(d) * (1 - sb.RESERVE_FRAC))
    assert lin.valid_from > lin.fold_edges[0]


def test_noise_is_not_proposed_and_trials_accumulate(tmp_path, monkeypatch):
    """Pure random walk: the search will find in-sample winners; none may survive harvest."""
    monkeypatch.setattr(sb, "POP", 16)
    loader = lambda s, c: _bars(6000, seed=11)  # noqa: E731
    rep = sb.run(budget_s=12, symbols=["EURUSD"], chart="H1", dry_run=True, state_dir=tmp_path,
                 loader=loader, meta={"symbols": META})
    st = rep["cells"]["EURUSD|H1"]
    assert st["evaluated_pass"] > 0
    assert rep["survivors"] == 0


def test_population_persists_and_trial_count_ratchets(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "POP", 12)
    loader = lambda s, c: _bars(5000, seed=5)  # noqa: E731
    monkeypatch.setattr(sb, "REPORT", tmp_path / "rep.json")
    import proposer_common
    monkeypatch.setattr(proposer_common, "donate", lambda *a, **k: None)
    sb.run(budget_s=6, symbols=["EURUSD"], chart="H1", state_dir=tmp_path, loader=loader,
           meta={"symbols": META})
    first = json.loads((tmp_path / "EURUSD_H1.json").read_text())
    sb.run(budget_s=6, symbols=["EURUSD"], chart="H1", state_dir=tmp_path, loader=loader,
           meta={"symbols": META})
    second = json.loads((tmp_path / "EURUSD_H1.json").read_text())
    assert second["evaluated_total"] > first["evaluated_total"] > 0
    assert len(second["pop"]) == sb.POP


def test_deflation_bites_with_more_trials():
    rng = np.random.default_rng(0)
    r = rng.normal(0.15, 1.0, 200)
    assert sb.deflated_sharpe(r, 1) > sb.deflated_sharpe(r, 10_000)


def test_bh_fdr():
    assert sb.bh_fdr([0.001, 0.5, 0.9]) == [True, False, False]
    assert sb.bh_fdr([0.2, 0.3]) == [False, False]


def test_intake_budget_follows_the_judge(tmp_path):
    p = tmp_path / "rate.json"
    assert sb.intake_budget(p)["cap"] == sb.EXPLORE_FLOOR                 # unreadable
    p.write_text(json.dumps({"status": "MEASURED", "eta_to_drain": {"status": "GROWING"}}))
    assert sb.intake_budget(p)["cap"] == sb.EXPLORE_FLOOR                 # growing: floor only
    p.write_text(json.dumps({"status": "MEASURED",
                             "eta_to_drain": {"status": "DRAINING", "net_per_hour": 2000.0}}))
    cap = sb.intake_budget(p)["cap"]
    assert cap == min(sb.MAX_PER_PASS, int(sb.DRAIN_SHARE * 48000 / sb.PASSES_PER_DAY))
    p.write_text(json.dumps({"status": "UNMEASURED"}))
    assert sb.intake_budget(p)["cap"] == sb.EXPLORE_FLOOR


def test_breadth_least_searched_first_and_exotic_cost_gate():
    meta = {"symbols": {**META, "USDTRY": {"contract_size": 100000, "tick_size": 0.00001,
                                             "tick_value": 1.0, "median_spread_pts": 50000}}}
    loader = lambda s, c: _bars(3000, seed=1)  # noqa: E731
    cov = {"passes": {"EURUSD|M15": 3, "EURUSD|H1": 1}}
    cells, refused = sb.pick_cells(["EURUSD", "USDTRY"], 4, loader, meta, cov,
                                   charts=("M15", "H1", "H4"))
    assert [(s, c) for s, c, _, _ in cells] == [("EURUSD", "H4")]
    assert any(k.startswith("USDTRY|") for k in refused)


def test_interleave_spreads_over_cells_and_classes():
    def row(sym, cls, dsr):
        return {"symbol": sym, "params": {"timeframe": "H1"}, "mechanism_class": cls,
                "evidence": {"valid_dsr": dsr}}
    rows = [row("EURUSD", "trend", 0.99 - i * 0.001) for i in range(10)]
    rows += [row("XAUUSD", "reversion", 0.96), row("USDJPY", "flow", 0.955)]
    out = sb.interleave(rows, 3)
    assert {r["symbol"] for r in out} == {"EURUSD", "XAUUSD", "USDJPY"}


def test_archive_keeps_every_class_niche():
    rng = random.Random(4)  # noqa: S311
    from mt5desk.family_rule_builder import MECH_CLASS
    classes = set(MECH_CLASS.values())
    seen = {sb.mech_class(sb.random_genome(rng, c)) for c in classes}
    assert seen == classes


def test_donations_go_through_the_shared_breadth_allocator():
    def row(sym, cls, dsr, i):
        return {"symbol": sym, "params": {"timeframe": "H1", "i": i}, "mechanism_class": cls,
                "evidence": {"valid_dsr": dsr}}
    rows = [row("EURUSD", "trend", 0.99, i) for i in range(20)]
    rows += [row("XAUUSD", "reversion", 0.96, 0), row("USDJPY", "flow", 0.955, 0)]
    out, info = sb.allocate_donations(rows, 6, {}, {})
    assert info["allocator"] == "libs.ops.breadth_allocator"
    assert {"XAUUSD", "USDJPY"} <= {r["symbol"] for r in out}
    assert sum(r["symbol"] == "EURUSD" for r in out) < len(out)


def test_generator_coverage_marks_built_not_live(tmp_path):
    import generator_coverage as gc
    (tmp_path / "desks/mt5/research").mkdir(parents=True)
    (tmp_path / "desks/mt5/research/strategy_builder.py").write_text("")
    doc = gc.build(tmp_path)
    by = {r["method"]: r for r in doc["methods"]}
    sbr = next(r for m, r in by.items() if m.startswith("rule-strategy"))
    assert sbr["status"] == "PARTIAL"                      # code, no report: not live
    rep = tmp_path / "desks/mt5/reports/STRATEGY_BUILDER.json"
    rep.parent.mkdir(parents=True)
    rep.write_text(json.dumps({"tests_run": 500, "donated": 3}))
    sbr = next(r for r in gc.build(tmp_path)["methods"] if r["method"].startswith("rule-strategy"))
    assert sbr["status"] == "LIVE" and sbr["cells_per_1k_tests"] == 6.0
    assert doc["counts"]["MISSING"] >= 1
