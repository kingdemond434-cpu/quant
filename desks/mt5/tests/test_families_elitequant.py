"""The five EliteQuant-map families: registered through the one door, causal, and seeded."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mt5desk import families_elitequant as eq
from mt5desk import families_orthogonal as fo


def _bars(n: int = 12_000, seed: int = 7, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    r = rng.standard_t(4, n) * 0.001 + drift
    close = 1.2 * np.exp(np.cumsum(r))
    open_ = np.concatenate(([close[0]], close[:-1]))
    wick = np.abs(rng.normal(0, 0.0006, n)) * close
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + wick,
                         "low": np.minimum(open_, close) - wick, "close": close,
                         "tick_volume": rng.integers(50, 500, n)}, index=idx)


def test_every_family_is_registered_price_only():
    for name, fn in eq.ELITEQUANT_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn
        assert fo.FAMILY_INPUTS[name][0] == "price only"
        assert set(eq.PARAM_GRID[name]) and set(eq.CULTURE[name]) == {
            "source_culture", "participant_structure", "crowding_prior",
            "failure_mode_hypothesis"}


@pytest.mark.parametrize("name", sorted(eq.ELITEQUANT_FAMILIES))
def test_family_fires_on_random_walk_and_signals_are_well_formed(name):
    d = _bars()
    sigs = eq.ELITEQUANT_FAMILIES[name](d)
    assert sigs, f"{name} never fired on 12,000 bars"
    for s in sigs:
        assert s.side in (1, -1) and s.ttl_bars > 0 and s.time in d.index
        assert (s.target - s.stop) * s.side > 0


@pytest.mark.parametrize("name", sorted(eq.ELITEQUANT_FAMILIES))
def test_no_lookahead_future_bars_do_not_change_past_signals(name):
    d = _bars()
    cut = 9_000
    full = {(s.time, s.side) for s in eq.ELITEQUANT_FAMILIES[name](d)
            if s.time < d.index[cut - 200]}
    part = {(s.time, s.side) for s in eq.ELITEQUANT_FAMILIES[name](d.iloc[:cut])
            if s.time < d.index[cut - 200]}
    assert full == part


def test_ffd_is_stationary_where_the_log_price_is_not():
    rng = np.random.default_rng(3)
    x = np.cumsum(rng.normal(0, 1, 5000))
    ffd = eq.frac_diff(x, 0.5)
    tail = ffd[~np.isnan(ffd)]
    # A random walk's variance grows with the window; the FFD series' does not.
    assert np.var(x[2500:]) > 3 * np.var(x[:1250])
    assert np.var(tail[len(tail) // 2:]) < 3 * np.var(tail[: len(tail) // 4])
    assert eq.ffd_weights(1.0)[:2].tolist() == [1.0, -1.0]


def test_corwin_schultz_recovers_a_known_spread():
    rng = np.random.default_rng(11)
    n, s = 20_000, 0.002
    mid = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    hi = mid * np.exp(np.abs(rng.normal(0, 0.001, n))) * (1 + s / 2)
    lo = mid * np.exp(-np.abs(rng.normal(0, 0.001, n))) * (1 - s / 2)
    est = np.nanmean(eq.corwin_schultz_spread(hi, lo))
    assert 0.3 * s < est < 3 * s


def test_bsadf_separates_an_explosive_root_from_a_random_walk():
    rng = np.random.default_rng(5)
    rw = np.cumsum(rng.normal(0, 1, 800))
    boom = rw.copy()
    boom[599] = abs(boom[599]) + 10.0
    for t in range(600, 800):
        boom[t] = boom[t - 1] * 1.02 + rng.normal(0, 1)
    assert np.nanmax(eq.bsadf(boom, window=240)[650:]) > np.nanmax(eq.bsadf(rw, window=240)[650:])
    assert np.nanmax(eq.bsadf(boom, window=240)[650:]) > 1.5


def test_seeder_is_wired_as_an_hourly_leg():
    from pathlib import Path

    from libs.research.layers import LEG_LAYER
    text = (Path(__file__).resolve().parents[1] / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("elitequant_breadth"' in text
    assert LEG_LAYER["elitequant_breadth"] == "prediction"
    from research import hourly_cycle as hc
    assert hc.department_of("elitequant_breadth") == "discovery"


def test_seeder_donates_cost_clearing_cells_with_culture(monkeypatch, tmp_path):
    from research import elitequant_breadth as eb
    from research import proposer_common as pc

    d = _bars(9_000)
    monkeypatch.setattr(eb, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(eb, "symbols", lambda: ["EURUSD"])
    monkeypatch.setattr(pc, "universe_meta", lambda: {"EURUSD": {}})
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(pc, "cost_frac", lambda *a: 1e-5)
    monkeypatch.setattr(pc, "screen", lambda d, sigs, cost: {
        "t_gross": 2.5 if sigs else 0.0, "n_independent": len(sigs), "clears_cost": True})
    got: dict = {}

    def _donate(source, rows, tests_run):
        got["rows"] = rows
        return tmp_path / "donated.json"
    monkeypatch.setattr(pc, "donate", _donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(got.get("rows", []))})
    rep = eb.seed(budget_s=120)
    assert rep["status"] == "OK" and rep["donation"]["status"] == "DONATED"
    rows = got["rows"]
    assert rows and {r["family"] for r in rows} <= set(eq.ELITEQUANT_FAMILIES)
    assert all(r["culture_derivation"]["source_culture"] == "declared" for r in rows)
    # a second pass the same day donates nothing new
    got.clear()
    assert eb.seed(budget_s=120)["candidates_this_pass"] == 0
