"""The learned miners (graph propagation, attention): recovery, falsification, PIT, the door.

What each test pins, in the order a skeptic would ask for it:

  * a PLANTED lead-lag graph is recovered: followers' next-day returns are forecast from their
    leaders', and the graph model beats ridge on the followers' own lags by a wide margin;
  * PURE NOISE yields no significant IC, and the full miner path (family signals, screen,
    self-deflation at the attempted count) proposes nothing on it;
  * POINT IN TIME: perturbing every return after row t0 leaves every prediction at or before t0
    bit-identical, for both models and through the family's own signals;
  * THE DOOR: an emitted cell compiles as EXACT_RECIPE, passes the economic prior, carries a
    complete pre-registration card and a PIT stamp, carries the schema's mechanism fields, and
    rebuilds into signals from its params exactly as the gauntlet would call it;
  * THE AXIS: the published forecast binds as a causal field through `alpha_dsl`.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_learned_propagation as FLP  # noqa: E402

from libs.models import learned_propagation as LP  # noqa: E402

WF = {"min_train": 300, "refit_every": 50, "window": 600}

#: Contract terms for the synthetic instruments: EURUSD's, so `Costs.from_symbol` prices them.
META_ROW = {"contract_size": 100000.0, "tick_size": 1e-05, "tick_value": 0.8632298608473467,
            "min_volume": 0.01, "volume_step": 0.01, "median_spread_pts": 12.0}


def _panel(ret: np.ndarray, start: str = "2019-01-01") -> LP.Panel:
    dates = pd.bdate_range(start, periods=ret.shape[0], tz="UTC")
    syms = [f"S{j:02d}" for j in range(ret.shape[1])]
    return LP.Panel(dates, syms, ret, np.full(ret.shape, 5e-5))


def _lead_lag_returns(t_n: int = 1100, seed: int = 3, beta: float = 0.5) -> np.ndarray:
    """Four leaders (iid) and four followers whose NEXT return loads on one leader's today."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, (t_n, 8))
    for f, lead in zip(range(4, 8), (0, 1, 2, 3), strict=True):
        r[1:, f] = beta * r[:-1, lead] + np.sqrt(1 - beta ** 2) * r[1:, f]
    return r


def _h1_bars(daily: np.ndarray, names: list[str], start: str = "2019-01-01",
             px0: float = 1.1) -> dict[str, pd.DataFrame]:
    """Hourly bars whose broker-date closes reproduce `daily` exactly (one weekday per row)."""
    days = pd.bdate_range(start, periods=daily.shape[0], tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in days for h in range(24)])
    out: dict[str, pd.DataFrame] = {}
    for j, s in enumerate(names):
        hourly = np.repeat(daily[:, j] / 24.0, 24)
        close = px0 * np.exp(np.cumsum(hourly))
        opn = np.concatenate([[px0], close[:-1]])
        out[s] = pd.DataFrame({"open": opn, "high": np.maximum(opn, close) * (1 + 1e-4),
                               "low": np.minimum(opn, close) * (1 - 1e-4), "close": close,
                               "tick_volume": 100, "spread": 10, "real_volume": 0}, index=idx)
    return out


# ============================================================================ recovery
def test_gnn_recovers_a_planted_lead_lag_graph() -> None:
    panel = _panel(_lead_lag_returns())
    d = LP.design(panel)
    gnn = LP.predictions(d, "gnn", {"adjacency": "lead_lag", "layers": 1}, **WF)
    ridge = LP.predictions(d, "ridge", {}, **WF)
    g = LP.evaluate(gnn, panel, d, start=WF["min_train"])
    b = LP.evaluate(ridge, panel, d, start=WF["min_train"])
    per = LP.per_symbol_ic(gnn, panel, start=WF["min_train"])
    followers = [per[f"S{j:02d}"]["ic"] for j in range(4, 8)]
    assert all(ic is not None and ic > 0.3 for ic in followers), followers
    assert g["ic_mean"] is not None and g["ic_mean"] > 0.1 and g["ic_t"] > 5, g
    assert (b["ic_mean"] or 0.0) < g["ic_mean"] - 0.05, (b, g)
    assert g["ls_sharpe_gross"] is not None and g["ls_sharpe_gross"] > 2.0, g


def test_the_learned_adjacency_points_from_leader_to_follower() -> None:
    panel = _panel(_lead_lag_returns())
    d = LP.design(panel)
    a = LP.adjacency(d.x[:600, :, 0], d.y[:600], "lead_lag", top_k=3)
    for f, lead in zip(range(4, 8), range(4), strict=True):
        assert int(np.argmax(np.abs(a[f]))) == lead
        assert a[f, lead] > 0.3


# ======================================================================== falsification
@pytest.mark.parametrize("model,config", [("gnn", {"adjacency": "lead_lag", "layers": 1}),
                                          ("gnn", {"adjacency": "corr", "layers": 2}),
                                          ("attention", {"heads": 1, "lookback": 10})])
def test_pure_noise_carries_no_significant_ic(model: str, config: dict) -> None:
    rng = np.random.default_rng(17)
    panel = _panel(rng.normal(0, 0.01, (1100, 8)))
    d = LP.design(panel)
    ev = LP.evaluate(LP.predictions(d, model, config, **WF), panel, d, start=WF["min_train"])
    assert ev["ic_t"] is not None and abs(ev["ic_t"]) < 3.0, ev
    assert abs(ev["ic_mean"]) < 0.03, ev


def test_the_miner_proposes_nothing_on_noise_and_charges_every_attempt() -> None:
    import learned_miners as LM

    rng = np.random.default_rng(5)
    names = [f"N{j:02d}" for j in range(6)]
    bars = _h1_bars(rng.normal(0, 0.006, (760, 6)), names)
    meta = {s: dict(META_ROW) for s in names}
    res = LM.mine("gnn", bars, meta, deadline=float("inf"),
                  grid=[{"adjacency": "lead_lag", "layers": 1}], entry_z=(1.0,))
    assert res["tests_attempted"] == 6              # 1 config x 6 symbols x 1 threshold
    assert res["proposals"] == []
    for r in res["rows"]:
        assert r["n_tests_sweep"] == res["tests_attempted"]
        assert r["proposed"] is False
    assert res["trial_census"]["n_raw"] == 6


# ============================================================================== PIT
@pytest.mark.parametrize("model,config", [("gnn", {"adjacency": "lead_lag", "layers": 2}),
                                          ("attention", {"heads": 2, "lookback": 10})])
def test_perturbing_the_future_never_changes_a_past_prediction(model: str, config: dict) -> None:
    ret = _lead_lag_returns(t_n=700)
    t0 = 520
    fut = ret.copy()
    fut[t0 + 1:] = np.random.default_rng(99).normal(0, 0.05, fut[t0 + 1:].shape)
    p1 = LP.predictions(LP.design(_panel(ret)), model, config, **WF)
    p2 = LP.predictions(LP.design(_panel(fut)), model, config, **WF)
    assert np.isfinite(p1[WF["min_train"]:t0 + 1]).all()
    np.testing.assert_array_equal(p1[:t0 + 1], p2[:t0 + 1])
    assert not np.allclose(p1[t0 + 1:], p2[t0 + 1:])        # the future did change


def test_the_family_signals_before_a_perturbation_are_unchanged() -> None:
    names = [f"S{j:02d}" for j in range(8)]
    ret = _lead_lag_returns(t_n=640)
    cut_row = 600
    fut = ret.copy()
    fut[cut_row:] = np.random.default_rng(7).normal(0, 0.03, fut[cut_row:].shape)
    a, b = _h1_bars(ret, names), _h1_bars(fut, names)
    cut = pd.bdate_range("2019-01-01", periods=640, tz="UTC")[cut_row]
    kw = {"symbol": "S05", "peer_symbols": names, "adjacency": "lead_lag", "layers": 1,
          "entry_z": 0.5}
    sa = FLP.family_gnn_propagation(a["S05"], peers=a, **kw)
    sb = FLP.family_gnn_propagation(b["S05"], peers=b, **kw)
    before_a = [(s.time, s.side, s.stop, s.target) for s in sa if s.time < cut]
    before_b = [(s.time, s.side, s.stop, s.target) for s in sb if s.time < cut]
    assert len(before_a) > 20
    assert before_a == before_b
    # And every signal acts AFTER the close its forecast used: the first bar at/after 02:00.
    assert all(s.time.hour == 2 for s in sa)


# ============================================================================ the door
def _candidate() -> dict:
    import learned_miners as LM

    row = {"symbol": "EURUSD", "config": dict(LP.GNN_GRID[0]), "entry_z": 1.0,
           "n_independent": 120, "gross_per_trade": 0.0004, "net_per_trade": 0.0002,
           "cost_frac": 0.0002, "t_gross": 3.1, "t_deflated_sweep": 0.5, "n_tests_sweep": 192,
           "oos_ic_symbol": 0.02, "oos_ic_t_symbol": 1.1}
    return LM.make_candidate("gnn", row, panel=list(LM.PANEL), tests_run=192, n_effective=2.4)


def test_an_emitted_cell_passes_the_compiler_prior_prereg_and_stamp() -> None:
    from research.frontier_identity import economic_prior
    from research.miner_candidate_compiler import compile_row

    from libs.data.pit import is_stamped, stamp
    from libs.research.preregistration import from_candidate, validate

    c = _candidate()
    compiled, disposition = compile_row("gnn_miner", c, {"EURUSD"})
    assert disposition == "EXACT_RECIPE"
    assert len(compiled) == 1                      # the H1 pin: no intraday fan-out of a daily call
    cell = compiled[0]
    assert cell["family"] == "gnn_propagation" and cell["params"] == c["params"]
    prior = economic_prior(cell)
    assert prior["passed"] and len(cell["mechanism_note"]) >= 12
    assert validate(from_candidate(c)) == []
    assert is_stamped(stamp(c, "gnn_miner"))


def test_an_emitted_cell_carries_the_schema_fields() -> None:
    c = _candidate()
    assert c["family"] == "gnn_propagation" and c["mechanism_event"] == "cross_market_lead"
    assert c["payer"] and c["falsifier"] and c["mechanism"] and c["constraint"]
    assert c["source_culture"] == "global/model"
    assert c["participant_structure"] in {"retail_heavy", "institutional", "tax_driven",
                                          "policy_driven", "physical_flow", "broker_specific",
                                          "settlement_constrained"}
    assert isinstance(c["failure_mode_hypothesis"], str) and c["failure_mode_hypothesis"]
    assert c["crowding_prior"] in {"low", "medium", "high"}
    assert c["tests_run"] == 192 and c["effective_trials"] == 2.4
    assert c["params"]["timeframe"] == "H1" and c["params"]["hold_bars"] == 20
    assert c["evidence"]["tests_attempted"] == 192


def test_the_cell_rebuilds_from_its_params_as_the_gauntlet_calls_it() -> None:
    """`build_cell` pops `timeframe`/`session`, tries fn(h1, side=1, **p), and on TypeError
    retries fn(h1, **p). The family must survive that and resolve its own peers."""
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    from mt5desk.family_inputs import strip_identity_keys

    names = [f"S{j:02d}" for j in range(8)]
    bars = _h1_bars(_lead_lag_returns(t_n=640), names)
    params = {"symbol": "S06", "peer_symbols": names, "adjacency": "lead_lag", "layers": 1,
              "entry_z": 1.0, "norm": 120, "hold_bars": 20, "signal_hour": 2, "timeframe": "H1"}
    fn = ORTHOGONAL_FAMILIES["gnn_propagation"]
    call = strip_identity_keys("gnn_propagation", params)
    with pytest.raises(TypeError):
        fn(bars["S06"], side=1, **call)
    FLP._PRED_CACHE.clear()
    orig = FLP.load_peer
    try:
        FLP.load_peer = lambda s: bars.get(s)      # the disk read, served from memory
        sigs = fn(bars["S06"], **call)
    finally:
        FLP.load_peer = orig
    assert len(sigs) > 10


def test_the_families_are_registered_and_kept_out_of_default_sweeps() -> None:
    import axis_registry as AR
    import orthogonal_sweep as osw
    from mt5desk.families_orthogonal import (
        FAMILY_INPUTS,
        FAMILY_TIMEFRAMES,
        ORTHOGONAL_FAMILIES,
        timeframe_refusal,
    )

    for fam in ("gnn_propagation", "attention_ts"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS
        assert fam in osw.NOT_SOURCED_HERE and fam in AR.NOT_A_FAMILY
        assert FAMILY_TIMEFRAMES[fam][0] == ("H1", "H4", "D1")
        assert timeframe_refusal(fam, "M5") is not None
        sig = inspect.signature(ORTHOGONAL_FAMILIES[fam])
        for req in ("symbol", "peer_symbols"):
            assert sig.parameters[req].default is inspect.Parameter.empty
    assert AR.classify_family("gnn_propagation")[0] == "cross_market_lead"
    assert AR.classify_family("attention_ts")[0] == "inventory_shock"


# ============================================================================ the axis door
def test_the_forecast_axis_binds_as_a_causal_field(tmp_path: Path) -> None:
    import axis_ingest
    import learned_miners as LM

    from libs.research import alpha_dsl

    names = [f"S{j:02d}" for j in range(8)]
    bars = _h1_bars(_lead_lag_returns(t_n=640), names)
    doc = LM.forecast_axis("gnn", bars)
    assert doc["n_rows"] > 500 and doc["id"] == "gnn_forecast"
    for r in doc["rows"][:50]:
        assert pd.Timestamp(r["knowable_at"]) > pd.Timestamp(r["as_of"], tz="UTC") + \
            pd.Timedelta(hours=24)
    out = axis_ingest.publish(doc["id"], doc, tmp_path, report=None)
    assert out.exists()
    fields = [f for f in alpha_dsl.axis_fields(tmp_path) if f.name == "gnn_forecast.forecast"]
    assert {f.symbol for f in fields} == set(names)
    f = next(x for x in fields if x.symbol == "S05")
    assert f.causal() and f.availability == "knowable_at"
    idx = bars["S05"].index
    s = alpha_dsl.FieldCatalogue(tmp_path).series(f, idx)
    assert s is not None
    first = pd.Timestamp(min(r["knowable_at"] for r in doc["rows"] if r["symbol"] == "S05"))
    assert s[idx < first].isna().all() and s[idx >= first].notna().any()

    intel = LM.allocation_intel({"gnn": doc}, contract=tmp_path / "absent.json")
    assert intel["models"]["gnn"]["allocation_eligible"] is False
    assert intel["models"]["gnn"]["contract_verdict"] == "UNMEASURED"
    assert set(intel["instruments"]) == set(names)
