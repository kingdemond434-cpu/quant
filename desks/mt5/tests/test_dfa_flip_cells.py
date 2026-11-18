"""Hurst/DFA regime-flip cells (C row 120): the state module, the hourly leg, and the conditioner.

THE MONEY-PATH PROMISE IS THE FIRST THING PINNED. `family_regime_transition` is in the box's
import closure, so adding `dfa_gate` must leave every existing cell exactly as it was. Two proofs:
the ungated function body is the pre-edit body character for character once the three additive
pieces are removed, and a fixed fixture's signals digest to the value the pre-edit file produced
(measured against the base file, with the vector path both on and off).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import family_regime_transition as frt  # noqa: E402

from libs.regime import dfa_flip  # noqa: E402

FAM = frt.family_regime_transition
WINDOW, REFIT = 60, 30

#: sha256 of `family_regime_transition`'s source on the base (684a3d133f), before this change.
BASE_BODY_SHA = "efb1a0916f36907023fee2fc139f29a6bc8bc7f4f3d0ac06cc720077dc9afee7"
#: The only text this change adds inside the function.
ADDED = (
    '    dfa_gate: str = "off",\n'
    "    dfa_fresh_days: int = 5,\n",
    "\n"
    '    `dfa_gate` (default "off": the cell is exactly the unconditioned family) keeps only the\n'
    "    signals entered within `dfa_fresh_days` after a Hurst/DFA regime flip -- see "
    "`_dfa_condition`.\n",
    '    if dfa_gate != "off":\n'
    "        return _dfa_condition(df, family_regime_transition(\n"
    "            df, window=window, refit_days=refit_days, horizon_days=horizon_days,\n"
    "            entry_p_leave=entry_p_leave, min_age=min_age, side_mode=side_mode, atr_n=atr_n,\n"
    "            stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars), dfa_gate, dfa_fresh_days)\n",
)


def _bars(days: int = 260, seed: int = 5) -> pd.DataFrame:
    """The fixture `test_regime_transition_family.py` uses: alternating calm/volatile stretches."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=days * 24, freq="h", tz="UTC")
    scale = np.where((np.arange(idx.size) // (24 * 40)) % 2 == 0, 0.0004, 0.0025)
    px = np.exp(np.cumsum(rng.normal(scale=scale))) * 1800
    return pd.DataFrame({"open": px, "high": px * 1.002, "low": px * 0.998, "close": px},
                        index=idx)


def _digest(sigs) -> str:
    rows = [(pd.Timestamp(s.time).isoformat(), int(s.side), round(float(s.stop), 6),
             round(float(s.target), 6), int(s.ttl_bars), s.tag, s.trigger, s.wait_bars)
            for s in sigs]
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()


# ------------------------------------------------------------------------------------------
# Existing cells are byte-identical
# ------------------------------------------------------------------------------------------

def test_the_ungated_body_is_the_pre_edit_body_character_for_character():
    src = inspect.getsource(FAM).replace("\r\n", "\n")
    for piece in ADDED:
        assert src.count(piece) == 1, f"additive piece changed or missing:\n{piece}"
        src = src.replace(piece, "")
    assert hashlib.sha256(src.encode()).hexdigest() == BASE_BODY_SHA


def _base_signals_digest(monkeypatch, vec: str, side: str) -> str:
    monkeypatch.setenv("MT5_VECTOR_FAMILIES", vec)
    return _digest(FAM(_bars(), window=WINDOW, refit_days=REFIT, entry_p_leave=0.15, min_age=3,
                       side_mode=side))


@pytest.mark.parametrize("vec", ["1", "0"])
def test_default_and_explicit_off_cells_emit_identical_signals(monkeypatch, vec):
    monkeypatch.setenv("MT5_VECTOR_FAMILIES", vec)
    kw = {"window": WINDOW, "refit_days": REFIT, "entry_p_leave": 0.15, "min_age": 3}
    default = FAM(_bars(), **kw)
    off = FAM(_bars(), dfa_gate="off", dfa_fresh_days=99, **kw)
    assert default and repr(default) == repr(off)


#: Digests of this fixture's signals from the PRE-EDIT family file (684a3d133f), measured with
#: the vector path on and off -- identical in both, and identical from the edited file.
BASE_DIGEST = {
    "exhaustion": "10e56a31cfc0b49ecdd2bca1d6e27008fd0e0361657888cd4b5c1f5eceb46457",
    "expansion": "071596d9eacfc2470e347665bb530c87cfc65e5e6023ed1395024930e4dbfb68",
}


@pytest.mark.parametrize("vec", ["1", "0"])
@pytest.mark.parametrize("side", ["exhaustion", "expansion"])
def test_existing_cells_emit_the_pre_edit_signals(monkeypatch, vec, side):
    assert _base_signals_digest(monkeypatch, vec, side) == BASE_DIGEST[side]


# ------------------------------------------------------------------------------------------
# The DFA estimator
# ------------------------------------------------------------------------------------------

def test_white_noise_reads_near_one_half():
    rng = np.random.default_rng(0)
    vals = [dfa_flip.dfa_exponent(rng.normal(size=2000), (4, 8, 16, 32, 64)) for _ in range(5)]
    assert 0.42 < float(np.mean(vals)) < 0.58


def test_persistent_returns_read_trending_and_antipersistent_read_reverting():
    rng = np.random.default_rng(1)
    e = rng.normal(size=3000)
    ar = np.zeros_like(e)
    for t in range(1, e.size):
        ar[t] = 0.6 * ar[t - 1] + e[t]
    assert dfa_flip.dfa_exponent(ar[-120:]) > 0.6
    assert dfa_flip.dfa_exponent(np.diff(e)[-120:]) < 0.4


def test_too_little_or_flat_input_is_nan_never_a_number():
    assert np.isnan(dfa_flip.dfa_exponent(np.zeros(200)))
    assert np.isnan(dfa_flip.dfa_exponent(np.ones(8)))


# ------------------------------------------------------------------------------------------
# Hysteresis and flips
# ------------------------------------------------------------------------------------------

def test_flips_need_the_band_crossed_and_the_first_setting_is_not_a_flip():
    days = pd.date_range("2024-01-01", periods=9, freq="D").date
    alpha = pd.Series([np.nan, 0.60, 0.52, 0.48, 0.51, 0.44, 0.49, 0.56, 0.47], index=days)
    ev = dfa_flip.flip_events(alpha)
    assert [e["direction"] for e in ev] == [dfa_flip.TO_REVERTING, dfa_flip.TO_TRENDING]
    assert [e["day"] for e in ev] == [str(days[5]), str(days[7])]
    states = dfa_flip.state_path(alpha)
    assert states.iloc[0] is None and states.iloc[4] == dfa_flip.TRENDING


def test_a_band_that_does_not_straddle_one_half_is_refused():
    with pytest.raises(ValueError):
        dfa_flip.state_path(pd.Series([0.5]), upper=0.45, lower=0.40)


def test_values_use_closed_days_only_and_carry_their_last_bar_stamp():
    d = _bars(400)
    daily, _ = dfa_flip.flip_events_from_bars(d)
    tampered = d.copy()
    cut = d.index[300 * 24]
    tampered.loc[tampered.index >= cut, "close"] *= np.linspace(1, 3, int((d.index >= cut).sum()))
    after, _ = dfa_flip.flip_events_from_bars(tampered)
    before_cut = daily.index < cut.date()
    pd.testing.assert_series_equal(daily["dfa_alpha"][before_cut], after["dfa_alpha"][before_cut])
    assert (pd.to_datetime(daily["asof"]).dt.hour == 23).all()
    dropped, _ = dfa_flip.flip_events_from_bars(d, drop_last=True)
    assert len(dropped) == len(daily) - 1


# ------------------------------------------------------------------------------------------
# The conditioner
# ------------------------------------------------------------------------------------------

def _gated(gate: str, fresh: int) -> tuple[list, list, list]:
    kw = {"window": WINDOW, "refit_days": REFIT, "entry_p_leave": 0.15, "min_age": 3}
    d = _bars(400)
    base = FAM(d, **kw)
    gated = FAM(d, dfa_gate=gate, dfa_fresh_days=fresh, **kw)
    _, events = dfa_flip.flip_events_from_bars(d)
    return base, gated, events


def test_the_conditioner_only_removes_signals_and_never_alters_one():
    base, gated, events = _gated("any", 60)
    assert events, "fixture must contain flips for the gate to be exercised"
    assert gated, "a 60-day freshness window over this fixture must keep some signals"
    base_by_time = {s.time: repr(s) for s in base}
    assert all(base_by_time.get(s.time) == repr(s) for s in gated)
    assert len(gated) <= len(base)


def test_every_kept_entry_is_strictly_after_a_flip_stamp_within_the_window():
    for gate in ("any", "to_trending", "to_reverting"):
        _, gated, events = _gated(gate, 30)
        stamps = [pd.Timestamp(e["asof"]) for e in events
                  if gate == "any" or e["direction"] == gate]
        for s in gated:
            t = pd.Timestamp(s.time)
            assert any(st < t <= st + pd.Timedelta(days=30) for st in stamps)


def test_direction_gates_partition_the_any_gate():
    _, anyg, _ = _gated("any", 30)
    _, up, _ = _gated("to_trending", 30)
    _, down, _ = _gated("to_reverting", 30)
    assert {s.time for s in up} | {s.time for s in down} == {s.time for s in anyg}


def test_an_unknown_gate_refuses_rather_than_falling_back():
    _, gated, _ = _gated("sideways", 30)
    assert gated == []
    _, zero, _ = _gated("any", 0)
    assert zero == []


# ------------------------------------------------------------------------------------------
# The hourly leg
# ------------------------------------------------------------------------------------------

def test_the_leg_writes_its_report_from_held_bars(tmp_path, monkeypatch):
    from research import dfa_flip_state as leg

    uni = tmp_path / "universe"
    uni.mkdir()
    _bars(400).to_parquet(uni / "XAUUSD_H1.parquet")
    _bars(50, seed=2).to_parquet(uni / "EURUSD_H1.parquet")
    _bars(400, seed=3).to_parquet(uni / "AAPL_H1.parquet")
    monkeypatch.setattr(leg, "_may_hypothesise", lambda s: s != "AAPL")
    out = tmp_path / "DFA_FLIP_STATE.json"
    rep = leg.run(uni=uni, report=out)
    disk = json.loads(out.read_text("utf-8"))
    assert disk["symbols_measured"] == rep["symbols_measured"] == 1
    assert disk["symbols_unmeasured"] == ["EURUSD"]
    assert "AAPL" in disk["skipped"]
    row = disk["symbols"]["XAUUSD"]
    assert row["status"] == "MEASURED" and row["state"] in {
        dfa_flip.TRENDING, dfa_flip.MEAN_REVERTING, "inside_band_unset"}
    assert row["closed_days"] == 399     # the newest (forming) day is dropped


def test_the_leg_is_wired_hourly_and_layered():
    from libs.research.layers import LEG_LAYER

    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"research/dfa_flip_state.py"' in src and '"dfa_flip_state": dfs' in src
    assert LEG_LAYER["dfa_flip_state"] == "information"


# ------------------------------------------------------------------------------------------
# The grids: the gated variants are enumerated and charged as trials (audit of #1345, MF1)
# ------------------------------------------------------------------------------------------

GATED = {"to_trending", "to_reverting", "any"}


def test_the_breadth_grid_carries_off_plus_the_three_gated_variants_at_one_freshness():
    from research import breadth_sweep as bs

    grid = bs.READY["regime_transition"]["grid"]
    assert grid[0] == {}, "off must be the bare cell so it dedupes against the cells held"
    gated = grid[1:]
    assert {g["dfa_gate"] for g in gated} == GATED == set(frt.DFA_GATES)
    assert {g["dfa_fresh_days"] for g in gated} == {5}
    assert len(grid) == 4
    # Listed in READY, so default_families no longer mints a second, identical bare cell.
    ok, _ = bs.default_families()
    assert "regime_transition" not in ok


def test_breadth_cells_include_the_gated_variants_and_the_census_counts_each(monkeypatch):
    from libs.research.trial_ledger import census, trial_from_record
    from research import breadth_sweep as bs

    monkeypatch.setattr(bs, "_with_bars", lambda: ["EURUSD", "XAUUSD"])
    monkeypatch.setattr(bs, "_charts_for", lambda sym: ["H1"])
    monkeypatch.setattr(bs, "_session_slots",
                        lambda fam, base, tf, sym: [(dict(base), None)])
    monkeypatch.setattr(bs, "_testable", lambda fam, p: True)
    monkeypatch.setattr(bs, "order_by_failure_memory", lambda rows: (rows, {}))
    monkeypatch.setattr(bs, "_orthogonal_key", lambda: (lambda r: (r["symbol"], str(r["params"]))))
    rows = bs.cells(only="regime_transition")
    assert len(rows) == 2 * 4
    for sym in ("EURUSD", "XAUUSD"):
        gates = {r["params"].get("dfa_gate", "off") for r in rows if r["symbol"] == sym}
        assert gates == GATED | {"off"}
    assert sum(1 for r in rows if "dfa_gate" in r["params"]) == 2 * 3
    doc = census(trial_from_record(r, index=i) for i, r in enumerate(rows)).to_dict()
    assert doc["n_raw"] == len(rows) == 8      # every gated cell is a charged trial


def test_the_gauntlet_proposer_tests_and_charges_every_gated_variant(tmp_path, monkeypatch):
    from research import transition_alpha as ta

    variants = ta._variants(60, 30, 1, 0.15, 3, "exhaustion")
    assert len(variants) == 4
    assert "dfa_gate" not in variants[0] and "dfa_fresh_days" not in variants[0]
    assert {v["dfa_gate"] for v in variants[1:]} == GATED
    assert {v["dfa_fresh_days"] for v in variants[1:]} == {5}

    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "XAUUSD_H1.parquet").write_bytes(b"")
    pc = ta.pc
    monkeypatch.setattr(pc, "UNI", uni)
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "bars", lambda sym: _bars(260))
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 1e-4)
    monkeypatch.setattr(pc, "artifact_hours", lambda d: {})
    monkeypatch.setattr(pc, "screen", lambda d, sig, cost, unf: {"n_signals": len(sig)})
    monkeypatch.setattr(pc, "deflate", lambda rows: rows)
    monkeypatch.setattr(pc, "best_per_cell", lambda rows: [])
    charged: list[int] = []
    monkeypatch.setattr(pc, "donate", lambda src, cands, n: charged.append(n))
    monkeypatch.setattr(ta, "REPORT", tmp_path / "transition_alpha.json")
    rep = ta.run(symbols=["XAUUSD"], window=WINDOW, refit_days=REFIT)
    per_side_cell = len(ta.HORIZON_DAYS) * len(ta.ENTRY_P) * len(ta.MIN_AGE)
    assert rep["tests_run"] == per_side_cell * len(ta.SIDES) * 4
    cells = {r["cell"] for r in rep["all"]}
    for side in ta.SIDES:
        assert f"XAUUSD.regime_transition.{side}" in cells
        for g in GATED:
            assert f"XAUUSD.regime_transition.{side}.dfa_{g}" in cells
