"""Specialist cells and the residual search: buildable, causal, charged, and research-only.

WHAT THIS PINS, on synthetic bars and ledgers only:
  * the four specialist families are registered where the sealed gauntlet looks, judged
    BUILDABLE by `gauntlet_buildability`, mapped by `axis_registry`, and built by the SEALED
    `external_gauntlet.build_cell` itself (through its `h1_override`), loading their foreign
    series from the bar store given only what the cell carries;
  * NO LOOKAHEAD: corrupting the future (own bars AND the foreign series) changes no signal
    dated before the corruption;
  * each mechanism trades the side its prior names (month-end against the equity-minus-bond gap,
    carry harvested in calm and unwound in risk-off, a seasonal window only inside its dates);
  * the specialist organ mints only buildable, lane-allowed cells, donates only over the floor,
    never twice, and charges every MEASURED cell to the trial census;
  * the residual search finds a planted hour effect after BH correction, emits the certified
    parent wrapped by `entry_conditioned`, prices a gate's refusals relaxed, says UNMEASURED for
    tightening without a margin and for absent inputs, and never touches a live-policy file;
  * both organs are hourly legs with budgets and layers, and residual_queue reads the report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_specialist as fs  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

DAYS = 700


def _bars(seed: int, drift: float = 0.0, days: int = DAYS, start: str = "2021-01-04"
          ) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    r = rng.normal(drift / 24.0, 0.002, len(idx))
    close = 100.0 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A bar store holding an index, a bond proxy, a risk proxy and a conditioner."""
    frames = {"IDX": _bars(1), "BOND": _bars(2), "RISK": _bars(3), "COND": _bars(4),
              "FXA": _bars(5)}
    for sym, f in frames.items():
        f.to_parquet(tmp_path / f"{sym}_H1.parquet")
    monkeypatch.setattr(xs, "UNIVERSE_DIR", tmp_path)
    xs._SERIES_CACHE.clear()
    yield frames
    xs._SERIES_CACHE.clear()


def _key(sigs: list[Signal]) -> list[tuple]:
    return [(pd.Timestamp(s.time).value, s.side, round(s.stop, 8), round(s.target, 8), s.tag)
            for s in sigs]


def _corrupt(df: pd.DataFrame, cut: pd.Timestamp, seed: int = 99) -> pd.DataFrame:
    out = df.copy()
    m = out.index >= cut
    rng = np.random.default_rng(seed)
    k = rng.normal(1.0, 0.05, int(m.sum()))
    for c in ("open", "high", "low", "close"):
        out.loc[m, c] = out.loc[m, c].to_numpy() * k
    return out


# ------------------------------------------------------------------------ registration ---
SPEC = ("carry_risk_off", "month_end_rebalance", "seasonal_window", "entry_conditioned")


@pytest.mark.parametrize("name", SPEC)
def test_registered_buildable_and_mapped(name):
    from research import axis_registry, gauntlet_buildability as gb
    assert fo.ORTHOGONAL_FAMILIES[name] is fs.SPECIALIST_FAMILIES[name]
    assert name in fo.FAMILY_INPUTS
    assert gb.family_verdict(name)[0] == gb.BUILDABLE
    assert name in axis_registry.FAMILY_TABLE


def test_clusters_and_sweep_exclusion():
    from libs.research.alpha_clusters import classify_family
    from research import orthogonal_sweep as osw
    assert classify_family("carry_risk_off") == "macro_rates"
    assert classify_family("month_end_rebalance") == "fixing_roll_calendar"
    for name in SPEC:
        assert name in osw.NOT_SOURCED_HERE


def test_carry_risk_off_and_month_end_rebalance_are_not_price_only():
    """Both read another series, so neither may carry the price-only label anywhere: the
    buildability census, the axis registry's information source, or FAMILY_INPUTS' sentinel."""
    from research import axis_registry, gauntlet_buildability as gb
    assert gb.information_class("carry_risk_off") == gb.EXOGENOUS
    assert gb.information_class("month_end_rebalance") == gb.CONDITIONED
    assert gb.information_class("seasonal_window") == gb.PRICE_ONLY
    for fam, param in (("carry_risk_off", "risk_symbol"), ("month_end_rebalance", "bond_symbol")):
        assert axis_registry.classify_family(fam)[1] != "price_only"
        assert not fo.FAMILY_INPUTS[fam][0].lower().startswith("price only")
        assert fo.FAMILY_INPUTS[fam][1] is not None           # shadow_forward: not replayable
        assert param in [k for k, _ in fs.FOREIGN_SERIES[fam]]
        why = gb.family_verdict(fam)[1]
        assert "not price-only" in why and "supplies every data input" not in why
        assert gb.census()[fam]["information"] != gb.PRICE_ONLY
    assert any("contract_terms" in path for path in gb.foreign_series("carry_risk_off"))
    # a cell that names an empty series would read nothing: refused by name, never built blind
    v, why = gb.cell_verdict("month_end_rebalance", {"bond_symbol": ""})
    assert v == gb.MISSING_PARAMS and "bond_symbol" in why
    assert gb.information_class("entry_conditioned", {"hours": [3]}) == gb.PRICE_ONLY
    assert gb.information_class("entry_conditioned", {"cond_symbol": "USDX"}) == gb.CONDITIONED


def test_breadth_counts_one_mechanism_once_however_many_cells_it_spans():
    """k-style breadth: 352 wmr_fix_reversal cells on many symbols and parameter points are ONE
    mechanism, not 352 breadth units -- and the trial charge still counts every cell."""
    from research import specialist_cell as sc
    grid = sc._grid({"fix_hour": [18, 19], "pre_window_bars": [2, 3],
                     "min_displacement_atr": [0.6, 1.0], "hold_bars": [3, 6]})
    cells = [{"klass": "fx", "mechanism": "wmr_fix_reversal", "symbol": f"FX{i:02d}",
              "family": "fx_fixing_reversal", "params": p} for i in range(22) for p in grid]
    cells += [{"klass": "indices", "mechanism": "overnight_gap", "symbol": "US500",
               "family": "overnight_gap_decay", "params": {"gap_atr": g}} for g in (0.5, 1.0)]
    b = sc.breadth(cells)
    assert b["cells"] == 22 * 16 + 2 and b["breadth_k"] == 2
    g = b["family_grids"]["fx/wmr_fix_reversal"]
    assert g == {"cells": 352, "families": ["fx_fixing_reversal"], "symbols": 22,
                 "param_points": 16}
    assert b["largest_unit"] == "fx/wmr_fix_reversal" and b["largest_unit_share"] > 0.99
    assert sc.charge(cells)["n_raw"] == len(cells)            # every trial is still charged


# ------------------------------------------------------------------------------ families ---
def test_seasonal_window_fires_only_inside_and_wraps_the_year():
    d = _bars(7)
    sigs = fs.family_seasonal_window(d, start_md=1215, end_md=115, side_bias=-1)
    assert sigs
    for s in sigs:
        md = s.time.month * 100 + s.time.day
        assert md >= 1215 or md <= 115
        assert s.side == -1 and s.time.hour <= 16
    assert fs.family_seasonal_window(d, start_md=1340, end_md=115, side_bias=1) == []
    assert fs.family_seasonal_window(d, start_md=101, end_md=115, side_bias=0) == []


def test_month_end_rebalance_trades_against_the_gap(store, monkeypatch):
    idx = store["IDX"].copy()
    # plant: the index out-runs the bond in every month's first half
    day = idx.index.day
    idx["close"] = idx["close"] * np.exp(np.where(day <= 20, 0.0004, 0.0).cumsum())
    sigs = fs.family_month_end_rebalance(idx, bond_symbol="BOND", days_before=3,
                                         min_gap_sd=0.0)
    assert sigs
    last3 = set()
    for y in range(2021, 2024):
        for m in range(1, 13):
            last3.update(fs.last_weekdays(y, m, 3))
    assert all(s.time.date() in last3 for s in sigs)
    assert sum(s.side < 0 for s in sigs) > 0.6 * len(sigs)
    assert fs.family_month_end_rebalance(idx, bond_symbol="ABSENT") == []


def test_carry_risk_off_harvests_in_calm_and_unwinds_in_risk_off(store, monkeypatch):
    monkeypatch.setattr(fs, "carry_side", lambda s: 1)
    d = store["FXA"]
    h = fs.family_carry_risk_off(d, symbol="FXA", mode="harvest", risk_symbol="RISK")
    u = fs.family_carry_risk_off(d, symbol="FXA", mode="unwind", risk_symbol="RISK")
    assert h and u
    assert all(s.side == 1 for s in h) and all(s.side == -1 for s in u)
    assert not ({s.time for s in h} & {s.time for s in u})
    monkeypatch.setattr(fs, "carry_side", lambda s: 0)
    assert fs.family_carry_risk_off(d, symbol="FXA", risk_symbol="RISK") == []


def test_entry_conditioned_filters_and_refuses_a_blind_cell(store):
    from mt5desk.families import get_family_func
    d = store["FXA"]
    base = get_family_func("mean_reversion_rsi")(d)
    assert base
    assert fs.family_entry_conditioned(d, base_family="mean_reversion_rsi") == []
    by_dow = fs.family_entry_conditioned(d, base_family="mean_reversion_rsi", dows=[1, 2])
    assert by_dow and all(s.time.dayofweek in (1, 2) for s in by_dow)
    assert len(by_dow) < len(base)
    up_ = fs.family_entry_conditioned(d, base_family="mean_reversion_rsi", cond_symbol="COND",
                                      cond_sign=1)
    dn = fs.family_entry_conditioned(d, base_family="mean_reversion_rsi", cond_symbol="COND",
                                     cond_sign=-1)
    assert up_ and dn and not ({s.time for s in up_} & {s.time for s in dn})
    hv = fs.family_entry_conditioned(d, base_family="mean_reversion_rsi", vol_regime="high_vol")
    nhv = fs.family_entry_conditioned(d, base_family="mean_reversion_rsi", vol_regime="not_high_vol")
    assert len(hv) + len(nhv) == len(base)
    assert fs.family_entry_conditioned(d, base_family="relative_value", hours=[3]) == []
    assert fs.family_entry_conditioned(d, base_family="discovered", hours=[3]) == []


@pytest.mark.parametrize("family,params", [
    ("seasonal_window", {"start_md": 601, "end_md": 831, "side_bias": 1}),
    ("month_end_rebalance", {"bond_symbol": "BOND", "min_gap_sd": 0.0}),
    ("entry_conditioned", {"base_family": "mean_reversion_rsi",
                           "base_params": {}, "cond_symbol": "COND",
                           "cond_sign": 1}),
])
def test_no_lookahead_with_the_foreign_series_corrupted_too(store, tmp_path, family, params):
    fn = fo.ORTHOGONAL_FAMILIES[family]
    d = store["IDX"]
    cut = d.index[len(d) * 2 // 3]
    clean = [s for s in fn(d, **params) if s.time < cut]
    assert clean, "vacuous: nothing before the cut"
    for sym in ("BOND", "COND"):
        _corrupt(store[sym], cut, seed=hash(sym) % 1000).to_parquet(tmp_path / f"{sym}_H1.parquet")
    xs._SERIES_CACHE.clear()
    dirty = [s for s in fn(_corrupt(d, cut), **params) if s.time < cut]
    assert _key(clean) == _key(dirty)


def test_carry_risk_off_no_lookahead(store, tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "carry_side", lambda s: 1)
    d = store["FXA"]
    cut = d.index[len(d) * 2 // 3]
    clean = [s for s in fs.family_carry_risk_off(d, symbol="FXA", risk_symbol="RISK",
                                                 mode="unwind") if s.time < cut]
    assert clean
    _corrupt(store["RISK"], cut).to_parquet(tmp_path / "RISK_H1.parquet")
    xs._SERIES_CACHE.clear()
    dirty = [s for s in fs.family_carry_risk_off(_corrupt(d, cut), symbol="FXA",
                                                 risk_symbol="RISK", mode="unwind")
             if s.time < cut]
    assert _key(clean) == _key(dirty)


def test_the_sealed_build_cell_builds_every_specialist_family(store):
    import external_gauntlet as eg
    cases = [("IDX", "seasonal_window", {"start_md": 601, "end_md": 831, "side_bias": 1}),
             ("IDX", "month_end_rebalance", {"bond_symbol": "BOND", "min_gap_sd": 0.0}),
             ("FXA", "entry_conditioned", {"base_family": "mean_reversion_rsi",
                                           "base_params": {}, "dows": [1]})]
    for sym, fam, params in cases:
        cell = eg.build_cell(sym, fam, dict(params), {}, h1_override=store[sym])
        assert cell is not None, (fam, eg.LAST_BUILD_FAILURE)
        assert cell["sigs"], fam


# ------------------------------------------------------------------- the specialist organ ---
def test_catalogue_is_lane_filtered_and_buildable():
    from research import specialist_cell as sc
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    cells = sc.plan({"fx": ["EURUSD"], "metals": ["XAUUSD"], "energy": ["XTIUSD"],
                     "indices": ["US500"], "softs": ["CORN"]})
    mechs = {(c["klass"], c["mechanism"]) for c in cells}
    for want in [("fx", "wmr_fix_reversal"), ("fx", "carry_risk_off"),
                 ("fx", "cb_meeting_drift"), ("metals", "gold_real_yield"),
                 ("metals", "gold_silver_ratio"), ("energy", "eia_inventory"),
                 ("indices", "overnight_gap"), ("indices", "open_drive"),
                 ("indices", "month_end_rebalance"), ("softs", "weather_window")]:
        assert want in mechs, want
    verdicts = {cell_verdict(c["family"], c["params"])[0] for c in cells}
    assert verdicts == {BUILDABLE}
    assert all(c["prior"] for c in cells)
    assert not sc.plan({"fx": ["APPLE"]})               # single names never hunted here


def test_seed_donates_over_the_floor_once_and_charges_every_measured_cell(tmp_path,
                                                                          monkeypatch):
    from research import proposer_common as pc
    from research import specialist_cell as sc
    monkeypatch.setattr(sc, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(sc, "CANON", tmp_path / "absent.json")
    monkeypatch.setattr(sc, "_meta", lambda: {})
    fired = iter([80, 10] * 1000)
    monkeypatch.setattr(sc, "measure", lambda s, f, p, m: {"built": True, "signal_days": 99,
                                                            "trade_days_lb": next(fired)})
    donated: list[list[dict]] = []

    def fake_donate(source, rows, tests_run):
        donated.append(rows)
        return tmp_path / "d.json"
    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(donated[-1])})
    doc = sc.run(budget_s=60, out=tmp_path / "SPECIALIST_CELLS.json",
                 symbols_by_class={"indices": ["US500"]})
    s = doc["seeding"]
    assert s["measured_this_pass"] == s["cells_in_catalogue"] > 0
    assert s["trial_charge_this_pass"]["n_raw"] == s["measured_this_pass"]
    assert len(donated) == 1 and len(donated[0]) == (s["measured_this_pass"] + 1) // 2
    assert all(r["source"] == "specialist_cell" for r in donated[0])
    again = sc.run(budget_s=60, out=tmp_path / "SPECIALIST_CELLS.json",
                   symbols_by_class={"indices": ["US500"]})
    assert again["seeding"]["measured_this_pass"] == 0
    assert again["seeding"]["donation"]["status"] == "NOTHING_NEW"
    assert again["certificates"]["status"] == "UNMEASURED"
    assert (tmp_path / "SPECIALIST_CELLS.json").exists()


def test_an_input_gap_is_counted_never_donated(tmp_path, monkeypatch):
    from research import specialist_cell as sc
    monkeypatch.setattr(sc, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(sc, "_meta", lambda: {})
    monkeypatch.setattr(sc, "measure", lambda s, f, p, m: {"built": False,
                                                            "why": "no H1 bars for X"})
    s = sc.seed(budget_s=60, dry_run=True, symbols_by_class={"energy": ["XTIUSD"]})
    assert s["candidates_this_pass"] == 0
    assert sum(r.get("input_gap", 0) for r in s["by_mechanism"]) == s["cells_in_catalogue"]


# ----------------------------------------------------------------- the residual search ---
def _trades(n_per: int = 60) -> list[dict]:
    """Four sleeves; hour 9 carries +0.8R nobody's sleeve mean explains."""
    rng = np.random.default_rng(3)
    out = []
    start = pd.Timestamp("2026-01-05 00:00", tz="UTC")
    for k, sleeve in enumerate(("EURUSD_overnight_gap_decay_asia", "GBPUSD_sleeve_b",
                                "AUDUSD_sleeve_c", "USDJPY_sleeve_d")):
        for i in range(n_per):
            t = start + pd.Timedelta(hours=int(rng.integers(0, 24 * 90)))
            r = rng.normal(0.05 * k, 0.5) + (0.8 if t.hour == 9 else 0.0)
            out.append({"sleeve": sleeve, "symbol": sleeve[:6], "basis": "shadow", "t": t,
                        "r": float(r)})
        for i in range(12):
            t = start + pd.Timedelta(days=int(rng.integers(0, 90)), hours=9)
            out.append({"sleeve": sleeve, "symbol": sleeve[:6], "basis": "shadow", "t": t,
                        "r": float(rng.normal(0.8, 0.5))})
    return out


def test_residual_search_finds_a_planted_hour_and_emits_the_parent_conditioned(monkeypatch):
    from research import residual_search as rs
    trades = _trades()
    specs = {"EURUSD_overnight_gap_decay_asia": {"symbol": "EURUSD",
                                                  "family": "overnight_gap_decay",
                                                  "params": {}, "cert": "c1",
                                                  "source": "canon"}}
    model = rs.residualise(trades, specs)
    assert model["n"] == len(trades)
    for t in trades:
        t["hour"], t["dow"] = t["t"].hour, t["t"].dayofweek
    found = rs.search(trades)
    hits = [f for f in found["findings"] if f["axis"] == "hour" and f["bucket"] == 9]
    assert hits and hits[0]["mean_residual_r"] > 0
    assert found["tests_run"] >= len(found["findings"])
    kids, skipped = rs.children(trades, hits, specs)
    assert len(kids) == 1
    k = kids[0]
    assert k["family"] == "entry_conditioned" and k["params"]["hours"] == [9]
    assert k["params"]["base_family"] == "overnight_gap_decay"
    assert skipped["parent sleeve has no certified spec"] == 3
    neg = {**hits[0], "mean_residual_r": -0.5}
    for t in trades:
        t["e"] = -abs(t["e"]) if t["hour"] == 9 else t["e"]
    kn, _ = rs.children(trades, [neg], specs)
    assert kn and 9 not in kn[0]["params"]["hours"] and len(kn[0]["params"]["hours"]) == 23


def test_residual_search_is_unmeasured_without_trades_and_writes_no_policy(tmp_path,
                                                                            monkeypatch):
    from research import residual_search as rs
    monkeypatch.setattr(rs, "load_trades", lambda: ([], {"n_trades": 0}))
    for name in ("CANON", "SLEEVES", "COUNTERFACTUALS", "DECISION_DATASET", "DECISIONS", "LIVE",
                 "MODIFIERS", "STATE"):
        monkeypatch.setattr(rs, name, tmp_path / f"absent_{name}")
    monkeypatch.setattr(rs, "CITED", {"x": tmp_path / "absent.json"})
    before = {p: p.stat().st_mtime_ns for p in (_DESK / "data").glob("*.json")}
    doc = rs.run(out=tmp_path / "RESIDUAL_SEARCH.json")
    assert doc["residual"]["status"] == "UNMEASURED"
    assert doc["counterfactual_policy"]["gates"]["status"] == "UNMEASURED"
    assert doc["counterfactual_policy"]["capital_modifiers"]["status"] == "UNMEASURED"
    assert "RESEARCH FINDINGS ONLY" in doc["scope"]
    after = {p: p.stat().st_mtime_ns for p in (_DESK / "data").glob("*.json")}
    assert before == after


def test_gate_relaxed_is_priced_and_tightened_is_unmeasured_without_a_margin(tmp_path,
                                                                           monkeypatch):
    from research import residual_search as rs
    cf = tmp_path / "counterfactuals.jsonl"
    rows = [{"sleeve": "s", "time": f"2026-01-{1 + i % 28:02d}T0{i % 9}:00", "side": "buy",
             "reason": "regime_veto", "status": "REPLAYED", "r": 1.0 + 0.1 * (i % 3)}
            for i in range(25)]
    rows.append({"sleeve": "s", "time": "x", "side": "buy", "reason": "regime_veto",
                 "status": "NOT_TRIGGERED"})
    cf.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    monkeypatch.setattr(rs, "COUNTERFACTUALS", cf)
    for name in ("DECISION_DATASET", "DECISIONS", "LIVE"):
        monkeypatch.setattr(rs, name, tmp_path / f"absent_{name}")
    g = rs.gate_policy()
    rel = g["gates"]["regime_veto"]["relaxed"]
    assert rel["n"] == 25 and rel["verdict"] == "RELAXING_WOULD_HAVE_EARNED"
    assert g["gates"]["regime_veto"]["tightened"]["status"] == "UNMEASURED"


def test_modifier_policy_holds_average_heat_fixed(tmp_path, monkeypatch):
    from research import residual_search as rs
    ml = tmp_path / "mods.jsonl"
    ml.write_text(json.dumps({"t": "2026-01-01T00:00:00+00:00", "sleeve": "s",
                              "category": "BOOST", "multiplier": 1.5}), "utf-8")
    monkeypatch.setattr(rs, "MODIFIERS", ml)
    trades = [{"sleeve": "s", "t": pd.Timestamp("2026-01-02", tz="UTC"), "r": 1.0}] * 5
    got = rs.modifier_policy(trades)
    curve = got["categories"]["BOOST"]["elog_per_trade_by_lambda"]
    # one multiplier: its dispersion is zero, so every lambda is the same bet at the same heat
    assert len(set(curve.values())) == 1


def test_residual_queue_reads_the_findings(tmp_path, monkeypatch):
    from research import residual_queue as rq
    doc = {"residual": {"findings": [{"axis": "hour", "bucket": 9, "n": 40,
                                      "mean_residual_r": 0.7, "t": 4.1}]},
           "counterfactual_policy": {"gates": {"gates": {"regime_veto": {"relaxed": {
               "n": 25, "sum_r": 27.5, "verdict": "RELAXING_WOULD_HAVE_EARNED"}}}}}}
    p = tmp_path / "RESIDUAL_SEARCH.json"
    p.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(rq, "RESIDUAL_SEARCH", p)
    items = rq._residual_search()
    keys = {i["key"] for i in items}
    assert "residual_search:hour=9" in keys and "gate_relaxed:regime_veto" in keys


# ------------------------------------------------------------------------------ wiring ---
@pytest.mark.parametrize("leg", ["specialist_cell", "residual_search"])
def test_both_organs_are_hourly_legs_with_a_budget_and_a_layer(leg):
    from libs.research.layers import LEG_LAYER
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert f'_costed("{leg}"' in src
    assert f'"{leg}": ' in src
    from research import hourly_cycle as hc
    assert leg in hc.LEG_BUDGET_SEC
    assert leg in LEG_LAYER


# ------------------------------------------------------------------ culture provenance ---
KEYS = ("source_culture", "participant_structure", "failure_mode_hypothesis")
STRUCTURES = {"retail_heavy", "institutional", "tax_driven", "policy_driven",
              "settlement_constrained", "physical_flow", "broker_specific", "mixed",
              "UNMEASURED"}


def test_every_specialist_cell_carries_culture_provenance():
    from research import specialist_cell as sc
    cells = sc.plan({"fx": ["USDJPY"], "indices": ["JPN225", "US500"],
                     "softs": ["COFROB", "CORN"], "metals": ["XAUUSD"]})
    assert cells
    for c in cells:
        assert all(c.get(k) for k in KEYS), c
        assert c["participant_structure"] in STRUCTURES
    tags = {c["source_culture"] for c in cells}
    assert {"JP", "VN", "US", "GLOBAL"} <= tags


def test_donated_rows_carry_culture_provenance(tmp_path, monkeypatch):
    from research import proposer_common as pc
    from research import residual_search as rs
    from research import specialist_cell as sc
    monkeypatch.setattr(sc, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(sc, "_meta", lambda: {})
    monkeypatch.setattr(sc, "measure", lambda s, f, p, m: {"built": True, "signal_days": 99,
                                                            "trade_days_lb": 99})
    got: list[list[dict]] = []
    monkeypatch.setattr(pc, "donate", lambda src, rows, n: got.append(rows) or tmp_path / "d")
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(got[-1])})
    sc.seed(budget_s=60, symbols_by_class={"indices": ["JPN225"]})
    assert got and all(all(r.get(k) for k in KEYS) for r in got[0])
    cultures = {r["source_culture"] for r in got[0]}
    assert "JP" in cultures and cultures <= {"JP", "GLOBAL"}, cultures
    assert all(rs.CULTURE.get(k) for k in KEYS)
    assert rs.CULTURE["source_culture"] == "GLOBAL"
