"""THE WORLD MODEL, BUILT OVER A SYNTHETIC WORLD WHOSE ONE RELATION IS PLANTED.

An organ that joins every series the desk owns onto every instrument it trades is exactly the
organ nobody can eyeball on live data: an R2 of 0.004 looks the same whether the model found a
weak real edge or silently aligned two arrays wrongly. So the world here is made: a daily driver
`x`, hourly bars whose NEXT return is `beta * x` plus noise, and the tests demand the model
recover beta's explanatory power and attribute it to the dataset that carries it.

The other half matters more. THE ANTI-LOOKAHEAD JOIN is pinned three ways, because every way of
getting it wrong produces a better-looking artifact than getting it right:
  * a series stamped entirely after the decision window contributes NOTHING and is named;
  * a value stamped one hour LATE is read at the next bar, never at its own;
  * a value stamped EXACTLY at t is usable at t -- the boundary, which is the half of the rule
    that a defensive `<` instead of `<=` silently discards.

Plus the properties an hourly organ is trusted on: the hypothesis lane is enforced at the door
(a share CFD is never modelled), `--dry-run` writes nothing at all, an empty desk reads UNMEASURED
rather than zero, and a budget-bounded pass MERGES the residual store instead of deleting the
symbols it did not reach.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as REG  # noqa: E402
from libs.research import representations as R  # noqa: E402
from research import universe_policy as up  # noqa: E402
from research import world_model as wm  # noqa: E402

REGISTRY = {"EURUSD": {"asset_class": "Forex"}, "USDJPY": {"asset_class": "Forex"},
            "XAUUSD": {"asset_class": "Commodities"}, "Apple": {"asset_class": "Equities"}}
N_BARS = 2600
BETA = 0.004


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def _synthetic(tmp: Path, symbol: str, *, driven: bool = True) -> np.ndarray:
    """H1 bars whose next return is BETA * (the driver knowable at this bar) + noise."""
    import pandas as pd

    rng = np.random.default_rng(11)
    index = pd.date_range("2024-01-01", periods=N_BARS, freq="h", tz="UTC", name="time")
    days = np.asarray([(t - index[0]).days for t in index])
    driver = rng.normal(0.0, 1.0, size=int(days.max()) + 2)
    # `x` for day d becomes knowable at d 00:00 + CLOCK_PAD_H, so the bar that may use it is the
    # one at or after that hour. Anything earlier in the day still carries the PREVIOUS day's.
    hours = np.asarray([t.hour for t in index])
    usable_day = np.where(hours >= wm.CLOCK_PAD_H, days, days - 1)
    known = driver[np.clip(usable_day, 0, None)]
    noise = rng.normal(0.0, 0.0004, size=N_BARS)
    step = np.zeros(N_BARS)
    if driven:
        step[1:] = BETA * known[:-1] + noise[1:]
    else:
        step[1:] = noise[1:]
    close = 1.10 * np.exp(np.cumsum(step))
    pd.DataFrame({"close": close, "open": close, "high": close, "low": close},
                 index=index).to_parquet(tmp / f"{symbol}_H1.parquet")
    return driver


def _axis(tmp: Path, driver: np.ndarray) -> None:
    points = [{"d": "2024-01-01T00:00:00+00:00", "v": float(driver[0])}]
    import pandas as pd

    base = pd.Timestamp("2024-01-01", tz="UTC")
    points = [{"d": (base + pd.Timedelta(days=int(i))).isoformat(), "v": float(v)}
              for i, v in enumerate(driver)]
    _write(tmp / "axes" / "synth.json",
           {"axis": "macro_state", "id": "synth", "series": {"x": {"what": "planted driver",
                                                                   "points": points}}})


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """One synthetic desk: bars, one axis, one registry, every module path repointed."""
    universe = tmp_path / "universe"
    universe.mkdir(parents=True, exist_ok=True)
    driver = _synthetic(universe, "EURUSD")
    _synthetic(universe, "USDJPY", driven=False)
    _synthetic(universe, "Apple")
    _write(universe / "universe.json", REGISTRY)
    _axis(tmp_path, driver)

    monkeypatch.setattr(wm, "UNIVERSE_DIR", universe)
    monkeypatch.setattr(wm, "UNIVERSE_JSON", universe / "universe.json")
    monkeypatch.setattr(wm, "AXES", tmp_path / "axes")
    monkeypatch.setattr(wm, "FRED", tmp_path / "no_fred.json")
    monkeypatch.setattr(wm, "REPRESENTATIONS", tmp_path / "representations")
    monkeypatch.setattr(wm, "MOAT_SERIES", tmp_path / "no_moat.json")
    monkeypatch.setattr(wm, "STORE", tmp_path / "world_model")
    monkeypatch.setattr(wm, "CURSOR", tmp_path / "world_model" / "cursor.json")
    monkeypatch.setattr(wm, "OUT", tmp_path / "reports" / "WORLD_MODEL.json")
    monkeypatch.setattr(wm, "HORIZONS", {"1h": 1})
    monkeypatch.setattr(wm, "MIN_NONLINEAR", 10 ** 9)      # linear only: fast and deterministic
    monkeypatch.setattr(up, "UNIVERSE", universe / "universe.json")
    up._registry.cache_clear()
    monkeypatch.setattr(REG, "BACKUP", tmp_path / "no_backup")
    REG.set_path(tmp_path / "alpha_registry.sqlite")
    yield {"tmp": tmp_path, "universe": universe, "driver": driver}
    REG.set_path(None)
    up._registry.cache_clear()


# ------------------------------------------------------------------ the planted relation
def test_the_model_finds_the_planted_relation_and_credits_its_dataset(desk):
    inputs = wm.load_inputs()
    assert any(s.dataset == "axis:synth" for s in inputs.series), inputs.unmeasured
    design = wm.build_design("EURUSD", 1, inputs)
    assert design is not None
    assert "synth:x" in design.columns
    fit = wm.purged_cv(design.X, design.y, 1, nonlinear=False)
    assert fit is not None
    assert fit.r2 > 0.5, f"the planted relation must be recovered, got R2={fit.r2}"
    credit = wm.contributions(design, 1)
    # The drop-one contribution is NOT the whole R2: the bar's own last return is itself
    # `BETA * driver + noise`, so the price block proxies part of the driver and the honest
    # marginal value of the dataset is what it adds ON TOP of that. A test that demanded the
    # full R2 here would be demanding the contribution measure double-count.
    assert credit["axis:synth"] > 0.05, credit
    assert credit["axis:synth"] > credit.get("price", 0.0)
    keep = [i for i, g in enumerate(design.groups) if g != "axis:synth"]
    without = wm.purged_cv(design.X[:, keep], design.y, 1, nonlinear=False)
    assert without is not None and without.r2 < fit.r2


def test_an_undriven_instrument_does_not_manufacture_an_edge(desk):
    inputs = wm.load_inputs()
    design = wm.build_design("USDJPY", 1, inputs)
    assert design is not None
    fit = wm.purged_cv(design.X, design.y, 1, nonlinear=False)
    assert fit is not None
    assert fit.r2 < 0.2, f"pure noise must not score, got R2={fit.r2}"


# ------------------------------------------------------------------ the anti-lookahead join
def _late_series(design_times: np.ndarray, values: np.ndarray, shift_s: int) -> wm.Inputs:
    import pandas as pd

    points = tuple(R.Point(available_time=pd.Timestamp(int(t) + shift_s, unit="s",
                                                       tz="UTC").isoformat(),
                           period_time=str(int(t)), value=float(v))
                   for t, v in zip(design_times, values, strict=False))
    series = R.Series(series_id="oracle:y", points=points, dataset="axis:oracle", region="US",
                      information_type="oracle")
    return wm.Inputs(series=[series], unmeasured=[], arrays=wm._prepare([series]))


def _clock_series(stamps, shift_s: int) -> wm.Inputs:
    """A series whose VALUE is the bar's own epoch second, stamped `shift_s` after that bar.

    Dense over every bar, so both designs keep exactly the same rows and the columns can be
    compared element by element -- which is what makes the boundary assertion exact rather than
    approximate.
    """
    import pandas as pd

    points = tuple(R.Point(available_time=pd.Timestamp(int(s) + shift_s, unit="s",
                                                       tz="UTC").isoformat(),
                           period_time=str(int(s)), value=float(s))
                   for s in stamps)
    series = R.Series(series_id="clock:t", points=points, dataset="axis:clock", region="US",
                      information_type="clock")
    return wm.Inputs(series=[series], unmeasured=[], arrays=wm._prepare([series]))


def test_the_join_boundary_is_inclusive_at_t_and_exclusive_after_it(desk):
    """A value stamped EXACTLY at t is usable at t; the same value stamped one hour later is
    read at the NEXT bar and never at its own. Both halves matter: a defensive `<` would discard
    every on-time print, and a `<=` on the wrong side would be a look-ahead."""
    stamps, _ = wm.load_bars("EURUSD")
    on_time = wm.build_design("EURUSD", 1, _clock_series(stamps, 0))
    late = wm.build_design("EURUSD", 1, _clock_series(stamps, 3600))
    assert on_time is not None and late is not None
    assert len(on_time.y) == len(late.y), "the same rows must survive in both designs"
    own = on_time.X[:, on_time.columns.index("clock:t")]
    delayed = late.X[:, late.columns.index("clock:t")]
    assert own == pytest.approx(on_time.times.astype(float)), "a stamp at t IS usable at t"
    assert delayed == pytest.approx(own - 3600.0), "a stamp after t is read one bar later"


def test_a_value_available_after_t_cannot_influence_the_prediction_at_t(desk):
    """The oracle series carries the TARGET itself. Stamped at t it is legitimately perfect
    information; stamped one hour later it must not predict at all. An implementation that
    compared availability the other way round would score ~1.0 in both cases, and the look-ahead
    would be invisible in every return curve the desk owns.

    ON THE UNDRIVEN INSTRUMENT, DELIBERATELY. EURUSD is planted with a driver that is constant
    through each day, so its returns are autocorrelated and the PREVIOUS hour genuinely predicts
    the next one -- a late oracle would score 0.88 there for an honest reason, and the test would
    be measuring the plant instead of the join. USDJPY is pure noise: nothing but a look-ahead
    can predict it."""
    base = wm.build_design("USDJPY", 1, wm.Inputs(series=[], unmeasured=[], arrays=[]))
    assert base is not None
    honest = wm.build_design("USDJPY", 1, _late_series(base.times, base.y, 0))
    late = wm.build_design("USDJPY", 1, _late_series(base.times, base.y, 3600))
    assert honest is not None and late is not None
    honest_fit = wm.purged_cv(honest.X, honest.y, 1, nonlinear=False)
    late_fit = wm.purged_cv(late.X, late.y, 1, nonlinear=False)
    assert honest_fit is not None and late_fit is not None
    assert honest_fit.r2 > 0.98, "the target stamped at t is legitimately perfect information"
    assert late_fit.r2 < 0.5, "the same values stamped one hour late must not predict"


def test_a_series_stamped_entirely_after_the_window_is_named_not_used(desk):
    base = wm.build_design("EURUSD", 1, wm.Inputs(series=[], unmeasured=[], arrays=[]))
    assert base is not None
    future = _late_series(base.times, base.y, 400 * 86400)
    design = wm.build_design("EURUSD", 1, future)
    assert design is not None
    assert "oracle:y" not in design.columns
    assert any("oracle:y" in name for name in design.unmeasured)


# ------------------------------------------------------------------ the pass
def test_the_pass_writes_the_report_the_store_and_the_registry(desk):
    report = wm.run(budget_s=120.0)
    assert report["n_targets"] >= 1
    assert wm.OUT.exists()
    modelled = {t["symbol"] for t in report["targets"]}
    assert "Apple" not in modelled, "a share CFD belongs to the event lane and is never modelled"
    assert modelled <= {"EURUSD", "USDJPY", "XAUUSD"}
    assert report["allocates_capital"] is False
    assert report["inputs"]["clock_pad_h"] == wm.CLOCK_PAD_H

    rows = wm.read_residuals("1h")
    assert rows, "the residual store is what residual_hunt consumes"
    row = rows[0]
    assert set(row) >= {"target", "time", "y", "yhat", "epsilon", "regime", "session"}
    assert row["regime"] in wm.REGIME_NAMES
    assert row["epsilon"] == pytest.approx(row["y"] - row["yhat"], abs=1e-9)

    kpis = {k["name"] for k in REG.kpis()}
    assert "world_model.targets" in kpis
    assert any(name.startswith("world_model.contribution.") for name in kpis)


def test_dry_run_writes_nothing_at_all(desk):
    report = wm.run(budget_s=60.0, dry_run=True)
    assert report["dry_run"] is True
    assert not wm.OUT.exists()
    assert not (wm.STORE / "residuals_1h.parquet").exists()
    assert not wm.CURSOR.exists()


def test_the_store_merges_rather_than_deleting_the_symbols_this_pass_missed(desk):
    wm.run(budget_s=120.0, symbols=["EURUSD"])
    first = {r["symbol"] for r in wm.read_residuals("1h")}
    assert first == {"EURUSD"}
    wm.run(budget_s=120.0, symbols=["USDJPY"])
    after = {r["symbol"] for r in wm.read_residuals("1h")}
    assert after == {"EURUSD", "USDJPY"}, "a budget-bounded pass must not delete what it skipped"


def test_a_desk_with_no_bars_reads_unmeasured_never_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(wm, "UNIVERSE_DIR", tmp_path / "empty")
    monkeypatch.setattr(wm, "UNIVERSE_JSON", tmp_path / "empty" / "universe.json")
    monkeypatch.setattr(wm, "AXES", tmp_path / "no_axes")
    monkeypatch.setattr(wm, "FRED", tmp_path / "no_fred.json")
    monkeypatch.setattr(wm, "REPRESENTATIONS", tmp_path / "no_repr")
    monkeypatch.setattr(wm, "MOAT_SERIES", tmp_path / "no_moat.json")
    inputs = wm.load_inputs()
    assert inputs.series == []
    names = {u["name"] for u in inputs.unmeasured}
    assert {"fred_macro", "representations", "moat_series"} <= names
    assert all(u.get("measured_by") for u in inputs.unmeasured), "name what would measure it"


# ------------------------------------------------------------------ the machinery
def test_the_purge_gap_keeps_the_forward_window_out_of_the_training_set():
    """With a target that is a pure function of a 50-bar-ahead value, an UNPURGED fit scores and
    a purged one does not. The gap is the only thing separating the two."""
    rng = np.random.default_rng(3)
    n = 1200
    hidden = rng.normal(size=n + 200)
    X = np.column_stack([hidden[:n], rng.normal(size=n)])
    y = np.roll(hidden[:n], -50)
    purged = wm.purged_cv(X, y, 50, nonlinear=False)
    assert purged is not None
    assert purged.folds >= 1 and purged.index.min() >= 0
    assert purged.r2 < 0.2


def test_vol_regime_is_causal_and_names_unmeasured():
    vol = np.abs(np.random.default_rng(5).normal(size=1500)) + 0.001
    labels, cuts = wm.vol_regime(vol)
    assert cuts is not None
    assert set(labels[:wm.VOL_PRE_MIN]) == {3}, "no label before the prior is long enough"
    assert wm.REGIME_NAMES[3] == "UNMEASURED"
    assert set(np.unique(labels[wm.VOL_PRE_MIN + wm.VOL_RECUT:])) <= {0, 1, 2, 3}


def test_session_labels_follow_the_desks_own_windows():
    assert wm.session_of(3) == "asia"
    assert wm.session_of(10) == "london"
    assert wm.session_of(15) == "overlap"
    assert wm.session_of(20) == "ny"
    assert wm.session_of(23) == "off"


def test_the_row_cap_is_derived_from_memory_and_never_below_the_floor():
    assert wm.max_store_rows() >= wm.MAX_ROWS_FLOOR
