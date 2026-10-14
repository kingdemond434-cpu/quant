"""THE STATE-GATED WRAPPERS on synthetic bars: the Kuramoto order parameter, the permutation
entropy, their point-in-time reads, the mechanism-fixed gate direction and the proposer's grid.

The panel loader and the base-family lookup are monkeypatched, so nothing here reads the desk's
own bar store or writes its reports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_state_gates as fsg  # noqa: E402
from mt5desk.families import Signal  # noqa: E402

T0 = pd.Timestamp("2026-01-05 00:00", tz="UTC")
N_BARS = 600
PERIOD = 32.0


def _stamps(n: int = N_BARS) -> pd.DatetimeIndex:
    return pd.date_range(T0, periods=n, freq="h")


def _panel(thetas: np.ndarray, n: int = N_BARS) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    idx = _stamps(n)
    k = np.arange(n, dtype="float64")
    out = {}
    for j, th in enumerate(thetas):
        closes = np.exp(0.02 * np.sin(2 * np.pi * k / PERIOD + th) + 0.0001 * k)
        out[f"S{j:03d}"] = (idx.asi8.astype("int64"), closes.astype("float32"))
    return out


def _locked(n_sym: int = 20) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return _panel(np.full(n_sym, 0.7))


def _random(n_sym: int = 20, seed: int = 0) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return _panel(np.random.default_rng(seed).uniform(0, 2 * np.pi, n_sym))


def _bars(close: np.ndarray) -> pd.DataFrame:
    idx = _stamps(len(close))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "tick_volume": 1.0}, index=idx)


def _fake_base(times: list[pd.Timestamp]):
    def fn(d: pd.DataFrame, **_kw) -> list[Signal]:
        return [Signal(time=t, side=1, stop=0.9, target=1.2, ttl_bars=12, tag="fake")
                for t in times if t in d.index]
    return fn


# ------------------------------------------------------------------------- (a) Kuramoto R ----
def test_phase_locked_panel_reads_r_near_one() -> None:
    t = _stamps()[400]
    r = fsg.kuramoto_r(_locked(), t, window=128, min_symbols=12)
    assert r is not None and r > 0.99


def test_random_phase_panel_reads_r_near_one_over_root_n() -> None:
    n = 400
    t = _stamps()[400]
    rs = [fsg.kuramoto_r(_random(n, seed), t, window=128, min_symbols=12) for seed in range(12)]
    assert all(r is not None for r in rs)
    mean_r = float(np.mean([r for r in rs if r is not None]))
    assert 0.3 / np.sqrt(n) < mean_r < 2.0 / np.sqrt(n)


# ----------------------------------------------------------------------- (b) point in time ----
def test_truncating_after_t_leaves_r_and_entropy_unchanged() -> None:
    idx = _stamps()
    t = idx[350]
    full = _random(30, seed=3)
    cut = {s: (st[st <= t.value], cl[: int((st <= t.value).sum())]) for s, (st, cl) in
           full.items()}
    assert fsg.kuramoto_r(full, t) == pytest.approx(fsg.kuramoto_r(cut, t), abs=1e-12)

    close = pd.Series(np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.001, 3000))),
                      index=_stamps(3000))
    t2 = close.index[2500]
    z_full = fsg.entropy_z(close, order=4, window=168, z_window=600)
    z_cut = fsg.entropy_z(close.loc[:t2], order=4, window=168, z_window=600)
    assert np.isfinite(z_full.loc[t2])
    assert z_full.loc[t2] == pytest.approx(z_cut.loc[t2], abs=1e-12)
    h_full = fsg.permutation_entropy(close.to_numpy(), order=4, window=168)
    h_cut = fsg.permutation_entropy(close.loc[:t2].to_numpy(), order=4, window=168)
    assert h_full[2500] == pytest.approx(h_cut[2500], abs=1e-12)


# ---------------------------------------------------------------- (c) mechanism-fixed gate ----
@pytest.mark.parametrize(("base", "panel", "kept"), [
    ("trend_ma_cross", "locked", True), ("trend_ma_cross", "random", False),
    ("session_range_breakout", "locked", True),
    ("mean_reversion_rsi", "locked", False), ("mean_reversion_rsi", "random", True),
])
def test_gate_direction_is_fixed_by_the_bases_mechanism(monkeypatch, base, panel, kept) -> None:
    idx = _stamps()
    times = [idx[300], idx[400], idx[500]]
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    monkeypatch.setattr(fsg, "load_panel", _locked if panel == "locked" else
                        (lambda: _random(200, seed=5)))
    out = fsg.family_sync_gated(_bars(np.linspace(1.0, 1.1, N_BARS)), base_family=base,
                                window=128, r_threshold=0.5, min_symbols=12)
    assert [s.time for s in out] == (times if kept else [])


def test_any_other_mechanism_class_returns_nothing(monkeypatch) -> None:
    idx = _stamps()
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([idx[400]]))
    monkeypatch.setattr(fsg, "load_panel", _locked)
    bars = _bars(np.linspace(1.0, 1.1, N_BARS))
    assert fsg.mechanism_class("dow_effect") == "calendar"
    assert fsg.family_sync_gated(bars, base_family="dow_effect") == []
    assert fsg.family_sync_gated(bars, base_family="no_such_family") == []
    # The wrappers never wrap each other, nor alt_conditioned.
    for inner in ("sync_gated", "entropy_gated", "alt_conditioned"):
        assert fsg.family_entropy_gated(bars, base_family=inner) == []


def test_mechanism_classes_are_declared_for_every_base_and_wrapper() -> None:
    from research import alpha_genome as ag
    import state_gate_proposer as P
    for b in P.BASES:
        assert ag.MECHANISM_CLASS[b] in {"trend", "breakout", "reversion"}
    assert ag.MECHANISM_CLASS["sync_gated"] == ag.MECHANISM_CLASS["entropy_gated"] == "regime"


# --------------------------------------------------------------------- (d) entropy bounds ----
def test_monotone_series_has_entropy_near_zero_and_noise_near_one() -> None:
    mono = np.linspace(1.0, 2.0, 1000)
    h = fsg.permutation_entropy(mono, order=4, window=168)
    assert np.all(np.isnan(h[:170])) and np.nanmax(h) < 1e-9
    noise = np.random.default_rng(7).normal(size=5000)
    hn = fsg.permutation_entropy(noise, order=4, window=168)
    assert 0.93 < float(np.nanmean(hn)) <= 1.0


def test_entropy_gate_keeps_a_subset_in_low_entropy_windows(monkeypatch) -> None:
    rng = np.random.default_rng(11)
    n = 3000
    steps = rng.normal(0, 0.001, n)
    steps[2000:2300] = 0.0005           # a monotone, perfectly predictable stretch
    close = np.exp(np.cumsum(steps))
    idx = _stamps(n)
    times = [idx[1500], idx[2250], idx[2800]]
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base(times))
    out = fsg.family_entropy_gated(_bars(close), base_family="trend_ma_cross", z_window=600)
    assert [s.time for s in out] == [idx[2250]]


# ------------------------------------------------------------------------- (e) the proposer ----
def test_proposer_mints_one_cell_per_wrapper_base_symbol_and_charges_it(monkeypatch,
                                                                         tmp_path) -> None:
    import proposer_common
    import state_gate_proposer as P
    monkeypatch.setattr(P, "store_symbols", lambda: ["AAPL", "EURUSD", "XAUUSD"])
    monkeypatch.setattr(P, "allowed", lambda sym, fam: sym != "AAPL")
    grid, refused = P.build_grid(P.store_symbols())
    keys = [(c["family"], c["params"]["base_family"], c["symbol"]) for c in grid]
    assert len(keys) == len(set(keys))
    expect = sum(len(P.bases_for(w)) for w in P.WRAPPERS) * 2
    assert len(grid) == expect == 2 * 2 * len(P.BASES)
    assert refused == {w: len(P.bases_for(w)) for w in P.WRAPPERS}
    assert {c["chart"] for c in grid} == {"H1"}
    for c in grid:
        assert c["params"]["base_params"] == {} and c["params"]["timeframe"] == "H1"
        assert c["falsifier"]

    seen: dict = {}

    def fake_donate(source, candidates, tests_run):
        seen.update(source=source, n=len(candidates), tests_run=tests_run)
        return tmp_path / "contract.json"

    monkeypatch.setattr(proposer_common, "donate", fake_donate)
    monkeypatch.setattr(proposer_common, "donation_counts",
                        lambda: {"donated": seen.get("n", 0)})
    monkeypatch.setattr(P, "REPORT", tmp_path / "STATE_GATE_PROPOSER.json")
    monkeypatch.setattr(P, "CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(P, "MINT_ROWS_PER_PASS", 7)
    assert P.main(["--once"]) == 0
    assert seen == {"source": "state_gate_proposer", "n": 7, "tests_run": 7}
    import json
    rep = json.loads((tmp_path / "STATE_GATE_PROPOSER.json").read_text("utf-8"))
    assert rep["trials_charged"] == 7 and rep["grid_total"] == expect
    assert json.loads((tmp_path / "cursor.json").read_text("utf-8"))["at"] == 7


# ----------------------------------------------------------------- (f) too few panel members ----
def test_too_few_panel_symbols_drops_the_signal(monkeypatch) -> None:
    idx = _stamps()
    t = idx[400]
    assert fsg.kuramoto_r(_locked(5), t, min_symbols=12) is None
    # Enough members, but most lack a full window at t: still dropped.
    short = {**_locked(5), **{f"Y{j}": (st[-100:], cl[-100:]) for j, (st, cl) in
                              enumerate(_locked(10).values())}}
    assert fsg.kuramoto_r(short, t, window=128, min_symbols=12) is None
    monkeypatch.setattr(fsg, "get_family_func", lambda name: _fake_base([t]))
    monkeypatch.setattr(fsg, "load_panel", lambda: _locked(5))
    assert fsg.family_sync_gated(_bars(np.linspace(1.0, 1.1, N_BARS)),
                                 base_family="trend_ma_cross") == []


def test_families_are_registered_where_the_gauntlet_looks() -> None:
    from mt5desk.family_alt_series import _UNWRAPPABLE
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES
    from research.axis_registry import FAMILY_TABLE
    from research.orthogonal_sweep import NOT_SOURCED_HERE
    for fam in ("sync_gated", "entropy_gated"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_INPUTS and fam in FAMILY_TABLE
        assert fam in _UNWRAPPABLE and fam in NOT_SOURCED_HERE
